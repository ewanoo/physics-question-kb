"""
KS3 Textbook question generator.

Simulates a KS3 physics textbook source by generating structured textbook-style
questions using the Claude API. Questions are written in a formal, textbook style
appropriate for the KS3 curriculum.
"""

from __future__ import annotations

import json
import logging

import anthropic

from src.models import ScraperResult
from src.scraper.base import BaseScraper
from src.taxonomy import TAXONOMY

logger = logging.getLogger(__name__)

_GENERATION_MODEL = "claude-haiku-4-5-20251001"
_QUESTIONS_PER_BATCH = 5

_DIFFICULTY_DESCRIPTIONS = {
    "easy": "recall a fact, definition, or simple observation (no calculation needed)",
    "medium": "apply a concept, make a simple 1-step calculation, or identify a relationship",
    "hard": "multi-step problem, compare/evaluate two ideas, or explain using scientific reasoning",
}

_GENERATION_PROMPT = """You are generating KS3 physics textbook questions for Year 8 students in England.
Write questions in a formal textbook style, as if from a published KS3 Physics textbook.

Topic: {topic}
Subtopic: {subtopic}
Difficulty: {difficulty} ({difficulty_desc})

Generate exactly {n} textbook-style practice questions about "{subtopic_display}" for KS3 Year 8.

Requirements:
- Mix of multiple_choice (at least 3) and short_answer (at least 1) types
- Multiple choice: 4 options (A/B/C/D), exactly one correct
- Formal textbook language, clear and precise
- Accurate science consistent with UK KS3 curriculum
- Different phrasing from common quiz formats — use textbook phrasing

Return ONLY a JSON array (no markdown, no explanation) with this exact structure:
[
  {{
    "question_text": "Which of the following correctly defines potential energy?",
    "question_type": "multiple_choice",
    "options": [
      {{"label": "A", "text": "Energy stored due to position or condition", "is_correct": true}},
      {{"label": "B", "text": "Energy of motion", "is_correct": false}},
      {{"label": "C", "text": "Energy transferred by heating", "is_correct": false}},
      {{"label": "D", "text": "Energy stored in chemical bonds only", "is_correct": false}}
    ],
    "correct_answer": "Energy stored due to position or condition",
    "explanation": "Potential energy is stored energy that an object has due to its position or state."
  }},
  {{
    "question_text": "Define the term 'thermal equilibrium'.",
    "question_type": "short_answer",
    "options": null,
    "correct_answer": "The state where two objects in contact reach the same temperature and there is no net heat transfer between them.",
    "explanation": "Thermal equilibrium is reached when there is no longer a temperature difference to drive heat transfer."
  }}
]"""


class KS3TextbookScraper(BaseScraper):
    """Generates KS3 textbook-style physics questions using the Claude API."""

    name = "ks3_textbook"
    base_url = "https://ks3-physics-textbook.example"

    def __init__(self, api_key: str = "", model: str = _GENERATION_MODEL) -> None:
        super().__init__()
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model

    def discover_urls(self, topic_slugs: list[str] | None = None) -> list[str]:
        """Return synthetic 'URLs' representing (subtopic, difficulty) pairs."""
        urls = []
        for topic_name, group_data in TAXONOMY.items():
            for subtopic_slug in group_data["subtopics"]:
                if topic_slugs and subtopic_slug not in topic_slugs:
                    continue
                for difficulty in ["easy", "medium", "hard"]:
                    urls.append(f"ks3textbook://{subtopic_slug}/{difficulty}")
        return urls

    def scrape_url(self, url: str) -> list[ScraperResult]:
        """Generate questions for a (subtopic_slug, difficulty) pair."""
        if not url.startswith("ks3textbook://"):
            logger.warning(f"Invalid KS3 textbook URL: {url}")
            return []

        parts = url.replace("ks3textbook://", "").split("/")
        if len(parts) != 2:
            return []

        subtopic_slug, difficulty = parts[0], parts[1]
        topic_name, subtopic_display = self._resolve_names(subtopic_slug)
        if not topic_name:
            logger.warning(f"Unknown subtopic slug: {subtopic_slug}")
            return []

        return self._generate_questions(
            topic=topic_name,
            subtopic=subtopic_slug,
            subtopic_display=subtopic_display,
            difficulty=difficulty,
            url=url,
        )

    def _resolve_names(self, subtopic_slug: str) -> tuple[str, str]:
        for topic_name, group_data in TAXONOMY.items():
            subtopics = group_data["subtopics"]
            if subtopic_slug in subtopics:
                return topic_name, subtopics[subtopic_slug]
        return "", ""

    def _generate_questions(self, topic, subtopic, subtopic_display, difficulty, url) -> list[ScraperResult]:
        prompt = _GENERATION_PROMPT.format(
            topic=topic,
            subtopic=subtopic,
            subtopic_display=subtopic_display,
            difficulty=difficulty,
            difficulty_desc=_DIFFICULTY_DESCRIPTIONS.get(difficulty, ""),
            n=_QUESTIONS_PER_BATCH,
        )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Claude API error for {url}: {e}")
            return []

        try:
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                raw_text = "\n".join(lines[1:-1])
            questions_data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {url}: {e}\nRaw: {raw_text[:200]}")
            return []

        results = []
        for q in questions_data:
            if not isinstance(q, dict):
                continue
            question_text = q.get("question_text", "").strip()
            if not question_text:
                continue

            results.append(
                ScraperResult(
                    raw_question_text=question_text,
                    raw_options=q.get("options"),
                    raw_answer=q.get("correct_answer", ""),
                    raw_explanation=q.get("explanation", ""),
                    source_url=url,
                    source_name=self.name,
                    page_context=f"topic={topic}|subtopic={subtopic}|difficulty={difficulty}",
                )
            )

        logger.info(f"[ks3_textbook] Generated {len(results)} {difficulty} questions for {subtopic_display}")
        return results
