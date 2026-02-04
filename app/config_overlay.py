"""
Calibration overlay: apply user settings (calibration_* from settings_repo) onto config sections.
Used by pipeline for LLM prompt config and by speech module when loading; lives in app so core owns the logic.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _overlay_audio_calibration(audio_cfg: dict, settings_repo: Any) -> dict:
    """Overlay calibration_* from settings_repo onto audio config. Returns new dict."""
    out = dict(audio_cfg)
    if settings_repo is None:
        return out
    try:
        sens_s = settings_repo.get("calibration_sensitivity")
        if sens_s is not None and sens_s.strip():
            try:
                s = float(sens_s)
                out["sensitivity"] = max(0.5, min(10.0, s))
            except (TypeError, ValueError):
                logger.debug("Invalid calibration_sensitivity, using config")
        chunk_s = settings_repo.get("calibration_chunk_duration_sec")
        if chunk_s is not None and chunk_s.strip():
            try:
                c = float(chunk_s)
                out["chunk_duration_sec"] = max(4.0, min(15.0, c))
            except (TypeError, ValueError):
                logger.debug("Invalid calibration_chunk_duration_sec, using config")
    except Exception as e:
        logger.debug("Calibration overlay failed: %s", e)
    return out


def _overlay_llm_calibration(llm_cfg: dict, settings_repo: Any) -> dict:
    """Overlay calibration_min_transcription_length from settings_repo onto llm config. Returns new dict."""
    out = dict(llm_cfg)
    if settings_repo is None:
        return out
    try:
        min_len_s = settings_repo.get("calibration_min_transcription_length")
        if min_len_s is not None and min_len_s.strip():
            try:
                n = int(min_len_s)
                out["min_transcription_length"] = max(0, n)
            except (TypeError, ValueError):
                logger.debug(
                    "Invalid calibration_min_transcription_length, using config"
                )
    except Exception as e:
        logger.debug("LLM calibration overlay failed: %s", e)
    return out


def apply_calibration_overlay(audio_cfg: dict, settings_repo: Any) -> dict:
    """Overlay calibration_* from settings_repo onto audio config. Returns a new dict."""
    return _overlay_audio_calibration(audio_cfg, settings_repo)


def apply_llm_calibration_overlay(llm_cfg: dict, settings_repo: Any) -> dict:
    """Overlay calibration_min_transcription_length onto llm config. Returns a new dict."""
    return _overlay_llm_calibration(llm_cfg, settings_repo)
