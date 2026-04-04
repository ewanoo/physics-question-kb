from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""
    classification_model: str = "claude-haiku-4-5-20251001"
    evaluation_model: str = "claude-sonnet-4-6"

    # Storage
    storage_backend: str = "local"   # "local" or "s3"
    s3_bucket: str = ""
    s3_region: str = "eu-west-2"
    db_path: Path = DATA_DIR / "physics_kb.db"
    questions_dir: Path = DATA_DIR / "questions"

    # Scraping
    request_delay_seconds: float = 1.5
    max_retries: int = 3
    request_timeout_seconds: int = 30

    # Quality thresholds
    min_questions_per_subtopic: int = 5
    target_total_questions: int = 500
    min_quality_score: float = 3.5
    min_sources: int = 3
    classification_confidence_threshold: float = 0.7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()
