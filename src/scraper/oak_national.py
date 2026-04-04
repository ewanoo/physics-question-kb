"""
Oak National Academy question generator.

Simulates Oak National Academy lesson quiz questions by generating short, clear
knowledge-check style questions using the Claude API. Oak National style questions
are typically shorter, more direct, and focused on single concepts.
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

_GENERATION_PROMPT = """You are generating KS3 physics lesson quiz questions in the style of Oak National Academy for Year 8 students.
Oak National quiz questions are short, direct knowledge-check questions used at the start or end of a lesson.

Topic: {topic}
Subtopic: {subtopic}
Difficulty: {difficulty} ({difficulty_desc})

Generate exactly {n} lesson quiz questions about "{subtopic_display}" for Year 8 (KS3) students.

Requirements:
- Mix of multiple_choice (at least 3) and short_answer (at least 1) types
- Multiple choice: 4 options (A/B/C/D), exactly one correct
- Keep questions SHORT and focused on a single key concept
- Conversational but academically accurate language
- Accurate science consistent with UK KS3 curriculum
- Start questions with varied stems: "What is...", "Which...", "How does...", "Why does...", etc.

Return ONLY a JSON array (no markdown, no explanation) with this exact structure:
[
  {{
    "question_text": "What type of energy does a moving car have?",
    "question_type": "multiple_choice",
    "options": [
      {{"label": "A", "text": "Chemical energy", "is_correct": false}},
      {{"label": "B", "text": "Kinetic energy", "is_correct": true}},
      {{"label": "C", "text": "Thermal energy", "is_correct": false}},
      {{"label": "D", "text": "Nuclear energy", "is_correct": false}}
    ],
    "correct_answer": "Kinetic energy",
    "explanation": "Moving objects have kinetic energy. The faster the car moves, the more kinetic energy it has."
  }},
  {{
    "question_text": "Name two ways to increase the gravitational potential energy of an object.",
    "question_type": "short_answer",
    "options": null,
    "correct_answer": "Increase its height above the ground, or increase its mass.",
    "explanation": "GPE = mass × gravitational field strength × height, so increasing mass or height increases GPE."
  }}
]"""


class OakNationalScraper(BaseScraper):
    """Generates Oak National Academy style quiz questions using the Claude API."""

    name = "oak_national"
    base_url = "https://www.thenational.academy"

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
                    urls.append(f"oak://{subtopic_slug}/{difficulty}")
        return urls

    def scrape_url(self, url: str) -> list[ScraperResult]:
        """Generate questions for a (subtopic_slug, difficulty) pair."""
        if not url.startswith("oak://"):
            logger.warning(f"Invalid Oak National URL: {url}")
            return []

        parts = url.replace("oak://", "").split("/")
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

        logger.info(f"[oak_national] Generated {len(results)} {difficulty} questions for {subtopic_display}")
        return results
