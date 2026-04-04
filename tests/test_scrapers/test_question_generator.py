"""Tests for Claude question generator scraper — mocked API calls."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.scraper.question_generator import QuestionGeneratorScraper

_MOCK_RESPONSE_JSON = json.dumps([
    {
        "question_text": "What is the unit of electric current?",
        "question_type": "multiple_choice",
        "options": [
            {"label": "A", "text": "Volt", "is_correct": False},
            {"label": "B", "text": "Ampere", "is_correct": True},
            {"label": "C", "text": "Ohm", "is_correct": False},
            {"label": "D", "text": "Watt", "is_correct": False},
        ],
        "correct_answer": "Ampere",
        "explanation": "Current is measured in amperes.",
    },
    {
        "question_text": "Describe what happens to resistance when wire length doubles.",
        "question_type": "short_answer",
        "options": None,
        "correct_answer": "Resistance doubles.",
        "explanation": "Resistance is proportional to wire length.",
    },
])


def _make_mock_client():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_MOCK_RESPONSE_JSON)]
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def scraper():
    s = QuestionGeneratorScraper(api_key="fake-key")
    s._client = _make_mock_client()
    return s


class TestQuestionGeneratorScraper:
    def test_name_and_base_url(self, scraper):
        assert scraper.name == "claude_generator"
        assert scraper.base_url

    def test_discover_urls_covers_all_subtopics(self, scraper):
        urls = scraper.discover_urls()
        # 33 subtopics × 3 difficulties = 99 urls
        assert len(urls) == 99
        assert all(url.startswith("generate://") for url in urls)

    def test_discover_urls_filters_by_topic(self, scraper):
        urls = scraper.discover_urls(topic_slugs=["electricity.circuits"])
        assert len(urls) == 3  # easy/medium/hard

    def test_scrape_url_returns_results(self, scraper):
        results = scraper.scrape_url("generate://electricity.circuits/easy")
        assert len(results) == 2

    def test_scrape_url_question_text_set(self, scraper):
        results = scraper.scrape_url("generate://electricity.circuits/easy")
        assert results[0].raw_question_text == "What is the unit of electric current?"

    def test_scrape_url_options_set_for_mc(self, scraper):
        results = scraper.scrape_url("generate://electricity.circuits/easy")
        mc = results[0]
        assert mc.raw_options is not None
        assert len(mc.raw_options) == 4

    def test_scrape_url_source_name(self, scraper):
        results = scraper.scrape_url("generate://electricity.circuits/easy")
        for r in results:
            assert r.source_name == "claude_generator"

    def test_scrape_url_page_context_contains_topic(self, scraper):
        results = scraper.scrape_url("generate://electricity.circuits/easy")
        for r in results:
            assert "electricity" in r.page_context

    def test_scrape_url_invalid_url_returns_empty(self, scraper):
        results = scraper.scrape_url("https://not-a-generator-url.com")
        assert results == []

    def test_scrape_url_unknown_slug_returns_empty(self, scraper):
        results = scraper.scrape_url("generate://unknown.slug/easy")
        assert results == []

    def test_scrape_url_handles_json_error(self, scraper):
        scraper._client.messages.create.return_value.content[0].text = "not json"
        results = scraper.scrape_url("generate://electricity.circuits/easy")
        assert results == []

    def test_scrape_url_handles_api_error(self, scraper):
        scraper._client.messages.create.side_effect = Exception("API down")
        results = scraper.scrape_url("generate://electricity.circuits/easy")
        assert results == []
