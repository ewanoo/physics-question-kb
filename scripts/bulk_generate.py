#!/usr/bin/env python3
"""
Bulk question generation script.
Generates 5 questions per (subtopic, difficulty) = 33 × 3 × 5 = 495 questions.
Also inserts fixture questions from Isaac Physics and BBC Bitesize as additional sources.
"""
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bulk_generate")

import anthropic

from src.classifier import classify_question
from src.config import get_settings
from src.db import count_questions, init_db, insert_question
from src.deduplicator import is_duplicate
from src.models import AnswerOption, Difficulty, Question, QuestionType, ScraperResult
from src.scraper.question_generator import QuestionGeneratorScraper
from src.storage import get_storage
from src.taxonomy import ALL_TOPIC_SLUGS, TAXONOMY


def load_fixture_results(fixture_path: Path, source_name: str) -> list[ScraperResult]:
    """Load saved fixture JSON as ScraperResults."""
    if not fixture_path.exists():
        return []
    data = json.loads(fixture_path.read_text())
    results = []

    if isinstance(data, dict) and "results" in data:
        items = data["results"]
    elif isinstance(data, list):
        items = data
    else:
        return []

    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("value", "") or item.get("title", "")
        import re
        text = re.sub(r"<[^>]+>", " ", str(value))
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        choices = item.get("choices", [])
        raw_options = None
        raw_answer = None
        if choices:
            raw_options = []
            for c in choices:
                c_text = re.sub(r"<[^>]+>", " ", c.get("value", "")).strip()
                is_correct = c.get("correct", False)
                raw_options.append({"text": c_text, "correct": is_correct, "is_correct": is_correct})
                if is_correct:
                    raw_answer = c_text

        tags = item.get("tags", [])
        results.append(ScraperResult(
            raw_question_text=text,
            raw_options=raw_options,
            raw_answer=raw_answer,
            source_url=f"https://isaacphysics.org/questions/{item.get('id', '')}",
            source_name=source_name,
            page_context=f"Tags: {', '.join(tags)}" if tags else None,
        ))
    return results


def main():
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    init_db(settings.db_path)
    storage = get_storage(settings)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    total_added = 0
    total_skipped = 0
    failed = 0

    # ── Step 1: Add Isaac Physics fixture questions ───────────────────────────
    logger.info("=== Step 1: Loading Isaac Physics fixture questions ===")
    isaac_fixture = Path("tests/fixtures/isaac_physics_sample.json")
    isaac_raws = load_fixture_results(isaac_fixture, "isaac_physics")
    logger.info(f"Loaded {len(isaac_raws)} Isaac Physics fixture questions")

    for raw in isaac_raws:
        try:
            q = classify_question(raw, settings, _client=client)
            if q and not is_duplicate(q, settings.db_path):
                if insert_question(settings.db_path, q):
                    storage.save_question(q)
                    total_added += 1
        except Exception as e:
            logger.warning(f"Failed to classify Isaac fixture: {e}")
            failed += 1

    logger.info(f"Isaac Physics: added {total_added} questions")

    # ── Step 2: Generate questions for all subtopics × difficulties ───────────
    logger.info("=== Step 2: Bulk generating questions via Claude ===")
    generator = QuestionGeneratorScraper(api_key=settings.anthropic_api_key)

    all_urls = generator.discover_urls()
    logger.info(f"Total generation URLs: {len(all_urls)}")

    for i, url in enumerate(all_urls):
        try:
            raws = generator.scrape_url(url)
            if not raws:
                continue

            added_this_url = 0
            for raw in raws:
                try:
                    q = classify_question(raw, settings, _client=client)
                    if q is None:
                        total_skipped += 1
                        continue
                    if is_duplicate(q, settings.db_path):
                        total_skipped += 1
                        continue
                    if insert_question(settings.db_path, q):
                        storage.save_question(q)
                        total_added += 1
                        added_this_url += 1
                except Exception as e:
                    logger.warning(f"Question processing error: {e}")
                    failed += 1

            total_so_far = count_questions(settings.db_path)
            logger.info(f"[{i+1}/{len(all_urls)}] {url}: +{added_this_url} | DB total: {total_so_far}")

        except Exception as e:
            logger.warning(f"URL failed {url}: {e}")
            failed += 1

    # ── Final stats ───────────────────────────────────────────────────────────
    final_count = count_questions(settings.db_path)
    logger.info(f"=== DONE ===")
    logger.info(f"Added: {total_added}, Skipped: {total_skipped}, Failed: {failed}")
    logger.info(f"Total in DB: {final_count}")

    return final_count


if __name__ == "__main__":
    main()
