"""
Re-export speech abstractions from the SDK for backward compatibility.
Pipeline and run.py may keep importing from app.abstractions.
"""

from __future__ import annotations

from sdk.abstractions import (
    AudioCapture,
    MicrophoneError,
    NoOpCapture,
    NoOpSpeakerFilter,
    NoOpSTTEngine,
    NoOpTTSEngine,
    SpeakerFilter,
    STTEngine,
    TTSEngine,
)

__all__ = [
    "AudioCapture",
    "MicrophoneError",
    "NoOpCapture",
    "NoOpSpeakerFilter",
    "NoOpSTTEngine",
    "NoOpTTSEngine",
    "SpeakerFilter",
    "STTEngine",
    "TTSEngine",
]
