"""Tests for persistence.history_repo (profile-related methods)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from persistence.history_repo import (
    HistoryRepo,
    MAX_TEXT_LENGTH,
    TRUNCATED_SUFFIX,
    _row_to_interaction_record,
    _truncate_for_storage,
)

_SCHEMA = """
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    original_transcription TEXT NOT NULL,
    llm_response TEXT NOT NULL,
    corrected_response TEXT,
    exclude_from_profile INTEGER NOT NULL DEFAULT 0,
    weight REAL,
    speaker_id TEXT,
    session_id TEXT
);
"""


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def repo(db_path: Path) -> HistoryRepo:
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_SCHEMA)
    return HistoryRepo(lambda: sqlite3.connect(str(db_path)))


def _insert(
    conn: sqlite3.Connection,
    original: str,
    llm_response: str,
    corrected: str | None = None,
    exclude: int = 0,
) -> None:
    conn.execute(
        """INSERT INTO interactions (created_at, original_transcription, llm_response, corrected_response, exclude_from_profile)
           VALUES (datetime('now'), ?, ?, ?, ?)""",
        (original, llm_response, corrected, exclude),
    )
    conn.commit()


def test_get_accepted_for_profile_excludes_corrected(
    repo: HistoryRepo, db_path: Path
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        _insert(conn, "hi", "Hello there", corrected=None)
        _insert(conn, "bye", "Goodbye", corrected="See you")
    accepted = repo.get_accepted_for_profile(limit=10)
    assert len(accepted) == 1
    assert accepted[0] == ("hi", "Hello there")
    assert isinstance(accepted[0], tuple)
    assert len(accepted[0]) == 2
    assert "Hello there" in accepted[0]


def test_get_accepted_respects_exclude(repo: HistoryRepo, db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        _insert(conn, "a", "A", exclude=0)
        _insert(conn, "b", "B", exclude=1)
    accepted = repo.get_accepted_for_profile(limit=10)
    assert len(accepted) == 1
    assert accepted[0][0] == "a"
    assert accepted[0][1] == "A"
    assert ("b", "B") not in accepted


def test_update_exclude_from_profile(repo: HistoryRepo, db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        _insert(conn, "x", "X", exclude=0)
        cur = conn.execute("SELECT id FROM interactions LIMIT 1")
        row = cur.fetchone()
    assert row is not None
    uid = row[0]
    assert isinstance(uid, int)
    repo.update_exclude_from_profile(uid, exclude=True)
    accepted = repo.get_accepted_for_profile(limit=10)
    assert len(accepted) == 0
    corrections = repo.get_corrections_for_profile(limit=10)
    assert ("X", "X") not in [(c[0], c[1]) for c in corrections]


def test_get_corrections_for_profile_excludes_excluded(
    repo: HistoryRepo, db_path: Path
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        _insert(conn, "o1", "r1", corrected="c1", exclude=0)
        _insert(conn, "o2", "r2", corrected="c2", exclude=1)
    corrections = repo.get_corrections_for_profile(limit=10)
    assert len(corrections) == 1
    assert corrections[0] == ("r1", "c1")
    assert ("r2", "c2") not in corrections
    assert isinstance(corrections[0], tuple)
    assert len(corrections[0]) == 2


def test_get_accepted_for_profile_empty_db(repo: HistoryRepo) -> None:
    accepted = repo.get_accepted_for_profile(limit=10)
    assert accepted == []
    assert isinstance(accepted, list)


def test_get_corrections_for_profile_empty_db(repo: HistoryRepo) -> None:
    corrections = repo.get_corrections_for_profile(limit=10)
    assert corrections == []
    assert isinstance(corrections, list)


def test_get_accepted_for_profile_respects_limit(
    repo: HistoryRepo, db_path: Path
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        for i in range(5):
            _insert(conn, f"u{i}", f"R{i}", corrected=None)
    accepted = repo.get_accepted_for_profile(limit=2)
    assert len(accepted) <= 2
    assert len(accepted) == 2


def test_get_corrections_for_profile_respects_limit(
    repo: HistoryRepo, db_path: Path
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        for i in range(5):
            _insert(conn, f"o{i}", f"r{i}", corrected=f"c{i}", exclude=0)
    corrections = repo.get_corrections_for_profile(limit=2)
    assert len(corrections) <= 2
    assert len(corrections) == 2


def test_insert_interaction_returns_positive_id(repo: HistoryRepo) -> None:
    uid = repo.insert_interaction("hello", "Hi there")
    assert uid > 0
    assert isinstance(uid, int)


def test_list_recent_order_newest_first(repo: HistoryRepo, db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        _insert(conn, "first", "R1", corrected=None)
        _insert(conn, "second", "R2", corrected=None)
    recent = repo.list_recent(limit=10)
    assert len(recent) >= 2
    transcriptions = [r["original_transcription"] for r in recent[:2]]
    assert "first" in transcriptions
    assert "second" in transcriptions
    assert recent[0]["original_transcription"] in ("first", "second")
    assert recent[1]["original_transcription"] in ("first", "second")
    assert recent[0]["llm_response"] in ("R1", "R2")
    assert recent[1]["llm_response"] in ("R1", "R2")


def test_list_recent_legacy_schema_7_columns(db_path: Path) -> None:
    """list_recent with legacy schema (no exclude_from_profile, no weight) uses 7-column SELECT."""
    legacy_schema = """
    CREATE TABLE interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        original_transcription TEXT NOT NULL,
        llm_response TEXT NOT NULL,
        corrected_response TEXT,
        speaker_id TEXT,
        session_id TEXT
    );
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(legacy_schema)
        conn.execute(
            """INSERT INTO interactions (created_at, original_transcription, llm_response, corrected_response, speaker_id, session_id)
               VALUES (datetime('now'), ?, ?, ?, ?, ?)""",
            ("legacy_orig", "legacy_resp", None, None, None),
        )
        conn.commit()
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    recent = repo.list_recent(limit=10)
    assert len(recent) >= 1
    assert recent[0]["original_transcription"] == "legacy_orig"
    assert recent[0]["llm_response"] == "legacy_resp"
    assert recent[0]["exclude_from_profile"] == 0
    assert recent[0]["weight"] is None


# ---- list_for_curation ----
def test_list_for_curation_returns_records_oldest_first(
    repo: HistoryRepo, db_path: Path
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        _insert(conn, "a", "A", corrected=None)
        _insert(conn, "b", "B", corrected=None)
        _insert(conn, "c", "C", corrected=None)
    rows = repo.list_for_curation(limit=10)
    assert len(rows) >= 3
    assert rows[0]["original_transcription"] == "a"
    assert rows[1]["original_transcription"] == "b"
    assert rows[2]["original_transcription"] == "c"
    assert rows[0]["llm_response"] == "A"
    assert rows[0]["id"] is not None
    assert "created_at" in rows[0]
    assert "corrected_response" in rows[0]
    assert "exclude_from_profile" in rows[0]


def test_list_for_curation_respects_limit(repo: HistoryRepo, db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        for i in range(5):
            _insert(conn, f"u{i}", f"R{i}", corrected=None)
    rows = repo.list_for_curation(limit=2)
    assert len(rows) == 2
    assert isinstance(rows[0], dict)
    assert "id" in rows[0] and "original_transcription" in rows[0]


def test_list_for_curation_empty_db(repo: HistoryRepo) -> None:
    rows = repo.list_for_curation(limit=100)
    assert rows == []
    assert isinstance(rows, list)


# ---- _row_to_interaction_record ----
def test_row_to_interaction_record_9_columns() -> None:
    r = (1, "2020-01-01", "orig", "resp", "corr", 0, 1.5, "sid", "sess")
    rec = _row_to_interaction_record(r)
    assert rec["id"] == 1
    assert rec["created_at"] == "2020-01-01"
    assert rec["original_transcription"] == "orig"
    assert rec["llm_response"] == "resp"
    assert rec["corrected_response"] == "corr"
    assert rec["exclude_from_profile"] == 0
    assert rec["weight"] == 1.5
    assert rec["speaker_id"] == "sid"
    assert rec["session_id"] == "sess"
    assert len(rec) == 9


def test_row_to_interaction_record_8_columns() -> None:
    r = (2, "2020-01-02", "o", "r", "c", 1, "sid", "sess")
    rec = _row_to_interaction_record(r)
    assert rec["id"] == 2
    assert rec["weight"] is None
    assert rec["speaker_id"] == "sid"
    assert rec["session_id"] == "sess"
    assert rec["exclude_from_profile"] == 1


def test_row_to_interaction_record_7_columns_legacy() -> None:
    r = (3, "2020-01-03", "o", "r", None, "sid", "sess")
    rec = _row_to_interaction_record(r)
    assert rec["id"] == 3
    assert rec["exclude_from_profile"] == 0
    assert rec["weight"] is None
    assert rec["speaker_id"] == "sid"
    assert rec["session_id"] == "sess"


# ---- _truncate_for_storage ----
def test_truncate_for_storage_under_limit_unchanged() -> None:
    short = "hello"
    out = _truncate_for_storage(short)
    assert out == short
    assert len(out) == len(short)


def test_truncate_for_storage_at_limit_unchanged() -> None:
    at_limit = "x" * MAX_TEXT_LENGTH
    out = _truncate_for_storage(at_limit)
    assert out == at_limit
    assert len(out) == MAX_TEXT_LENGTH


def test_truncate_for_storage_over_limit_truncated() -> None:
    long_text = "a" * (MAX_TEXT_LENGTH + 1000)
    out = _truncate_for_storage(long_text)
    assert len(out) == MAX_TEXT_LENGTH
    assert out.endswith(TRUNCATED_SUFFIX)
    assert len(out) <= MAX_TEXT_LENGTH
    assert TRUNCATED_SUFFIX in out


# ---- update_weight ----
def test_update_weight_sets_weight(repo: HistoryRepo, db_path: Path) -> None:
    uid = repo.insert_interaction("hello", "Hi there.")
    assert uid > 0
    repo.update_weight(uid, 2.5)
    rows = repo.list_for_curation(limit=10)
    assert len(rows) >= 1
    found = next((r for r in rows if r["id"] == uid), None)
    assert found is not None
    assert found["weight"] == 2.5
    assert isinstance(found["weight"], float)


def test_update_weight_none_clears_weight(repo: HistoryRepo, db_path: Path) -> None:
    uid = repo.insert_interaction("x", "Y")
    repo.update_weight(uid, 1.0)
    repo.update_weight(uid, None)
    rows = repo.list_for_curation(limit=10)
    found = next((r for r in rows if r["id"] == uid), None)
    assert found is not None
    assert found["weight"] is None


# ---- update_weights_batch ----
def test_update_weights_batch_empty_no_op(repo: HistoryRepo) -> None:
    repo.update_weights_batch([])
    rows = repo.list_for_curation(limit=10)
    assert isinstance(rows, list)


def test_update_weights_batch_sets_multiple(repo: HistoryRepo, db_path: Path) -> None:
    u1 = repo.insert_interaction("a", "A")
    u2 = repo.insert_interaction("b", "B")
    repo.update_weights_batch([(u1, 1.5), (u2, 3.0)])
    rows = repo.list_for_curation(limit=10)
    by_id = {r["id"]: r["weight"] for r in rows}
    assert by_id.get(u1) == 1.5
    assert by_id.get(u2) == 3.0
    assert len(by_id) >= 2


# ---- set_exclude_batch ----
def test_set_exclude_batch_empty_no_op(repo: HistoryRepo) -> None:
    repo.set_exclude_batch([], exclude=True)
    repo.set_exclude_batch([], exclude=False)


def test_set_exclude_batch_excludes_ids(repo: HistoryRepo, db_path: Path) -> None:
    u1 = repo.insert_interaction("a", "A")
    repo.insert_interaction("b", "B")
    repo.set_exclude_batch([u1], exclude=True)
    accepted = repo.get_accepted_for_profile(limit=10)
    origs = [t[0] for t in accepted]
    assert "a" not in origs
    assert "b" in origs
    repo.set_exclude_batch([u1], exclude=False)
    accepted2 = repo.get_accepted_for_profile(limit=10)
    assert any(t[0] == "a" for t in accepted2)


# ---- list_ids_older_than ----
def test_list_ids_older_than_empty_when_none_older(
    repo: HistoryRepo, db_path: Path
) -> None:
    repo.insert_interaction("new", "New")
    from datetime import datetime, timezone, timedelta

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    ids = repo.list_ids_older_than(past)
    assert isinstance(ids, list)
    assert len(ids) == 0


def test_list_ids_older_than_returns_older_ids(
    repo: HistoryRepo, db_path: Path
) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO interactions (created_at, original_transcription, llm_response) VALUES (?, ?, ?)",
            ("2000-01-01T00:00:00+00:00", "old", "Old"),
        )
        conn.commit()
    uid = repo.insert_interaction("new", "New")
    ids = repo.list_ids_older_than("2001-01-01T00:00:00+00:00")
    assert isinstance(ids, list)
    assert len(ids) >= 1
    assert uid not in ids


# ---- delete_interactions ----
def test_delete_interactions_empty_returns_zero(repo: HistoryRepo) -> None:
    n = repo.delete_interactions([])
    assert n == 0
    assert isinstance(n, int)


def test_delete_interactions_removes_ids(repo: HistoryRepo, db_path: Path) -> None:
    u1 = repo.insert_interaction("a", "A")
    u2 = repo.insert_interaction("b", "B")
    n = repo.delete_interactions([u1])
    assert n == 1
    assert isinstance(n, int)
    recent = repo.list_recent(limit=10)
    ids = [r["id"] for r in recent]
    assert u1 not in ids
    assert u2 in ids
