"""Tests for run.validate_config: valid config and invalid (empty, sample_rate, sensitivity, model_name)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import run after path is set (tests run from project root)
import run as run_module  # noqa: E402


def _valid_config() -> dict:
    return {
        "audio": {"sample_rate": 16000, "chunk_duration_sec": 5.0, "sensitivity": 2.5},
        "ollama": {"model_name": "mistral", "base_url": "http://localhost:11434"},
    }


def test_validate_config_empty_raises() -> None:
    with pytest.raises(ValueError, match="Config is empty"):
        run_module.validate_config({})


def test_validate_config_invalid_sample_rate_raises() -> None:
    cfg = _valid_config()
    cfg["audio"]["sample_rate"] = "not_an_int"
    with pytest.raises(ValueError, match="sample_rate must be a positive integer"):
        run_module.validate_config(cfg)


def test_validate_config_zero_sample_rate_raises() -> None:
    cfg = _valid_config()
    cfg["audio"]["sample_rate"] = 0
    with pytest.raises(ValueError, match="sample_rate must be positive"):
        run_module.validate_config(cfg)


def test_validate_config_invalid_sensitivity_raises() -> None:
    cfg = _valid_config()
    cfg["audio"]["sensitivity"] = "high"
    with pytest.raises(ValueError, match="sensitivity must be a number"):
        run_module.validate_config(cfg)


def test_validate_config_sensitivity_out_of_range_raises() -> None:
    cfg = _valid_config()
    cfg["audio"]["sensitivity"] = 0.05
    with pytest.raises(ValueError, match="sensitivity must be between"):
        run_module.validate_config(cfg)


def test_validate_config_empty_model_name_raises() -> None:
    cfg = _valid_config()
    cfg["ollama"]["model_name"] = ""
    with pytest.raises(ValueError, match="model_name must be non-empty"):
        run_module.validate_config(cfg)


def test_validate_config_ollama_unreachable_raises() -> None:
    cfg = _valid_config()
    mock_class = MagicMock()
    mock_class.return_value.check_connection.return_value = False
    with patch("llm.client.OllamaClient", mock_class):
        with pytest.raises(ValueError, match="Ollama is not reachable"):
            run_module.validate_config(cfg)


def test_validate_config_valid_passes() -> None:
    cfg = _valid_config()
    mock_class = MagicMock()
    mock_class.return_value.check_connection.return_value = True
    mock_class.return_value.check_model_available.return_value = True
    with patch("llm.client.OllamaClient", mock_class):
        run_module.validate_config(cfg)
    mock_class.return_value.check_connection.assert_called_once()
    mock_class.return_value.check_model_available.assert_called()
