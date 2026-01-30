"""
HTTP fetcher for URLs: GET with timeout, retries, and redirect following.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import requests

from modules.browser.base import FetchResult

logger = logging.getLogger(__name__)


class HttpFetcher:
    """Fetches URLs via requests with configurable timeout and retries."""

    def __init__(
        self,
        timeout_sec: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        self._timeout = max(5.0, min(120.0, float(timeout_sec)))
        self._max_retries = max(0, min(5, int(max_retries)))

    def fetch(self, url: str) -> FetchResult:
        """
        GET the URL with timeout and retries. Returns FetchResult with status_code, text (or error message).
        Follows redirects. Uses a brief backoff between retries.
        """
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return FetchResult(
                status_code=0,
                text="",
                error="Invalid URL.",
            )
        last_error: str | None = None
        last_code = 0
        for attempt in range(self._max_retries + 1):
            try:
                r = requests.get(
                    url,
                    timeout=self._timeout,
                    allow_redirects=True,
                    headers={"User-Agent": "Talkie/1.0"},
                )
                r.raise_for_status()
                ct = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
                text = r.text
                if r.encoding and r.encoding.lower() != "utf-8":
                    try:
                        text = r.content.decode("utf-8", errors="replace")
                    except Exception:
                        pass
                return FetchResult(
                    status_code=r.status_code, text=text, content_type=ct or None
                )
            except requests.exceptions.Timeout as e:
                last_error = "Request timed out."
                last_code = 0
                logger.debug(
                    "Fetch timeout for %s (attempt %d): %s", url, attempt + 1, e
                )
            except requests.exceptions.RequestException as e:
                last_error = str(e) if str(e).strip() else "Request failed."
                last_code = (
                    getattr(e.response, "status_code", 0)
                    if hasattr(e, "response") and e.response is not None
                    else 0
                )
                logger.debug(
                    "Fetch failed for %s (attempt %d): %s", url, attempt + 1, e
                )
            if attempt < self._max_retries:
                time.sleep(1.0 + attempt * 0.5)
        return FetchResult(
            status_code=last_code or 0,
            text="",
            error=last_error or "Could not load the page.",
        )
