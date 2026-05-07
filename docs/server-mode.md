# Server Mode (HTTP/SSE) — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

Since v1.7.0, `eq-chatbot-core` can run as a local HTTP sidecar that exposes the provider abstraction over REST + Server-Sent Events. Designed for apps that cannot embed Python directly (Avalonia/.NET, Electron, native iOS/Android).

The sidecar binds to `127.0.0.1` only, supports an OS-assigned ephemeral port, and authenticates every non-`/health` request with a Bearer token. It uses constant-time token comparison (`hmac.compare_digest`) and an optional parent-PID watchdog that terminates the sidecar when the parent process exits — preventing zombie processes on parent crash.

### Installation

The server mode is an optional extra and pulls in FastAPI, uvicorn, and sse-starlette:

```bash
uv pip install eq-chatbot-core[server]
```

Pure CLI/RAG/MCP imports keep working without these packages — they are only loaded when `eq-chatbot serve` is invoked.

### Starting the sidecar

```bash
# Production pattern: ephemeral port, token via stdin, parent watchdog
echo "$RANDOM_TOKEN" | eq-chatbot serve \
    --port 0 \
    --auth-token-fd 0 \
    --parent-pid $$
# stdout: LISTENING ON host=127.0.0.1 port=NNNN
```

The parent process scrapes the announced port from stdout and uses it for subsequent HTTP calls.

#### CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--host` | `127.0.0.1` | Bind interface. Keep on loopback for sidecar use. |
| `--port` | `0` | TCP port. `0` = OS-assigned (ephemeral). |
| `--auth-token-fd <fd>` | — | Read up to 256 bytes from the given file descriptor (recommended). |
| `--auth-token <token>` | — | Argv-based token (insecure: visible in `ps`/`/proc/<pid>/cmdline`). |
| `--parent-pid <pid>` | — | Watchdog: poll `os.kill(pid, 0)` every 5s, self-terminate via SIGTERM when parent exits. |
| `--log-level` | `info` | uvicorn log level. |

The environment variable `EQ_CHATBOT_AUTH_TOKEN` is honored as a fallback when no `--auth-token*` flag is given.

### Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/health` | none | Liveness probe — returns `{"status":"ok","version":"..."}` |
| `GET` | `/providers` | bearer | Available provider catalog |
| `POST` | `/models` | bearer | List models for a given provider |
| `POST` | `/chat` | bearer | Single-shot chat completion → `LLMResponse` JSON |
| `POST` | `/chat/stream` | bearer | SSE stream of `StreamChunk` events |

OpenAPI/Swagger UI lives at `/docs` and `/redoc` (auth-free, useful for exploration).

### SSE event types

The `/chat/stream` endpoint emits these named events:

| Event | Payload | Meaning |
|-------|---------|---------|
| `chunk` | `{content, is_final: false}` | Token-by-token text delta |
| `tool_call_delta` | partial tool-call JSON | Streaming tool-call assembly |
| `tool_calls` | accumulated tool-calls array | Final tool-call list at stream end |
| `usage` | `{input_tokens, output_tokens, total_tokens}` | Token counts |
| `done` | `{}` | Final marker — stream is complete |
| `error` | `{type, message, retry_after?}` | Provider error mid-stream |

### HTTP error mapping

Provider exceptions are mapped to HTTP status codes:

| Provider exception | HTTP code | Notes |
|--------------------|-----------|-------|
| `AuthenticationError` | `401` | Invalid API key |
| `RateLimitError` | `429` | Includes `retry_after` in response body |
| `ContextLengthError` | `413` | Token budget exceeded |
| `OverloadedError` | `503` | Transient — client should retry |
| `ProviderError` (other) | `502` | Bad upstream response |

### Example client calls

```bash
TOKEN="$(uuidgen)"

# 1. Liveness probe (no auth)
curl http://127.0.0.1:$PORT/health

# 2. Provider catalog
curl -H "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:$PORT/providers

# 3. List OpenAI models
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"provider\":\"openai\",\"api_key\":\"$OPENAI_API_KEY\"}" \
     http://127.0.0.1:$PORT/models

# 4. Single-shot chat
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "messages":[{"role":"user","content":"Hi in 5 words"}],
       "provider":"openai",
       "model":"gpt-4o-mini",
       "api_key":"sk-..."
     }' \
     http://127.0.0.1:$PORT/chat

# 5. SSE streaming
curl -N -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "messages":[{"role":"user","content":"Explain streaming"}],
       "provider":"openai",
       "model":"gpt-4o-mini",
       "stream":true,
       "api_key":"sk-..."
     }' \
     http://127.0.0.1:$PORT/chat/stream
```

### Security model

- **Constant-time token comparison** (`hmac.compare_digest`) defeats timing attacks against the bearer middleware.
- **`--auth-token-fd <fd>`** is the recommended way to pass the token: the parent generates a random GUID, opens a pipe, writes the token once, and closes it. The token never appears in `argv` or `ps` output.
- **Ephemeral port discovery** via stdout (`LISTENING ON host=H port=P`) lets the parent learn the bound port without prior coordination.
- **Parent-PID watchdog** polls `os.kill(parent_pid, 0)` every 5 s and sends SIGTERM to itself when the parent disappears. Avoids zombie sidecars on parent crash.
- **API keys are passed per request**, not stored on the sidecar — a memory-inspection of the sidecar only sees the keys for in-flight requests.

### Public Python API

```python
from eq_chatbot_core.server import create_app, run_server

app = create_app(auth_token="your-token")
run_server(app, host="127.0.0.1", port=8765)
```

Both symbols are lazy proxies — they raise `ImportError` with an actionable message if the `[server]` extra is not installed.

### Reference implementation

The `plan_chatbot_fr_designer.md` document (in repo root) describes a real-world consumer of this sidecar pattern: a C#/Avalonia desktop app that bundles `eq-chatbot-core` as a frozen sidecar, reads the announced port from stdout, and proxies chat traffic to a local HTTP+SSE client.

### See also

- [CLI reference](cli.md#english) — other `eq-chatbot` subcommands
- [Providers](providers.md#english) — provider names and capabilities exposed via `/providers`

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

Seit v1.7.0 kann `eq-chatbot-core` als lokaler HTTP-Sidecar laufen, der die Provider-Abstraktion über REST + Server-Sent Events exponiert. Entwickelt für Apps, die Python nicht direkt einbetten können (Avalonia/.NET, Electron, native iOS/Android).

Der Sidecar bindet ausschließlich auf `127.0.0.1`, unterstützt einen vom OS zugewiesenen ephemeren Port und authentifiziert jeden Nicht-`/health`-Request mit einem Bearer-Token. Token-Vergleich läuft constant-time (`hmac.compare_digest`); ein optionaler Parent-PID-Watchdog beendet den Sidecar wenn der Parent-Prozess verschwindet — verhindert Zombies bei Parent-Crash.

### Installation

Der Server-Mode ist ein optionales Extra und zieht FastAPI, uvicorn und sse-starlette mit:

```bash
uv pip install eq-chatbot-core[server]
```

Reine CLI-/RAG-/MCP-Imports laufen weiterhin ohne diese Pakete — sie werden nur beim Aufruf von `eq-chatbot serve` geladen.

### Sidecar starten

```bash
# Produktiv-Pattern: ephemeral Port, Token via stdin, Parent-Watchdog
echo "$RANDOM_TOKEN" | eq-chatbot serve \
    --port 0 \
    --auth-token-fd 0 \
    --parent-pid $$
# stdout: LISTENING ON host=127.0.0.1 port=NNNN
```

Der Parent-Prozess liest den angekündigten Port aus stdout und nutzt ihn für nachfolgende HTTP-Calls.

#### CLI-Flags

| Flag | Default | Zweck |
|------|---------|-------|
| `--host` | `127.0.0.1` | Bind-Interface. Für Sidecar-Use auf Loopback halten. |
| `--port` | `0` | TCP-Port. `0` = OS-zugewiesen (ephemeral). |
| `--auth-token-fd <fd>` | — | Liest bis 256 Bytes vom angegebenen File-Descriptor (empfohlen). |
| `--auth-token <token>` | — | Argv-basiertes Token (unsicher: in `ps`/`/proc/<pid>/cmdline` sichtbar). |
| `--parent-pid <pid>` | — | Watchdog: pollt `os.kill(pid, 0)` alle 5 s, sendet SIGTERM an sich selbst bei Parent-Exit. |
| `--log-level` | `info` | uvicorn-Log-Level. |

Die Umgebungsvariable `EQ_CHATBOT_AUTH_TOKEN` wird als Fallback akzeptiert wenn kein `--auth-token*`-Flag gesetzt ist.

### Endpunkte

| Methode | Pfad | Auth | Zweck |
|---------|------|------|-------|
| `GET` | `/health` | keine | Liveness-Probe — liefert `{"status":"ok","version":"..."}` |
| `GET` | `/providers` | Bearer | Verfügbarer Provider-Katalog |
| `POST` | `/models` | Bearer | Modell-Liste für einen Provider |
| `POST` | `/chat` | Bearer | Single-Shot Chat-Completion → `LLMResponse` JSON |
| `POST` | `/chat/stream` | Bearer | SSE-Stream von `StreamChunk`-Events |

OpenAPI-/Swagger-UI ist unter `/docs` und `/redoc` erreichbar (auth-frei, gut zum Erkunden).

### SSE-Event-Typen

Der Endpunkt `/chat/stream` emittiert diese benannten Events:

| Event | Payload | Bedeutung |
|-------|---------|-----------|
| `chunk` | `{content, is_final: false}` | Token-für-Token Text-Delta |
| `tool_call_delta` | partielles Tool-Call-JSON | Streaming-Tool-Call-Assembly |
| `tool_calls` | akkumulierte Tool-Call-Liste | Finale Tool-Call-Liste am Stream-Ende |
| `usage` | `{input_tokens, output_tokens, total_tokens}` | Token-Counts |
| `done` | `{}` | Finaler Marker — Stream ist abgeschlossen |
| `error` | `{type, message, retry_after?}` | Provider-Error mid-stream |

### HTTP-Error-Mapping

Provider-Exceptions werden auf HTTP-Status-Codes gemappt:

| Provider-Exception | HTTP-Code | Hinweise |
|--------------------|-----------|----------|
| `AuthenticationError` | `401` | Ungültiger API-Key |
| `RateLimitError` | `429` | Enthält `retry_after` im Body |
| `ContextLengthError` | `413` | Token-Budget überschritten |
| `OverloadedError` | `503` | Transient — Client soll retryen |
| `ProviderError` (sonstige) | `502` | Schlechte Upstream-Antwort |

### Beispiel-Client-Calls

```bash
TOKEN="$(uuidgen)"

# 1. Liveness-Probe (keine Auth)
curl http://127.0.0.1:$PORT/health

# 2. Provider-Katalog
curl -H "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:$PORT/providers

# 3. OpenAI-Modelle listen
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"provider\":\"openai\",\"api_key\":\"$OPENAI_API_KEY\"}" \
     http://127.0.0.1:$PORT/models

# 4. Single-Shot Chat
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "messages":[{"role":"user","content":"Hi in 5 Worten"}],
       "provider":"openai",
       "model":"gpt-4o-mini",
       "api_key":"sk-..."
     }' \
     http://127.0.0.1:$PORT/chat

# 5. SSE-Streaming
curl -N -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "messages":[{"role":"user","content":"Erkläre Streaming"}],
       "provider":"openai",
       "model":"gpt-4o-mini",
       "stream":true,
       "api_key":"sk-..."
     }' \
     http://127.0.0.1:$PORT/chat/stream
```

### Sicherheitsmodell

- **Constant-time Token-Vergleich** (`hmac.compare_digest`) verhindert Timing-Angriffe gegen die Bearer-Middleware.
- **`--auth-token-fd <fd>`** ist die empfohlene Token-Übergabe: Parent generiert eine Random-GUID, öffnet eine Pipe, schreibt das Token einmal und schließt sie. Das Token erscheint nie in `argv`/`ps`.
- **Ephemeral-Port-Discovery** via stdout (`LISTENING ON host=H port=P`) lässt den Parent den gebundenen Port erfahren ohne Vorab-Absprache.
- **Parent-PID-Watchdog** pollt `os.kill(parent_pid, 0)` alle 5 s und schickt SIGTERM an sich selbst wenn der Parent verschwindet. Vermeidet Sidecar-Zombies.
- **API-Keys werden pro Request übergeben**, nicht im Sidecar gespeichert — eine Memory-Inspektion des Sidecars sieht nur Keys für laufende Requests.

### Öffentliche Python-API

```python
from eq_chatbot_core.server import create_app, run_server

app = create_app(auth_token="dein-token")
run_server(app, host="127.0.0.1", port=8765)
```

Beide Symbole sind Lazy-Proxies — sie werfen `ImportError` mit einer aussagekräftigen Meldung, wenn das `[server]`-Extra nicht installiert ist.

### Referenz-Implementierung

Das Dokument `plan_chatbot_fr_designer.md` (im Repo-Root) beschreibt einen realen Konsumenten dieses Sidecar-Patterns: eine C#-/Avalonia-Desktop-App, die `eq-chatbot-core` als gefrorenen Sidecar bundelt, den angekündigten Port aus stdout liest und Chat-Traffic über einen lokalen HTTP+SSE-Client routet.

### Siehe auch

- [CLI-Referenz](cli.md#deutsch) — andere `eq-chatbot`-Subcommands
- [Provider](providers.md#deutsch) — Provider-Namen und Fähigkeiten, exponiert via `/providers`

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
