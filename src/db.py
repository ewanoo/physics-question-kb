from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from src.models import CoverageReport, Difficulty, Question, QuestionType
from src.taxonomy import ALL_TOPIC_SLUGS, TAXONOMY


def init_db(db_path: Path) -> None:
    """Create database schema if it doesn't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                topic TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                source_name TEXT NOT NULL,
                source_url TEXT,
                scraped_at TEXT NOT NULL,
                classified_at TEXT,
                classification_confidence REAL,
                quality_score REAL,
                year_group TEXT DEFAULT 'year8',
                data_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_topic ON questions(topic);
            CREATE INDEX IF NOT EXISTS idx_difficulty ON questions(difficulty);
            CREATE INDEX IF NOT EXISTS idx_source ON questions(source_name);
            CREATE INDEX IF NOT EXISTS idx_type ON questions(question_type);

            CREATE TABLE IF NOT EXISTS scraper_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                urls_attempted INTEGER DEFAULT 0,
                questions_found INTEGER DEFAULT 0,
                questions_stored INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running'
            );

            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                source_name TEXT NOT NULL,
                status TEXT NOT NULL,
                questions_found INTEGER DEFAULT 0,
                error_message TEXT,
                scraped_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                phase TEXT,
                questions_added INTEGER DEFAULT 0,
                coverage_score REAL,
                status TEXT DEFAULT 'running',
                notes TEXT
            );
        """)


@contextmanager
def get_connection(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_question(db_path: Path, question: Question) -> bool:
    """Insert a question. Returns True if inserted, False if duplicate id."""
    with get_connection(db_path) as conn:
        try:
            conn.execute(
                """INSERT INTO questions
                   (id, question_text, question_type, difficulty, topic, tags,
                    source_name, source_url, scraped_at, classified_at,
                    classification_confidence, quality_score, year_group, data_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    question.id,
                    question.question_text,
                    question.question_type.value,
                    question.difficulty.value,
                    question.topic,
                    json.dumps(question.tags),
                    question.source_name,
                    question.source_url,
                    question.scraped_at.isoformat(),
                    question.classified_at.isoformat() if question.classified_at else None,
                    question.classification_confidence,
                    question.quality_score,
                    question.year_group,
                    question.model_dump_json(),
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_questions(
    db_path: Path,
    topic: str | None = None,
    difficulty: str | None = None,
    source: str | None = None,
    question_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Question]:
    clauses = []
    params: list = []

    if topic:
        if "." in topic:
            clauses.append("topic = ?")
        else:
            clauses.append("topic LIKE ?")
            topic = f"{topic}.%"
        params.append(topic)
    if difficulty:
        clauses.append("difficulty = ?")
        params.append(difficulty)
    if source:
        clauses.append("source_name = ?")
        params.append(source)
    if question_type:
        clauses.append("question_type = ?")
        params.append(question_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])

    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"SELECT data_json FROM questions {where} LIMIT ? OFFSET ?", params
        ).fetchall()

    return [Question.model_validate_json(row["data_json"]) for row in rows]


def count_questions(db_path: Path, topic: str | None = None) -> int:
    with get_connection(db_path) as conn:
        if topic:
            if "." in topic:
                return conn.execute(
                    "SELECT COUNT(*) FROM questions WHERE topic = ?", (topic,)
                ).fetchone()[0]
            else:
                return conn.execute(
                    "SELECT COUNT(*) FROM questions WHERE topic LIKE ?", (f"{topic}.%",)
                ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]


def get_coverage_stats(db_path: Path) -> dict:
    """Return raw coverage stats from the database."""
    with get_connection(db_path) as conn:
        by_topic = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT topic, COUNT(*) FROM questions GROUP BY topic"
            ).fetchall()
        }
        by_difficulty = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty"
            ).fetchall()
        }
        by_source = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT source_name, COUNT(*) FROM questions GROUP BY source_name"
            ).fetchall()
        }
        by_type = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT question_type, COUNT(*) FROM questions GROUP BY question_type"
            ).fetchall()
        }
        mean_quality = conn.execute(
            "SELECT AVG(quality_score) FROM questions WHERE quality_score IS NOT NULL"
        ).fetchone()[0]

    return {
        "by_topic": by_topic,
        "by_difficulty": by_difficulty,
        "by_source": by_source,
        "by_type": by_type,
        "mean_quality": mean_quality,
        "total": sum(by_topic.values()) if by_topic else 0,
    }


def get_scraped_urls(db_path: Path) -> set[str]:
    """Return all URLs that have been scraped (successfully or not)."""
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT url FROM scrape_log").fetchall()
    return {row["url"] for row in rows}


def log_scrape(
    db_path: Path,
    url: str,
    source_name: str,
    status: str,
    questions_found: int = 0,
    error_message: str | None = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO scrape_log (url, source_name, status, questions_found, error_message, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url, source_name, status, questions_found, error_message, datetime.utcnow().isoformat()),
        )
