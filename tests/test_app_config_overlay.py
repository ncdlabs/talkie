"""Tests for app.config_overlay: apply_calibration_overlay, apply_llm_calibration_overlay."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from app.config_overlay import (
    apply_calibration_overlay,
    apply_llm_calibration_overlay,
)


def test_apply_calibration_overlay_uses_repo_values() -> None:
    repo = MagicMock()
    repo.get = lambda k: {
        "calibration_sensitivity": "3.0",
        "calibration_chunk_duration_sec": "9.0",
    }.get(k)
    audio_cfg = {"sensitivity": 2.5, "chunk_duration_sec": 7.0}
    out = apply_calibration_overlay(audio_cfg, repo)
    assert out["sensitivity"] == 3.0
    assert out["chunk_duration_sec"] == 9.0
    assert out is not audio_cfg
    assert set(out.keys()) == set(audio_cfg.keys())


def test_apply_calibration_overlay_clamps_values() -> None:
    repo = MagicMock()
    repo.get = lambda k: {
        "calibration_sensitivity": "100",
        "calibration_chunk_duration_sec": "1.0",
    }.get(k)
    audio_cfg = {"sensitivity": 2.5, "chunk_duration_sec": 7.0}
    out = apply_calibration_overlay(audio_cfg, repo)
    assert out["sensitivity"] == 10.0
    assert out["chunk_duration_sec"] == 4.0


def test_apply_calibration_overlay_missing_keys_unchanged() -> None:
    repo = MagicMock()
    repo.get = lambda k: None
    audio_cfg = {"sensitivity": 2.5, "chunk_duration_sec": 7.0}
    out = apply_calibration_overlay(audio_cfg, repo)
    assert out["sensitivity"] == 2.5
    assert out["chunk_duration_sec"] == 7.0
    assert out == audio_cfg
    assert out is not audio_cfg


def test_apply_calibration_overlay_none_repo_returns_copy() -> None:
    audio_cfg = {"sensitivity": 2.5, "chunk_duration_sec": 7.0}
    out = apply_calibration_overlay(audio_cfg, None)
    assert out == audio_cfg
    assert out is not audio_cfg


def test_apply_calibration_overlay_whitespace_only_repo_value_unchanged() -> None:
    repo = MagicMock()
    repo.get = lambda k: "   " if k == "calibration_sensitivity" else None
    audio_cfg = {"sensitivity": 2.5, "chunk_duration_sec": 7.0}
    out = apply_calibration_overlay(audio_cfg, repo)
    assert out["sensitivity"] == 2.5
    assert out["chunk_duration_sec"] == 7.0


def test_apply_llm_calibration_overlay_uses_repo_value() -> None:
    repo = MagicMock()
    repo.get = lambda k: "5" if k == "calibration_min_transcription_length" else None
    llm_cfg = {"min_transcription_length": 3}
    out = apply_llm_calibration_overlay(llm_cfg, repo)
    assert out["min_transcription_length"] == 5
    assert out is not llm_cfg


def test_apply_llm_calibration_overlay_clamps_non_negative() -> None:
    repo = MagicMock()
    repo.get = lambda k: "-1" if k == "calibration_min_transcription_length" else None
    llm_cfg = {"min_transcription_length": 3}
    out = apply_llm_calibration_overlay(llm_cfg, repo)
    assert out["min_transcription_length"] == 0


def test_apply_llm_calibration_overlay_invalid_falls_back() -> None:
    repo = MagicMock()
    repo.get = (
        lambda k: "not_a_number"
        if k == "calibration_min_transcription_length"
        else None
    )
    llm_cfg = {"min_transcription_length": 3}
    out = apply_llm_calibration_overlay(llm_cfg, repo)
    assert out["min_transcription_length"] == 3


def test_apply_llm_calibration_overlay_none_repo_returns_copy() -> None:
    llm_cfg = {"min_transcription_length": 3}
    out = apply_llm_calibration_overlay(llm_cfg, None)
    assert out == llm_cfg
    assert out is not llm_cfg


def test_apply_llm_calibration_overlay_empty_string_unchanged() -> None:
    repo = MagicMock()
    repo.get = lambda k: "" if k == "calibration_min_transcription_length" else None
    llm_cfg = {"min_transcription_length": 4}
    out = apply_llm_calibration_overlay(llm_cfg, repo)
    assert out["min_transcription_length"] == 4


def test_create_pipeline_uses_calibration_min_transcription_length() -> None:
    """create_pipeline overlays calibration_min_transcription_length into llm_prompt_config."""
    from persistence.database import init_database
    from app.pipeline import create_pipeline
    from persistence.history_repo import HistoryRepo
    from persistence.settings_repo import SettingsRepo
    from persistence.training_repo import TrainingRepo
    from config import AppConfig

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    try:
        init_database(str(db_path))

        def conn_factory():
            return sqlite3.connect(str(db_path))

        history_repo = HistoryRepo(conn_factory)
        settings_repo = SettingsRepo(conn_factory)
        settings_repo.set_many([("calibration_min_transcription_length", "7")])
        training_repo = TrainingRepo(conn_factory)

        config = {
            "modules": {"speech": {"prompt": {"system": "S", "user_template": "U"}}},
            "audio": {"sensitivity": 2.5, "chunk_duration_sec": 7.0, "sample_rate": 16000},
            "stt": {"engine": "vosk", "vosk": {"model_path": "models/vosk-model-small-en-us-0.15"}},
            "ollama": {"base_url": "http://localhost:11434", "model_name": "mistral"},
            "profile": {},
            "tts": {"enabled": False},
            "llm": {"min_transcription_length": 3},
        }
        app_config = AppConfig(config)
        pipeline = create_pipeline(
            app_config, history_repo, settings_repo, training_repo
        )
        assert pipeline._llm_prompt_config.get("min_transcription_length") == 7
    finally:
        db_path.unlink(missing_ok=True)
