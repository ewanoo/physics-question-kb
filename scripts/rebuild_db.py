"""
Rebuild the local SQLite database from committed question JSON files.
Run this after a git pull to get questions without needing API credits.

Usage:
    python scripts/rebuild_db.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db import init_db, insert_question
from src.models import Question


def rebuild():
    settings = get_settings()
    questions_dir = settings.questions_dir

    if not questions_dir.exists():
        print(f"No questions directory found at {questions_dir}")
        print("Run the remote agent first to generate questions.")
        return

    json_files = list(questions_dir.glob("*.json"))
    if not json_files:
        print("No question JSON files found. Run the remote agent first.")
        return

    print(f"Found {len(json_files)} question files. Rebuilding database...")
    init_db(settings.db_path)

    inserted = 0
    skipped = 0
    errors = 0

    for path in json_files:
        try:
            question = Question.model_validate_json(path.read_text())
            if insert_question(settings.db_path, question):
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error loading {path.name}: {e}")
            errors += 1

    print(f"Done. Inserted: {inserted}, Skipped (duplicates): {skipped}, Errors: {errors}")
    print(f"Database: {settings.db_path}")


if __name__ == "__main__":
    rebuild()
