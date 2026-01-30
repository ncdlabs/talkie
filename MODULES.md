# Talkie module standard

The app discovers **modules** by scanning the `modules/` directory. Adding a new subdirectory with the required structure is enough for config to be merged; optional runtime wiring is documented below.

**SDK**: Config normalization, speech abstractions, discovery, and logging for modules live in the **`sdk`** package. See [docs/SDK.md](docs/SDK.md) for full API and usage. Modules should use `sdk.get_rag_section(raw)`, `sdk.get_browser_section(raw)`, and `sdk.abstractions` (e.g. `AudioCapture`, `STTEngine`) instead of duplicating logic or importing from `app`.

## What the app recognizes

- **Location**: Any direct subdirectory of `modules/` (e.g. `modules/myfeature/`).
- **Config**: The directory must contain a config file (by default `config.yaml`). Its contents are merged into the app config in discovery order (see below).
- **Optional manifest**: A file named `MODULE.yaml` in the module directory can override name, order, and whether the module is enabled.

## Directory structure

Minimum:

```
modules/
  myfeature/
    config.yaml     # required for discovery
```

With manifest:

```
modules/
  myfeature/
    MODULE.yaml     # optional
    config.yaml     # required (or path given in MODULE.yaml config_file)
    __init__.py     # optional; use for runtime entry points
```

## MODULE.yaml manifest

Optional. If present, it can define:

| Key           | Type    | Default        | Description |
|---------------|---------|----------------|-------------|
| `name`        | string  | directory name | Display/log name for the module. |
| `description` | string  | (none)         | Short description. |
| `enabled`     | boolean | true           | If false, the module is skipped (no config merge). |
| `order`       | number  | 0              | Merge order: lower values are merged first. Ties are broken by directory name. |
| `config_file` | string  | config.yaml    | Config filename inside this module directory. |

Example:

```yaml
name: myfeature
description: My optional feature.
order: 40
enabled: true
config_file: config.yaml
```

## Config merge order

1. Module configs in **discovery order** (each module’s `config.yaml` or `config_file`). Order is: `order` value from MODULE.yaml (default 0), then directory name.
2. Root `config.yaml` (or path from `TALKIE_CONFIG`).
3. `config.user.yaml` in the same directory as the root config, if it exists.

Later sources override earlier ones (deep merge).

## Module server config (HTTP API)

When a module runs as an HTTP server (e.g. speech, rag, browser), its config lives under `config.modules.<name>.server`. All module server blocks share the same structure so you can copy one block when adding a new module. Typical keys: `enabled`, `host`, `port`, `timeout_sec`, `retry_max`, `retry_delay_sec`, `health_check_interval_sec`, `circuit_breaker_failure_threshold`, `circuit_breaker_recovery_timeout_sec`, `api_key`, `use_service_discovery`, `endpoints`. See root `config.yaml` under `modules.speech.server`, `modules.rag.server`, or `modules.browser.server` for the template.

## Adding a new module (config only)

1. Create a directory under `modules/`, e.g. `modules/myfeature/`.
2. Add `config.yaml` with your default keys (they will be merged into the app config).
3. Optionally add `MODULE.yaml` to set `order` or `enabled`.
4. No code changes in the core app are required for your config to be loaded.

## Runtime integration (optional)

Config discovery is automatic (via `sdk.discovery`). Registering a module at runtime (e.g. with the pipeline or UI) is done by the app using known module names and entry points:

- **speech**: `modules.speech.create_speech_components(config, settings_repo)` provides capture, STT, TTS, etc. Implements `sdk.abstractions` (AudioCapture, STTEngine, TTSEngine, SpeakerFilter).
- **rag**: `modules.rag.register_with_pipeline(pipeline, config)` registers the RAG retriever and returns the service. Uses `sdk.get_rag_section(raw)` for config.
- **browser**: `modules.browser.create_web_handler(config, ollama_client, rag_ingest_callback)` returns the web handler for the pipeline. Uses `sdk.get_browser_section(raw)` for config.

To add a new **runtime** plugin (not just config):

- Use the SDK for config (`sdk.get_section` or a section getter) and, if applicable, implement `sdk.abstractions`. Wire your module in `run.py` by importing it and calling your registration function.
- In the future, the app may support a single `register(context)` entry point per module; for now, wiring remains in `run.py` for the three built-in modules.

## Summary

- **Config**: Add `modules/<name>/config.yaml` (and optionally `MODULE.yaml`). The app will discover and merge it.
- **SDK**: Use `sdk` for config section access, abstractions, discovery, and logging; see [docs/SDK.md](docs/SDK.md).
- **Runtime**: Wire your module in `run.py` or follow the same entry point pattern as speech/rag/browser.
