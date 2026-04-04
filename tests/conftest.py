"""Shared fixtures for all tests."""

import tempfile
from pathlib import Path

import pytest

from src.db import init_db
from src.models import AnswerOption, Difficulty, Question, QuestionType


@pytest.fixture
def tmp_db(tmp_path):
    """A fresh, initialized SQLite database in a temp directory."""
    db_path = tmp_path / "test_physics_kb.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def sample_mc_question():
    """A sample multiple-choice question for testing."""
    return Question(
        question_text="What is the unit of electrical resistance?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        difficulty=Difficulty.EASY,
        topic="electricity.current_voltage",
        tags=["resistance", "units"],
        options=[
            AnswerOption(label="A", text="Ampere", is_correct=False),
            AnswerOption(label="B", text="Ohm", is_correct=True),
            AnswerOption(label="C", text="Volt", is_correct=False),
            AnswerOption(label="D", text="Watt", is_correct=False),
        ],
        correct_answer="B",
        explanation="Resistance is measured in Ohms (Ω), named after Georg Ohm.",
        source_name="test",
        quality_score=4.0,
    )


@pytest.fixture
def sample_questions(sample_mc_question):
    """A small set of diverse sample questions."""
    return [
        sample_mc_question,
        Question(
            question_text="A car travels 150 m in 10 s. What is its speed?",
            question_type=QuestionType.CALCULATION,
            difficulty=Difficulty.MEDIUM,
            topic="forces.speed",
            tags=["speed", "calculation"],
            correct_answer="15 m/s",
            explanation="Speed = distance / time = 150 / 10 = 15 m/s",
            source_name="test",
            quality_score=4.5,
        ),
        Question(
            question_text="Name two renewable energy sources.",
            question_type=QuestionType.SHORT_ANSWER,
            difficulty=Difficulty.EASY,
            topic="energy.resources",
            tags=["renewable", "energy-sources"],
            correct_answer="Any two from: solar, wind, hydroelectric, tidal, geothermal",
            source_name="test",
            quality_score=3.5,
        ),
    ]
