# Browser module (voice-controlled web)

Voice-controlled browse: search (API → table only, no search-engine page), open URL, store page for RAG, click/select links, scroll. Self-contained addon; config merged by discovery.

Supporting code for browse/search lives in this module:

- **`browse_results_repo.py`** — save_run / get_run for the temporary indexed table (uses app conn_factory; table in persistence/schema.sql).
- **`browse_results_http.py`** — handle_browse_results(request, conn_factory): serves GET /browse-results (run_id or legacy data=).
- **`search_api.py`** — search_via_api(query): DDGS API, no search-engine HTML fetch.
- **`service.py`** — execute search, build table URL, open table only; open_url with search URL → search flow.

## Deployment (container)

When this module runs as a **compose service** (e.g. `talkie-browser`), the container image is built from the project Dockerfile with `COPY . .`—code is baked in at **build** time. To pick up code changes:

1. **Rebuild** the image: `podman compose build browser` (or `./talkie restart browser`, which now builds then recreates).
2. **Recreate** the container so it uses the new image: `podman compose up -d --force-recreate browser`.

Restarting the container without rebuilding keeps the old image and old code. The top-level `./talkie restart browser` performs build + recreate so the running container gets the new code.

## Config

- **Local (in-process)**: `modules.browser.server.enabled: false` (default). The web UI runs the browser code in the same process; restarting the web UI (`./talkie restart web`) picks up changes.
- **Remote (container)**: `modules.browser.server.enabled: true`. The web UI calls the browser container via HTTP; rebuild and recreate the browser container to pick up changes.
