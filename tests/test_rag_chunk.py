"""Tests for modules.rag.chunk: chunk_text."""

from __future__ import annotations

from modules.rag.chunk import chunk_text


def test_chunk_text_empty_returns_empty_list() -> None:
    assert chunk_text("", 100, 20) == []
    assert chunk_text("   ", 100, 20) == []
    assert isinstance(chunk_text("", 10, 2), list)
    assert len(chunk_text("", 10, 2)) == 0


def test_chunk_text_short_fits_one_chunk() -> None:
    text = "Hello world."
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world."
    assert isinstance(chunks[0], str)


def test_chunk_text_multiple_chunks_with_overlap() -> None:
    text = "a" * 50 + " " + "b" * 50
    chunks = chunk_text(text, chunk_size=30, overlap=10)
    assert len(chunks) >= 2
    assert all(isinstance(c, str) for c in chunks)
    assert all(len(c) <= 30 for c in chunks)
    concatenated = " ".join(chunks).replace(" ", "")
    assert "a" in concatenated or "b" in concatenated


def test_chunk_text_chunk_size_zero_returns_full_text() -> None:
    text = "hello"
    chunks = chunk_text(text, chunk_size=0, overlap=0)
    assert len(chunks) == 1
    assert chunks[0] == "hello"


def test_chunk_text_overlap_clamped() -> None:
    text = "x" * 100
    chunks = chunk_text(text, chunk_size=10, overlap=100)
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)


def test_chunk_text_strips_whitespace_only_chunks() -> None:
    text = "a" * 5 + " " * 10 + "b" * 5
    chunks = chunk_text(text, chunk_size=10, overlap=0)
    assert all(c.strip() for c in chunks)
    assert len(chunks) >= 1
