#!/bin/sh
# Start Ollama, wait for server, pre-pull models from OLLAMA_PRELOAD_MODELS, then keep serving.
# OLLAMA_PRELOAD_MODELS: comma-separated list (default: phi). Set empty to skip preload.
set -e

ollama serve &
until ollama list 2>/dev/null; do sleep 1; done

preload="${OLLAMA_PRELOAD_MODELS:-phi}"
if [ -n "$preload" ]; then
  for model in $(echo "$preload" | tr ',' ' '); do
    model=$(echo "$model" | tr -d ' ')
    [ -z "$model" ] && continue
    ollama pull "$model" || true
  done
fi

wait
