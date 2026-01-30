"""
Extract main text from HTML for RAG indexing (minimal, no optional deps).
Also extract links for click navigation.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping script/style."""

    def __init__(self) -> None:
        super().__init__()
        self._skip = False
        self._bits: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self._skip = False
        if tag.lower() in ("p", "div", "br", "li", "tr"):
            self._bits.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip and data:
            self._bits.append(data)

    def get_text(self) -> str:
        raw = "".join(self._bits)
        raw = re.sub(r"\s+", " ", raw)
        return raw.strip()


def extract_text_from_html(html: str) -> str:
    """
    Extract visible text from HTML. Strips script/style, normalizes whitespace.
    Returns empty string if input is empty or not HTML-like.
    """
    if not html or not html.strip():
        return ""
    html = html.strip()
    if not html.lstrip().lower().startswith("<"):
        return html
    try:
        parser = _TextExtractor()
        parser.feed(html)
        return parser.get_text()
    except Exception:
        return ""


class _LinkExtractor(HTMLParser):
    """Extract all links (anchor tags) with their href, text, and position."""

    def __init__(self, base_url: str = "") -> None:
        super().__init__()
        self._base_url = base_url
        self._links: list[dict[str, str | int]] = []
        self._current_link: dict[str, str] | None = None
        self._current_text: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self._skip = True
            return
        if tag.lower() == "a":
            href = None
            for attr_name, attr_value in attrs:
                if attr_name.lower() == "href" and attr_value:
                    href = attr_value.strip()
                    break
            if href:
                # Resolve relative URLs
                if self._base_url:
                    href = urljoin(self._base_url, href)
                self._current_link = {
                    "href": href,
                    "text": "",
                    "index": len(self._links) + 1,
                }
                self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self._skip = False
            return
        if tag.lower() == "a" and self._current_link:
            # Join collected text and normalize
            text = " ".join(self._current_text).strip()
            text = re.sub(r"\s+", " ", text)
            self._current_link["text"] = text
            # Only add links with href (empty text is OK)
            if self._current_link["href"]:
                self._links.append(self._current_link)
            self._current_link = None
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if not self._skip and self._current_link and data:
            self._current_text.append(data)

    def get_links(self) -> list[dict[str, str | int]]:
        """Return list of links, each with href, text, and index (1-based)."""
        return self._links.copy()


def extract_title_from_html(html: str) -> str:
    """
    Extract the first <title>...</title> from HTML. Returns empty string if none.
    """
    if not html or not html.strip():
        return ""
    html = html.strip()
    if not html.lstrip().lower().startswith("<"):
        return ""
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.IGNORECASE)
    if match:
        title = re.sub(r"\s+", " ", match.group(1).strip())
        return title
    return ""


class _H1Extractor(HTMLParser):
    """Extract all <h1>...</h1> text in document order."""

    def __init__(self) -> None:
        super().__init__()
        self._h1s: list[str] = []
        self._in_h1 = False
        self._current: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self._skip = True
            return
        if tag.lower() == "h1":
            self._in_h1 = True
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("script", "style", "noscript"):
            self._skip = False
            return
        if tag.lower() == "h1" and self._in_h1:
            text = re.sub(r"\s+", " ", " ".join(self._current).strip())
            if text:
                self._h1s.append(text)
            self._in_h1 = False
            self._current = []

    def handle_data(self, data: str) -> None:
        if not self._skip and self._in_h1 and data:
            self._current.append(data)

    def get_h1s(self) -> list[str]:
        return self._h1s.copy()


def extract_h1_from_html(html: str) -> list[str]:
    """
    Extract all <h1>...</h1> text from HTML in document order.
    Returns empty list if input is empty or not HTML-like.
    """
    if not html or not html.strip():
        return []
    html = html.strip()
    if not html.lstrip().lower().startswith("<"):
        return []
    try:
        parser = _H1Extractor()
        parser.feed(html)
        return parser.get_h1s()
    except Exception:
        return []


def extract_links_from_html(
    html: str, base_url: str = ""
) -> list[dict[str, str | int]]:
    """
    Extract all links from HTML. Returns list of dicts with keys:
    - href: str - the link URL (resolved if base_url provided)
    - text: str - the visible link text
    - index: int - 1-based position in document order

    Returns empty list if input is empty or not HTML-like.
    """
    if not html or not html.strip():
        return []
    html = html.strip()
    if not html.lstrip().lower().startswith("<"):
        return []
    try:
        parser = _LinkExtractor(base_url=base_url)
        parser.feed(html)
        return parser.get_links()
    except Exception:
        return []
