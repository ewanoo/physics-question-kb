"""
Storage backends for saving and loading Questions.

Supports:
- LocalStorage: JSON files in data/questions/{id}.json
- S3Storage: s3://{bucket}/questions/{id}.json (if boto3 + credentials available)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from src.config import Settings
from src.models import CoverageReport, Question

logger = logging.getLogger(__name__)


# ─── Protocol ────────────────────────────────────────────────────────────────

@runtime_checkable
class StorageBackend(Protocol):
    def save_question(self, question: Question) -> None: ...
    def load_question(self, question_id: str) -> Optional[Question]: ...
    def save_coverage_report(self, report: CoverageReport) -> None: ...


# ─── Local storage ────────────────────────────────────────────────────────────

class LocalStorage:
    """Saves questions as JSON files in data/questions/{id}.json."""

    def __init__(self, questions_dir: Path) -> None:
        self.questions_dir = questions_dir
        questions_dir.mkdir(parents=True, exist_ok=True)

    def save_question(self, question: Question) -> None:
        path = self.questions_dir / f"{question.id}.json"
        path.write_text(question.model_dump_json(indent=2), encoding="utf-8")

    def load_question(self, question_id: str) -> Optional[Question]:
        path = self.questions_dir / f"{question_id}.json"
        if not path.exists():
            return None
        try:
            return Question.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load question {question_id}: {e}")
            return None

    def save_coverage_report(self, report: CoverageReport) -> None:
        path = self.questions_dir.parent / "coverage_report.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    def count(self) -> int:
        return sum(1 for _ in self.questions_dir.glob("*.json"))


# ─── S3 storage ───────────────────────────────────────────────────────────────

class S3Storage:
    """Saves questions to S3. Falls back gracefully if boto3 unavailable."""

    def __init__(self, bucket: str, region: str = "eu-west-2", prefix: str = "questions/") -> None:
        self.bucket = bucket
        self.prefix = prefix
        try:
            import boto3
            self._s3 = boto3.client("s3", region_name=region)
            self._available = True
        except ImportError:
            logger.warning("boto3 not installed — S3 storage unavailable")
            self._available = False
        except Exception as e:
            logger.warning(f"Failed to initialise S3 client: {e}")
            self._available = False

    def save_question(self, question: Question) -> None:
        if not self._available:
            return
        key = f"{self.prefix}{question.id}.json"
        try:
            self._s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=question.model_dump_json(indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:
            logger.warning(f"S3 save failed for {question.id}: {e}")

    def load_question(self, question_id: str) -> Optional[Question]:
        if not self._available:
            return None
        key = f"{self.prefix}{question_id}.json"
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=key)
            return Question.model_validate_json(obj["Body"].read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"S3 load failed for {question_id}: {e}")
            return None

    def save_coverage_report(self, report: CoverageReport) -> None:
        if not self._available:
            return
        key = "coverage_report.json"
        try:
            self._s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=report.model_dump_json(indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:
            logger.warning(f"S3 save coverage report failed: {e}")


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_storage(settings: Settings) -> StorageBackend:
    """Return appropriate storage backend based on settings."""
    if settings.storage_backend == "s3" and settings.s3_bucket:
        logger.info(f"Using S3 storage: s3://{settings.s3_bucket}/")
        return S3Storage(bucket=settings.s3_bucket, region=settings.s3_region)

    if settings.storage_backend == "s3":
        logger.warning("S3 backend requested but S3_BUCKET not configured — falling back to local")

    logger.info(f"Using local storage: {settings.questions_dir}")
    return LocalStorage(questions_dir=settings.questions_dir)
