"""Tests for llm.client: OllamaClient, check_connection, check_model_available, generate, FALLBACK_MESSAGE."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from llm.client import (
    FALLBACK_MESSAGE,
    MEMORY_ERROR_MESSAGE,
    OllamaClient,
)


@pytest.fixture
def client() -> OllamaClient:
    return OllamaClient(
        base_url="http://test:11434",
        model_name="mistral",
        timeout_sec=10.0,
        max_retries=1,
    )


def test_fallback_message_constant() -> None:
    assert isinstance(FALLBACK_MESSAGE, str)
    assert "couldn't generate" in FALLBACK_MESSAGE or "try again" in FALLBACK_MESSAGE
    assert len(FALLBACK_MESSAGE) > 0


def test_memory_error_message_constant() -> None:
    assert isinstance(MEMORY_ERROR_MESSAGE, str)
    assert "memory" in MEMORY_ERROR_MESSAGE.lower()
    assert len(MEMORY_ERROR_MESSAGE) > 0


def test_ollama_client_init_strips_trailing_slash() -> None:
    c = OllamaClient(base_url="http://x/", model_name="phi")
    assert c.base_url == "http://x"
    assert c.model_name == "phi"
    assert c._resolved_model is None


def test_ollama_client_init_options_merge() -> None:
    c = OllamaClient(base_url="http://x", model_name="m", options={"temperature": 0.5})
    assert c._options.get("temperature") == 0.5
    assert "num_predict" in c._options


def test_set_debug_log_and_debug(client: OllamaClient) -> None:
    lines: list[str] = []

    def capture(msg: str) -> None:
        lines.append(msg)

    client.set_debug_log(capture)
    client._debug("hello")
    assert len(lines) == 1
    assert lines[0] == "hello"
    client._debug("world")
    assert len(lines) == 2
    assert lines[1] == "world"


def test_debug_no_callback_no_op(client: OllamaClient) -> None:
    client._debug("ignored")
    client.set_debug_log(None)
    client._debug("ignored")


def test_check_connection_200_returns_true(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.return_value.status_code = 200
        result = client.check_connection(timeout_sec=1.0)
        assert result is True
        assert m.called
        call_args = m.call_args[0]
        assert "/api/tags" in call_args[0]


def test_check_connection_non_200_returns_false(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.return_value.status_code = 404
        result = client.check_connection(timeout_sec=1.0)
        assert result is False


def test_check_connection_request_exception_returns_false(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.side_effect = requests.RequestException("network error")
        result = client.check_connection(timeout_sec=1.0)
        assert result is False


def test_check_model_available_200_with_model(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}
        result = client.check_model_available(timeout_sec=1.0)
        assert result is True


def test_check_model_available_200_without_model(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = {"models": [{"name": "phi:latest"}]}
        result = client.check_model_available(timeout_sec=1.0)
        assert result is False


def test_check_model_available_non_200_returns_false(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.return_value.status_code = 500
        result = client.check_model_available(timeout_sec=1.0)
        assert result is False


def test_get_model_for_api_resolved_cached(client: OllamaClient) -> None:
    client._resolved_model = "mistral:latest"
    with patch("llm.client.requests.get"):
        result = client._get_model_for_api()
        assert result == "mistral:latest"


def test_get_model_for_api_resolves_from_tags(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}
        result = client._get_model_for_api()
        assert result == "mistral:latest"
        assert client._resolved_model == "mistral:latest"


def test_get_model_for_api_non_200_returns_config_name(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as m:
        m.return_value.status_code = 500
        result = client._get_model_for_api()
        assert result == "mistral"


def test_get_model_for_api_request_exception_returns_config_name(
    client: OllamaClient,
) -> None:
    with patch("llm.client.requests.get") as m:
        m.side_effect = requests.RequestException()
        result = client._get_model_for_api()
        assert result == "mistral"


def test_generate_success_returns_reply(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as get_m:
        get_m.return_value.status_code = 200
        get_m.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}
        with patch("llm.client.requests.post") as post_m:
            post_m.return_value.status_code = 200
            post_m.return_value.json.return_value = {"response": "  Hello world.  "}
            post_m.return_value.raise_for_status = lambda: None
            result = client.generate("hi", system="You are helpful.")
            assert result == "Hello world."
            assert isinstance(result, str)
            payload = post_m.call_args[1]["json"]
            assert payload.get("model") == "mistral:latest"
            assert payload.get("prompt") == "hi"
            assert payload.get("system") == "You are helpful."


def test_generate_empty_response_returns_fallback(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as get_m:
        get_m.return_value.status_code = 200
        get_m.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}
        with patch("llm.client.requests.post") as post_m:
            post_m.return_value.status_code = 200
            post_m.return_value.json.return_value = {"response": ""}
            post_m.return_value.raise_for_status = lambda: None
            result = client.generate("hi")
            assert result == FALLBACK_MESSAGE


def test_generate_500_memory_error_returns_memory_message(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as get_m:
        get_m.return_value.status_code = 200
        get_m.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}
        with patch("llm.client.requests.post") as post_m:
            err = requests.HTTPError()
            err.response = type(
                "R", (), {"status_code": 500, "text": '{"error": "system memory"}'}
            )()
            post_m.side_effect = err
            result = client.generate("hi")
            assert result == MEMORY_ERROR_MESSAGE


def test_generate_500_non_memory_returns_fallback(client: OllamaClient) -> None:
    with patch("llm.client.requests.get") as get_m:
        get_m.return_value.status_code = 200
        get_m.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}
        with patch("llm.client.requests.post") as post_m:
            err = requests.HTTPError()
            err.response = type(
                "R", (), {"status_code": 500, "text": "internal error"}
            )()
            post_m.side_effect = err
            result = client.generate("hi")
            assert result == FALLBACK_MESSAGE


def test_generate_request_exception_after_retries_returns_fallback(
    client: OllamaClient,
) -> None:
    with patch("llm.client.requests.get") as get_m:
        get_m.return_value.status_code = 200
        get_m.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}
        with patch("llm.client.requests.post") as post_m:
            post_m.side_effect = requests.RequestException("timeout")
            result = client.generate("hi")
            assert result == FALLBACK_MESSAGE
            assert post_m.call_count >= 1
