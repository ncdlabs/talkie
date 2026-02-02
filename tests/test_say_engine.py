"""Tests for modules.speech.tts.say_engine: SayEngine speak_timeout_sec."""

from __future__ import annotations

from modules.speech.tts.say_engine import SayEngine


def test_say_engine_init_default_timeout() -> None:
    engine = SayEngine(voice=None)
    assert engine._speak_timeout_sec == 300.0


def test_say_engine_init_custom_timeout() -> None:
    engine = SayEngine(voice="Daniel", speak_timeout_sec=60.0)
    assert engine._speak_timeout_sec == 60.0


def test_say_engine_init_timeout_clamped_min() -> None:
    engine = SayEngine(voice=None, speak_timeout_sec=0.5)
    assert engine._speak_timeout_sec == 1.0


def test_say_engine_init_timeout_clamped_max() -> None:
    engine = SayEngine(voice=None, speak_timeout_sec=5000.0)
    assert engine._speak_timeout_sec == 3600.0
