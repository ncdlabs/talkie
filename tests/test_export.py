"""Tests for curation.export: _row_to_instruction_json, export_for_finetuning."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

import curation.export as export_module
from curation.export import export_for_finetuning
from persistence.database import init_database
from persistence.history_repo import HistoryRepo


def test_row_to_instruction_json_prefers_corrected() -> None:
    rec = export_module._row_to_instruction_json(
        "hello",
        "Hi there.",
        "Hello, how can I help?",
        "You are helpful.",
    )
    assert rec["instruction"] == "You are helpful."
    assert rec["input"] == "hello"
    assert rec["output"] == "Hello, how can I help?"
    assert isinstance(rec, dict)
    assert len(rec) == 3


def test_row_to_instruction_json_uses_llm_when_no_corrected() -> None:
    rec = export_module._row_to_instruction_json(
        "hi",
        "Hello!",
        None,
        "Base.",
    )
    assert rec["output"] == "Hello!"
    assert rec["input"] == "hi"


def test_row_to_instruction_json_empty_output() -> None:
    rec = export_module._row_to_instruction_json("", "", None, "Base.")
    assert rec["output"] == ""
    assert rec["input"] == ""


@pytest.fixture
def db_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def out_path(tmp_path: Path) -> Path:
    return tmp_path / "export.jsonl"


def test_export_for_finetuning_empty_db(db_path: Path, out_path: Path) -> None:
    init_database(str(db_path))
    n = export_for_finetuning(str(db_path), str(out_path), limit=100)
    assert n == 0
    assert isinstance(n, int)
    assert out_path.exists()
    assert out_path.read_text().strip() == ""


def test_export_for_finetuning_with_rows(db_path: Path, out_path: Path) -> None:
    init_database(str(db_path))
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    repo.insert_interaction("hello", "Hi there.")
    uid = repo.insert_interaction("bye", "Goodbye.")
    repo.update_correction(uid, "See you.")
    n = export_for_finetuning(str(db_path), str(out_path), limit=10)
    assert n >= 1
    assert n <= 2
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == n
    for line in lines:
        rec = json.loads(line)
        assert "instruction" in rec
        assert "input" in rec
        assert "output" in rec
        assert isinstance(rec["output"], str)
        assert len(rec["output"]) > 0


def test_export_for_finetuning_respects_limit(db_path: Path, out_path: Path) -> None:
    init_database(str(db_path))
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    for i in range(5):
        repo.insert_interaction(f"u{i}", f"R{i}")
    n = export_for_finetuning(str(db_path), str(out_path), limit=2)
    assert n == 2
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 2


def test_export_for_finetuning_custom_system_instruction(
    db_path: Path, out_path: Path
) -> None:
    init_database(str(db_path))
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    repo.insert_interaction("x", "Y")
    n = export_for_finetuning(
        str(db_path),
        str(out_path),
        limit=10,
        system_instruction="Custom instruction.",
    )
    assert n >= 1
    rec = json.loads(out_path.read_text().strip().split("\n")[0])
    assert rec["instruction"] == "Custom instruction."


def test_export_for_finetuning_min_weight_filters_rows(
    db_path: Path, out_path: Path
) -> None:
    init_database(str(db_path))
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    u1 = repo.insert_interaction("low", "L")
    u2 = repo.insert_interaction("high", "H")
    repo.update_weight(u1, 0.5)
    repo.update_weight(u2, 5.0)
    n = export_for_finetuning(
        str(db_path),
        str(out_path),
        limit=10,
        min_weight=2.0,
    )
    assert n == 1
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec.get("output") == "H"
    assert rec.get("input") == "high"
    assert "instruction" in rec


def test_export_for_finetuning_skips_empty_output_rows(
    db_path: Path, out_path: Path
) -> None:
    init_database(str(db_path))
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    repo.insert_interaction("has_response", "Yes.")
    uid_empty = repo.insert_interaction("empty_llm", "")
    repo.update_correction(uid_empty, "")
    n = export_for_finetuning(str(db_path), str(out_path), limit=10)
    assert n == 1
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec.get("input") == "has_response"
    assert rec.get("output") == "Yes."


def test_export_for_finetuning_creates_parent_directory(
    db_path: Path, tmp_path: Path
) -> None:
    init_database(str(db_path))
    repo = HistoryRepo(lambda: sqlite3.connect(str(db_path)))
    repo.insert_interaction("x", "Y")
    nested = tmp_path / "sub" / "dir" / "export.jsonl"
    assert not nested.parent.exists()
    n = export_for_finetuning(str(db_path), str(nested), limit=10)
    assert n >= 1
    assert nested.parent.exists()
    assert nested.exists()
    lines = nested.read_text().strip().split("\n")
    assert len(lines) >= 1
