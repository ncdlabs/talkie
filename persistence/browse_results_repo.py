"""
Repository for browse search result runs: temporary indexed table per search command.
Saves run to SQLite; HTML table view is generated from this data. Original search page is not shown.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable

from persistence.database import with_connection

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_run(
    conn_factory: Callable[[], object],
    query: str,
    search_url: str,
    links: list[dict],
    max_rows: int = 50,
) -> str | None:
    """
    Save a search result run to SQLite: one row per result with auto-increment # (row_num).
    Returns run_id for the URL (e.g. /browse-results?run_id=xxx), or None on failure.
    """
    run_id = str(uuid.uuid4())
    query = (query or "").strip()[:500]
    search_url = (search_url or "").strip()[:2000]
    taken = (links or [])[:max_rows]
    now = _now_iso()

    def do_save(conn) -> None:
        for i, link in enumerate(taken, start=1):
            href = (link.get("href") or "").strip()[:2000]
            title = (link.get("text") or link.get("href") or "").strip()[:500]
            desc = (link.get("description") or "").strip()[:1000]
            conn.execute(
                """
                INSERT INTO browse_search_results (run_id, row_num, query, search_url, href, title, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, i, query, search_url, href, title, desc, now),
            )

    try:
        with_connection(conn_factory, do_save, commit=True)
        return run_id
    except Exception as e:
        logger.exception("browse_results save_run failed: %s", e)
        return None


def get_run(conn_factory: Callable[[], object], run_id: str) -> dict | None:
    """
    Load a search result run by run_id. Returns dict with "query", "rows" (list of dicts
    with row_num, href, title, description). Returns None if run_id not found.
    """
    if not (run_id or "").strip():
        return None

    def do_get(conn) -> dict | None:
        cur = conn.execute(
            """
            SELECT row_num, query, search_url, href, title, description
            FROM browse_search_results
            WHERE run_id = ?
            ORDER BY row_num
            """,
            (run_id.strip(),),
        )
        rows = []
        query = ""
        for r in cur.fetchall():
            query = query or (r[1] or "")
            rows.append({
                "row_num": r[0],
                "query": r[1] or "",
                "search_url": r[2] or "",
                "href": r[3] or "",
                "title": r[4] or "",
                "description": r[5] or "",
            })
        if not rows:
            return None
        return {"query": query, "rows": rows}

    try:
        rows = with_connection(conn_factory, do_get)
        return rows if rows else None
    except Exception as e:
        logger.exception("browse_results get_run failed: %s", e)
        return None
