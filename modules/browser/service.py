"""
Browser service facade: search URL, open in Chrome, record current page, run demos, store page for RAG.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from typing import Callable
from urllib.parse import parse_qs, quote_plus, urlparse, urljoin

from modules.browser.base import FetchResult
from modules.browser.chrome_opener import ChromeOpener
from modules.browser.fetcher import HttpFetcher
from modules.browser.html_content import (
    extract_h1_from_html,
    extract_links_from_html,
    extract_text_from_html,
    extract_title_from_html,
)
from modules.browser.search_api import search_via_api

logger = logging.getLogger(__name__)

# Default demo scenarios (parameterized synthetic testing)
DEFAULT_DEMO_SCENARIOS: list[dict] = [
    {"type": "search", "query": "cats"},
    {"type": "search", "query": "weather today"},
    {"type": "open_url", "url": "https://example.com"},
]


def _sanitize_source_for_rag(url: str) -> str:
    """Produce a short label for RAG source from URL (e.g. for list_indexed_sources)."""
    s = re.sub(r"[^a-zA-Z0-9._-]", "_", url)
    return (s[:100] + "..") if len(s) > 100 else s


def _query_from_search_engine_url(url: str) -> str | None:
    """
    If url is a search engine search URL (Google, DuckDuckGo, Bing, etc.),
    return the query string; otherwise return None. Used to never open
    the search engine page and instead run the search flow (API -> table).
    """
    if not (url or "").strip():
        return None
    try:
        parsed = urlparse(url.strip())
        netloc = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        qs = parse_qs(parsed.query)
        if "google." in netloc and "/search" in path:
            return (qs.get("q") or [None])[0]
        if "duckduckgo." in netloc:
            return (qs.get("q") or [None])[0]
        if "bing." in netloc and "/search" in path:
            return (qs.get("q") or [None])[0]
        if "yahoo." in netloc and "/search" in path:
            return (qs.get("p") or qs.get("q") or [None])[0]
    except Exception:
        pass
    return None


class BrowserService:
    """
    Voice-controlled browser: build search URL, open in Chrome, track last opened URL,
    run demo scenarios, and (with rag_ingest) store current page for RAG.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._fetcher = HttpFetcher(
            timeout_sec=config.get("fetch_timeout_sec", 20),
            max_retries=config.get("fetch_max_retries", 2),
        )
        self._opener = ChromeOpener(
            chrome_app_name=config.get("chrome_app_name", "Google Chrome")
        )
        self._search_template = (
            config.get("search_engine_url") or ""
        ).strip() or "https://duckduckgo.com/?q={query}"
        self._cooldown_sec = max(0.0, float(config.get("cooldown_sec", 2.0)))
        self._demo_delay_sec = max(
            1.0, float(config.get("demo_delay_between_scenarios_sec", 4.0))
        )
        self._last_opened_url: str | None = None
        self._last_action_time: float = 0.0
        self._demos: list[dict] = list(
            config.get("demo_scenarios") or DEFAULT_DEMO_SCENARIOS
        )
        # Selected link for "select" then "click" flow: dict with href, text, index
        self._selected_link: dict[str, str | int] | None = None
        # Last N pages: URL history (most recent last) and cache of title+links per URL
        self._page_history_max = max(2, int(config.get("page_history_max", 10)))
        self._page_history: list[str] = []  # URLs, most recent last
        self._page_index_cache: dict[
            str, dict
        ] = {}  # url -> {"title": str, "links": list}
        self._search_results_numbered_count = max(
            0, int(config.get("search_results_numbered_count", 10))
        )
        self._talkie_web_base = (
            (config.get("talkie_web_base_url") or "").strip()
            or "http://localhost:8765"
        ).rstrip("/")
        # Use search API (structured results only); no fetch of search engine HTML page.
        self._search_use_api = config.get("search_use_api", True)

    def _build_browse_results_url(
        self, search_url: str, query: str, links: list[dict]
    ) -> str:
        """
        Build Talkie browse-results URL with encoded links so numbers appear in the DOM.
        Always returns a URL (even when links is empty) so we only open the table view.
        Links are truncated to keep URL length safe (href max 200, text max 80).
        """
        n = max(0, self._search_results_numbered_count)
        taken = (links or [])[:n]
        payload = []
        for i, link in enumerate(taken, start=1):
            href = (link.get("href") or "").strip()[:200]
            text = (link.get("text") or link.get("href") or "").strip()[:80]
            desc = (link.get("description") or "").strip()[:150]
            payload.append({"href": href, "text": text, "description": desc, "index": i})
        data_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("ascii")
        base_url = self._talkie_web_base
        params = [
            "url=" + quote_plus(search_url),
            "q=" + quote_plus(query[:100]),
            "data=" + quote_plus(data_b64),
        ]
        return base_url + "/browse-results?" + "&".join(params)

    def _build_browse_results_url_by_run_id(self, run_id: str) -> str:
        """Build browse-results URL that serves the table from SQLite by run_id."""
        return self._talkie_web_base + "/browse-results?run_id=" + quote_plus(run_id)

    def _format_numbered_links(
        self, links: list[dict], max_title_len: int = 50
    ) -> str:
        """
        Format the first N links (by config search_results_numbered_count) as
        "1. Title1, 2. Title2, ..." for display after a search. Numbers match
        link_index so the user can say "open 3" to open the third link.
        """
        n = self._search_results_numbered_count
        if n <= 0 or not links:
            return ""
        taken = links[:n]
        parts = []
        for i, link in enumerate(taken, start=1):
            text = (link.get("text") or link.get("href") or "").strip()
            if len(text) > max_title_len:
                text = text[: max_title_len - 3].rstrip() + "..."
            if not text:
                text = "link " + str(i)
            parts.append(f"{i}. {text}")
        return " ".join(parts)

    def build_search_url(self, query: str) -> str:
        """Build search URL from template and query."""
        q = (query or "").strip()
        if not q:
            return self._search_template.replace("{query}", "")
        encoded = quote_plus(q)
        return self._search_template.replace("{query}", encoded)

    def get_last_opened_url(self) -> str | None:
        """Return the last URL we opened in the browser (for store this page)."""
        return self._last_opened_url

    def _push_page_history(self, url: str) -> None:
        """Append URL to page history (if different from current) and trim to max size."""
        url = (url or "").strip()
        if not url or (self._page_history and self._page_history[-1] == url):
            return
        self._page_history.append(url)
        if len(self._page_history) > self._page_history_max:
            removed = self._page_history.pop(0)
            self._page_index_cache.pop(removed, None)
        logger.debug(
            "BrowserService: page history has %d entries", len(self._page_history)
        )

    def _get_or_build_page_index(self, url: str) -> tuple[str, list[dict]]:
        """
        Return (title, links) for the given URL. Uses cache if present; otherwise fetches,
        extracts title and links, stores in cache (trimming to page_history_max), and returns.
        """
        url = (url or "").strip()
        if not url:
            return ("", [])
        if "://" not in url:
            url = "https://" + url
        cached = self._page_index_cache.get(url)
        if cached is not None:
            return (cached.get("title", ""), cached.get("links", []))
        try:
            result = self.fetch(url)
        except Exception as e:
            logger.exception("BrowserService: fetch failed building page index: %s", e)
            return ("", [])
        if not result.ok:
            return ("", [])
        is_html = (result.content_type or "").lower().find("html") >= 0
        if not is_html:
            self._page_index_cache[url] = {"title": "", "h1s": [], "links": []}
            self._trim_page_index_cache()
            return ("", [])
        title = extract_title_from_html(result.text)
        h1s = extract_h1_from_html(result.text)
        links = extract_links_from_html(result.text, base_url=url)
        self._page_index_cache[url] = {"title": title, "h1s": h1s, "links": links}
        self._trim_page_index_cache()
        logger.debug(
            "BrowserService: page index cached for %r (title=%r, %d h1s, %d links)",
            url,
            (title[:40] + "..." if title and len(title) > 40 else title),
            len(h1s),
            len(links),
        )
        return (title, links)

    def _trim_page_index_cache(self) -> None:
        """Keep only entries for URLs in recent history; drop the rest."""
        keep = set(self._page_history)
        for url in list(self._page_index_cache):
            if url not in keep:
                del self._page_index_cache[url]

    def get_previous_page_url(self) -> str | None:
        """Return the URL of the previous page in history (for go back), or None if not enough history."""
        if len(self._page_history) < 2:
            return None
        return self._page_history[-2]

    def _link_text_partial_match(self, user_phrase: str, link_text: str) -> bool:
        """
        True if user phrase partially matches link text: exact/substring, or all words in
        user phrase appear in link text (substring or as whole words). Enables "click weather"
        to match "Weather forecast for today".
        """
        up = (user_phrase or "").strip().lower()
        lt = (link_text or "").strip().lower()
        if not up:
            return False
        if not lt:
            return up == lt
        if up == lt or up in lt or lt in up:
            return True
        user_words = [w for w in re.split(r"\s+", up) if len(w) > 0]
        if not user_words:
            return True
        link_words = [x.lower() for x in re.split(r"[\s\-_]+", lt) if x]
        for w in user_words:
            if w in lt:
                continue
            if link_words and w in link_words:
                continue
            return False
        return True

    def _match_link(
        self,
        links: list[dict],
        intent: dict,
        use_selected: bool = False,
    ) -> dict[str, str | int] | None:
        """Match a link by intent link_index or link_text (partial sentence match), or (if use_selected) from _selected_link."""
        if use_selected and self._selected_link:
            return self._selected_link
        link_index = intent.get("link_index")
        link_text = (intent.get("link_text") or "").strip()
        if link_text:
            link_text_lower = link_text.lower()
            # Prefer exact/substring matches, then partial (all words in link text)
            exact_matches = []
            partial_matches = []
            for link in links:
                lt = (link.get("text") or "").strip()
                lt_lower = lt.lower()
                if (
                    link_text_lower == lt_lower
                    or link_text_lower in lt_lower
                    or lt_lower in link_text_lower
                ):
                    exact_matches.append(link)
                elif self._link_text_partial_match(link_text, lt):
                    partial_matches.append(link)
            if exact_matches:
                return exact_matches[0]
            if partial_matches:
                return partial_matches[0]
            return None
        if link_index is not None:
            try:
                idx = int(link_index)
                if 1 <= idx <= len(links):
                    return links[idx - 1]
            except (TypeError, ValueError):
                pass
        return None

    def _record_opened_url(self, url: str) -> None:
        """Record URL as the current page, push to history, and bump action time for cooldown."""
        url = (url or "").strip() or self._last_opened_url
        if url:
            self._push_page_history(url)
        self._last_opened_url = url
        self._last_action_time = time.monotonic()

    def _in_cooldown(self) -> bool:
        if self._cooldown_sec <= 0:
            return False
        return (time.monotonic() - self._last_action_time) < self._cooldown_sec

    def open_in_browser(self, url: str) -> str:
        """
        Open URL in Chrome and record it as current page.
        Returns a short user-facing message (success or error).
        """
        if self._in_cooldown():
            return "Please wait a moment before opening another page."
        url = (url or "").strip()
        if not url:
            return "No URL to open."
        try:
            self._opener.open_in_browser(url)
            self._record_opened_url(url)
            return "Opened in Chrome."
        except RuntimeError as e:
            return str(e)
        except Exception as e:
            logger.exception("Open in browser failed: %s", e)
            return "Could not open the browser."

    def fetch(self, url: str) -> FetchResult:
        """Fetch URL; returned for store_page flow."""
        return self._fetcher.fetch(url)

    def run_demo(self, index: int) -> str:
        """
        Run the demo scenario at the given index (0-based). Never opens the search engine
        HTML page; open_url demos open the given URL. For search demos use normal search flow.
        """
        if self._in_cooldown():
            return "Please wait a moment before running another demo."
        if index < 0 or index >= len(self._demos):
            return "No such demo."
        scenario = self._demos[index]
        t = (scenario.get("type") or "").lower()
        if t == "search":
            query = (scenario.get("query") or "").strip()
            return (
                f"Demo search: say \"search {query}\" to see results in the table "
                "(search engine page is not opened)."
            )
        if t == "open_url":
            url = (scenario.get("url") or "").strip()
            if not url:
                return "Demo URL is missing."
            msg = self.open_in_browser(url)
            if "Opened" in msg:
                return f"Opened {url} in Chrome."
            return msg
        return "Unknown demo type."

    def run_demo_by_name(self, name: str) -> str:
        """Run demo by short name if configured (e.g. 'search', 'weather'); else fall back to index 0."""
        name = (name or "").strip().lower()
        for i, sc in enumerate(self._demos):
            if (sc.get("name") or "").strip().lower() == name:
                return self.run_demo(i)
        if name in ("first", "one", "1"):
            return self.run_demo(0)
        if name in ("second", "two", "2"):
            return self.run_demo(1)
        if name in ("third", "three", "3"):
            return self.run_demo(2)
        return self.run_demo(0)

    def execute(
        self,
        intent: dict,
        rag_ingest: Callable[[str, str], None] | None = None,
        on_selection_changed: Callable[[str | None], None] | None = None,
        on_open_url: Callable[[str], None] | None = None,
        on_save_search_results: Callable[[str, str, list], str | None] | None = None,
        open_locally: bool = True,
    ) -> str | tuple[str, str | None]:
        """
        Execute a parsed browse intent (search, open_url, demo, store_page, click_link, select_link).
        Opens the system browser (e.g. Chrome) in front of the user to perform the action.
        intent has action, and optionally query, url, demo_index, link_index, link_text.
        rag_ingest(source: str, text: str) is called for store_page when available.
        on_selection_changed(display_text) is called when selected link changes (select_link sets it, click clears it).
        on_open_url(url) if provided is called with the URL to open instead of opening here (e.g. so UI can open on main thread or on client).
        open_locally: when False (e.g. server mode), click_link returns (message, url) so the client can open the URL locally.
        Returns a short TTS-friendly message, or for click_link when open_locally=False returns (message, url).
        """
        action = (intent.get("action") or "").strip().lower()
        logger.debug("BrowserService.execute: action=%r", action)
        if not action or action == "unknown":
            return "I didn't understand that browse command."

        if action == "browse_on":
            return 'Browse mode is on. Say "search", then your search term.'
        if action == "browse_off":
            return "Browse mode is off."

        if action in ("scroll_up", "scroll_down", "scroll_left", "scroll_right"):
            direction = action.replace("scroll_", "")
            return self._opener.scroll(direction)

        if action == "go_back":
            prev_url = self.get_previous_page_url()
            if not prev_url:
                return "No previous page to go back to."
            logger.debug("BrowserService: go_back to %r", prev_url)
            try:
                self._opener.open_in_browser(prev_url)
                self._last_opened_url = prev_url
                self._last_action_time = time.monotonic()
            except Exception as e:
                logger.exception("BrowserService: go_back open failed: %s", e)
                return "Could not open the previous page."
            return "Opened the previous page."

        if self._in_cooldown() and action not in (
            "store_page",
            "browse_on",
            "browse_off",
            "go_back",
        ):
            return "Please wait a moment."

        if action == "search":
            query = (intent.get("query") or "").strip()
            if not query:
                return 'Say "search", then your search term.'
            # Obtain results via API only; never fetch or display the search engine HTML page.
            links: list[dict] = []
            search_url_for_save = ""
            if self._search_use_api:
                try:
                    links = search_via_api(
                        query,
                        max_results=max(
                            self._search_results_numbered_count, 30,
                        ),
                    )
                    search_url_for_save = self.build_search_url(query)
                except Exception as e:
                    logger.debug(
                        "BrowserService: search API failed: %s", e
                    )
            if not links:
                try:
                    url = self.build_search_url(query)
                    logger.debug(
                        "BrowserService: fallback fetch query=%r url=%r",
                        query,
                        url,
                    )
                    _title, links = self._get_or_build_page_index(url)
                    search_url_for_save = url
                except Exception as e:
                    logger.debug(
                        "BrowserService: page index for search failed: %s", e
                    )
            # Build table from API/fetch results; save to SQLite; serve HTML from it. Do not show original search page.
            run_id = None
            if on_save_search_results:
                try:
                    run_id = on_save_search_results(
                        query,
                        search_url_for_save,
                        links[: self._search_results_numbered_count],
                    )
                except Exception as e:
                    logger.debug(
                        "BrowserService: save search results failed: %s", e
                    )
            if run_id:
                browse_results_url = self._build_browse_results_url_by_run_id(
                    run_id
                )
            else:
                browse_results_url = self._build_browse_results_url(
                    search_url_for_save, query, links
                )
            # No original search page to discard when using API; clear any cached fetch URL.
            if search_url_for_save:
                self._page_index_cache.pop(search_url_for_save, None)
            self._page_index_cache[browse_results_url] = {
                "title": f"Search: {query}",
                "links": links[: self._search_results_numbered_count],
            }
            self._push_page_history(browse_results_url)
            self._last_opened_url = browse_results_url
            # Only ever open the table URL (browse_results_url). Never open the search engine page.
            logger.info(
                "Browse search: opening table only (never search page): %s",
                browse_results_url[:80] + ("..." if len(browse_results_url) > 80 else ""),
            )
            if on_open_url:
                try:
                    on_open_url(browse_results_url)
                except Exception as e:
                    logger.debug("on_open_url failed: %s", e)
            # Always open the table in Chrome so the user sees our page, not the search engine.
            try:
                self._opener.open_in_new_tab(browse_results_url)
            except Exception as e:
                logger.exception(
                    "BrowserService: open browse-results failed: %s", e
                )
                return "Could not open the results page in the browser."
            n = min(len(links), self._search_results_numbered_count)
            msg = (
                f"Say 'open 1' through 'open {n}' to open a result."
                if n > 0
                else "Say open and a number to open a result."
            )
            if not open_locally and not on_open_url:
                return (msg, browse_results_url)
            return msg

        if action == "open_url":
            url = (intent.get("url") or "").strip()
            if not url:
                return "Which URL should I open?"
            if "://" not in url:
                url = "https://" + url
            # Never open search engine pages: run search flow and show table instead.
            query = _query_from_search_engine_url(url)
            if query is not None:
                logger.info(
                    "Browse: open_url is search URL, running search flow instead (query=%r)",
                    query[:60] + ("..." if len(query) > 60 else ""),
                )
                search_intent = dict(intent)
                search_intent["action"] = "search"
                search_intent["query"] = query
                return self.execute(
                    search_intent,
                    rag_ingest=rag_ingest,
                    on_selection_changed=on_selection_changed,
                    on_open_url=on_open_url,
                    on_save_search_results=on_save_search_results,
                    open_locally=open_locally,
                )
            logger.debug("BrowserService: open_url url=%r (new tab)", url)
            try:
                self._opener.open_in_new_tab(url)
                self._record_opened_url(url)
            except Exception as e:
                logger.exception("BrowserService: open_in_new_tab failed: %s", e)
                return "Could not open the URL in the browser."
            return "Opened the page in a new tab."

        if action == "demo":
            idx = intent.get("demo_index")
            if idx is not None:
                try:
                    i = int(idx)
                    return self.run_demo(i)
                except (TypeError, ValueError):
                    pass
            name = (intent.get("demo_name") or "").strip()
            if name:
                return self.run_demo_by_name(name)
            return self.run_demo(0)

        if action == "store_page":
            url = (intent.get("url") or "").strip()
            if not url:
                url = self.get_last_opened_url() or ""
            if not url or not url.strip():
                return "No page to store. Open a page first, then say store this page."
            if "://" not in url:
                url = "https://" + url
            if not rag_ingest:
                return "Storage is not available."
            logger.debug("BrowserService: store_page fetching url=%r", url)
            try:
                result = self.fetch(url)
            except Exception as e:
                logger.exception("BrowserService: fetch failed in store_page: %s", e)
                return "Could not load the page. Check the address or try again."
            if not result.ok:
                logger.debug(
                    "BrowserService: store_page fetch not ok: %s", result.error
                )
                if result.error:
                    return result.error
                return "Could not load the page. Check the address or try again."
            text = (
                extract_text_from_html(result.text)
                if (result.content_type or "").lower().find("html") >= 0
                else result.text
            )
            text = (text or "").strip()
            if len(text) < 50:
                return "The page had no text to store."
            source = _sanitize_source_for_rag(url)
            try:
                rag_ingest(source, text)
            except Exception as e:
                logger.exception("RAG ingest failed for %s: %s", url, e)
                return "Could not store the page. Try again."
            return "Stored the page. You can ask about it in Query Documents."

        if action == "select_link":
            current_url = self.get_last_opened_url() or ""
            if not current_url or not current_url.strip():
                return "No page is open. Open a page first, then select a link."
            if "://" not in current_url:
                current_url = "https://" + current_url
            logger.debug(
                "BrowserService: select_link using page index for url=%r", current_url
            )
            title, links = self._get_or_build_page_index(current_url)
            if not links:
                return "Could not load the current page or no links found. Try opening it again."
            logger.debug("BrowserService: select_link found %d links", len(links))
            if not links:
                return "No links found on this page."
            matched = self._match_link(links, intent)
            if not matched:
                link_text = (intent.get("link_text") or "").strip()
                link_index = intent.get("link_index")
                if link_text:
                    return (
                        f"Could not find a link with text '{link_text}' on this page."
                    )
                if link_index is not None:
                    return f"Link number {link_index} not found. This page has {len(links)} link(s)."
                return "Please specify which link to select by position (e.g. 'select the third link') or text (e.g. 'select trump tariffs')."
            self._selected_link = matched
            display = (matched.get("text") or matched.get("href") or "").strip()
            if len(display) > 50:
                display = display[:50] + "..."
            try:
                if on_selection_changed:
                    on_selection_changed(display)
            except Exception as e:
                logger.debug("on_selection_changed failed: %s", e)
            return "Selected: " + (display or "link")

        if action == "click_link":
            use_selected = (
                intent.get("link_index") is None
                and not (intent.get("link_text") or "").strip()
            )
            if use_selected and not self._selected_link:
                return 'No link is selected. Say "select" and then the link text or position (e.g. "select the third link"), then say "click".'
            if use_selected and self._selected_link:
                sel = self._selected_link
                href = (sel.get("href") or "").strip()
                if not href:
                    return "The selected link has no URL."
                sel_text = (sel.get("text") or href) or ""
                if len(sel_text) > 50:
                    sel_text = str(sel_text)[:50] + "..."
                self._selected_link = None
                try:
                    if on_selection_changed:
                        on_selection_changed(None)
                except Exception as e:
                    logger.debug("on_selection_changed failed: %s", e)
                if on_open_url:
                    try:
                        self._record_opened_url(href)
                        on_open_url(href)
                    except Exception as e:
                        logger.debug("on_open_url failed: %s", e)
                        return "Could not open the link."
                    return f"Clicked link: {sel_text}"
                if not open_locally:
                    return (f"Clicked link: {sel_text}", href)
                msg = self.open_in_browser(href)
                if "Opened" in msg:
                    return f"Clicked link: {sel_text}"
                return msg
            current_url = self.get_last_opened_url() or ""
            if not current_url or not current_url.strip():
                return "No page is open. Open a page first, then click a link."
            if "://" not in current_url:
                current_url = "https://" + current_url
            logger.debug(
                "BrowserService: click_link using page index for url=%r", current_url
            )
            title, links = self._get_or_build_page_index(current_url)
            if not links:
                return "Could not load the current page or no links found. Try opening it again."
            logger.debug("BrowserService: click_link found %d links", len(links))
            if not links:
                return "No links found on this page."
            matched_link = self._match_link(links, intent, use_selected=False)
            if not matched_link:
                link_text = (intent.get("link_text") or "").strip()
                link_index = intent.get("link_index")
                if link_text:
                    return (
                        f"Could not find a link with text '{link_text}' on this page."
                    )
                if link_index is not None:
                    return f"Link number {link_index} not found. This page has {len(links)} link(s)."
                return "Please specify which link to click by position (e.g. 'click the third link') or text (e.g. 'click trump tariffs')."
            href = (matched_link.get("href") or "").strip()
            if not href:
                return "The selected link has no URL."
            if "://" not in href:
                href = urljoin(current_url, href)
            self._selected_link = None
            try:
                if on_selection_changed:
                    on_selection_changed(None)
            except Exception as e:
                logger.debug("on_selection_changed failed: %s", e)
            link_display = (matched_link.get("text") or href) or ""
            if len(link_display) > 50:
                link_display = link_display[:50] + "..."
            msg_ok = f"Clicked link: {link_display}"
            if on_open_url:
                try:
                    self._record_opened_url(href)
                    on_open_url(href)
                except Exception as e:
                    logger.debug("on_open_url failed: %s", e)
                    return "Could not open the link."
                return msg_ok
            if not open_locally:
                return (msg_ok, href)
            msg = self.open_in_browser(href)
            if "Opened" in msg:
                return msg_ok
            return msg

        return "I didn't understand that browse command."
