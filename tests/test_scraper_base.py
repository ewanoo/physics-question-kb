"""Tests for scraper base and utils — all use mocking, no live HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.models import ScraperResult
from src.scraper.base import BaseScraper
from src.scraper.utils import (
    USER_AGENTS,
    extract_text,
    get_html,
    get_json,
    is_paywall_page,
    safe_get,
)


# ---------------------------------------------------------------------------
# Concrete scraper for testing the abstract base
# ---------------------------------------------------------------------------

class DummyScraper(BaseScraper):
    name = "dummy"
    base_url = "https://example.com"

    def discover_urls(self, topic_slugs=None):
        return ["https://example.com/page1", "https://example.com/page2"]

    def scrape_url(self, url):
        return [
            ScraperResult(
                raw_question_text="What is gravity?",
                source_url=url,
                source_name=self.name,
            )
        ]


# ---------------------------------------------------------------------------
# BaseScraper tests
# ---------------------------------------------------------------------------

class TestBaseScraper:
    def test_instantiation(self):
        scraper = DummyScraper()
        assert scraper.name == "dummy"
        assert scraper.base_url == "https://example.com"

    def test_missing_name_raises(self):
        class BadScraper(BaseScraper):
            name = ""
            base_url = "https://example.com"
            def discover_urls(self, topic_slugs=None): return []
            def scrape_url(self, url): return []

        with pytest.raises(ValueError, match="name"):
            BadScraper()

    def test_missing_base_url_raises(self):
        class BadScraper(BaseScraper):
            name = "bad"
            base_url = ""
            def discover_urls(self, topic_slugs=None): return []
            def scrape_url(self, url): return []

        with pytest.raises(ValueError, match="base_url"):
            BadScraper()

    def test_scrape_all_collects_results(self):
        scraper = DummyScraper()
        results = scraper.scrape_all()
        assert len(results) == 2  # 2 URLs x 1 result each

    def test_scrape_all_max_urls(self):
        scraper = DummyScraper()
        results = scraper.scrape_all(max_urls=1)
        assert len(results) == 1

    def test_scrape_all_skips_failing_urls(self):
        class FaultyScraper(DummyScraper):
            def scrape_url(self, url):
                if "page2" in url:
                    raise RuntimeError("Network error")
                return super().scrape_url(url)

        scraper = FaultyScraper()
        results = scraper.scrape_all()
        assert len(results) == 1  # page2 failure is skipped

    def test_fetch_delegates_to_get_html(self):
        scraper = DummyScraper()
        with patch("src.scraper.base.get_html", return_value="<html>test</html>") as mock_get:
            result = scraper.fetch("https://example.com/test")
        mock_get.assert_called_once()
        assert result == "<html>test</html>"

    def test_safe_fetch_returns_none_on_error(self):
        scraper = DummyScraper()
        with patch("src.scraper.base.safe_get", return_value=None) as mock_get:
            result = scraper.safe_fetch("https://example.com/broken")
        assert result is None


# ---------------------------------------------------------------------------
# utils: USER_AGENTS
# ---------------------------------------------------------------------------

class TestUserAgents:
    def test_has_at_least_five(self):
        assert len(USER_AGENTS) >= 5

    def test_all_strings(self):
        for ua in USER_AGENTS:
            assert isinstance(ua, str) and len(ua) > 20


# ---------------------------------------------------------------------------
# utils: get_html
# ---------------------------------------------------------------------------

class TestGetHtml:
    def _make_response(self, status_code=200, text="<html>OK</html>"):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = text
        mock_resp.raise_for_status = MagicMock()
        if status_code >= 400:
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_resp
            )
        return mock_resp

    def test_returns_html_on_success(self):
        with patch("httpx.get", return_value=self._make_response(200, "<p>hello</p>")):
            html = get_html("https://example.com")
        assert html == "<p>hello</p>"

    def test_raises_on_403(self):
        with patch("httpx.get", return_value=self._make_response(403)):
            with pytest.raises(httpx.HTTPStatusError):
                get_html("https://example.com")

    def test_retries_on_500(self):
        responses = [
            self._make_response(500),
            self._make_response(500),
            self._make_response(200, "<html>OK</html>"),
        ]
        with patch("httpx.get", side_effect=responses):
            with patch("time.sleep"):  # Don't actually sleep in tests
                html = get_html("https://example.com", retries=3, delay=0.1)
        assert html == "<html>OK</html>"

    def test_raises_after_all_retries_fail(self):
        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            with patch("time.sleep"):
                with pytest.raises(RuntimeError, match="Failed to fetch"):
                    get_html("https://example.com", retries=2, delay=0.1)


# ---------------------------------------------------------------------------
# utils: safe_get
# ---------------------------------------------------------------------------

class TestSafeGet:
    def test_returns_html_on_success(self):
        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = "<html>OK</html>"
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            result = safe_get("https://example.com")
        assert result == "<html>OK</html>"

    def test_returns_none_on_error(self):
        with patch("httpx.get", side_effect=httpx.RequestError("error")):
            with patch("time.sleep"):
                result = safe_get("https://example.com", retries=1)
        assert result is None


# ---------------------------------------------------------------------------
# utils: extract_text
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_strips_tags(self):
        html = "<p>Hello <b>world</b>!</p>"
        assert extract_text(html) == "Hello world !"

    def test_normalises_whitespace(self):
        html = "<p>  Multiple   spaces  </p>"
        assert extract_text(html) == "Multiple spaces"

    def test_removes_script(self):
        html = "<script>alert('hi')</script><p>Content</p>"
        assert "alert" not in extract_text(html)
        assert "Content" in extract_text(html)

    def test_removes_style(self):
        html = "<style>.foo { color: red }</style><p>Text</p>"
        assert "color" not in extract_text(html)
        assert "Text" in extract_text(html)

    def test_decodes_entities(self):
        html = "<p>A &amp; B &lt;3 &gt; 1</p>"
        result = extract_text(html)
        assert "&" in result
        assert "<" in result
        assert ">" in result

    def test_empty_string(self):
        assert extract_text("") == ""


# ---------------------------------------------------------------------------
# utils: is_paywall_page
# ---------------------------------------------------------------------------

class TestIsPaywallPage:
    def test_detects_signup_text(self):
        html = "<p>Sign up to access this content and more!</p>" + " word" * 200
        assert is_paywall_page(html) is True

    def test_detects_thin_content(self):
        html = "<p>Short page.</p>"
        assert is_paywall_page(html) is True

    def test_normal_page_not_paywall(self):
        html = "<p>" + "This is normal educational content about physics. " * 15 + "</p>"
        assert is_paywall_page(html) is False


# ---------------------------------------------------------------------------
# utils: get_json
# ---------------------------------------------------------------------------

class TestGetJson:
    def test_returns_parsed_json(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"key": "value"}
        mock_resp.raise_for_status = MagicMock()
        with patch("httpx.get", return_value=mock_resp):
            result = get_json("https://api.example.com/data")
        assert result == {"key": "value"}

    def test_returns_none_on_404(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "not found", request=MagicMock(), response=MagicMock(status_code=404)
        )
        with patch("httpx.get", return_value=mock_resp):
            result = get_json("https://api.example.com/missing")
        assert result is None

    def test_returns_none_on_network_error(self):
        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            with patch("time.sleep"):
                result = get_json("https://api.example.com/data", retries=1)
        assert result is None
