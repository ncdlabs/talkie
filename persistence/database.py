"""
SQLite connection and schema initialization for Talkie.

Repositories (e.g. history_repo, settings_repo, training_repo) use with_connection
to run a function inside a connection. They typically wrap the call in
try/except sqlite3.Error, log with logger.exception, and re-raise so callers
can show a user-facing message.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def with_connection(
    connector: Callable[[], sqlite3.Connection],
    fn: Callable[[sqlite3.Connection], _T],
    *,
    commit: bool = False,
) -> _T:
    """
    Obtain a connection, call fn(conn), and close in finally.
    If commit=True, commit on success and rollback on exception.
    """
    conn = connector()
    try:
        result = fn(conn)
        if commit:
            conn.commit()
        return result
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        conn.close()


_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply performance and robustness PRAGMAs. Safe to call on every connection."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run idempotent migrations for existing DBs (e.g. add new columns)."""
    cur = conn.execute("PRAGMA table_info(interactions)")
    columns = {row[1] for row in cur.fetchall()}
    if "exclude_from_profile" not in columns:
        conn.execute(
            "ALTER TABLE interactions ADD COLUMN exclude_from_profile INTEGER NOT NULL DEFAULT 0"
        )
        logger.debug("Added exclude_from_profile to interactions")
    if "weight" not in columns:
        conn.execute("ALTER TABLE interactions ADD COLUMN weight REAL")
        logger.debug("Added weight to interactions")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_interactions_weight ON interactions(weight) WHERE weight IS NOT NULL"
    )
    # Browse search results table (search page rebuilt as indexed table in SQLite)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='browse_search_results'"
    )
    if cur.fetchone() is None:
        conn.execute("""
            CREATE TABLE browse_search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                row_num INTEGER NOT NULL,
                query TEXT NOT NULL,
                search_url TEXT,
                href TEXT,
                title TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX idx_browse_search_results_run_id ON browse_search_results(run_id)"
        )
        logger.debug("Added browse_search_results table")


def init_database(db_path: str) -> None:
    """
    Create the database file if needed and apply schema.
    Idempotent; safe to call on every startup.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    schema_sql = _SCHEMA_PATH.read_text()
    with sqlite3.connect(db_path) as conn:
        _apply_pragmas(conn)
        conn.executescript(schema_sql)
        _run_migrations(conn)
    logger.info("Schema applied to %s", db_path)


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    Return a new SQLite connection. Caller must close it or use as context manager.
    Applies WAL and busy_timeout for concurrent use and lock robustness.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _apply_pragmas(conn)
    return conn
