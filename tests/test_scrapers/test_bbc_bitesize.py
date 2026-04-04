"""Tests for BBC Bitesize scraper using fixture HTML."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.scraper.bbc_bitesize import BBCBitesizeScraper

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "bbc_bitesize_sample.html"


@pytest.fixture
def scraper():
    return BBCBitesizeScraper()


@pytest.fixture
def fixture_html():
    return FIXTURE_PATH.read_text()


class TestBBCBitesizeScraper:
    def test_name_and_base_url(self, scraper):
        assert scraper.name == "bbc_bitesize"
        assert "bbc.co.uk" in scraper.base_url

    def test_discover_urls_returns_list(self, scraper):
        urls = scraper.discover_urls()
        assert len(urls) >= 5
        assert all("bbc.co.uk" in u for u in urls)

    def test_discover_urls_filters_by_topic(self, scraper):
        urls = scraper.discover_urls(topic_slugs=["electricity"])
        assert len(urls) >= 1
        assert all("bbc.co.uk" in u for u in urls)

    def test_parse_html_finds_questions(self, scraper, fixture_html):
        results = scraper.parse_html(fixture_html, "https://www.bbc.co.uk/bitesize/test")
        assert len(results) >= 2

    def test_parse_html_question_text_not_empty(self, scraper, fixture_html):
        results = scraper.parse_html(fixture_html, "https://www.bbc.co.uk/bitesize/test")
        for r in results:
            assert r.raw_question_text
            assert len(r.raw_question_text) > 10

    def test_parse_html_source_name_set(self, scraper, fixture_html):
        results = scraper.parse_html(fixture_html, "https://www.bbc.co.uk/bitesize/test")
        for r in results:
            assert r.source_name == "bbc_bitesize"

    def test_parse_html_source_url_set(self, scraper, fixture_html):
        url = "https://www.bbc.co.uk/bitesize/test"
        results = scraper.parse_html(fixture_html, url)
        for r in results:
            assert r.source_url == url

    def test_scrape_url_returns_empty_on_403(self, scraper):
        """Scrape URL returns empty list when fetch fails (simulating 403)."""
        with patch.object(scraper, "safe_fetch", return_value=None):
            results = scraper.scrape_url("https://www.bbc.co.uk/bitesize/test")
        assert results == []

    def test_scrape_url_uses_parsed_html(self, scraper, fixture_html):
        """Scrape URL parses HTML when fetch succeeds."""
        with patch.object(scraper, "safe_fetch", return_value=fixture_html):
            results = scraper.scrape_url("https://www.bbc.co.uk/bitesize/test")
        assert len(results) >= 2
