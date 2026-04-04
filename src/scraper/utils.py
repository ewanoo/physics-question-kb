"""HTTP utilities shared across all scrapers."""

from __future__ import annotations

import random
import re
import time
from typing import Optional

import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36",
]


def get_html(
    url: str,
    retries: int = 3,
    timeout: int = 30,
    delay: float = 1.5,
    extra_headers: Optional[dict] = None,
) -> str:
    """GET with retries, timeout, random user-agent. Returns HTML or raises."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if extra_headers:
        headers.update(extra_headers)

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 401):
                raise  # Don't retry auth errors
            last_exc = e
        except (httpx.RequestError, httpx.TimeoutException) as e:
            last_exc = e

        if attempt < retries - 1:
            time.sleep(delay * (attempt + 1))

    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts") from last_exc


def safe_get(
    url: str,
    retries: int = 3,
    timeout: int = 30,
    delay: float = 1.5,
    extra_headers: Optional[dict] = None,
) -> Optional[str]:
    """Like get_html but returns None instead of raising."""
    try:
        return get_html(url, retries=retries, timeout=timeout, delay=delay, extra_headers=extra_headers)
    except Exception:
        return None


def get_json(
    url: str,
    retries: int = 3,
    timeout: int = 30,
    delay: float = 1.5,
    extra_headers: Optional[dict] = None,
) -> Optional[dict | list]:
    """GET JSON from a URL. Returns parsed JSON or None on failure."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, */*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 401, 404):
                return None
            last_exc = e
        except Exception as e:
            last_exc = e

        if attempt < retries - 1:
            time.sleep(delay * (attempt + 1))

    return None


def extract_text(html: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    # Remove script and style elements
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_paywall_page(html: str, min_content_words: int = 100) -> bool:
    """Detect paywall or sign-up required pages."""
    text = extract_text(html).lower()
    paywall_indicators = [
        "sign up to access",
        "create a free account",
        "subscribe to view",
        "login to continue",
        "sign in to access",
        "upgrade your plan",
        "premium content",
    ]
    if any(indicator in text for indicator in paywall_indicators):
        return True
    # Too little content
    words = text.split()
    if len(words) < min_content_words:
        return True
    return False
