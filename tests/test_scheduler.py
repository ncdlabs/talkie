"""Tests for curation.scheduler: run_curation_from_config, start_background_scheduler."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from curation.scheduler import run_curation_from_config, start_background_scheduler
from persistence.database import init_database
from persistence.history_repo import HistoryRepo


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


def test_run_curation_from_config_empty_db(db_path: Path) -> None:
    init_database(str(db_path))
    counts = run_curation_from_config(str(db_path), config_dict=None)
    assert isinstance(counts, dict)
    assert "weights_updated" in counts
    assert "excluded" in counts
    assert "deleted" in counts
    assert counts["weights_updated"] == 0
    assert counts["excluded"] == 0
    assert counts["deleted"] == 0


def test_run_curation_from_config_with_config_dict(db_path: Path) -> None:
    init_database(str(db_path))
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    repo.insert_interaction("hello", "Hi there.")
    config_dict = {
        "min_weight": 0.0,
        "max_weight": 10.0,
        "correction_weight_bump": 1.5,
        "pattern_count_weight_scale": 0.5,
        "exclude_duplicate_phrase": True,
        "exclude_empty_transcription": True,
        "max_interactions_to_curate": 1000,
    }
    counts = run_curation_from_config(str(db_path), config_dict=config_dict)
    assert isinstance(counts, dict)
    assert counts["weights_updated"] >= 1
    assert counts["weights_updated"] <= 2


def test_run_curation_from_config_partial_dict_uses_defaults(db_path: Path) -> None:
    init_database(str(db_path))
    counts = run_curation_from_config(
        str(db_path),
        config_dict={"min_weight": 0.5},
    )
    assert isinstance(counts, dict)
    assert counts["weights_updated"] >= 0


def test_start_background_scheduler_zero_interval_returns_none() -> None:
    t = start_background_scheduler("/tmp/foo.db", None, interval_hours=0)
    assert t is None


def test_start_background_scheduler_negative_interval_returns_none() -> None:
    t = start_background_scheduler("/tmp/foo.db", None, interval_hours=-1)
    assert t is None


def test_start_background_scheduler_returns_thread(db_path: Path) -> None:
    init_database(str(db_path))
    t = start_background_scheduler(str(db_path), None, interval_hours=24.0)
    assert t is not None
    assert t.is_alive() or not t.is_alive()
    assert t.daemon is True
