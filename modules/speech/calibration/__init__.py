"""
Voice calibration: record user speech, analyze level and optional STT/LLM, suggest settings.
Includes voice profile enrollment so the app listens only to the enrolled speaker.
"""

from __future__ import annotations

from .analyzer import analyze_recording
from .constants import CALIBRATION_STEPS
from .recorder import record_seconds
from .voice_profile import (
    VOICE_ENROLLMENT_MIN_SEC,
    VOICE_PROFILE_SIMILARITY_THRESHOLD_DEFAULT,
    clear_voice_profile,
    enroll_user_voice,
    is_voice_profile_available,
    load_embedding,
)

__all__ = [
    "CALIBRATION_STEPS",
    "VOICE_ENROLLMENT_MIN_SEC",
    "VOICE_PROFILE_SIMILARITY_THRESHOLD_DEFAULT",
    "analyze_recording",
    "clear_voice_profile",
    "enroll_user_voice",
    "is_voice_profile_available",
    "load_embedding",
    "record_seconds",
]
