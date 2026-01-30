"""
Talkie SDK: common library for app and modules.
Use for config section access, speech abstractions, module discovery, and logging.

Example:
    from sdk import get_rag_section, get_browser_section
    cfg = get_rag_section(raw_config)

    from sdk import AudioCapture, STTEngine  # abstractions
    from sdk import get_module_config_paths, discover_modules
    from sdk import get_logger
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
from sdk.config import get_browser_section, get_rag_section, get_section
from sdk.discovery import discover_modules, get_module_config_paths
from sdk.logging import get_logger

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
    "get_browser_section",
    "get_logger",
    "get_rag_section",
    "get_section",
    "discover_modules",
    "get_module_config_paths",
]
