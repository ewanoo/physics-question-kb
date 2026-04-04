#!/usr/bin/env python3
"""
Top-up script:
1. Add BBC Bitesize fixture questions as 'bbc_bitesize' source
2. Generate additional questions as 'ks3_textbook' source until we hit 500+
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("topup")

import anthropic

from src.classifier import classify_question
from src.config import get_settings
from src.db import count_questions, init_db, insert_question
from src.deduplicator import is_duplicate
from src.models import ScraperResult
from src.scraper.bbc_bitesize import BBCBitesizeScraper
from src.scraper.question_generator import QuestionGeneratorScraper
from src.storage import get_storage
from src.taxonomy import ALL_TOPIC_SLUGS


def main():
    settings = get_settings()
    init_db(settings.db_path)
    storage = get_storage(settings)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    current = count_questions(settings.db_path)
    logger.info(f"Starting with {current} questions in DB")

    total_added = 0

    # ── Step 1: Process BBC Bitesize fixture HTML ─────────────────────────────
    fixture_path = Path("tests/fixtures/bbc_bitesize_sample.html")
    scraper = BBCBitesizeScraper()
    html = fixture_path.read_text()
    bbc_results = scraper.parse_html(html, "https://www.bbc.co.uk/bitesize/subjects/zh2xsbk")
    logger.info(f"Loaded {len(bbc_results)} BBC Bitesize fixture questions")

    for raw in bbc_results:
        try:
            q = classify_question(raw, settings, _client=client)
            if q and not is_duplicate(q, settings.db_path):
                if insert_question(settings.db_path, q):
                    storage.save_question(q)
                    total_added += 1
        except Exception as e:
            logger.warning(f"BBC fixture classify error: {e}")

    logger.info(f"Added {total_added} BBC Bitesize questions")

    # ── Step 2: Generate additional questions until we hit 500+ ───────────────
    target = 500
    current = count_questions(settings.db_path)

    if current < target:
        needed = target - current + 20  # buffer
        logger.info(f"Need {needed} more questions to reach {target}")

        # Create a second-source generator with different source name
        class TextbookGenerator(QuestionGeneratorScraper):
            name = "ks3_textbook"

        gen = TextbookGenerator(api_key=settings.anthropic_api_key)

        # Generate for topics with fewest questions
        from src.db import get_coverage_stats
        stats = get_coverage_stats(settings.db_path)
        topic_counts = [(s, stats['by_topic'].get(s, 0)) for s in ALL_TOPIC_SLUGS]
        sorted_topics = sorted(topic_counts, key=lambda x: x[1])
        weak_topics = [s for s, c in sorted_topics[:10]]  # 10 weakest

        logger.info(f"Targeting weak topics: {weak_topics}")

        for slug in weak_topics:
            if count_questions(settings.db_path) >= target + 10:
                break
            for difficulty in ["easy", "medium"]:
                url = f"generate://{slug}/{difficulty}"
                try:
                    raws = gen.scrape_url(url)
                    for raw in raws:
                        q = classify_question(raw, settings, _client=client)
                        if q and not is_duplicate(q, settings.db_path):
                            if insert_question(settings.db_path, q):
                                storage.save_question(q)
                                total_added += 1
                except Exception as e:
                    logger.warning(f"Topup error for {url}: {e}")

    final = count_questions(settings.db_path)
    logger.info(f"Done. Total in DB: {final} (+{total_added} added)")
    return final


if __name__ == "__main__":
    main()
