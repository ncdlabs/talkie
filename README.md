# Talkie

**TLDR:** Talkie is a local, voice-first app that helps people with reduced speech clarity communicate. You speak; it transcribes, clarifies with a local LLM, and shows (or speaks) the result. All processing stays on your machine.

## Stack (engineering view)

- **Runtime:** Python 3.11+, Pipenv. Entry: Web UI via `run_web.py` (FastAPI + WebSocket + static HTML at http://localhost:8765).
- **Audio → text:** Microphone capture (sounddevice) → STT (Whisper default, or Vosk). Optional speaker filter and calibration.
- **Text → response:** Local LLM via Ollama (e.g. phi, mistral). Optional two-step flow: raw STT → regeneration (intent/homophone fix) → completion. Profile built from user context, corrections, accepted responses, and training facts.
- **Persistence:** SQLite (history, settings, training). Optional curation and JSONL export for fine-tuning.
- **Optional modules:** RAG (documents in Chroma, Ollama embeddings), voice-controlled browser (search, open URL, store page for RAG). Modules are discovered under `modules/` and register with the pipeline; they can run in-process or as HTTP servers.
- **Optional infrastructure:** Podman (Compose) for Consul, KeyDB, HAProxy, Chroma, module servers, healthbeat, VictoriaMetrics, Grafana. Managed by the `./talkie` CLI.

Full documentation (features, configuration, architecture, modules, SDK, troubleshooting) lives in the **project wiki** (see the wiki link in the repository).

## Local dev: get running

1. **Requirements:** Python 3.11+, microphone, [Ollama](https://ollama.ai/) running with a model (e.g. `ollama pull phi`).
2. **Install:** `pipenv install`
3. **Start:** Use the Talkie CLI (do not run the Python process directly):
   - **Web UI only (no containers):** `./talkie start web` → open http://localhost:8765
   - **Full stack (containers + Web UI):** `./talkie start all`
4. **Optional:** Set `TALKIE_CONFIG` to the path of a different `config.yaml`.

Other useful commands: `./talkie status`, `./talkie logs <service> --follow`, `./talkie stop`, `./talkie help`. See the wiki for configuration, service groups (`core`, `modules`), and troubleshooting.

## Tests and code quality

```bash
pipenv install --dev
pipenv run pytest tests/ -v
pipenv run ruff check .
pipenv run ruff format .
```

`requirements.txt` is for the **rifai_scholar_downloader** subproject only; use Pipfile for the Talkie app.

## License

See repository.
