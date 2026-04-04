"""
Claude-based question generator.

Since most education websites block cloud IPs, this scraper uses the Claude API
to generate KS3 Year 8 physics questions directly. Each generated batch is
associated with a topic slug and difficulty, producing well-structured questions
in MCQ and short-answer formats.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import anthropic

from src.models import ScraperResult
from src.scraper.base import BaseScraper
from src.taxonomy import TAXONOMY

logger = logging.getLogger(__name__)

_GENERATION_MODEL = "claude-haiku-4-5-20251001"

# Questions to generate per (subtopic, difficulty) combination
_QUESTIONS_PER_BATCH = 5

# Difficulty → description mapping for the prompt
_DIFFICULTY_DESCRIPTIONS = {
    "easy": "recall a fact, definition, or simple observation (no calculation needed)",
    "medium": "apply a concept, make a simple 1-step calculation, or identify a relationship",
    "hard": "multi-step problem, compare/evaluate two ideas, or explain using scientific reasoning",
}

_GENERATION_PROMPT = """You are an expert KS3 physics teacher generating practice questions for Year 8 students in England.

Topic: {topic}
Subtopic: {subtopic}
Difficulty: {difficulty} ({difficulty_desc})

Generate exactly {n} practice questions about "{subtopic_display}" suitable for KS3 Year 8 students.

Requirements:
- Mix of multiple_choice (at least 3) and short_answer (at least 1) types
- Multiple choice: 4 options (A/B/C/D), exactly one correct
- All questions must be clearly about the given subtopic
- Language appropriate for 12-13 year olds
- Accurate science, consistent with UK KS3 curriculum

Return ONLY a JSON array (no markdown, no explanation) with this exact structure:
[
  {{
    "question_text": "What is the unit of electric current?",
    "question_type": "multiple_choice",
    "options": [
      {{"label": "A", "text": "Volt", "is_correct": false}},
      {{"label": "B", "text": "Ampere", "is_correct": true}},
      {{"label": "C", "text": "Ohm", "is_correct": false}},
      {{"label": "D", "text": "Watt", "is_correct": false}}
    ],
    "correct_answer": "Ampere",
    "explanation": "Electric current is measured in amperes (A), named after André-Marie Ampère."
  }},
  {{
    "question_text": "Explain what happens to resistance when the length of a wire is doubled.",
    "question_type": "short_answer",
    "options": null,
    "correct_answer": "The resistance doubles because resistance is proportional to the length of the wire.",
    "explanation": "Resistance increases with wire length because electrons have more collisions over a longer path."
  }}
]"""


class QuestionGeneratorScraper(BaseScraper):
    """Generates KS3 physics questions using the Claude API."""

    name = "claude_generator"
    base_url = "https://api.anthropic.com"

    def __init__(self, api_key: str = "", model: str = _GENERATION_MODEL) -> None:
        super().__init__()
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model

    def discover_urls(self, topic_slugs: list[str] | None = None) -> list[str]:
        """Return synthetic 'URLs' representing (subtopic, difficulty) pairs."""
        urls = []
        for topic_name, group_data in TAXONOMY.items():
            for subtopic_slug in group_data["subtopics"]:
                # Only generate for requested slugs if specified
                if topic_slugs and subtopic_slug not in topic_slugs:
                    continue
                for difficulty in ["easy", "medium", "hard"]:
                    urls.append(f"generate://{subtopic_slug}/{difficulty}")
        return urls

    def scrape_url(self, url: str) -> list[ScraperResult]:
        """Generate questions for a (subtopic_slug, difficulty) pair."""
        if not url.startswith("generate://"):
            logger.warning(f"Invalid generator URL: {url}")
            return []

        parts = url.replace("generate://", "").split("/")
        if len(parts) != 2:
            return []

        subtopic_slug, difficulty = parts[0], parts[1]

        # Find topic and subtopic display names
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
        """Return (topic_name, subtopic_display) for a slug."""
        for topic_name, group_data in TAXONOMY.items():
            subtopics = group_data["subtopics"]
            if subtopic_slug in subtopics:
                return topic_name, subtopics[subtopic_slug]
        return "", ""

    def _generate_questions(
        self,
        topic: str,
        subtopic: str,
        subtopic_display: str,
        difficulty: str,
        url: str,
    ) -> list[ScraperResult]:
        """Call Claude to generate questions, return ScraperResults."""
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

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
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

            options = q.get("options")
            correct_answer = q.get("correct_answer", "")
            explanation = q.get("explanation", "")

            results.append(
                ScraperResult(
                    raw_question_text=question_text,
                    raw_options=options,
                    raw_answer=correct_answer,
                    raw_explanation=explanation,
                    source_url=url,
                    source_name=self.name,
                    page_context=f"topic={topic}|subtopic={subtopic}|difficulty={difficulty}",
                )
            )

        logger.info(
            f"Generated {len(results)} {difficulty} questions for {subtopic_display}"
        )
        return results

    def generate_all(
        self,
        topic_slugs: list[str] | None = None,
        save_dir: Path | None = None,
    ) -> list[ScraperResult]:
        """Generate all questions and optionally save raw results to disk."""
        urls = self.discover_urls(topic_slugs)
        all_results: list[ScraperResult] = []

        for url in urls:
            try:
                results = self.scrape_url(url)
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"Failed to generate for {url}: {e}")

        if save_dir and all_results:
            save_dir.mkdir(parents=True, exist_ok=True)
            output_path = save_dir / "generated_questions.json"
            with open(output_path, "w") as f:
                json.dump(
                    [r.model_dump() for r in all_results],
                    f,
                    indent=2,
                    default=str,
                )
            logger.info(f"Saved {len(all_results)} questions to {output_path}")

        return all_results
