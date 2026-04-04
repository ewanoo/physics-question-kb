from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    CALCULATION = "calculation"


class Difficulty(str, Enum):
    EASY = "easy"      # Recall / basic knowledge
    MEDIUM = "medium"  # Application / some reasoning
    HARD = "hard"      # Multi-step / synthesis


class AnswerOption(BaseModel):
    label: str       # "A", "B", "C", "D"
    text: str
    is_correct: bool = False


class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_text: str
    question_type: QuestionType
    difficulty: Difficulty
    topic: str                           # e.g. "electricity.circuits"
    tags: list[str] = []
    options: Optional[list[AnswerOption]] = None  # For MC/true-false
    correct_answer: Optional[str] = None          # For non-MC questions
    explanation: Optional[str] = None
    source_url: Optional[str] = None
    source_name: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    classified_at: Optional[datetime] = None
    classification_confidence: Optional[float] = None
    quality_score: Optional[float] = None         # 1.0 - 5.0
    year_group: str = "year8"
    curriculum: str = "ks3"
    raw_html: Optional[str] = None


class ScraperResult(BaseModel):
    """Raw output from a scraper, before classification."""
    raw_question_text: str
    raw_options: Optional[list[dict]] = None
    raw_answer: Optional[str] = None
    raw_explanation: Optional[str] = None
    source_url: str
    source_name: str
    page_context: Optional[str] = None
    raw_html: Optional[str] = None


class CoverageReport(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_questions: int
    by_topic: dict[str, int]            # topic_slug -> count
    by_difficulty: dict[str, int]       # difficulty -> count
    by_source: dict[str, int]           # source_name -> count
    by_type: dict[str, int]             # question_type -> count
    weak_topics: list[str]              # Topics below minimum threshold
    mean_quality_score: Optional[float] = None
    duplicate_rate: float = 0.0
    overall_quality_score: float = 0.0  # 0.0 - 1.0
    is_complete: bool = False
    notes: str = ""
