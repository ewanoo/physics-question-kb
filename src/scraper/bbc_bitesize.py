"""BBC Bitesize KS3 Physics scraper.

Note: This site returns 403 from cloud IPs. The scraper is built and tested
against saved fixture HTML, but live scraping may fail in cloud environments.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from src.models import ScraperResult
from src.scraper.base import BaseScraper
from src.scraper.utils import extract_text

logger = logging.getLogger(__name__)

_TOPIC_URLS = {
    "energy": "https://www.bbc.co.uk/bitesize/topics/z49cwmn",
    "forces": "https://www.bbc.co.uk/bitesize/topics/zgrk34j",
    "waves.sound": "https://www.bbc.co.uk/bitesize/topics/zgffr82",
    "waves.light": "https://www.bbc.co.uk/bitesize/topics/zxsvr82",
    "electricity": "https://www.bbc.co.uk/bitesize/topics/zgy39j6",
    "matter": "https://www.bbc.co.uk/bitesize/topics/ztrg87h",
    "space": "https://www.bbc.co.uk/bitesize/topics/zdrrd2p",
}


class BBCBitesizeScraper(BaseScraper):
    name = "bbc_bitesize"
    base_url = "https://www.bbc.co.uk"

    def discover_urls(self, topic_slugs: list[str] | None = None) -> list[str]:
        """Return BBC Bitesize topic URLs."""
        if topic_slugs:
            urls = []
            for slug in topic_slugs:
                # Match on exact or prefix
                for key, url in _TOPIC_URLS.items():
                    if key == slug or key.startswith(slug + ".") or slug.startswith(key):
                        urls.append(url)
            return list(set(urls))
        return list(_TOPIC_URLS.values())

    def scrape_url(self, url: str) -> list[ScraperResult]:
        """Scrape a BBC Bitesize topic page for questions."""
        html = self.safe_fetch(url)
        if not html:
            logger.warning(f"Failed to fetch {url} (likely 403 from cloud IP)")
            return []
        return self.parse_html(html, url)

    def parse_html(self, html: str, source_url: str) -> list[ScraperResult]:
        """Parse BBC Bitesize HTML for quiz questions. Exposed for testing."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # BBC Bitesize quiz questions appear in several patterns:
        # 1. <div class="question"> containing prompt and options
        # 2. <li class="question-item"> in quiz sections
        # 3. Structured quiz blocks with data-testid attributes

        # Pattern 1: data-testid quiz blocks
        quiz_blocks = soup.find_all(attrs={"data-testid": re.compile(r"question|quiz", re.I)})
        for block in quiz_blocks:
            result = self._parse_quiz_block(block, source_url)
            if result:
                results.append(result)

        # Pattern 2: generic question divs
        if not results:
            question_divs = soup.find_all("div", class_=re.compile(r"question", re.I))
            for div in question_divs:
                result = self._parse_question_div(div, source_url)
                if result:
                    results.append(result)

        # Pattern 3: list-based questions
        if not results:
            q_items = soup.find_all("li", class_=re.compile(r"question", re.I))
            for item in q_items:
                text = extract_text(str(item))
                if len(text) > 20 and "?" in text:
                    results.append(ScraperResult(
                        raw_question_text=text,
                        source_url=source_url,
                        source_name=self.name,
                    ))

        logger.info(f"Parsed {len(results)} questions from {source_url}")
        return results

    def _parse_quiz_block(self, block, source_url: str) -> ScraperResult | None:
        """Parse a quiz block element."""
        # Find question text
        prompt = block.find(attrs={"data-testid": re.compile(r"prompt|question-text", re.I)})
        if not prompt:
            prompt = block.find(["h2", "h3", "p"], class_=re.compile(r"question|prompt", re.I))
        if not prompt:
            return None

        question_text = extract_text(str(prompt))
        if not question_text or len(question_text) < 10:
            return None

        # Find options
        option_elements = block.find_all(attrs={"data-testid": re.compile(r"option|answer|choice", re.I)})
        raw_options = []
        labels = ["A", "B", "C", "D"]
        for i, opt in enumerate(option_elements[:4]):
            opt_text = extract_text(str(opt))
            is_correct = bool(opt.get("data-correct") or "correct" in opt.get("class", []))
            raw_options.append({
                "label": labels[i] if i < len(labels) else str(i),
                "text": opt_text,
                "correct": is_correct,
            })

        return ScraperResult(
            raw_question_text=question_text,
            raw_options=raw_options if raw_options else None,
            source_url=source_url,
            source_name=self.name,
        )

    def _parse_question_div(self, div, source_url: str) -> ScraperResult | None:
        """Parse a generic question div."""
        text = extract_text(str(div))
        if not text or len(text) < 15:
            return None
        # Require either a question mark or known question starters
        if "?" not in text and not re.match(r"(what|which|how|why|when|describe|explain|state|name|give)", text, re.I):
            return None

        return ScraperResult(
            raw_question_text=text[:500],
            source_url=source_url,
            source_name=self.name,
        )
