"""
Browse-results HTTP handler: serve table HTML from run_id or legacy data=.
Self-contained in browser module; run_web mounts this route.
"""

from __future__ import annotations

import base64
import html as html_module
import json
import logging
from urllib.parse import unquote_plus
from typing import Any, Callable

from starlette.requests import Request
from starlette.responses import HTMLResponse

from modules.browser.browse_results_repo import get_run

logger = logging.getLogger(__name__)


def _render_table(title: str, rows: list[str]) -> str:
    table_rows_html = "\n".join(rows)
    n_results = len(rows)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_module.escape(title)}</title>
  <style>
    :root {{ --bg: #111; --fg: #eee; --accent: #0c6; --muted: #666; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; background: var(--bg); color: var(--fg); margin: 1.5rem; font-size: 1.25rem; line-height: 1.5; display: flex; flex-direction: column; min-height: 100vh; }}
    .scroll-hint {{ font-size: 1rem; color: var(--muted); text-align: center; padding: 0.5rem 0; flex-shrink: 0; }}
    .browse-scroll-wrapper {{ flex: 1; min-height: 0; overflow-y: scroll; max-height: calc(100vh - 8rem); }}
    h1 {{ font-size: 1.5rem; color: var(--muted); margin-bottom: 0.5rem; font-weight: 600; }}
    .hint {{ font-size: 1.125rem; color: var(--muted); margin-bottom: 1rem; }}
    table {{ width: 100%; max-width: 56rem; border-collapse: collapse; font-size: 1.25rem; }}
    th {{ text-align: left; padding: 0.75rem 1rem; border-bottom: 2px solid var(--muted); color: var(--muted); font-weight: 600; font-size: 1.125rem; }}
    td {{ padding: 0.75rem 1rem; border-bottom: 1px solid var(--muted); vertical-align: top; }}
    .browse-num-cell {{ width: 4rem; text-align: right; padding-right: 1.25rem; }}
    .browse-num {{ font-size: 2rem; font-weight: bold; color: var(--accent); line-height: 1; }}
    .browse-title-cell {{ min-width: 12rem; }}
    .browse-desc-cell {{ color: var(--muted); font-size: 1.125rem; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <p class="scroll-hint">Say &quot;scroll up&quot;</p>
  <div class="browse-scroll-wrapper">
    <h1>{html_module.escape(title)}</h1>
    <p class="hint">Say &quot;open 1&quot; through &quot;open {n_results}&quot; to open a result.</p>
    <table aria-hidden="true">
    <thead>
      <tr><th scope="col" class="browse-num-cell">#</th><th scope="col">Page title</th><th scope="col">Page description</th></tr>
    </thead>
    <tbody>
{table_rows_html}
    </tbody>
  </table>
  </div>
  <p class="scroll-hint">Say &quot;scroll down&quot;</p>
</body>
</html>"""


def handle_browse_results(
    request: Request, conn_factory: Callable[[], Any] | None
) -> HTMLResponse:
    """
    Handle GET /browse-results. Query params: run_id (load from SQLite) or url/q/data (legacy base64).
    Returns HTMLResponse (table page or error).
    """
    run_id_param = request.query_params.get("run_id", "")
    q_param = request.query_params.get("q", "")
    data_param = request.query_params.get("data", "")

    if run_id_param and conn_factory:
        run_data = get_run(conn_factory, run_id_param)
        if run_data and run_data.get("rows"):
            query_esc = html_module.escape(run_data.get("query", ""))
            title = f"Search: {query_esc}" if query_esc else "Search results"
            rows = []
            for r in run_data["rows"]:
                idx = r.get("row_num", 0)
                href = (r.get("href") or "").strip()
                text = (r.get("title") or href or "").strip()
                desc = (r.get("description") or "").strip() or "\u2014"
                href_esc = html_module.escape(href)
                text_esc = html_module.escape(
                    text[:120] + ("..." if len(text) > 120 else "")
                )
                desc_esc = html_module.escape(
                    desc[:200] + ("..." if len(desc) > 200 else "")
                )
                rows.append(
                    f'<tr><td class="browse-num-cell"><span class="browse-num" aria-hidden="true">{idx}</span></td>'
                    f'<td class="browse-title-cell"><a href="{href_esc}">{text_esc}</a></td>'
                    f'<td class="browse-desc-cell">{desc_esc}</td></tr>'
                )
            return HTMLResponse(_render_table(title, rows))
        if run_data is None:
            return HTMLResponse(
                "<!DOCTYPE html><html><body><p>Results not found or expired.</p></body></html>",
                status_code=404,
            )

    if not data_param:
        return HTMLResponse(
            "<!DOCTYPE html><html><body><p>No results data.</p></body></html>",
            status_code=400,
        )
    try:
        data_bytes = base64.urlsafe_b64decode(data_param.encode("ascii"))
        links = json.loads(data_bytes.decode("utf-8"))
    except Exception as e:
        logger.debug("browse-results decode failed: %s", e)
        return HTMLResponse(
            "<!DOCTYPE html><html><body><p>Invalid results data.</p></body></html>",
            status_code=400,
        )
    if not isinstance(links, list):
        links = []
    query_esc = html_module.escape(unquote_plus(q_param))
    title = f"Search: {query_esc}" if query_esc else "Search results"
    rows = []
    for item in links:
        if not isinstance(item, dict):
            continue
        idx = item.get("index", 0)
        href = (item.get("href") or "").strip()
        text = (item.get("text") or item.get("href") or "").strip()
        desc = (item.get("description") or "").strip() or "\u2014"
        href_esc = html_module.escape(href)
        text_esc = html_module.escape(text[:120] + ("..." if len(text) > 120 else ""))
        desc_esc = html_module.escape(desc[:200] + ("..." if len(desc) > 200 else ""))
        rows.append(
            f'<tr><td class="browse-num-cell"><span class="browse-num" aria-hidden="true">{idx}</span></td>'
            f'<td class="browse-title-cell"><a href="{href_esc}">{text_esc}</a></td>'
            f'<td class="browse-desc-cell">{desc_esc}</td></tr>'
        )
    return HTMLResponse(_render_table(title, rows))
