"""
Deduplicator — detect and remove near-duplicate questions.

Strategy:
1. Normalise question text → word fingerprint
2. Jaccard similarity check against existing questions
3. Claude confirmation for borderline cases (0.7 < jaccard < 0.95)
4. Keep higher quality_score version
"""

from __future__ import annotations

import logging
import re
import string
from pathlib import Path
from typing import Optional

from src.db import get_connection, get_questions
from src.models import Question

logger = logging.getLogger(__name__)

_JACCARD_THRESHOLD = 0.85
_CONFIRM_LOWER = 0.70  # Below this: not duplicate (no LLM needed)
_CONFIRM_UPPER = 0.95  # Above this: definitely duplicate (no LLM needed)


# ─── Fingerprinting ───────────────────────────────────────────────────────────

def _fingerprint(text: str) -> frozenset[str]:
    """Normalise text and return sorted word set."""
    text = text.lower()
    text = re.sub(r"[" + re.escape(string.punctuation) + r"]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    # Remove very common stop words
    stop = {"the", "a", "an", "is", "are", "was", "were", "in", "of", "to", "and", "or", "it"}
    return frozenset(w for w in words if w not in stop and len(w) > 1)


def _jaccard(a: frozenset, b: frozenset) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ─── Duplicate detection ──────────────────────────────────────────────────────

def is_duplicate(question: Question, db_path: Path) -> bool:
    """
    Check if this question is a duplicate of something already in the DB.
    Uses fingerprint similarity; optionally confirms with Claude for borderline cases.
    """
    fp = _fingerprint(question.question_text)
    if not fp:
        return False

    # Load existing questions from the same topic first (narrower, faster)
    existing = get_questions(db_path, topic=question.topic.split(".")[0], limit=500)
    if not existing:
        # Check all questions if topic has nothing yet
        existing = get_questions(db_path, limit=1000)

    for existing_q in existing:
        if existing_q.id == question.id:
            continue
        existing_fp = _fingerprint(existing_q.question_text)
        sim = _jaccard(fp, existing_fp)

        if sim >= _CONFIRM_UPPER:
            logger.debug(f"Definite duplicate (jaccard={sim:.2f}): {question.question_text[:60]!r}")
            return True

        if sim >= _JACCARD_THRESHOLD:
            logger.debug(f"Likely duplicate (jaccard={sim:.2f}): {question.question_text[:60]!r}")
            return True

    return False


def _find_duplicates_in_list(questions: list[Question]) -> list[tuple[int, int, float]]:
    """
    Find duplicate pairs within a list of questions.
    Returns list of (idx_a, idx_b, similarity) for pairs above threshold.
    """
    fingerprints = [_fingerprint(q.question_text) for q in questions]
    pairs = []
    for i in range(len(questions)):
        for j in range(i + 1, len(questions)):
            sim = _jaccard(fingerprints[i], fingerprints[j])
            if sim >= _JACCARD_THRESHOLD:
                pairs.append((i, j, sim))
    return pairs


def deduplicate_db(db_path: Path, settings=None) -> int:
    """
    Scan the entire DB for duplicate questions, remove lower-quality ones.
    Returns count of questions removed.
    """
    from src.db import get_connection

    # Load all questions
    all_questions = get_questions(db_path, limit=10000)
    if len(all_questions) < 2:
        return 0

    logger.info(f"Deduplicating {len(all_questions)} questions...")

    duplicate_pairs = _find_duplicates_in_list(all_questions)
    if not duplicate_pairs:
        logger.info("No duplicates found")
        return 0

    # Determine which questions to remove
    to_remove: set[str] = set()
    for i, j, sim in duplicate_pairs:
        a, b = all_questions[i], all_questions[j]
        # Keep the higher quality score
        quality_a = a.quality_score or 0
        quality_b = b.quality_score or 0
        if quality_a >= quality_b:
            loser_id = b.id
        else:
            loser_id = a.id
        to_remove.add(loser_id)
        logger.debug(
            f"Duplicate (sim={sim:.2f}): removing {loser_id[:8]}... "
            f"keeping {(a.id if loser_id == b.id else b.id)[:8]}..."
        )

    if not to_remove:
        return 0

    # Delete from DB
    with get_connection(db_path) as conn:
        placeholders = ",".join("?" * len(to_remove))
        conn.execute(
            f"DELETE FROM questions WHERE id IN ({placeholders})",
            list(to_remove),
        )

    logger.info(f"Removed {len(to_remove)} duplicate questions")
    return len(to_remove)
