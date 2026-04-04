"""
Planner — decide what to scrape next based on coverage gaps.
"""

from __future__ import annotations

import logging

from src.models import CoverageReport
from src.taxonomy import ALL_TOPIC_SLUGS, get_parent_topic

logger = logging.getLogger(__name__)

# Scraper priority order (most reliable first)
_SCRAPER_PRIORITY = [
    "claude_generator",
    "isaac_physics",
    "bbc_bitesize",
]


def decide_next_action(report: CoverageReport, scraped_urls: set[str]) -> dict:
    """
    Given coverage gaps, decide what to generate/scrape next.

    Returns a dict:
    {
        "scraper": "claude_generator",
        "topic_hints": ["electricity.circuits"],
        "reason": "electricity.circuits has only 2 questions",
    }
    """
    if report.is_complete:
        return {"scraper": None, "topic_hints": [], "reason": "KB is complete"}

    # Priority 1: Find subtopics with fewest questions
    topic_counts = {slug: report.by_topic.get(slug, 0) for slug in ALL_TOPIC_SLUGS}
    sorted_weak = sorted(topic_counts.items(), key=lambda x: x[1])

    # Pick up to 5 weakest subtopics
    weak_slugs = [slug for slug, count in sorted_weak[:5]]

    if not weak_slugs:
        return {"scraper": None, "topic_hints": [], "reason": "No weak topics found"}

    weakest_slug, weakest_count = sorted_weak[0]
    reason = f"{weakest_slug!r} has {weakest_count} questions (need 5+)"

    # If overall total is low, generate for multiple weak topics at once
    if report.total_questions < 200:
        topic_hints = weak_slugs  # Generate for all 5 weakest
    else:
        topic_hints = weak_slugs[:3]

    # Choose scraper: try generator first (always works), then fallback to web scrapers
    # For now, always use claude_generator since web scrapers 403 from cloud
    scraper = "claude_generator"

    # Check if difficulty balance is off — if so, hint difficulty
    difficulty_action = _check_difficulty_balance(report)
    if difficulty_action:
        reason += f" | {difficulty_action['reason']}"

    return {
        "scraper": scraper,
        "topic_hints": topic_hints,
        "reason": reason,
    }


def _check_difficulty_balance(report: CoverageReport) -> dict | None:
    """Check if any difficulty level needs boosting."""
    min_needed = 50
    for difficulty in ["easy", "medium", "hard"]:
        count = report.by_difficulty.get(difficulty, 0)
        if count < min_needed:
            return {
                "difficulty": difficulty,
                "count": count,
                "reason": f"Need more {difficulty} questions ({count}/{min_needed})",
            }
    return None


def get_scraper(scraper_name: str, api_key: str = ""):
    """Instantiate and return a scraper by name."""
    from src.scraper.bbc_bitesize import BBCBitesizeScraper
    from src.scraper.isaac_physics import IsaacPhysicsScraper
    from src.scraper.question_generator import QuestionGeneratorScraper

    scrapers = {
        "claude_generator": lambda: QuestionGeneratorScraper(api_key=api_key),
        "isaac_physics": IsaacPhysicsScraper,
        "bbc_bitesize": BBCBitesizeScraper,
    }

    factory = scrapers.get(scraper_name)
    if not factory:
        raise ValueError(f"Unknown scraper: {scraper_name!r}. Valid: {list(scrapers)}")

    return factory()
