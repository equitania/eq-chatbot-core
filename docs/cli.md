# CLI Reference — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

`eq-chatbot-core` ships a Click-based CLI named `eq-chatbot`. Five subcommands cover provider testing, model discovery, programmatic chat I/O, the HTTP/SSE sidecar, and package introspection.

```bash
eq-chatbot --help
```

### Subcommands

#### `eq-chatbot info`

Print the package version, installed extras, and Python version. Useful for bug reports.

```bash
eq-chatbot info
```

#### `eq-chatbot test-provider`

Smoke-test a provider connection by sending a single chat completion. Exits non-zero on auth or transport errors.

```bash
eq-chatbot test-provider -p openai -k $OPENAI_API_KEY
eq-chatbot test-provider -p anthropic -k sk-ant-... -m claude-3-5-sonnet-20241022
eq-chatbot test-provider -p local --base-url http://localhost:1234/v1
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Provider name (`openai`, `anthropic`, `azure`, `vertex`, `langdock`, `openrouter`, `mammouth`, `local`, `lm_studio`, `ollama`) |
| `-k`, `--api-key` | API key (cloud providers only) |
| `-m`, `--model` | Model id (defaults to provider's `default_model`) |
| `--message` | Custom test prompt (default: a short greeting) |
| `--base-url` | Custom endpoint (Azure, local OpenAI-compatible) |

#### `eq-chatbot list-models`

List models available from a provider. Output is human-readable by default; pass `--json` for machine consumption.

```bash
eq-chatbot list-models -p openai -k YOUR_KEY
eq-chatbot list-models -p langdock -k YOUR_KEY --vision-only
eq-chatbot list-models -p anthropic -k YOUR_KEY --json
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Provider name |
| `-k`, `--api-key` | API key |
| `--base-url` | Custom endpoint |
| `--json` | Output as JSON array of model objects |
| `--vision-only` | Filter to vision-capable models |

#### `eq-chatbot chat`

Single-turn chat with JSON I/O — designed for integration with tools that don't speak Python (Rust, Go, Bash). Reads a JSON envelope from stdin, writes the result to stdout, errors as JSON to stderr with non-zero exit.

```bash
echo '{"messages":[{"role":"user","content":"Hello"}]}' | \
    eq-chatbot chat -p openai -k YOUR_KEY

# Output: {"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}
```

**Input schema** (stdin):

```json
{
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Question here"}
  ]
}
```

Stdin is capped at **1 MB** to avoid runaway memory usage.

**Output schema** (stdout):

```json
{
  "content": "model response text",
  "model": "gpt-4o-mini",
  "input_tokens": 42,
  "output_tokens": 17
}
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Provider name |
| `-k`, `--api-key` | API key (or set `LLM_API_KEY` env) |
| `-m`, `--model` | Model id |
| `-t`, `--temperature` | Sampling temperature (clamped per provider rules) |
| `--max-tokens` | Output token cap |
| `--base-url` | Custom endpoint |

This subcommand was added in v1.5.0 and is used by external tools like the sysReporter Rust CLI.

#### `eq-chatbot serve`

Start the local HTTP/SSE sidecar. See [server-mode.md](server-mode.md) for the full reference.

```bash
echo "$TOKEN" | eq-chatbot serve --port 0 --auth-token-fd 0 --parent-pid $$
```

### Environment variables

| Variable | Purpose | Used by |
|----------|---------|---------|
| `LLM_API_KEY` | Fallback API key when `-k`/`--api-key` is not given | `chat` |
| `EQ_CHATBOT_AUTH_TOKEN` | Fallback bearer token when no `--auth-token*` flag is given | `serve` |

### See also

- [Providers](providers.md#english) — provider names accepted by `-p`
- [Server mode](server-mode.md#english) — full reference for `eq-chatbot serve`

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

`eq-chatbot-core` liefert ein Click-basiertes CLI namens `eq-chatbot`. Fünf Subcommands decken Provider-Tests, Modell-Discovery, programmatische Chat-I/O, den HTTP/SSE-Sidecar und Paket-Introspektion ab.

```bash
eq-chatbot --help
```

### Subcommands

#### `eq-chatbot info`

Gibt Paket-Version, installierte Extras und Python-Version aus. Nützlich für Bug-Reports.

```bash
eq-chatbot info
```

#### `eq-chatbot test-provider`

Smoke-Test einer Provider-Verbindung über eine einzelne Chat-Completion. Exit-Code != 0 bei Auth-/Transport-Fehlern.

```bash
eq-chatbot test-provider -p openai -k $OPENAI_API_KEY
eq-chatbot test-provider -p anthropic -k sk-ant-... -m claude-3-5-sonnet-20241022
eq-chatbot test-provider -p local --base-url http://localhost:1234/v1
```

| Flag | Zweck |
|------|-------|
| `-p`, `--provider` | Provider-Name (`openai`, `anthropic`, `azure`, `vertex`, `langdock`, `openrouter`, `mammouth`, `local`, `lm_studio`, `ollama`) |
| `-k`, `--api-key` | API-Key (nur Cloud-Provider) |
| `-m`, `--model` | Modell-ID (Default: `default_model` des Providers) |
| `--message` | Eigener Test-Prompt (Default: kurzer Gruß) |
| `--base-url` | Eigener Endpoint (Azure, lokale OpenAI-kompatible) |

#### `eq-chatbot list-models`

Listet verfügbare Modelle eines Providers. Default human-readable; `--json` für maschinelle Verarbeitung.

```bash
eq-chatbot list-models -p openai -k YOUR_KEY
eq-chatbot list-models -p langdock -k YOUR_KEY --vision-only
eq-chatbot list-models -p anthropic -k YOUR_KEY --json
```

| Flag | Zweck |
|------|-------|
| `-p`, `--provider` | Provider-Name |
| `-k`, `--api-key` | API-Key |
| `--base-url` | Eigener Endpoint |
| `--json` | Ausgabe als JSON-Array von Modell-Objekten |
| `--vision-only` | Auf vision-fähige Modelle filtern |

#### `eq-chatbot chat`

Single-Turn-Chat mit JSON-I/O — für Integration mit Tools, die kein Python sprechen (Rust, Go, Bash). Liest JSON-Envelope von stdin, schreibt Ergebnis nach stdout, Fehler als JSON nach stderr mit non-zero Exit.

```bash
echo '{"messages":[{"role":"user","content":"Hallo"}]}' | \
    eq-chatbot chat -p openai -k YOUR_KEY

# Ausgabe: {"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}
```

**Input-Schema** (stdin):

```json
{
  "messages": [
    {"role": "system", "content": "Du bist hilfreich."},
    {"role": "user", "content": "Frage hier"}
  ]
}
```

Stdin ist auf **1 MB** begrenzt um Runaway-Memory zu vermeiden.

**Output-Schema** (stdout):

```json
{
  "content": "Modell-Antwort",
  "model": "gpt-4o-mini",
  "input_tokens": 42,
  "output_tokens": 17
}
```

| Flag | Zweck |
|------|-------|
| `-p`, `--provider` | Provider-Name |
| `-k`, `--api-key` | API-Key (oder `LLM_API_KEY`-Env) |
| `-m`, `--model` | Modell-ID |
| `-t`, `--temperature` | Sampling-Temperatur (per Provider-Regel geclampt) |
| `--max-tokens` | Output-Token-Cap |
| `--base-url` | Eigener Endpoint |

Dieser Subcommand wurde in v1.5.0 hinzugefügt und wird z.B. vom sysReporter-Rust-CLI verwendet.

#### `eq-chatbot serve`

Startet den lokalen HTTP/SSE-Sidecar. Vollständige Referenz: [server-mode.md](server-mode.md).

```bash
echo "$TOKEN" | eq-chatbot serve --port 0 --auth-token-fd 0 --parent-pid $$
```

### Umgebungsvariablen

| Variable | Zweck | Genutzt von |
|----------|-------|-------------|
| `LLM_API_KEY` | Fallback-API-Key wenn `-k`/`--api-key` fehlt | `chat` |
| `EQ_CHATBOT_AUTH_TOKEN` | Fallback-Bearer-Token wenn kein `--auth-token*`-Flag | `serve` |

### Siehe auch

- [Provider](providers.md#deutsch) — Provider-Namen für `-p`
- [Server-Mode](server-mode.md#deutsch) — vollständige Referenz für `eq-chatbot serve`

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
