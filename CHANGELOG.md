# Changelog

## Unreleased

### Code quality and cleanup

- **Module servers:** Consolidated duplicate error response logic into `BaseModuleServer` helpers: `_service_unavailable_response()`, `_error_response(status_code, error_code, message)`, and `_require_service(service)`. Browser, RAG, and speech module servers now use these helpers instead of inline `JSONResponse` blocks. Metrics attributes are initialized before middleware that uses them.
- **run.py:** Removed duplicate and redundant imports inside `_maybe_start_local_servers`; added top-level `requests` and `subprocess` where used.
- **Documentation:** Persistence pattern (repos use `with_connection` and log+re-raise on `sqlite3.Error`) documented in `persistence/database.py`. Module server config template (same structure for `modules.<name>.server`) documented in MODULES.md. README notes that `requirements.txt` is for the rifai_scholar_downloader subproject; main app uses Pipfile. MODULE_API.md documents the shared response helpers for implementers.
