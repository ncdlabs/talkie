# Module API Specification

This document defines the standard REST API that all Talkie modules must implement when running as HTTP servers.

## Standard Endpoints (All Modules)

All modules must implement these standard endpoints:

### `GET /health`

Health check endpoint. Returns module status, readiness, and version information.

**Response:**
```json
{
  "status": "ok",
  "ready": true,
  "version": "1.0",
  "module": "speech"
}
```

- `status`: Always `"ok"` when server is responding
- `ready`: `true` if module is initialized and ready to accept requests, `false` if still initializing
- `version`: API version (e.g., `"1.0"`)
- `module`: Module name (e.g., `"speech"`, `"rag"`, `"browser"`)

**Status Codes:**
- `200`: Server is healthy
- `503`: Server is not ready (still initializing)

### `GET /config`

Get current module configuration.

**Response:**
```json
{
  "config": { ... }
}
```

### `POST /config`

Update module configuration. Configuration is validated before applying.

**Request Body:**
```json
{
  "config": { ... }
}
```

**Response:**
```json
{
  "success": true
}
```

### `POST /config/reload`

Reload configuration from file without restarting the server.

**Response:**
```json
{
  "success": true
}
```

### `GET /metrics`

Optional metrics endpoint (Prometheus-style). Recommended for monitoring.

**Response:**
```json
{
  "requests_total": 1234,
  "requests_by_endpoint": {
    "/transcribe": 500,
    "/speak": 300
  },
  "latency_p50_ms": 45,
  "latency_p95_ms": 120,
  "latency_p99_ms": 250,
  "errors_total": 5,
  "circuit_breaker_state": "closed"
}
```

### `GET /version`

API version information.

**Response:**
```json
{
  "api_version": "1.0",
  "module_version": "1.0.0"
}
```

## Request/Response Format

### Headers

- `X-Request-ID`: Correlation ID for request tracing (optional, generated if not provided)
- `X-API-Version`: Client API version for version negotiation
- `Content-Type`: `application/json` for JSON requests
- `Authorization`: Optional `Bearer <api_key>` for authenticated requests

### Error Format

All errors follow this standard format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "additional context"
  }
}
```

**Common Error Codes:**
- `invalid_request`: Request validation failed
- `not_found`: Resource not found
- `internal_error`: Server error
- `service_unavailable`: Module not ready or temporarily unavailable
- `timeout`: Request timeout
- `authentication_failed`: Invalid or missing API key

**Status Codes:**
- `400`: Bad Request (validation error)
- `401`: Unauthorized (authentication required)
- `404`: Not Found
- `500`: Internal Server Error
- `503`: Service Unavailable

**Implementer note:** Module servers that extend `BaseModuleServer` (`modules.api.server`) use shared helpers for consistent error responses: `_service_unavailable_response()`, `_error_response(status_code, error_code, message)`, and `_require_service(service)` (returns 503 if service is None). See speech, rag, and browser server implementations.

## Module-Specific Endpoints

### Speech Module (`/api/v1/speech`)

#### `POST /capture/start`

Start audio capture.

**Response:**
```json
{
  "success": true
}
```

#### `POST /capture/stop`

Stop audio capture.

**Response:**
```json
{
  "success": true
}
```

#### `POST /capture/read_chunk`

Read one audio chunk.

**Response:**
```json
{
  "audio_base64": "base64_encoded_audio_bytes",
  "level": 0.5
}
```

- `audio_base64`: Base64-encoded audio bytes (int16 PCM, mono, 16kHz)
- `level`: RMS audio level (0.0-1.0)

#### `GET /capture/sensitivity`

Get current sensitivity setting.

**Response:**
```json
{
  "sensitivity": 3.0
}
```

#### `POST /capture/sensitivity`

Set sensitivity.

**Request Body:**
```json
{
  "sensitivity": 3.0
}
```

**Response:**
```json
{
  "success": true,
  "sensitivity": 3.0
}
```

#### `POST /stt/transcribe`

Transcribe audio to text.

**Request Body:**
```json
{
  "audio_base64": "base64_encoded_audio_bytes"
}
```

**Response:**
```json
{
  "text": "transcribed text"
}
```

#### `POST /stt/start`

Start STT engine (load model, warmup).

**Response:**
```json
{
  "success": true
}
```

#### `POST /stt/stop`

Stop STT engine (release model).

**Response:**
```json
{
  "success": true
}
```

#### `POST /tts/speak`

Speak text via TTS.

**Request Body:**
```json
{
  "text": "Text to speak"
}
```

**Response:**
```json
{
  "success": true
}
```

#### `POST /tts/stop`

Stop current TTS playback.

**Response:**
```json
{
  "success": true
}
```

#### `POST /speaker_filter/accept`

Check if transcription should be accepted.

**Request Body:**
```json
{
  "transcription": "text",
  "audio_base64": "base64_encoded_audio_bytes"
}
```

**Response:**
```json
{
  "accept": true
}
```

### RAG Module (`/api/v1/rag`)

#### `POST /ingest`

Ingest documents.

**Request Body:**
```json
{
  "paths": ["/path/to/doc1.pdf", "/path/to/doc2.txt"]
}
```

**Response:**
```json
{
  "success": true,
  "ingested_count": 2
}
```

#### `POST /ingest_text`

Ingest text directly.

**Request Body:**
```json
{
  "source": "web_page_123",
  "text": "Document text content..."
}
```

**Response:**
```json
{
  "success": true
}
```

#### `POST /retrieve`

Retrieve context for a query.

**Request Body:**
```json
{
  "query": "search query",
  "top_k": 5
}
```

**Response:**
```json
{
  "context": "Retrieved context text..."
}
```

#### `GET /sources`

List all indexed sources.

**Response:**
```json
{
  "sources": ["source1", "source2"]
}
```

#### `DELETE /sources/{source}`

Remove a source from the index.

**Response:**
```json
{
  "success": true
}
```

#### `POST /clear`

Clear entire index.

**Response:**
```json
{
  "success": true
}
```

#### `GET /has_documents`

Check if any documents are indexed.

**Response:**
```json
{
  "has_documents": true
}
```

### Browser Module (`/api/v1/browser`)

#### `POST /execute`

Execute a browser intent.

**Request Body:**
```json
{
  "intent": {
    "action": "search",
    "query": "search term"
  }
}
```

**Response:**
```json
{
  "result": "Opened search results",
  "url": "https://..."
}
```

## Versioning

API version is specified in the `X-API-Version` header. Current version is `1.0`. Clients should include this header, and servers should validate compatibility.

## Authentication

For remote modules, API key authentication is supported via the `Authorization: Bearer <api_key>` header or `X-API-Key` header.

## Timeouts

Recommended timeouts:
- Health check: 1 second
- Configuration: 5 seconds
- Transcribe: 30 seconds
- Other operations: 10 seconds
