# Browse search: query, table, display

This doc shows the code path for: **search** (get results), **table** (build and persist), **display** (open table URL). The search engine HTML page (e.g. Google) is never opened.

---

## 1. Search (get raw results)

**Intent:** User says "search &lt;query&gt;". Pipeline calls the browser web handler with that utterance.

**Parse intent:** `modules/browser/__init__.py` (local handler) uses LLM to get `action: "search"`, `query: "<user query>"`.

**Execute search:** `modules/browser/service.py` — `execute()` when `action == "search"`:

```python
# modules/browser/service.py  (lines ~418–451)

if action == "search":
    query = (intent.get("query") or "").strip()
    links: list[dict] = []
    search_url_for_save = ""

    # API path (default): get results from DDGS; no HTML fetch.
    if self._search_use_api:
        try:
            links = search_via_api(query, max_results=...)
            search_url_for_save = self.build_search_url(query)  # only for save metadata
        except Exception as e:
            ...

    # Fallback if API returns nothing (e.g. ddgs not installed)
    if not links:
        url = self.build_search_url(query)
        _title, links = self._get_or_build_page_index(url)  # HTTP fetch + parse HTML
        search_url_for_save = url
```

**API implementation:** `modules/browser/search_api.py` — `search_via_api(query)`:

- Calls `DDGS().text(query, max_results=...)` (ddgs package).
- Returns list of `{href, text, description}`.
- Does **not** fetch or open any search engine page.

**Config:** `browser.search_use_api` (default `true`) in `modules/browser/config.yaml` and root `config.yaml`.

---

## 2. Table (build and persist)

Still in `modules/browser/service.py` search block, after `links` is set:

```python
# modules/browser/service.py  (lines ~452–475)

run_id = None
if on_save_search_results:
    try:
        run_id = on_save_search_results(
            query,
            search_url_for_save,
            links[: self._search_results_numbered_count],
        )
    except Exception as e:
        ...

if run_id:
    browse_results_url = self._build_browse_results_url_by_run_id(run_id)
    # => e.g. http://localhost:8765/browse-results?run_id=<uuid>
else:
    browse_results_url = self._build_browse_results_url(
        search_url_for_save, query, links
    )
    # => same host + /browse-results?url=...&q=...&data=<base64>
```

**Save to SQLite:** `persistence/browse_results_repo.py` — `save_run(conn_factory, query, search_url, links)`:

- Generates a UUID `run_id`.
- Inserts one row per result into `browse_search_results` (row_num, query, href, title, description).
- Returns `run_id` for the URL.

**URL builders** (service.py):

- `_build_browse_results_url_by_run_id(run_id)` → `{talkie_web_base}/browse-results?run_id={run_id}`.
- `_build_browse_results_url(url, query, links)` → same path with `url`, `q`, `data=` (base64 JSON).

So the **only** URL we use for “open results” is the Talkie `/browse-results?...` URL, never the Google/DDG search URL.

---

## 3. Display (open table in browser)

Still in `modules/browser/service.py` search block:

```python
# modules/browser/service.py  (lines ~481–516)

if on_open_url:
    try:
        on_open_url(browse_results_url)   # <-- only URL we pass: table URL
    except Exception as e:
        ...
elif not open_locally:
    return (msg, browse_results_url)
else:
    self._opener.open_in_new_tab(browse_results_url)
```

**Pipeline callback:** `run_web.py`:

```python
# run_web.py  (line ~141)
pipeline.set_on_open_url(lambda url: broadcast({"type": "open_url", "url": url}))
```

So `on_open_url(browse_results_url)` broadcasts `{type: "open_url", url: "<table URL>"}` to all WebSocket clients.

**Client:** `web/index.html` — WebSocket `onmessage`:

```javascript
// web/index.html  (lines ~696–698)
else if (msg.type === 'open_url' && msg.url) {
  window.open(msg.url, '_blank', 'noopener,noreferrer');
}
```

So the browser opens `msg.url` in a new tab — which is always `/browse-results?run_id=...` or `/browse-results?url=...&q=...&data=...`.

**Serving the table HTML:** `run_web.py` — route `GET /browse-results`:

- If `run_id` is set: loads run from SQLite via `get_browse_run(conn_factory, run_id)`, builds HTML table, returns it.
- Else if `data=` is set: decodes base64 JSON, builds same table HTML, returns it.

So the tab that opens shows only the Talkie table page, not the search engine.

---

## Where the Google page could still appear

1. **Popup / new tab**  
   If `window.open(msg.url, '_blank')` is blocked or fails, no new tab is created; the user might still be looking at an existing tab (e.g. Google). Check the browser console for popup-blocker messages.

2. **Wrong tab in focus**  
   A new tab with the table URL may open in the background; the user might be looking at another tab that already had Google open.

3. **Log to verify**  
   On search, the server logs: `Browse search: opening table only (never search page): <url>`. Confirm that URL is `.../browse-results?run_id=...` or `.../browse-results?url=...&q=...&data=...` (same host as Talkie). If you see a Google URL there, that’s a bug.

---

## Summary

| Step   | What happens | Code |
|--------|--------------|------|
| Search | Get links via API (or fallback fetch). No opening of search page. | `service.py` search block; `search_api.search_via_api()` |
| Table  | Save links to SQLite; build `browse_results_url` (run_id or data=). | `browse_results_repo.save_run()`; `_build_browse_results_url_by_run_id` / `_build_browse_results_url` |
| Display| Call `on_open_url(browse_results_url)` → broadcast → client `window.open(msg.url)`. | `service.py`; `run_web.py` broadcast; `web/index.html` onmessage |
| Serve  | `GET /browse-results?run_id=...` → load from DB → return table HTML. | `run_web.py` `browse_results()`; `browse_results_repo.get_run()` |

The only URL ever passed to `on_open_url` or `open_in_new_tab` for search is the Talkie table URL; the raw search engine URL is never opened in the search path.
