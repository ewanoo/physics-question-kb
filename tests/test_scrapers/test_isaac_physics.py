"""Tests for Isaac Physics scraper using fixture JSON."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.scraper.isaac_physics import IsaacPhysicsScraper

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "isaac_physics_sample.json"


@pytest.fixture
def scraper():
    return IsaacPhysicsScraper()


@pytest.fixture
def fixture_data():
    return json.loads(FIXTURE_PATH.read_text())


class TestIsaacPhysicsScraper:
    def test_name_and_base_url(self, scraper):
        assert scraper.name == "isaac_physics"
        assert "isaacphysics.org" in scraper.base_url

    def test_discover_urls_returns_list(self, scraper):
        urls = scraper.discover_urls()
        assert len(urls) >= 5
        assert all("isaacphysics.org" in u for u in urls)

    def test_discover_urls_filters_by_topic(self, scraper):
        urls = scraper.discover_urls(topic_slugs=["energy"])
        assert len(urls) >= 1

    def test_scrape_url_parses_fixture_json(self, scraper, fixture_data):
        url = "https://isaacphysics.org/api/pages/questions?tags=electricity"
        with patch("src.scraper.isaac_physics.get_json", return_value=fixture_data):
            results = scraper.scrape_url(url)
        assert len(results) >= 3

    def test_scrape_url_returns_empty_on_403(self, scraper):
        with patch("src.scraper.isaac_physics.get_json", return_value=None):
            results = scraper.scrape_url("https://isaacphysics.org/api/pages/questions?tags=physics")
        assert results == []

    def test_parsed_results_have_question_text(self, scraper, fixture_data):
        url = "https://isaacphysics.org/api/pages/questions?tags=electricity"
        with patch("src.scraper.isaac_physics.get_json", return_value=fixture_data):
            results = scraper.scrape_url(url)
        for r in results:
            assert r.raw_question_text
            assert len(r.raw_question_text) > 5

    def test_multiple_choice_has_options(self, scraper, fixture_data):
        url = "https://isaacphysics.org/api/pages/questions?tags=electricity"
        with patch("src.scraper.isaac_physics.get_json", return_value=fixture_data):
            results = scraper.scrape_url(url)
        mc_results = [r for r in results if r.raw_options]
        assert len(mc_results) >= 2

    def test_source_name_is_isaac_physics(self, scraper, fixture_data):
        url = "https://isaacphysics.org/api/pages/questions?tags=electricity"
        with patch("src.scraper.isaac_physics.get_json", return_value=fixture_data):
            results = scraper.scrape_url(url)
        for r in results:
            assert r.source_name == "isaac_physics"
