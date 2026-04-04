"""
Autonomous agent loop — orchestrates scraping, classification, storage.

Designed to be called repeatedly; stops when max_iterations reached or KB is complete.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.agent.evaluator import build_coverage_report, print_coverage_summary, save_coverage_report
from src.agent.planner import decide_next_action, get_scraper
from src.classifier import classify_batch, classify_question
from src.config import DATA_DIR, Settings, get_settings
from src.db import get_scraped_urls, init_db, insert_question, log_scrape
from src.deduplicator import is_duplicate
from src.models import ScraperResult
from src.storage import get_storage

logger = logging.getLogger(__name__)

_STATE_PATH = DATA_DIR / "agent_state.json"


def load_state() -> dict:
    """Load agent state from disk."""
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text())
        except Exception:
            pass
    return {"status": "running", "iterations": 0, "questions_total": 0, "started_at": datetime.utcnow().isoformat()}


def save_state(state: dict) -> None:
    """Persist agent state to disk."""
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, indent=2, default=str))


def run_agent_session(settings: Optional[Settings] = None, max_iterations: int = 50) -> None:
    """
    Run one session of the autonomous agent loop.
    Stops when max_iterations reached or KB is complete.
    """
    if settings is None:
        settings = get_settings()

    # Ensure DB exists
    db_path = settings.db_path
    init_db(db_path)
    storage = get_storage(settings)

    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    state = load_state()
    logger.info(f"Agent session starting. State: {state}")

    for i in range(max_iterations):
        iteration_start = time.time()
        logger.info(f"─── Iteration {i + 1}/{max_iterations} ───")

        # 1. Evaluate coverage
        report = build_coverage_report(db_path, settings)
        print_coverage_summary(report)

        if report.is_complete:
            logger.info("✓ KB complete! All criteria met.")
            state["status"] = "complete"
            save_state(state)
            save_coverage_report(report)
            break

        # 2. Plan next action
        scraped_urls = get_scraped_urls(db_path)
        action = decide_next_action(report, scraped_urls)

        if not action.get("scraper"):
            logger.info("No action needed — KB appears complete")
            break

        logger.info(f"Action: scraper={action['scraper']}, topics={action['topic_hints']}, reason={action['reason']}")

        # 3. Get scraper
        try:
            scraper = get_scraper(action["scraper"], api_key=settings.anthropic_api_key)
        except Exception as e:
            logger.error(f"Failed to instantiate scraper {action['scraper']}: {e}")
            continue

        # 4. Discover URLs for weak topics
        topic_hints = action.get("topic_hints", [])
        try:
            urls = scraper.discover_urls(topic_hints if topic_hints else None)
        except Exception as e:
            logger.error(f"discover_urls failed: {e}")
            continue

        # Filter already-scraped URLs (limit to 10 per iteration to control API cost)
        new_urls = [u for u in urls if u not in scraped_urls][:10]

        if not new_urls:
            logger.info(f"All URLs for {topic_hints} already scraped — picking different topics")
            # Force different topics next iteration by picking the globally weakest unseen
            all_urls = scraper.discover_urls(None)
            new_urls = [u for u in all_urls if u not in scraped_urls][:10]
            if not new_urls:
                logger.warning("No new URLs available — breaking")
                break

        logger.info(f"Processing {len(new_urls)} new URLs")

        # 5. Scrape + classify + store
        questions_added = 0
        for url in new_urls:
            try:
                raws: list[ScraperResult] = scraper.scrape_url(url)
                if not raws:
                    log_scrape(db_path, url, scraper.name, "empty", 0)
                    continue

                for raw in raws:
                    try:
                        question = classify_question(raw, settings, _client=client)
                        if question is None:
                            continue
                        if is_duplicate(question, db_path):
                            logger.debug(f"Skipping duplicate: {question.question_text[:50]!r}")
                            continue
                        inserted = insert_question(db_path, question)
                        if inserted:
                            storage.save_question(question)
                            questions_added += 1
                    except Exception as e:
                        logger.warning(f"Failed to process question from {url}: {e}")

                log_scrape(db_path, url, scraper.name, "success", len(raws))

            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}")
                log_scrape(db_path, url, scraper.name, "error", 0, error_message=str(e))

        logger.info(f"Added {questions_added} new questions this iteration")

        # Update state
        state["iterations"] = state.get("iterations", 0) + 1
        state["questions_total"] = state.get("questions_total", 0) + questions_added
        state["last_action"] = action
        state["last_iteration_at"] = datetime.utcnow().isoformat()
        save_state(state)

        # Save coverage report every 5 iterations
        if (i + 1) % 5 == 0:
            report = build_coverage_report(db_path, settings)
            save_coverage_report(report)

        elapsed = time.time() - iteration_start
        logger.info(f"Iteration {i + 1} took {elapsed:.1f}s")

    # Final coverage report
    final_report = build_coverage_report(db_path, settings)
    save_coverage_report(final_report)
    state["final_total"] = final_report.total_questions
    state["is_complete"] = final_report.is_complete
    save_state(state)

    logger.info(f"Session ended. Total questions: {final_report.total_questions}, Complete: {final_report.is_complete}")
