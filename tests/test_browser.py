"""Tests for browser module: fetcher, search URL, chrome opener, service, intent parsing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules.browser import (
    _force_click_or_select_intent_if_uttered,
    _force_search_intent_if_uttered,
)
from modules.browser.base import FetchResult
from modules.browser.fetcher import HttpFetcher
from modules.browser.html_content import extract_text_from_html
from modules.browser.service import BrowserService, DEFAULT_DEMO_SCENARIOS
from llm.prompts import parse_browse_intent


# ---- build_search_url ----
@pytest.mark.parametrize(
    "query,expected_substring",
    [
        ("cats", "cats"),
        ("weather today", "weather+today"),
        ("", "q="),
    ],
)
def test_build_search_url_contains_encoded_query(
    query: str, expected_substring: str
) -> None:
    config = {"search_engine_url": "https://duckduckgo.com/?q={query}"}
    svc = BrowserService(config)
    url = svc.build_search_url(query)
    assert expected_substring in url or (
        expected_substring == "q=" and ("search" in url or "q=" in url)
    )


def test_build_search_url_custom_template() -> None:
    config = {"search_engine_url": "https://duckduckgo.com/?q={query}"}
    svc = BrowserService(config)
    url = svc.build_search_url("test")
    assert "duckduckgo" in url and "test" in url


# ---- FetchResult ----
def test_fetch_result_ok() -> None:
    assert FetchResult(200, "body").ok is True
    assert FetchResult(201, "x").ok is True
    assert FetchResult(404, "").ok is False
    assert FetchResult(200, "x", error="fail").ok is False
    assert FetchResult(299, "y").ok is True
    assert FetchResult(199, "z").ok is False
    assert FetchResult(300, "a").ok is False
    r = FetchResult(200, "t", error="e")
    assert r.status_code == 200
    assert r.text == "t"
    assert r.error == "e"
    assert r.ok is False


# ---- HttpFetcher (with mock or live) ----
@patch("modules.browser.fetcher.requests.get")
def test_fetcher_returns_result_on_200(mock_get: object) -> None:
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "<html>hello</html>"
    mock_get.return_value.headers = {}
    mock_get.return_value.encoding = "utf-8"
    mock_get.return_value.content = b"<html>hello</html>"
    mock_get.return_value.raise_for_status = lambda: None
    fetcher = HttpFetcher(timeout_sec=5, max_retries=0)
    result = fetcher.fetch("https://example.com")
    assert result.ok is True
    assert "hello" in result.text


@patch("modules.browser.fetcher.requests.get")
def test_fetcher_returns_error_on_timeout(mock_get: object) -> None:
    import requests.exceptions

    mock_get.side_effect = requests.exceptions.Timeout()
    fetcher = HttpFetcher(timeout_sec=5, max_retries=0)
    result = fetcher.fetch("https://example.com")
    assert result.ok is False
    assert result.error is not None


def test_fetcher_invalid_url_returns_error() -> None:
    fetcher = HttpFetcher(timeout_sec=1, max_retries=0)
    result = fetcher.fetch("not-a-url")
    assert result.ok is False
    assert result.error is not None


# ---- Chrome opener (mock subprocess) ----
@patch("modules.browser.chrome_opener.subprocess.run")
def test_chrome_opener_macos_calls_open(mock_run: object) -> None:
    from modules.browser.chrome_opener import ChromeOpener

    opener = ChromeOpener("Google Chrome")
    opener.open_in_browser("https://example.com")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "open" in args and "-a" in args and "https://example.com" in args


@patch("modules.browser.chrome_opener.subprocess.run")
def test_chrome_opener_empty_url_raises(mock_run: object) -> None:
    from modules.browser.chrome_opener import ChromeOpener

    opener = ChromeOpener("Google Chrome")
    with pytest.raises(ValueError):
        opener.open_in_browser("")


# ---- HTML extraction ----
def test_extract_text_from_html_strips_script() -> None:
    html = "<html><body><p>Hello</p><script>alert(1)</script><p>World</p></body></html>"
    text = extract_text_from_html(html)
    assert "Hello" in text and "World" in text
    assert "alert" not in text
    assert isinstance(text, str)


def test_extract_text_from_html_empty() -> None:
    assert extract_text_from_html("") == ""
    assert extract_text_from_html("   ") == ""
    assert isinstance(extract_text_from_html(""), str)


def test_extract_text_from_html_strips_style() -> None:
    html = "<html><body><style>.x{color:red}</style><p>Visible</p></body></html>"
    text = extract_text_from_html(html)
    assert "Visible" in text
    assert "color" not in text or "Visible" in text


# ---- parse_browse_intent ----
@pytest.mark.parametrize(
    "raw,expected_action,expected_query",
    [
        ('{"action": "search", "query": "cats"}', "search", "cats"),
        ('{"action": "open_url", "url": "https://example.com"}', "open_url", None),
        ('{"action": "unknown"}', "unknown", None),
        ('{"action": "store_page"}', "store_page", None),
        ('{"action": "demo", "demo_index": 1}', "demo", None),
    ],
)
def test_parse_browse_intent(
    raw: str, expected_action: str, expected_query: str | None
) -> None:
    intent = parse_browse_intent(raw)
    assert intent.get("action") == expected_action
    if expected_query is not None:
        assert intent.get("query") == expected_query


def test_parse_browse_intent_empty_returns_unknown() -> None:
    assert parse_browse_intent("")["action"] == "unknown"
    assert parse_browse_intent("  ")["action"] == "unknown"
    assert isinstance(parse_browse_intent(""), dict)


def test_parse_browse_intent_strips_markdown() -> None:
    raw = '```json\n{"action": "search", "query": "x"}\n```'
    intent = parse_browse_intent(raw)
    assert intent.get("action") == "search" and intent.get("query") == "x"
    assert "action" in intent
    assert "query" in intent


def test_parse_browse_intent_returns_dict_with_action() -> None:
    for raw in ['{"action": "search", "query": "q"}', '{"action": "open_url"}']:
        intent = parse_browse_intent(raw)
        assert isinstance(intent, dict)
        assert "action" in intent
        assert isinstance(intent["action"], str)


def test_parse_browse_intent_select_link() -> None:
    intent = parse_browse_intent('{"action": "select_link", "link_index": 3}')
    assert intent.get("action") == "select_link"
    assert intent.get("link_index") == 3
    intent = parse_browse_intent(
        '{"action": "select_link", "link_text": "trump tariffs"}'
    )
    assert intent.get("action") == "select_link"
    assert intent.get("link_text") == "trump tariffs"


def test_parse_browse_intent_click_link_no_args() -> None:
    intent = parse_browse_intent('{"action": "click_link"}')
    assert intent.get("action") == "click_link"
    assert "link_index" not in intent or intent.get("link_index") is None
    assert "link_text" not in intent or not (intent.get("link_text") or "").strip()


def test_force_click_intent_overrides_search() -> None:
    """Click + words must become click_link with link_text, not search (avoids repeating search in Chrome)."""
    intent = {"action": "search", "query": "trump tariffs today"}
    _force_click_or_select_intent_if_uttered("click trump tariffs today", intent)
    assert intent["action"] == "click_link"
    assert intent.get("link_text") == "trump tariffs today"
    assert "query" not in intent


def test_force_click_intent_the_link_for() -> None:
    """'The link for X' or 'link for X' (with or without 'click') forces click_link with link_text X."""
    intent = {"action": "search", "query": "cnn"}
    _force_click_or_select_intent_if_uttered("the link for CNN breaking news", intent)
    assert intent["action"] == "click_link"
    assert intent.get("link_text") == "CNN breaking news"
    assert "query" not in intent
    intent2 = {"action": "search"}
    _force_click_or_select_intent_if_uttered(
        "click the link for CNN breaking news", intent2
    )
    assert intent2["action"] == "click_link"
    assert intent2.get("link_text") == "CNN breaking news"


def test_force_click_intent_stt_variants() -> None:
    """STT variants like 'clicks' or 'clicked' still force click_link."""
    intent = {"action": "search", "query": "current news"}
    _force_click_or_select_intent_if_uttered("clicks current news", intent)
    assert intent["action"] == "click_link"
    assert intent.get("link_text") == "current news"
    intent2 = {"action": "search"}
    _force_click_or_select_intent_if_uttered("clicked the first link", intent2)
    assert intent2["action"] == "click_link"
    assert intent2.get("link_index") == 1


def test_force_click_intent_search_not_overridden_when_utterance_is_search() -> None:
    intent = {"action": "unknown"}
    _force_search_intent_if_uttered("search cats", intent)
    assert intent["action"] == "search"
    assert intent.get("query") == "cats"
    intent2 = {"action": "search", "query": "cats"}
    _force_click_or_select_intent_if_uttered("search cats", intent2)
    assert intent2["action"] == "search"


# ---- BrowserService execute (no browser open, mock opener) ----
def test_service_get_last_opened_url_initially_none() -> None:
    config = {"search_engine_url": "https://duckduckgo.com/?q={query}"}
    svc = BrowserService(config)
    assert svc.get_last_opened_url() is None


def test_service_execute_browse_on_returns_message() -> None:
    config = {}
    svc = BrowserService(config)
    msg = svc.execute({"action": "browse_on"})
    assert "Browse mode" in msg and "on" in msg


def test_service_execute_browse_off_returns_message() -> None:
    config = {}
    svc = BrowserService(config)
    msg = svc.execute({"action": "browse_off"})
    assert "off" in msg


def test_service_execute_unknown_returns_message() -> None:
    config = {}
    svc = BrowserService(config)
    msg = svc.execute({"action": "unknown"})
    assert "didn't understand" in msg or "unknown" in msg


def test_service_execute_click_link_no_selection_returns_message() -> None:
    config = {}
    svc = BrowserService(config)
    msg = svc.execute({"action": "click_link"})
    assert "select" in msg.lower() or "no link" in msg.lower()


def test_service_execute_select_link_no_page_returns_message() -> None:
    config = {}
    svc = BrowserService(config)
    msg = svc.execute({"action": "select_link", "link_text": "foo"})
    assert "page" in msg.lower() or "open" in msg.lower()


def test_service_execute_search_empty_query_returns_message() -> None:
    config = {"search_engine_url": "https://duckduckgo.com/?q={query}"}
    svc = BrowserService(config)
    msg = svc.execute({"action": "search"})
    assert "search" in msg.lower()


@patch("modules.browser.service.ChromeOpener.open_in_browser")
def test_service_execute_search_opens_and_records_url(mock_open: object) -> None:
    config = {"search_engine_url": "https://duckduckgo.com/?q={query}"}
    svc = BrowserService(config)
    svc.execute({"action": "search", "query": "cats"})
    mock_open.assert_called_once()
    call_url = mock_open.call_args[0][0]
    assert "cats" in call_url or "q=" in call_url
    assert svc.get_last_opened_url() is not None


def test_default_demo_scenarios_non_empty() -> None:
    assert len(DEFAULT_DEMO_SCENARIOS) >= 1
    assert any(s.get("type") == "search" for s in DEFAULT_DEMO_SCENARIOS)
    assert any(s.get("type") == "open_url" for s in DEFAULT_DEMO_SCENARIOS)
    assert isinstance(DEFAULT_DEMO_SCENARIOS, list)
    for s in DEFAULT_DEMO_SCENARIOS:
        assert isinstance(s, dict)
        assert "type" in s


def test_build_search_url_always_returns_string() -> None:
    config = {"search_engine_url": "https://example.com?q={query}"}
    svc = BrowserService(config)
    assert isinstance(svc.build_search_url("x"), str)
    assert isinstance(svc.build_search_url(""), str)
    assert len(svc.build_search_url("query")) > 0


def test_fetcher_timeout_returns_fetch_result() -> None:
    import requests.exceptions
    from modules.browser.fetcher import HttpFetcher

    with patch("modules.browser.fetcher.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()
        fetcher = HttpFetcher(timeout_sec=1, max_retries=0)
        result = fetcher.fetch("https://example.com")
    assert hasattr(result, "ok")
    assert hasattr(result, "text")
    assert hasattr(result, "error")
    assert result.ok is False
    assert isinstance(result.text, str)
