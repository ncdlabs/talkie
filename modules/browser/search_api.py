"""
Search via API: structured results only. No fetch of search engine HTML page.
Uses ddgs (DuckDuckGo metasearch) to get title, href, body; returns links for table view.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def search_via_api(
    query: str,
    max_results: int = 30,
    timeout: int = 10,
) -> list[dict[str, Any]]:
    """
    Run a text search via DDGS API. Returns list of dicts with keys:
    href, text, description (suitable for browse table and SQLite).
    Never fetches or opens the search engine HTML page.
    """
    query = (query or "").strip()
    if not query:
        return []
    try:
        from ddgs import DDGS
    except ImportError:
        logger.warning("ddgs not installed; pip install ddgs for API search")
        return []
    links: list[dict[str, Any]] = []
    try:
        ddgs = DDGS(timeout=timeout)
        for r in ddgs.text(query, max_results=max_results):
            if not isinstance(r, dict):
                continue
            href = (r.get("href") or r.get("url") or "").strip()
            title = (r.get("title") or "").strip()
            body = (r.get("body") or "").strip()
            if href:
                links.append(
                    {
                        "href": href,
                        "text": title or href,
                        "description": body,
                    }
                )
    except Exception as e:
        logger.exception("Search API failed: %s", e)
    return links
