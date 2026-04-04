"""Abstract base class for all scrapers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from src.models import ScraperResult
from src.scraper.utils import get_html, safe_get

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class that all scrapers must inherit from."""

    name: str = ""
    base_url: str = ""

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__} must define a 'name' class attribute")
        if not self.base_url:
            raise ValueError(f"{type(self).__name__} must define a 'base_url' class attribute")
        self._logger = logging.getLogger(f"scraper.{self.name}")

    @abstractmethod
    def discover_urls(self, topic_slugs: list[str] | None = None) -> list[str]:
        """Return URLs to scrape for given topics (or all topics if None)."""
        ...

    @abstractmethod
    def scrape_url(self, url: str) -> list[ScraperResult]:
        """Extract raw questions from a single page. Returns empty list on failure."""
        ...

    def fetch(self, url: str, extra_headers: Optional[dict] = None) -> str:
        """GET with retries, timeout, random user-agent. Returns HTML or raises."""
        return get_html(
            url,
            retries=3,
            timeout=30,
            delay=1.5,
            extra_headers=extra_headers,
        )

    def safe_fetch(self, url: str, extra_headers: Optional[dict] = None) -> Optional[str]:
        """Like fetch but returns None instead of raising."""
        return safe_get(
            url,
            retries=3,
            timeout=30,
            delay=1.5,
            extra_headers=extra_headers,
        )

    def scrape_all(self, topic_slugs: list[str] | None = None, max_urls: int | None = None) -> list[ScraperResult]:
        """
        Discover URLs and scrape them all. Convenience method for running a full scrape.
        Errors on individual URLs are logged and skipped.
        """
        urls = self.discover_urls(topic_slugs)
        if max_urls is not None:
            urls = urls[:max_urls]

        all_results: list[ScraperResult] = []
        for url in urls:
            try:
                results = self.scrape_url(url)
                all_results.extend(results)
                self._logger.info(f"Scraped {len(results)} questions from {url}")
            except Exception as e:
                self._logger.warning(f"Failed to scrape {url}: {e}")

        return all_results
