"""
Coverage evaluator — analyses the DB and produces a CoverageReport.

Completion criteria:
- Total questions >= 500
- All 33 subtopics have >= 5 questions
- All three difficulty levels have >= 50 questions each
- At least 3 different sources represented
- Mean quality score >= 3.5
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import DATA_DIR, Settings
from src.db import get_coverage_stats
from src.models import CoverageReport
from src.taxonomy import ALL_TOPIC_SLUGS, SUBTOPIC_MINIMUM

logger = logging.getLogger(__name__)

_MIN_PER_DIFFICULTY = 50
_MIN_SOURCES = 3
_MIN_QUALITY = 3.5
_TARGET_TOTAL = 500


def build_coverage_report(db_path: Path, settings: Settings) -> CoverageReport:
    """Analyse the DB and return a CoverageReport."""
    stats = get_coverage_stats(db_path)

    total = stats["total"]
    by_topic: dict[str, int] = stats["by_topic"]
    by_difficulty: dict[str, int] = stats["by_difficulty"]
    by_source: dict[str, int] = stats["by_source"]
    by_type: dict[str, int] = stats["by_type"]
    mean_quality: float | None = stats["mean_quality"]

    # Determine weak topics (below minimum per subtopic)
    weak_topics: list[str] = []
    for slug in ALL_TOPIC_SLUGS:
        count = by_topic.get(slug, 0)
        if count < SUBTOPIC_MINIMUM:
            weak_topics.append(slug)

    # Check completion criteria
    enough_total = total >= _TARGET_TOTAL
    no_weak_topics = len(weak_topics) == 0
    difficulty_ok = all(
        by_difficulty.get(d, 0) >= _MIN_PER_DIFFICULTY
        for d in ["easy", "medium", "hard"]
    )
    sources_ok = len(by_source) >= _MIN_SOURCES
    quality_ok = (mean_quality is not None and mean_quality >= _MIN_QUALITY)

    is_complete = enough_total and no_weak_topics and difficulty_ok and sources_ok and quality_ok

    # Build notes
    notes_parts = []
    if not enough_total:
        notes_parts.append(f"Need {_TARGET_TOTAL - total} more questions (have {total})")
    if weak_topics:
        notes_parts.append(f"{len(weak_topics)} subtopics below minimum ({SUBTOPIC_MINIMUM}): {weak_topics[:5]}")
    if not difficulty_ok:
        for d in ["easy", "medium", "hard"]:
            count = by_difficulty.get(d, 0)
            if count < _MIN_PER_DIFFICULTY:
                notes_parts.append(f"Need {_MIN_PER_DIFFICULTY - count} more {d} questions")
    if not sources_ok:
        notes_parts.append(f"Only {len(by_source)} sources (need {_MIN_SOURCES})")
    if not quality_ok:
        q_str = f"{mean_quality:.2f}" if mean_quality else "N/A"
        notes_parts.append(f"Mean quality {q_str} < {_MIN_QUALITY}")

    report = CoverageReport(
        total_questions=total,
        by_topic=by_topic,
        by_difficulty=by_difficulty,
        by_source=by_source,
        by_type=by_type,
        weak_topics=weak_topics,
        mean_quality_score=mean_quality,
        is_complete=is_complete,
        notes=" | ".join(notes_parts) if notes_parts else "All criteria met",
    )

    return report


def get_weak_topics(report: CoverageReport) -> list[str]:
    """Return subtopic slugs that are below the minimum question threshold."""
    return report.weak_topics


def save_coverage_report(report: CoverageReport, data_dir: Path = DATA_DIR) -> None:
    """Save the coverage report to data/coverage_report.json."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "coverage_report.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info(f"Coverage report saved to {path}")


def print_coverage_summary(report: CoverageReport) -> None:
    """Log a summary of coverage stats."""
    logger.info("=== Coverage Report ===")
    logger.info(f"Total questions: {report.total_questions}")
    logger.info(f"By difficulty: {report.by_difficulty}")
    logger.info(f"By source: {report.by_source}")
    logger.info(f"Weak topics ({len(report.weak_topics)}): {report.weak_topics[:10]}")
    logger.info(f"Mean quality: {report.mean_quality_score}")
    logger.info(f"Is complete: {report.is_complete}")
    logger.info(f"Notes: {report.notes}")
