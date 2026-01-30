# Talkie

A Python application for laptop or Raspberry Pi that helps people with speech impairments (e.g., Parkinson's) communicate more clearly. All processing runs locally.

## Features

- **Audio input**: Continuous capture from a connected microphone
- **Speech recognition**: Local STT (Vosk or Whisper)
- **Speaker filtering**: Pluggable filter (no-op by default; extensible to verification/diarization)
- **LLM interaction**: Local Mistral via Ollama for full-sentence responses
- **Response display**: Web-based UI with large, high-contrast text (http://localhost:8765)
- **History**: SQLite storage of transcriptions, LLM responses, and corrections
- **Correction and personalization**: Edit past responses in the UI; language profile built from corrections, accepted responses, and optional user context (e.g. "PhD, professor at Brown")
- **Learning profile**: User context (Settings), explicit corrections, and accepted completions are combined so the LLM tailors vocabulary and style; curate which interactions are used for learning (History "Use for learning" checkbox)
- **Scheduled curation**: Optional background process (or cron) that curates the SQLite DB: pattern recognition on sentences/phrases, assigns weights (higher for corrections and recurring patterns), and can exclude or remove low-value/old entries; higher-weighted examples are preferred when building the profile
- **Audio training**: Record short facts (e.g. "Star is my dog", "Susan is my wife") via the Train (T) button; they are injected into the LLM context
- **Export for fine-tuning**: Export interactions to JSONL (instruction/input/output) to train or fine-tune a model externally (e.g. Ollama create, Unsloth)
- **Volume display**: Waveform-style strip showing microphone input level
- **RAG-ready**: Extension point for retrieval over the user's publications; when implemented, pass a retriever to the pipeline and relevant chunks are appended to the system prompt

## Requirements

- Python 3.11+
- Microphone
- [Ollama](https://ollama.ai/) running with a model (e.g. `ollama pull mistral`)
- STT: Vosk or Whisper. Default is **Whisper** for best accuracy; use Vosk on Raspberry Pi if Whisper is too slow

## Setup

The main app uses **Pipfile** for dependencies. Install and run:

```bash
pipenv install
pipenv run python run_web.py
```

Note: `requirements.txt` is for the **rifai_scholar_downloader** subproject only; use Pipfile for the Talkie app.

Then open http://localhost:8765. Optional: set `TALKIE_CONFIG` to the path of a different `config.yaml`.

## Service Management

For managing infrastructure services (Consul, KeyDB, HAProxy, etc.):

```bash
# Start all services
./talkie start

# Start specific service groups
./talkie start infrastructure  # Consul, KeyDB, HAProxy, etc.
./talkie start core            # Ollama, Chroma
./talkie start modules         # Module servers

# Check status
./talkie status

# View logs
./talkie logs consul-server --follow

# Health check
./talkie health

# Stop services
./talkie stop

# Restart services
./talkie restart

# Clean up
./talkie clean containers
```

See `./talkie help` for all commands.

### macOS with Ollama

**Podman (recommended):** Run `./talkie app` or `./talkie start core`. Ollama runs in a Podman container (`talkie-ollama`); the script starts it, pulls the configured model if missing, and warms the model so the first request does not 500. Logs: `podman logs talkie-ollama`.

**Without Podman:** Run Ollama from the menu bar or start it with `ollama serve`. Ensure a model is available (e.g. `ollama pull mistral`). The default `config.yaml` uses `http://localhost:11434` and model `mistral`, so no config change is needed. Speech-to-text defaults to **Whisper** (`small` model); the model downloads on first run. On a Raspberry Pi or low-RAM machine, set `stt.engine: vosk` and download a Vosk model from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models). For best accuracy (especially with impaired speech), set `stt.whisper.model_path: "medium"` (needs ~5GB RAM).

## Configuration

Config is merged from module configs (`modules/speech/config.yaml`, etc.), root `config.yaml`, and optional `config.user.yaml` (user overrides, e.g. from Settings). Edit `config.yaml` (and optionally `config.user.yaml`) to set:

- `audio.device_id`, `audio.sample_rate`, `audio.chunk_duration_sec`, `audio.sensitivity` (gain for quiet speech, default 2.5; 1.0 = normal, 2.0–4.0 = more sensitive)
- `stt.engine` (`whisper` or `vosk`) and `stt.whisper.model_path` (`base`, `small`, `medium`, `large-v3`); see "Speech-to-text accuracy" below
- `ollama.base_url`, `ollama.model_name`
- `llm.system_prompt`, `llm.user_prompt_template`, `llm.export_instruction` (all prompt text; edit in config to change behavior), `llm.min_transcription_length` (skip LLM when transcription is shorter than this many characters; reduces repeated wrong phrases from noise)
- `tts.enabled`, `tts.engine`, `tts.voice`
- `persistence.db_path`
- `curation.interval_hours` (optional; 0 = disabled), `curation.correction_weight_bump`, `curation.pattern_count_weight_scale`, `curation.delete_older_than_days`, `curation.max_interactions_to_curate`
- `profile.correction_limit`, `profile.accepted_limit` (optional; defaults in `profile/constants.py`)
- Web UI: `TALKIE_WEB_HOST`, `TALKIE_WEB_PORT` (default 8765)
- `logging.level`

## Speech-to-text accuracy

Talkie uses **faster-whisper** (Whisper) by default. Among free, local STT options, Whisper is one of the most accurate and is used in research for dysarthric and speech-impaired speech (e.g. Parkinson's). Vosk is lighter and faster but less accurate.

- **Default**: `stt.engine: whisper`, `stt.whisper.model_path: "small"` — good balance of speed and accuracy.
- **Best accuracy** (especially for unclear or impaired speech): set `stt.whisper.model_path: "medium"` (~5GB RAM, slower). Optional: `audio.chunk_duration_sec: 5` or `6` for a bit more context.
- **Lighter / Pi**: set `stt.engine: vosk` and use a [Vosk model](https://alphacephei.com/vosk/models); for better Vosk accuracy use a larger model (e.g. `vosk-model-en-us-0.22`).

Other free options (e.g. Sherpa-ONNX, cloud APIs) can match or exceed Whisper in some setups, but Whisper via faster-whisper is a strong choice for local, offline use and impaired speech.

## Troubleshooting: wrong or repeated phrase ("not hearing" / "says the same thing")

If the app keeps saying an unrelated phrase (e.g. "can you help me understand my bill") instead of what you said, the cause is usually:

1. **STT mishearing** – Background noise or quiet speech gets transcribed as a few words; the LLM then "completes" that into a common phrase. Check the debug log (if enabled) for "You said: …" to see what was actually transcribed.
2. **Config changes that help**  
   - Increase `audio.sensitivity` (e.g. 3.0–4.0) if your voice is quiet, or decrease it if the mic is picking up too much noise.  
   - Set `llm.min_transcription_length` (e.g. 4 or 5) so very short/noisy transcriptions are not sent to the LLM.  
   - The system prompt in `config.yaml` now tells the model to output "I didn't catch that." when the transcription is unclear and to never invent sentences.
3. **Microphone** – Confirm the correct mic in system settings; in `config.yaml` you can set `audio.device_id` to a specific device index if needed.

## Curation and fine-tuning

A **curator** runs pattern recognition on the interaction history, assigns a **weight** to each sentence/phrase (corrected and frequently used patterns get higher weight), and can exclude or delete entries. The language profile uses these weights so heavier examples are prioritized. Run it on a schedule (in-app or cron) or once via CLI.

- **In-app**: Set `curation.interval_hours` in `config.yaml` (e.g. `24`). A background thread runs the curator every N hours while the app is open.
- **CLI (once or cron)**:
  ```bash
  pipenv run python -m curation
  ```
- **Export for fine-tuning**: Write high-weight and corrected interactions to JSONL for external training:
  ```bash
  pipenv run python -m curation --export data/talkie_export.jsonl [--limit 5000]
  ```
  Each line is a JSON object with `instruction`, `input`, `output`. You can then use that file with Ollama (e.g. custom Modelfile/system prompt), Unsloth, or other fine-tuning tools to train or fine-tune a model on the user’s speech patterns.

## RAG / Documents

You can upload documents (TXT, PDF), vectorize them with Ollama embeddings, and query them by voice.

1. **Documents dialog** (Documents button): Add files, then click **Vectorize** to chunk, embed (Ollama), and store them in Chroma at `data/rag_chroma` (configurable in `config.yaml` under `rag.vector_db_path`). The dialog shows indexed documents; you can **Remove from index** or **Clear all**.
2. **Ask documents (?)** button: Turn it on, then speak a question. The app retrieves relevant chunks from the vector DB and the LLM answers using only that context. Document Q&A responses are stored in the same History as regular answers.
3. **Embedding model**: Set `rag.embedding_model` in `config.yaml` (default `nomic-embed-text`). Pull it first: `ollama pull nomic-embed-text`. If the configured model is missing, the app tries fallbacks (e.g. `mxbai-embed-large`, `all-minilm`) or shows a clear error.
4. **Vector DB in Podman** (optional): To run Chroma in a container, use `podman compose up -d` (see project root `compose.yaml`). Then set `rag.chroma_host: "localhost"` and optionally `rag.chroma_port: 8000` in `config.yaml`. If `chroma_host` is unset, the app uses an embedded Chroma store at `rag.vector_db_path`.

RAG retrieval runs only when "Ask documents" is on, so normal conversation has no extra latency. Training facts (Train dialog) remain in the system prompt as before.

## Tests

```bash
pipenv install --dev
pipenv run pytest tests/ -v
```

Code quality: `pipenv run ruff check .` and `pipenv run ruff format .`.

## Scholar PDF downloader (rifai_scholar_downloader)

Optional tool to download **openly available** PDFs for a Google Scholar author (default: Dr. Abdalla Rifai). Output goes under `downloads/` by default. Resumable and idempotent.

```bash
pip install -r requirements.txt
python -m rifai_scholar_downloader.cli
```

See `rifai_scholar_downloader/README.md` for setup, usage examples, and limitations (rate limits, paywalls, no CAPTCHA bypass).

## Project structure

Core (application root):

- `app/` – Pipeline orchestration, speech abstractions, audio level helper
- `config.py` – Config loading (merges module configs, root `config.yaml`, optional `config.user.yaml`)
- `llm/` – Ollama/Mistral client and prompts
- `profile/` – Language profile (user context, corrections, accepted pairs) and constants
- `persistence/` – SQLite schema, history repo, settings repo; migrations in `database.py`
- `curation/` – Curator (pattern recognition, weighting, add/remove), scheduler, CLI, and JSONL export for fine-tuning
- `web/` – Web UI static assets (index.html); FastAPI + WebSocket in `run_web.py`
- `rifai_scholar_downloader/` – Resumable Google Scholar author PDF downloader (open-access only)

**Modules** (optional features under `modules/`):

- `modules/speech/` – Audio capture, STT (Vosk, Whisper), TTS (say), speaker filter, calibration; each has its own `config.yaml` merged into the main config
- `modules/rag/` – Document ingestion (chunk, embed via Ollama, Chroma store), retrieval; plugin entry point `register_with_pipeline()`
- `modules/browser/` – Voice-controlled web (search, open URL, store page for RAG); plugin entry point `create_web_handler()`

The app composes these at startup: if a module is missing or fails to load, the rest of the app still runs (e.g. without RAG or browser). Core depends only on abstractions and plugin APIs so modules can be maintained or removed independently.

## Modular design

Talkie is split into **core** and **modules** so the codebase stays maintainable and contributors can work on one area (speech, RAG, web) without touching the rest.

- **Core** defines interfaces (e.g. in `app/abstractions.py`) and wires optional plugins in `run_web.py`. Pipeline accepts injected speech components and optional RAG/web handlers.
- **Modules** live under `modules/`: `speech`, `rag`, `browser`. Each module can provide a default `config.yaml` in its directory; the main `config.yaml` (and optional `config.user.yaml`) are merged on top. To disable a module, omit or remove its directory, or set the relevant config (e.g. `browser.enabled: false`).
- **Configuration**: Root `config.yaml` plus optional `config.user.yaml` (written by the Settings UI). Module defaults are in `modules/<name>/config.yaml`. Load order: module configs merged first, then root config, then user overrides. Some settings take effect after restart.
- **Debugging**: Errors and warnings appear in the web UI debug area and in `talkie_debug.log` with `[ERROR]` / `[WARN]` prefixes. Safe to leave debug on for troubleshooting.

## License

See repository.
