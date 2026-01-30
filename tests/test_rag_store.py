"""Tests for RAG store: add_text (store page for RAG), list_indexed_sources, remove."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from modules.rag.store import RAGStore


class MockEmbedClient:
    """Returns fixed-dimension fake embeddings for testing."""

    def __init__(self, dim: int = 4) -> None:
        self._dim = dim

    def embed(self, documents: str | list[str]) -> list[list[float]]:
        if isinstance(documents, str):
            documents = [documents]
        return [
            [0.1 * (i + j) for j in range(self._dim)] for i in range(len(documents))
        ]


@pytest.fixture
def temp_db_path() -> Path:
    d = tempfile.mkdtemp()
    yield Path(d)
    import shutil

    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def store(temp_db_path: Path) -> RAGStore:
    return RAGStore(
        vector_db_path=str(temp_db_path),
        embed_client=MockEmbedClient(),
        chunk_size=100,
        chunk_overlap=20,
    )


def test_add_text_chunks_and_stores(store: RAGStore) -> None:
    source = "https___example_com"
    text = "Some long enough article text. " * 30
    store.add_text(source, text)
    sources = store.list_indexed_sources()
    assert source in sources
    assert store.count() >= 1
    assert isinstance(sources, list)
    assert len(sources) == 1
    assert isinstance(store.count(), int)


def test_add_text_replace_by_source(store: RAGStore) -> None:
    source = "web_page_1"
    store.add_text(source, "First content. " * 40)
    first_count = store.count()
    assert first_count >= 1
    store.add_text(source, "Second content. " * 40)
    sources = store.list_indexed_sources()
    assert source in sources
    assert store.count() == first_count
    assert len(sources) == 1


def test_add_text_empty_source_raises(store: RAGStore) -> None:
    with pytest.raises(ValueError):
        store.add_text("", "some text")
    with pytest.raises(ValueError):
        store.add_text("   ", "some text")


def test_add_text_empty_text_returns_without_adding(store: RAGStore) -> None:
    store.add_text("src", "")
    assert store.count() == 0
    assert (
        store.list_indexed_sources() == [] or "src" not in store.list_indexed_sources()
    )
    store.add_text("src", "   ")
    assert store.count() == 0


def test_retrieve_after_add_text(store: RAGStore) -> None:
    source = "test_source"
    text = "Unique phrase to find: banana mango. " * 25
    store.add_text(source, text)
    result = store.retrieve("banana mango", top_k=2, min_query_length=1)
    assert "banana" in result or "Unique" in result
    assert "Source:" in result
    assert isinstance(result, str)
    assert source in result or "test_source" in result


def test_retrieve_short_query_returns_empty(store: RAGStore) -> None:
    store.add_text("src", "Some content here. " * 40)
    out = store.retrieve("ab", top_k=2, min_query_length=3)
    assert out == ""
    out2 = store.retrieve("", top_k=2, min_query_length=3)
    assert out2 == ""


def test_list_indexed_sources_empty(store: RAGStore) -> None:
    sources = store.list_indexed_sources()
    assert sources == []
    assert isinstance(sources, list)


def test_count_empty_store(store: RAGStore) -> None:
    assert store.count() == 0
    assert isinstance(store.count(), int)


def test_remove_from_index_after_add_text(store: RAGStore) -> None:
    source = "to_remove"
    store.add_text(source, "Content. " * 40)
    assert source in store.list_indexed_sources()
    count_before = store.count()
    assert count_before >= 1
    store.remove_from_index(source)
    assert source not in store.list_indexed_sources()
    assert store.count() == 0
    assert len(store.list_indexed_sources()) == 0


def test_retrieve_respects_min_query_length(store: RAGStore) -> None:
    store.add_text("s", "Unique content. " * 40)
    assert store.retrieve("Un", top_k=2, min_query_length=3) == ""
    assert len(store.retrieve("Unique content", top_k=2, min_query_length=3)) > 0
