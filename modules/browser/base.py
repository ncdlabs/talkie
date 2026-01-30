"""
Abstract interface for browser-related operations: fetch URL, open in browser, build search URL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FetchResult:
    """Result of fetching a URL: status code, body text or error message, content-type hint."""

    status_code: int
    text: str
    content_type: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300 and self.error is None


class WebFetcher(ABC):
    """Interface for HTTP GET with timeout and retries."""

    @abstractmethod
    def fetch(self, url: str) -> FetchResult:
        """Fetch URL; return status, text (or error message), and optional content-type."""
        ...


class BrowserOpener(ABC):
    """Interface for opening a URL in the system browser (e.g. Chrome)."""

    @abstractmethod
    def open_in_browser(self, url: str) -> None:
        """Open URL in the configured browser. May raise or return; implementation reports success/failure."""
        ...


class SearchUrlBuilder(ABC):
    """Interface for building a search engine URL from a query."""

    @abstractmethod
    def build_search_url(self, query: str) -> str:
        """Return the full search URL for the given query."""
        ...
