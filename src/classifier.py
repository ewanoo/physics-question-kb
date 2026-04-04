"""
Classifier — uses Claude to classify raw ScraperResults into Question objects.

Two-stage classification:
1. claude-haiku (fast/cheap) for all questions
2. Escalate to claude-sonnet if confidence < 0.7
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import anthropic

from src.config import Settings
from src.models import AnswerOption, Difficulty, Question, QuestionType, ScraperResult
from src.taxonomy import ALL_TOPIC_SLUGS, TAXONOMY

logger = logging.getLogger(__name__)

# ─── Prompt ──────────────────────────────────────────────────────────────────

_TAXONOMY_BLOCK = "\n".join(
    f"  {slug}: {desc}"
    for group in TAXONOMY.values()
    for slug, desc in group["subtopics"].items()
)

_CLASSIFY_PROMPT = """You are a KS3 physics curriculum expert. Classify the following question for a Year 8 UK physics knowledge base.

## Valid topic slugs:
{taxonomy}

## Question to classify:
Source: {source_name}
URL: {source_url}
Raw question text: {question_text}
Raw options: {options}
Raw answer: {answer}
Raw explanation: {explanation}
Page context: {page_context}

## Instructions:
Return ONLY a JSON object (no markdown, no explanation) with exactly these fields:
{{
  "topic": "<subtopic_slug from the list above>",
  "difficulty": "easy|medium|hard",
  "question_type": "multiple_choice|short_answer|long_answer|true_false|fill_blank|calculation",
  "tags": ["tag1", "tag2"],
  "correct_answer": "<the correct answer as plain text>",
  "explanation": "<brief explanation suitable for a Year 8 student>",
  "confidence": <0.0-1.0 float>,
  "is_valid_ks3": <true|false>,
  "quality_score": <1.0-5.0 float>,
  "cleaned_question_text": "<cleaned, grammatically correct question text>"
}}

## Difficulty guidelines:
- easy: recall a fact or definition (no calculation needed)
- medium: apply a concept, simple 1-step calculation
- hard: multi-step problem, compare/evaluate, extended reasoning

## Quality score guidelines:
- 5.0: Excellent — clear, unambiguous, pedagogically strong
- 4.0: Good — clear question, minor wording issues
- 3.0: Acceptable — usable but some clarity issues
- 2.0: Poor — confusing, too vague, or incomplete
- 1.0: Unusable — garbled, wrong subject, not a physics question

## is_valid_ks3: true only if the question is genuinely about KS3 UK physics content.
""".strip()


# ─── Classification function ──────────────────────────────────────────────────

def classify_question(
    raw: ScraperResult,
    settings: Settings,
    _client: Optional[anthropic.Anthropic] = None,
) -> Optional[Question]:
    """
    Classify a raw ScraperResult into a Question.
    Returns None if the question is invalid or unusable.

    Uses Haiku by default; escalates to Sonnet if confidence < threshold.
    """
    client = _client or anthropic.Anthropic(api_key=settings.anthropic_api_key)

    result = _call_classifier(raw, settings.classification_model, client)
    if result is None:
        return None

    # Escalate to stronger model if confidence is low
    if result.get("confidence", 1.0) < settings.classification_confidence_threshold:
        logger.debug(
            f"Low confidence ({result['confidence']:.2f}), escalating to {settings.evaluation_model}"
        )
        result2 = _call_classifier(raw, settings.evaluation_model, client)
        if result2 is not None:
            result = result2

    return _build_question(raw, result)


def _call_classifier(
    raw: ScraperResult,
    model: str,
    client: anthropic.Anthropic,
) -> Optional[dict]:
    """Call Claude to classify a raw question. Returns parsed JSON dict or None."""
    options_str = json.dumps(raw.raw_options) if raw.raw_options else "none"

    prompt = _CLASSIFY_PROMPT.format(
        taxonomy=_TAXONOMY_BLOCK,
        source_name=raw.source_name,
        source_url=raw.source_url,
        question_text=raw.raw_question_text[:1000],
        options=options_str[:500],
        answer=str(raw.raw_answer or "")[:200],
        explanation=str(raw.raw_explanation or "")[:300],
        page_context=str(raw.page_context or "")[:200],
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Claude API error during classification: {e}")
        return None

    # Parse JSON
    try:
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1])
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error in classification: {e}\nRaw: {raw_text[:200]}")
        return None


def _build_question(raw: ScraperResult, classification: dict) -> Optional[Question]:
    """Convert raw + classification dict → Question model. Returns None if invalid."""
    # Validate required fields
    topic = classification.get("topic", "")
    if topic not in ALL_TOPIC_SLUGS:
        logger.debug(f"Invalid topic slug: {topic!r}")
        return None

    if not classification.get("is_valid_ks3", False):
        logger.debug("Question marked as not valid KS3")
        return None

    quality_score = float(classification.get("quality_score", 0))
    if quality_score < 2.5:
        logger.debug(f"Quality score too low: {quality_score}")
        return None

    confidence = float(classification.get("confidence", 0))
    if confidence < 0.5:
        logger.debug(f"Confidence too low: {confidence}")
        return None

    # Map question type
    q_type_str = classification.get("question_type", "short_answer")
    try:
        question_type = QuestionType(q_type_str)
    except ValueError:
        question_type = QuestionType.SHORT_ANSWER

    # Map difficulty
    difficulty_str = classification.get("difficulty", "medium")
    try:
        difficulty = Difficulty(difficulty_str)
    except ValueError:
        difficulty = Difficulty.MEDIUM

    # Build answer options for MC
    options = None
    if question_type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
        if raw.raw_options:
            options = []
            labels = ["A", "B", "C", "D"]
            for i, opt in enumerate(raw.raw_options):
                if isinstance(opt, dict):
                    options.append(AnswerOption(
                        label=opt.get("label", labels[i] if i < len(labels) else str(i)),
                        text=str(opt.get("text", "")),
                        is_correct=bool(opt.get("is_correct") or opt.get("correct", False)),
                    ))

    question_text = (
        classification.get("cleaned_question_text")
        or raw.raw_question_text
    ).strip()

    return Question(
        question_text=question_text,
        question_type=question_type,
        difficulty=difficulty,
        topic=topic,
        tags=classification.get("tags", []),
        options=options,
        correct_answer=classification.get("correct_answer") or raw.raw_answer,
        explanation=classification.get("explanation") or raw.raw_explanation,
        source_url=raw.source_url,
        source_name=raw.source_name,
        classified_at=datetime.utcnow(),
        classification_confidence=confidence,
        quality_score=quality_score,
    )


def classify_batch(
    raws: list[ScraperResult],
    settings: Settings,
    _client: Optional[anthropic.Anthropic] = None,
) -> list[Question]:
    """
    Classify a batch of raw results.
    Skips failures, logs them. Returns successfully classified questions.
    """
    client = _client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    results: list[Question] = []
    failed = 0

    for i, raw in enumerate(raws):
        try:
            question = classify_question(raw, settings, _client=client)
            if question:
                results.append(question)
            else:
                logger.debug(f"Question {i} filtered out during classification")
        except Exception as e:
            failed += 1
            logger.warning(f"Classification failed for question {i}: {e}")

    logger.info(
        f"Classified {len(results)}/{len(raws)} questions "
        f"({failed} errors, {len(raws) - len(results) - failed} filtered)"
    )
    return results
