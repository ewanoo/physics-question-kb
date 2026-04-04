"""Isaac Physics scraper — uses the public REST API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.models import ScraperResult
from src.scraper.base import BaseScraper
from src.scraper.utils import get_json

logger = logging.getLogger(__name__)

# Isaac Physics API endpoints
_API_BASE = "https://isaacphysics.org/api"

# KS3 / Year 8 relevant subject tags to query
_SUBJECT_TAGS = [
    "ks3",
    "physics",
]

# Topic tags that map to KS3 physics content
_TOPIC_TAGS = [
    "energy",
    "forces",
    "waves",
    "electricity",
    "matter",
    "space",
    "light",
    "sound",
    "magnets",
    "gravity",
    "pressure",
    "density",
    "motion",
    "circuits",
    "static_electricity",
    "thermal",
]


class IsaacPhysicsScraper(BaseScraper):
    name = "isaac_physics"
    base_url = "https://isaacphysics.org"

    def discover_urls(self, topic_slugs: list[str] | None = None) -> list[str]:
        """Return API endpoint URLs for Isaac Physics questions."""
        urls = []
        # Try the main questions API with various tag combinations
        base_url = f"{_API_BASE}/pages/questions"

        # Generate URLs for each topic tag
        tags_to_try = topic_slugs if topic_slugs else _TOPIC_TAGS
        for tag in tags_to_try:
            urls.append(f"{base_url}?tags={tag}&limit=100&start_index=0")

        # Also try the main physics page listing
        urls.append(f"{_API_BASE}/pages/questions?subjects=physics&limit=100&start_index=0")
        urls.append(f"{_API_BASE}/pages/questions?tags=physics_skills_1&limit=100&start_index=0")
        urls.append(f"{_API_BASE}/pages/questions?tags=phys_linking&limit=100&start_index=0")

        return urls

    def scrape_url(self, url: str) -> list[ScraperResult]:
        """Fetch and parse Isaac Physics API response."""
        data = get_json(url)
        if not data:
            logger.warning(f"No data returned from {url}")
            return []

        results = []

        # API returns {"results": [...], "totalResults": N}
        questions = []
        if isinstance(data, dict):
            questions = data.get("results", [])
            if not questions:
                # Sometimes direct question object
                questions = [data] if data.get("type") else []
        elif isinstance(data, list):
            questions = data

        for q in questions:
            result = self._parse_question(q, url)
            if result:
                results.append(result)

        logger.info(f"Found {len(results)} questions from {url}")
        return results

    def _parse_question(self, q: dict, source_url: str) -> ScraperResult | None:
        """Parse a single Isaac Physics question object."""
        if not isinstance(q, dict):
            return None

        q_type = q.get("type", "")
        # Only process question types we can handle
        valid_types = {
            "isaacMultiChoiceQuestion",
            "isaacNumericQuestion",
            "isaacSymbolicQuestion",
            "isaacStringMatchQuestion",
            "isaacFreeTextQuestion",
            "isaacQuickQuestion",
        }

        # Also handle containers (question pages)
        if q_type == "isaacQuestionPage":
            return self._parse_question_page(q, source_url)

        if q_type not in valid_types and not q_type.startswith("isaac"):
            return None

        # Extract question text
        value = q.get("value", "") or ""
        title = q.get("title", "") or ""

        # Build question text from value (HTML/markdown)
        raw_text = _extract_content_text(q)
        if not raw_text and title:
            raw_text = title
        if not raw_text:
            return None

        # Extract answer choices for multiple choice
        raw_options = None
        raw_answer = None
        if q_type == "isaacMultiChoiceQuestion":
            choices = q.get("choices", [])
            raw_options = []
            for choice in choices:
                choice_text = _extract_content_text(choice)
                is_correct = choice.get("correct", False)
                raw_options.append({"text": choice_text, "correct": is_correct})
                if is_correct:
                    raw_answer = choice_text

        # Get explanation/hints
        raw_explanation = None
        hints = q.get("hints", [])
        if hints:
            raw_explanation = " ".join(_extract_content_text(h) for h in hints if h)

        # Build context from tags
        tags = q.get("tags", [])
        page_context = f"Tags: {', '.join(tags)}" if tags else None

        question_url = source_url
        q_id = q.get("id", "")
        if q_id:
            question_url = f"{self.base_url}/questions/{q_id}"

        return ScraperResult(
            raw_question_text=raw_text,
            raw_options=raw_options,
            raw_answer=raw_answer,
            raw_explanation=raw_explanation,
            source_url=question_url,
            source_name=self.name,
            page_context=page_context,
        )

    def _parse_question_page(self, page: dict, source_url: str) -> ScraperResult | None:
        """Parse an isaacQuestionPage that contains sub-questions."""
        title = page.get("title", "")
        children = page.get("children", [])
        if not children:
            return None

        # Get first actual question child
        for child in children:
            result = self._parse_question(child, source_url)
            if result:
                if title and not result.page_context:
                    result.page_context = f"Page: {title}"
                return result
        return None

    def scrape_topic_questions(self, topic: str, save_dir: Path | None = None) -> list[ScraperResult]:
        """Scrape all questions for a specific topic and optionally save to disk."""
        urls = [f"{_API_BASE}/pages/questions?tags={topic}&limit=100&start_index=0"]
        all_results = []

        for url in urls:
            results = self.scrape_url(url)
            all_results.extend(results)

        if save_dir and all_results:
            save_dir.mkdir(parents=True, exist_ok=True)
            output = save_dir / f"{topic}.json"
            with open(output, "w") as f:
                json.dump([r.model_dump() for r in all_results], f, indent=2, default=str)
            logger.info(f"Saved {len(all_results)} questions to {output}")

        return all_results


def _extract_content_text(obj: dict) -> str:
    """Recursively extract text from Isaac Physics content object."""
    if not isinstance(obj, dict):
        return str(obj) if obj else ""

    parts = []

    # Direct value field
    value = obj.get("value", "")
    if value and isinstance(value, str):
        # Strip basic HTML
        import re
        text = re.sub(r"<[^>]+>", " ", value)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            parts.append(text)

    # Children
    children = obj.get("children", [])
    if children and isinstance(children, list):
        for child in children:
            child_text = _extract_content_text(child)
            if child_text:
                parts.append(child_text)

    return " ".join(parts).strip()
