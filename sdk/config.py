"""
Normalized config section access for Talkie modules.
Provides get_section() and section-specific getters (RAG, browser) so
config normalization lives in one place; app and modules use these instead of duplicating logic.
"""

from __future__ import annotations

from typing import Any, Callable


def get_section(
    raw_config: dict,
    section: str,
    defaults: dict[str, Any],
    validators: dict[str, Callable[[Any], Any]] | None = None,
) -> dict[str, Any]:
    """
    Return a normalized config section by merging raw section with defaults and applying validators.

    Args:
        raw_config: Full merged config dict (e.g. from load_config()).
        section: Top-level key (e.g. "rag", "browser").
        defaults: Default values for the section; merged with raw_config.get(section, {}).
        validators: Optional dict mapping section key -> callable(value) -> value (e.g. clamp int).

    Returns:
        New dict with all keys from defaults, overridden by raw section, then validated.
    """
    validators = validators or {}
    raw_section = dict(raw_config.get(section) or {})
    out = dict(defaults)
    for k, v in raw_section.items():
        if k in out or k in defaults:
            out[k] = v
    for k, validator in validators.items():
        if k in out:
            try:
                out[k] = validator(out[k])
            except (TypeError, ValueError):
                pass
    return out


def get_rag_section(raw_config: dict) -> dict[str, Any]:
    """
    Return normalized RAG config from full raw config.
    Uses "rag" and "ollama" sections (base_url from ollama).
    """
    r = raw_config.get("rag") or {}
    ollama = raw_config.get("ollama") or {}
    chroma_host = r.get("chroma_host")
    chroma_host = (
        str(chroma_host).strip()
        if chroma_host is not None and str(chroma_host).strip()
        else None
    )
    chroma_port = r.get("chroma_port")
    if chroma_port is not None:
        try:
            chroma_port = max(1, min(65535, int(chroma_port)))
        except (TypeError, ValueError):
            chroma_port = 8000
    else:
        chroma_port = 8000
    return {
        "embedding_model": str(r.get("embedding_model", "nomic-embed-text")).strip()
        or "nomic-embed-text",
        "base_url": str(ollama.get("base_url", "http://localhost:11434")).rstrip("/"),
        "vector_db_path": str(r.get("vector_db_path", "data/rag_chroma")),
        "chroma_host": chroma_host,
        "chroma_port": chroma_port,
        "top_k": max(1, min(20, int(r.get("top_k", 5)))),
        "document_qa_top_k": max(1, min(20, int(r.get("document_qa_top_k", 8)))),
        "chunk_size": max(100, min(2000, int(r.get("chunk_size", 500)))),
        "chunk_overlap": max(0, min(500, int(r.get("chunk_overlap", 100)))),
        "min_query_length": max(0, int(r.get("min_query_length", 3))),
    }


def get_browser_section(raw_config: dict) -> dict[str, Any]:
    """
    Return normalized browser config from full raw config.
    """
    b = raw_config.get("browser") or {}
    timeout = b.get("fetch_timeout_sec")
    try:
        timeout = max(5, min(120, int(timeout))) if timeout is not None else 20
    except (TypeError, ValueError):
        timeout = 20
    retries = b.get("fetch_max_retries")
    try:
        retries = max(0, min(5, int(retries))) if retries is not None else 2
    except (TypeError, ValueError):
        retries = 2
    search_url = (b.get("search_engine_url") or "").strip()
    if not search_url or "{query}" not in search_url:
        search_url = "https://duckduckgo.com/?q={query}"
    cooldown = b.get("cooldown_sec")
    try:
        cooldown = max(0.0, float(cooldown)) if cooldown is not None else 2.0
    except (TypeError, ValueError):
        cooldown = 2.0
    demo_delay = b.get("demo_delay_between_scenarios_sec")
    try:
        demo_delay = max(1.0, float(demo_delay)) if demo_delay is not None else 4.0
    except (TypeError, ValueError):
        demo_delay = 4.0
    return {
        "enabled": bool(b.get("enabled", True)),
        "chrome_app_name": str(b.get("chrome_app_name", "Google Chrome")).strip()
        or "Google Chrome",
        "fetch_timeout_sec": timeout,
        "fetch_max_retries": retries,
        "search_engine_url": search_url,
        "cooldown_sec": cooldown,
        "demo_delay_between_scenarios_sec": demo_delay,
    }
