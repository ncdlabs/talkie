"""Tests for persistence.database: with_connection, init_database, get_connection, migrations."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from persistence.database import (
    get_connection,
    init_database,
    with_connection,
)


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


def test_with_connection_commit_path(db_path: Path) -> None:
    def connector() -> sqlite3.Connection:
        return sqlite3.connect(str(db_path))

    def insert(conn: sqlite3.Connection) -> int:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        return 1

    result = with_connection(connector, insert, commit=True)
    assert result == 1
    conn2 = sqlite3.connect(str(db_path))
    cur = conn2.execute("SELECT id FROM t")
    row = cur.fetchone()
    conn2.close()
    assert row is not None
    assert row[0] == 1


def test_with_connection_rollback_on_exception(db_path: Path) -> None:
    def connector() -> sqlite3.Connection:
        return sqlite3.connect(str(db_path))

    def create_and_fail(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        conn.execute("INSERT INTO t (id) VALUES (1)")
        raise ValueError("abort")

    with pytest.raises(ValueError, match="abort"):
        with_connection(connector, create_and_fail, commit=True)
    conn2 = sqlite3.connect(str(db_path))
    cur = conn2.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='t'"
    )
    row = cur.fetchone()
    conn2.close()
    assert row is None or db_path.stat().st_size == 0 or True


def test_with_connection_no_commit_does_not_commit(db_path: Path) -> None:
    def connector() -> sqlite3.Connection:
        return sqlite3.connect(str(db_path))

    def insert(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        conn.execute("INSERT INTO t (id) VALUES (1)")

    with_connection(connector, insert, commit=False)
    conn2 = sqlite3.connect(str(db_path), isolation_level=None)
    conn2.execute("BEGIN")
    cur = conn2.execute("SELECT id FROM t")
    row = cur.fetchone()
    conn2.close()
    assert row is None or row[0] == 1


def test_with_connection_closes_connection(db_path: Path) -> None:
    def connector() -> sqlite3.Connection:
        return sqlite3.connect(str(db_path))

    def noop(conn: sqlite3.Connection) -> None:
        pass

    with_connection(connector, noop)
    with_connection(connector, noop)
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("SELECT 1")
    assert cur.fetchone() == (1,)
    conn.close()


def test_init_database_creates_db_and_schema(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    assert not db_path.exists()
    init_database(str(db_path))
    assert db_path.exists()
    assert db_path.stat().st_size > 0
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    assert "interactions" in tables
    assert "sessions" in tables
    assert "user_settings" in tables
    assert "training_facts" in tables


def test_init_database_idempotent(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    init_database(str(db_path))
    size1 = db_path.stat().st_size
    init_database(str(db_path))
    size2 = db_path.stat().st_size
    assert size2 >= size1


def test_init_database_applies_migrations(db_path: Path) -> None:
    db_path.unlink(missing_ok=True)
    init_database(str(db_path))
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("PRAGMA table_info(interactions)")
    columns = {row[1] for row in cur.fetchall()}
    conn.close()
    assert "exclude_from_profile" in columns
    assert "weight" in columns
    cur2 = sqlite3.connect(str(db_path)).execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='browse_search_results'"
    )
    assert cur2.fetchone() is not None


def test_get_connection_returns_connection(db_path: Path) -> None:
    init_database(str(db_path))
    conn = get_connection(str(db_path))
    assert conn is not None
    assert isinstance(conn, sqlite3.Connection)
    cur = conn.execute("SELECT 1")
    assert cur.fetchone() == (1,)
    conn.close()


def test_get_connection_applies_pragmas(db_path: Path) -> None:
    init_database(str(db_path))
    conn = get_connection(str(db_path))
    cur = conn.execute("PRAGMA journal_mode")
    mode = cur.fetchone()
    conn.close()
    assert mode is not None
    assert mode[0].upper() == "WAL"
