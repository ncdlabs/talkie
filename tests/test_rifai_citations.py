"""Tests for rifai_scholar_downloader.citations: bib_entry, emit_bib, ris_entry, emit_ris, _bibtex_escape, _sanitize_key."""

from __future__ import annotations

import rifai_scholar_downloader.citations as citations


def test_bibtex_escape_empty_returns_braces() -> None:
    out = citations._bibtex_escape("")
    assert out == "{}"
    assert isinstance(out, str)


def test_bibtex_escape_plain_unchanged() -> None:
    out = citations._bibtex_escape("Hello world")
    assert out == "{Hello world}"
    assert "Hello" in out
    assert "world" in out


def test_bibtex_escape_special_chars_escaped() -> None:
    out = citations._bibtex_escape("x{y}z")
    assert "{" in out
    assert "}" in out
    assert "\\" in out
    out2 = citations._bibtex_escape("a#b")
    assert "\\" in out2
    assert "#" in out2


def test_sanitize_key_alphanumeric_kept() -> None:
    out = citations._sanitize_key("abc123")
    assert out == "abc123"
    assert isinstance(out, str)


def test_sanitize_key_unsafe_chars_removed() -> None:
    out = citations._sanitize_key("a b/c:d")
    assert " " not in out
    assert "/" not in out
    assert ":" not in out
    assert "a" in out
    assert "b" in out


def test_sanitize_key_capped_at_64() -> None:
    long_key = "a" * 100
    out = citations._sanitize_key(long_key)
    assert len(out) == 64
    assert out == "a" * 64


def test_sanitize_key_empty_returns_key() -> None:
    out = citations._sanitize_key("...")
    assert out == "key"
    assert len(out) >= 1


def test_bib_entry_format() -> None:
    bib = {"title": "My Paper", "author": "Jane Doe", "year": "2023"}
    out = citations.bib_entry(1, bib, "My Paper")
    assert "@article{" in out
    assert "}" in out
    assert "title" in out
    assert "My Paper" in out
    assert "author" in out
    assert "Jane Doe" in out
    assert "year" in out
    assert "2023" in out
    assert out.endswith("}")
    assert isinstance(out, str)


def test_bib_entry_uses_title_fallback() -> None:
    bib = {}
    out = citations.bib_entry(0, bib, "Fallback Title")
    assert "Fallback Title" in out
    assert "title" in out.lower() or "Untitled" in out or "Fallback" in out


def test_bib_entry_sanitizes_key() -> None:
    bib = {"year": "2024"}
    out = citations.bib_entry(1, bib, "T")
    assert "rifai" in out
    assert "2024" in out
    assert "@article{" in out


def test_emit_bib_empty_items_returns_empty_string() -> None:
    out = citations.emit_bib([])
    assert out == ""
    assert isinstance(out, str)


def test_emit_bib_single_item() -> None:
    items = [{"bib": {"title": "A", "author": "X"}, "title": "A"}]
    out = citations.emit_bib(items)
    assert "@article{" in out
    assert "A" in out
    assert "X" in out
    assert len(out) > 0
    assert out.count("@article") == 1


def test_emit_bib_multiple_items() -> None:
    items = [
        {"bib": {"title": "First"}, "title": "First"},
        {"bib": {"title": "Second"}, "title": "Second"},
    ]
    out = citations.emit_bib(items)
    assert out.count("@article") == 2
    assert "First" in out
    assert "Second" in out


def test_ris_entry_format() -> None:
    bib = {"title": "Paper", "author": "Author", "year": "2024"}
    out = citations.ris_entry(1, bib, "Paper")
    assert "TY  - JOUR" in out or "TY" in out
    assert "TI" in out
    assert "Paper" in out
    assert "ER  - " in out
    assert isinstance(out, str)


def test_ris_entry_empty_bib_uses_title() -> None:
    out = citations.ris_entry(1, {}, "Untitled")
    assert "Untitled" in out or "TI" in out
    assert len(out) > 0


def test_emit_ris_empty_items() -> None:
    out = citations.emit_ris([])
    assert out == ""
    assert isinstance(out, str)


def test_emit_ris_single_item() -> None:
    items = [{"bib": {"title": "R"}, "title": "R"}]
    out = citations.emit_ris(items)
    assert "TY" in out
    assert "R" in out
    assert "ER" in out
    assert len(out) > 0


def test_emit_ris_multiple_items() -> None:
    items = [
        {"bib": {"title": "One"}, "title": "One"},
        {"bib": {"title": "Two"}, "title": "Two"},
    ]
    out = citations.emit_ris(items)
    assert "One" in out
    assert "Two" in out
    assert out.count("ER  - ") == 2
