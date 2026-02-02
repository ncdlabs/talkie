"""Tests for modules.speech.audio.capture: AudioCapture buffer (bytearray) and config."""

from __future__ import annotations

from modules.speech.audio.capture import AudioCapture


def test_audio_capture_buffer_is_bytearray() -> None:
    """After init, _buffer is a bytearray for efficient extend (buffer reuse)."""
    cap = AudioCapture(
        device_id=None,
        sample_rate=16000,
        chunk_duration_sec=5.0,
        sensitivity=2.5,
    )
    assert isinstance(cap._buffer, bytearray)
    assert len(cap._buffer) == 0


def test_audio_capture_stop_clears_buffer() -> None:
    """stop() clears the buffer (clear() on bytearray)."""
    cap = AudioCapture(
        device_id=None,
        sample_rate=16000,
        chunk_duration_sec=5.0,
        sensitivity=2.5,
    )
    cap._buffer.extend(b"\x00\x00" * 100)
    cap._running = True
    cap.stop()
    assert len(cap._buffer) == 0
