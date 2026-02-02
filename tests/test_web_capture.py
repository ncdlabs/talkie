"""Tests for app.web_capture: WebSocketAudioCapture start/stop, put_chunk/read_chunk, set_client_sample_rate."""

from __future__ import annotations

import struct
import threading
import time

import pytest

from app.web_capture import WebSocketAudioCapture


@pytest.fixture
def capture() -> WebSocketAudioCapture:
    return WebSocketAudioCapture(chunk_size_bytes=320, sample_rate=16000)


def test_websocket_audio_capture_init() -> None:
    c = WebSocketAudioCapture(chunk_size_bytes=640, sample_rate=16000)
    assert c._chunk_size == 640
    assert c._sample_rate == 16000
    assert c._buffer_len == 0
    assert c._started is False
    assert c._sensitivity == 1.0
    assert c._client_sample_rate is None


def test_start_sets_started_and_clears_buffer(capture: WebSocketAudioCapture) -> None:
    capture._buffer.append(b"x")
    capture._buffer_len = 1
    capture.start()
    assert capture._started is True
    assert capture._buffer_len == 0
    assert len(capture._buffer) == 0


def test_stop_sets_started_false(capture: WebSocketAudioCapture) -> None:
    capture.start()
    assert capture._started is True
    capture.stop()
    assert capture._started is False


def test_put_chunk_when_not_started_ignores(capture: WebSocketAudioCapture) -> None:
    data = struct.pack("<80h", *([0] * 80))
    capture.put_chunk(data)
    assert capture._buffer_len == 0
    assert len(capture._buffer) == 0


def test_put_chunk_empty_ignores(capture: WebSocketAudioCapture) -> None:
    capture.start()
    capture.put_chunk(b"")
    assert capture._buffer_len == 0


def test_put_chunk_and_read_chunk_single_chunk(capture: WebSocketAudioCapture) -> None:
    capture.start()
    data = struct.pack("<160h", *([100] * 160))
    assert len(data) == 320
    capture.put_chunk(data)
    out = capture.read_chunk()
    assert out is not None
    assert isinstance(out, bytes)
    assert len(out) == 320
    assert out == data


def test_read_chunk_when_stopped_returns_none(capture: WebSocketAudioCapture) -> None:
    capture.start()
    capture.stop()
    out = capture.read_chunk()
    assert out is None


def test_put_chunk_multiple_small_chunks(capture: WebSocketAudioCapture) -> None:
    capture.start()
    for _ in range(4):
        capture.put_chunk(struct.pack("<80h", *([0] * 80)))
    out = capture.read_chunk()
    assert out is not None
    assert len(out) == 320
    assert isinstance(out, bytes)


def test_set_client_sample_rate() -> None:
    c = WebSocketAudioCapture(chunk_size_bytes=320, sample_rate=16000)
    assert c._client_sample_rate is None
    c.set_client_sample_rate(48000)
    assert c._client_sample_rate == 48000
    c.set_client_sample_rate(None)
    assert c._client_sample_rate is None


def test_get_sensitivity_default() -> None:
    c = WebSocketAudioCapture(chunk_size_bytes=320)
    assert c.get_sensitivity() == 1.0
    assert isinstance(c.get_sensitivity(), float)


def test_set_sensitivity_clamps(capture: WebSocketAudioCapture) -> None:
    capture.set_sensitivity(0.05)
    assert capture.get_sensitivity() == 0.1
    capture.set_sensitivity(20.0)
    assert capture.get_sensitivity() == 10.0
    capture.set_sensitivity(1.5)
    assert capture.get_sensitivity() == 1.5


def test_read_chunk_blocks_until_enough_data(capture: WebSocketAudioCapture) -> None:
    capture.start()
    result: list[bytes | None] = []

    def reader() -> None:
        result.append(capture.read_chunk())

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.1)
    capture.put_chunk(struct.pack("<160h", *([0] * 160)))
    t.join(timeout=2.0)
    assert len(result) == 1
    assert result[0] is not None
    assert len(result[0]) == 320
