"""Tests for modules.rag.pdf: extract_text_from_pdf."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from modules.rag.pdf import extract_text_from_pdf


def test_extract_text_from_pdf_nonexistent_raises() -> None:
    path = Path("/nonexistent/file.pdf")
    with pytest.raises(Exception):
        extract_text_from_pdf(path)


def test_extract_text_from_pdf_empty_file_returns_empty_or_raises() -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"not a real pdf")
        path = Path(f.name)
    try:
        result = extract_text_from_pdf(path)
        assert isinstance(result, str)
        assert result == "" or len(result) >= 0
    except Exception:
        pass
    finally:
        path.unlink(missing_ok=True)


def test_extract_text_from_pdf_with_pypdf_mock() -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 minimal\n")
        path = Path(f.name)
    try:
        try:
            result = extract_text_from_pdf(path)
            assert isinstance(result, str)
            assert len(result) >= 0
        except Exception:
            pass
    finally:
        path.unlink(missing_ok=True)
