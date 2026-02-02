"""Tests for modules.rag.embed: _get_available_models, resolve_embedding_model, OllamaEmbedClient."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from modules.rag.embed import (
    EMBEDDING_MODEL_FALLBACKS,
    PULL_MESSAGE,
    OllamaEmbedClient,
    resolve_embedding_model,
)


def test_embedding_model_fallbacks_non_empty() -> None:
    assert len(EMBEDDING_MODEL_FALLBACKS) >= 1
    assert all(isinstance(m, str) for m in EMBEDDING_MODEL_FALLBACKS)
    assert "nomic-embed-text" in EMBEDDING_MODEL_FALLBACKS


def test_pull_message_constant() -> None:
    assert isinstance(PULL_MESSAGE, str)
    assert "pull" in PULL_MESSAGE.lower() or "ollama" in PULL_MESSAGE.lower()


def test_resolve_embedding_model_configured_available() -> None:
    with patch("modules.rag.embed.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = {
            "models": [{"name": "nomic-embed-text:latest"}]
        }
        result = resolve_embedding_model("http://localhost:11434", "nomic-embed-text")
        assert result == "nomic-embed-text"
        assert isinstance(result, str)


def test_resolve_embedding_model_not_reachable_raises() -> None:
    with patch("modules.rag.embed.requests.get") as m:
        m.side_effect = requests.RequestException("network error")
        with pytest.raises(ValueError) as exc_info:
            resolve_embedding_model("http://localhost:11434", "nomic-embed-text")
        assert "Ollama" in str(exc_info.value) or "pull" in str(exc_info.value)


def test_resolve_embedding_model_empty_models_raises() -> None:
    with patch("modules.rag.embed.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = {"models": []}
        with pytest.raises(ValueError) as exc_info:
            resolve_embedding_model("http://localhost:11434", "nomic-embed-text")
        assert "pull" in str(exc_info.value) or "model" in str(exc_info.value).lower()


def test_resolve_embedding_model_fallback_used() -> None:
    with patch("modules.rag.embed.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = {
            "models": [{"name": "nomic-embed-text:latest"}]
        }
        result = resolve_embedding_model("http://localhost:11434", "nonexistent-model")
        assert result == "nomic-embed-text"
        assert result in EMBEDDING_MODEL_FALLBACKS


def test_ollama_embed_client_init_strips_trailing_slash() -> None:
    client = OllamaEmbedClient(
        base_url="http://x/",
        model_name="nomic-embed-text",
    )
    assert client.base_url == "http://x"
    assert client.model_name == "nomic-embed-text"
    assert client._model_resolved is None


def test_ollama_embed_client_embed_single_mocked() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
    )
    with patch.object(client, "ensure_model", return_value="nomic-embed-text"):
        with patch("modules.rag.embed.requests.post") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {"embeddings": [[0.1] * 4]}
            result = client.embed("hello")
            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], list)
            assert len(result[0]) == 4
            assert result[0][0] == 0.1


def test_ollama_embed_client_embed_list_of_inputs_mocked() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
    )
    with patch.object(client, "ensure_model", return_value="nomic-embed-text"):
        with patch("modules.rag.embed.requests.post") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {
                "embeddings": [[0.1] * 4, [0.2] * 4],
            }
            result = client.embed(["hello", "world"])
            assert isinstance(result, list)
            assert len(result) == 2
            assert len(result[0]) == 4
            assert len(result[1]) == 4
            assert result[0][0] == 0.1
            assert result[1][0] == 0.2


def test_ollama_embed_client_embed_empty_inputs_returns_empty_list() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
    )
    with patch.object(client, "ensure_model", return_value="nomic-embed-text"):
        result = client.embed([])
        assert result == []
        assert isinstance(result, list)


def test_ollama_embed_client_embed_filters_none_from_inputs() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
    )
    with patch.object(client, "ensure_model", return_value="nomic-embed-text"):
        with patch("modules.rag.embed.requests.post") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {
                "embeddings": [[0.1] * 4, [0.2] * 4],
            }
            result = client.embed(["hello", None, "world"])
            assert isinstance(result, list)
            assert len(result) == 2
            assert len(result[0]) == 4
            assert len(result[1]) == 4


def test_ollama_embed_client_embed_404_clears_model_resolved() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
    )
    client._model_resolved = "nomic-embed-text:latest"
    with patch.object(client, "ensure_model", return_value="nomic-embed-text"):
        with patch("modules.rag.embed.requests.post") as m:
            m.return_value.status_code = 404
            m.return_value.json.return_value = {}
            with pytest.raises(ValueError):
                client.embed("hello")
    assert client._model_resolved is None


def test_get_available_models_returns_set() -> None:
    import modules.rag.embed as embed_mod

    with patch("modules.rag.embed.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = {
            "models": [{"name": "nomic-embed-text:latest"}, {"name": "other:v1"}]
        }
        result = embed_mod._get_available_models("http://localhost:11434")
    assert isinstance(result, set)
    assert "nomic-embed-text" in result
    assert "other" in result


def test_get_available_models_non_200_returns_empty() -> None:
    import modules.rag.embed as embed_mod

    with patch("modules.rag.embed.requests.get") as m:
        m.return_value.status_code = 500
        result = embed_mod._get_available_models("http://localhost:11434")
    assert result == set()


def test_get_available_models_request_exception_returns_empty() -> None:
    import modules.rag.embed as embed_mod

    with patch("modules.rag.embed.requests.get") as m:
        m.side_effect = requests.RequestException("network")
        result = embed_mod._get_available_models("http://localhost:11434")
    assert result == set()


def test_ollama_embed_client_ensure_model_caches() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
    )
    with patch(
        "modules.rag.embed.resolve_embedding_model", return_value="nomic-embed-text"
    ) as resolve:
        first = client.ensure_model()
        second = client.ensure_model()
        assert first == second == "nomic-embed-text"
        resolve.assert_called_once()


def test_ollama_embed_client_embed_unexpected_shape_returns_empty() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
    )
    with patch.object(client, "ensure_model", return_value="nomic-embed-text"):
        with patch("modules.rag.embed.requests.post") as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = {"embeddings": [[0.1] * 4]}
            result = client.embed(["a", "b"])
    assert result == []


def test_ollama_embed_client_embed_request_exception_retries_then_raises() -> None:
    client = OllamaEmbedClient(
        base_url="http://test:11434",
        model_name="nomic-embed-text",
        max_retries=1,
    )
    with patch.object(client, "ensure_model", return_value="nomic-embed-text"):
        with patch("modules.rag.embed.requests.post") as m:
            m.side_effect = requests.RequestException("timeout")
            with patch("modules.rag.embed.time.sleep"):
                with pytest.raises(requests.RequestException):
                    client.embed("hello")
            assert m.call_count == 2
