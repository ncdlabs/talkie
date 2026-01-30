"""Shared calibration constants for sensitivity, chunk duration, and UI choice lists."""

from __future__ import annotations

SENSITIVITY_MIN = 0.5
SENSITIVITY_MAX = 10.0
CHUNK_DURATION_MIN = 4.0
CHUNK_DURATION_MAX = 15.0
MIN_TRANSCRIPTION_LENGTH_MIN = 0
MIN_TRANSCRIPTION_LENGTH_MAX = 10

# Volume options: (label, sensitivity value)
VOLUME_CHOICES = [
    ("Loud", 1.0),
    ("Normal", 1.5),
    ("Quiet", 2.5),
    ("Very quiet", 3.5),
]

# Pause options: (label, chunk_duration_sec)
PAUSE_CHOICES = [
    ("No", 5.5),
    ("A little", 7.0),
    ("Yes, I pause often", 9.0),
]

# Ordered calibration steps so the app only listens to the correct speaker
CALIBRATION_STEPS = [
    {
        "id": "voice_enrollment",
        "title": "Record your voice",
        "description": "Record 5–10 seconds of your voice so the app learns to respond only to you. It will ignore other people and its own spoken responses.",
        "min_seconds": 3,
        "setting_keys": ["voice_profile_embedding"],
    },
    {
        "id": "sensitivity",
        "title": "Volume and pause",
        "description": "Adjust sensitivity and pause length so the app hears you clearly and waits for you to finish speaking.",
        "setting_keys": [
            "calibration_sensitivity",
            "calibration_chunk_duration_sec",
            "calibration_min_transcription_length",
        ],
    },
]
