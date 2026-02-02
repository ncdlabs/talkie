"""Tests for curation.curator: CuratorConfig, run_curation, weight updates, exclude."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from curation.curator import CuratorConfig, run_curation
from persistence.database import init_database
from persistence.history_repo import HistoryRepo


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def history_repo(db_path: Path) -> HistoryRepo:
    init_database(str(db_path))
    return HistoryRepo(lambda: sqlite3.connect(str(db_path)))


def test_curator_config_defaults() -> None:
    cfg = CuratorConfig()
    assert cfg.min_weight == 0.0
    assert cfg.max_weight == 10.0
    assert cfg.correction_weight_bump == 1.5
    assert cfg.pattern_count_weight_scale == 0.5
    assert cfg.exclude_duplicate_phrase is True
    assert cfg.exclude_empty_transcription is True
    assert cfg.delete_older_than_days is None
    assert cfg.max_interactions_to_curate == 10_000
    assert isinstance(cfg.min_weight, float)
    assert isinstance(cfg.max_weight, float)


def test_run_curation_empty_db_returns_zero_counts(
    history_repo: HistoryRepo,
) -> None:
    counts = run_curation(history_repo, config=None)
    assert isinstance(counts, dict)
    assert counts["weights_updated"] == 0
    assert counts["excluded"] == 0
    assert counts["deleted"] == 0
    assert "weights_updated" in counts
    assert "excluded" in counts
    assert "deleted" in counts


def test_run_curation_with_rows_updates_weights(
    history_repo: HistoryRepo, db_path: Path
) -> None:
    history_repo.insert_interaction("hello", "Hi there.")
    history_repo.insert_interaction("bye", "Goodbye.")
    counts = run_curation(history_repo, config=CuratorConfig())
    assert counts["weights_updated"] >= 1
    assert counts["weights_updated"] <= 2
    assert isinstance(counts["weights_updated"], int)


def test_run_curation_exclude_empty_transcription(
    history_repo: HistoryRepo, db_path: Path
) -> None:
    history_repo.insert_interaction("", "Response only.")
    counts = run_curation(
        history_repo,
        config=CuratorConfig(exclude_empty_transcription=True),
    )
    assert counts["excluded"] >= 1
    assert isinstance(counts["excluded"], int)


def test_run_curation_with_config_override() -> None:
    cfg = CuratorConfig(
        min_weight=0.5,
        max_weight=5.0,
        correction_weight_bump=2.0,
        max_interactions_to_curate=100,
    )
    assert cfg.min_weight == 0.5
    assert cfg.max_weight == 5.0
    assert cfg.correction_weight_bump == 2.0
    assert cfg.max_interactions_to_curate == 100


def test_run_curation_returns_counts_dict(history_repo: HistoryRepo) -> None:
    counts = run_curation(history_repo)
    assert isinstance(counts, dict)
    assert set(counts.keys()) == {"weights_updated", "excluded", "deleted"}
    for k in counts:
        assert isinstance(counts[k], int)
        assert counts[k] >= 0
