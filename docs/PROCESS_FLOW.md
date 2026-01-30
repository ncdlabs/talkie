# Talkie process flow (web UI)

End-to-end flow from browser to response and back. Used to verify the pipeline is wired correctly.

## 1. Connection and capture

1. Browser opens WebSocket to `/ws`.
2. User clicks **Speech** (or Web/RAG). Client sends `{ "action": "start", "sample_rate": 16000, "module": "speech" }`.
3. Server: `web_capture.set_client_sample_rate(sample_rate)`, `web_capture.start()`, `pipeline.start()`.
4. Pipeline thread starts: `_capture.start()`, `_stt.start()`, checks Ollama, then enters run loop.
5. Browser streams Int16 audio in 100 ms chunks via WebSocket binary frames; server calls `web_capture.put_chunk(bytes)`. If client rate != 16000, chunks are resampled to 16 kHz before buffering.
6. Pipeline blocks on `read_chunk()` until `chunk_size` bytes (config: `chunk_duration_sec * sample_rate * 2`) are available, then continues.

## 2. Audio → text

7. Chunk is passed to `_stt.transcribe(chunk)` (e.g. Whisper). Result is trimmed.
8. Skip if empty; optional auto-sensitivity bump when level in band and no transcription.
9. Skip if length < `min_transcription_length`.
10. Skip if `_speaker_filter.accept(text, chunk)` is False (e.g. noise gate).
11. Skip if same as previous chunk (consecutive duplicate).
12. Skip if transcription matches last spoken response (echo) or high word overlap with it (fuzzy echo).
13. Abort any playing TTS: `_tts.stop()`.

## 3. Regeneration (optional)

14. If `regeneration_enabled`: build regeneration prompts, call `_llm.generate(reg_user, reg_system)` (Ollama with options: `num_predict`, `temperature`). Parse JSON for `sentence` and `certainty` if requested. Set `intent_sentence`, `used_regeneration`, `regeneration_certainty`. Profile and recent context are prefetched in parallel when using executor.

## 4. Training mode

15. If training mode is on: call `_on_training_transcription(text)`, invalidate profile cache, broadcast `training_fact_added`, `continue` (no LLM response, no TTS).

## 5. Browse / web handler

16. If web handler is set and (web mode **or** utterance looks like search/store/go_back/click/select/scroll): call `_web_handler(browse_utterance, ...)`. On success: save interaction, `_on_response(web_response, id)`, update `_last_spoken_response`, `_tts.speak(web_response)` (no-op in web UI), `_on_status("Listening...")`, `continue`.

## 6. Main response path

17. Build recent context: `list_recent(turns)`, build `conversation_context` and `recent_reply_norms` / `recent_user_phrase_norms` for repeat detection.
18. **Document Q&A**: If document QA mode and no docs → short-circuit message. Else: RAG retrieve, `build_document_qa_system_prompt`, `build_document_qa_user_prompt`, `_llm.generate(user_prompt, system)`.
19. **Completion**: If “heard full sentence” and intent matches transcript → use intent as response (skip completion). Else if `use_regeneration_as_response` and regeneration used and (certainty is None or >= threshold) → use `intent_sentence` (skip completion). Else: build system prompt (base + profile + conversation + retrieved), build user prompt, `_llm.generate(user_prompt, system)`.
20. Repeat check: if response normalizes to a recent reply or last spoken, replace with intent or raw text (or fallback).
21. If response empty, use intent_sentence or transcript or `FALLBACK_MESSAGE`.

## 7. Persist and output

22. Save to history: `insert_interaction(original_transcription, llm_response)`; update profile cache.
23. `_on_response(response, interaction_id)` → server broadcasts `{ "type": "response", "text": response, "interaction_id": id }` to all WebSocket clients.
24. Update `_last_spoken_response`. If different from previous spoken, `_tts.speak(response)` (no-op in web UI; browser speaks via `speechSynthesis`).
25. `_on_status("Listening...")`. Loop continues from step 6 (next chunk).

## 8. Web client

26. On `msg.type === "response"`: set `#response` text, then `window.speechSynthesis.speak(msg.text)` (single voice; server TTS is no-op when using web UI).

## 9. Stop and disconnect

27. Client sends `{ "action": "stop" }` or disconnects. Server: remove socket from connections; **stop capture first** so `read_chunk()` returns; then `pipeline.stop()` so run loop exits and thread joins.
28. Pipeline run loop: `while self._running` becomes false; `_capture.stop()`, `_stt.stop()`, status “Stopped”.

## Checks (current behavior)

- **Ollama**: All generate calls use `options` (defaults `num_predict: 256`, `temperature: 0.4`); config can override via `ollama.options`.
- **Double voice**: Web UI uses `NoOpTTSEngine` on the server; only the browser speaks.
- **Echo**: Last-spoken and fuzzy word-overlap skip avoid re-processing TTS as new input.
- **Clean exit**: On WebSocket disconnect, capture is stopped before pipeline so the worker thread can exit without join timeout.
