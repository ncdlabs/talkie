"""
Speaker filter that accepts only audio matching the enrolled user voice profile.
Rejects TTS echo and other speakers when a voice profile is calibrated.
"""

from __future__ import annotations

import logging
from typing import Any

from sdk.abstractions import SpeakerFilter

from modules.speech.calibration.voice_profile import (
    _get_encoder,
    get_similarity_threshold,
    load_embedding,
    similarity_to_user,
)

logger = logging.getLogger(__name__)

# Minimum audio length (seconds) to run verification; shorter segments are accepted to avoid false rejects
MIN_VERIFY_SEC = 0.5


class VoiceProfileSpeakerFilter(SpeakerFilter):
    """
    Accepts a segment only if its speaker embedding matches the enrolled user profile.
    When no profile is stored, accepts all (backward compatible). Does not pick up
    the app's own TTS (pipeline also skips by text match) or other people.
    """

    def __init__(
        self,
        settings_repo: Any | None = None,
        sample_rate: int = 16000,
    ) -> None:
        self._settings_repo = settings_repo
        self._sample_rate = sample_rate
        self._encoder: Any = None

    def _ensure_encoder(self) -> Any | None:
        if self._encoder is None:
            self._encoder = _get_encoder()
        return self._encoder

    def _get_user_embedding(self) -> Any | None:
        return load_embedding(self._settings_repo)

    def accept(self, transcription: str, audio_bytes: bytes | None = None) -> bool:
        user_embedding = self._get_user_embedding()
        if user_embedding is None:
            return True
        if audio_bytes is None or len(audio_bytes) < self._sample_rate * 2 * MIN_VERIFY_SEC:
            return True
        encoder = self._ensure_encoder()
        if encoder is None:
            return True
        threshold = get_similarity_threshold(self._settings_repo)
        sim = similarity_to_user(
            audio_bytes,
            self._sample_rate,
            user_embedding,
            encoder,
        )
        if sim >= threshold:
            return True
        logger.debug(
            "Speaker filter: rejected (similarity %.2f < %.2f)",
            sim,
            threshold,
        )
        return False
