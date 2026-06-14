# eq-chatbot-core

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyPI](https://img.shields.io/pypi/v/eq-chatbot-core.svg)

Core library for LLM chatbot integration with multi-provider support.

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

**eq-chatbot-core** is a Python library for integrating Large Language Models (LLMs) into your applications. It provides a unified interface across cloud and local providers, security primitives, an MCP client, a RAG pipeline, and an optional HTTP/SSE sidecar — usable from any language.

Originally extracted from an Odoo 18 chatbot integration; works standalone without any Odoo dependency.

### Key Features

- **Multi-Provider Support** — OpenAI, Anthropic, Azure AI, Google Vertex AI, LangDock, OpenRouter, Mammouth AI, LiteLLM gateway, IONOS AI Model Hub (EU-hosted), Local (LM Studio/Ollama)
- **Unified API** — same interface regardless of provider
- **Temperature Safety** — automatic model-specific temperature clamping
- **Security** — Fernet encryption, prompt-injection detection, file-upload validation, token-bucket rate limiting
- **RAG Pipeline** — chunking, embeddings, Qdrant-backed retrieval, context-window management
- **MCP Client** — HTTP/SSE and stdio transports, hardened against DNS rebinding and SSRF
- **CLI Tool** — provider testing, model discovery, programmatic JSON I/O chat
- **HTTP/SSE Server Mode** (v1.7.0) — run as a local sidecar (`eq-chatbot serve`) for cross-language integrations (Avalonia/.NET, Electron, native mobile)

### Installation

```bash
# Basic installation
uv pip install eq-chatbot-core
# (or: pip install eq-chatbot-core)

# With optional extras
uv pip install eq-chatbot-core[pdf]       # PDF→image conversion (vision)
uv pip install eq-chatbot-core[security]  # MIME-type file validation
uv pip install eq-chatbot-core[azure]     # Azure AI Foundry
uv pip install eq-chatbot-core[vertex]    # Google Vertex AI
uv pip install eq-chatbot-core[server]    # HTTP/SSE sidecar (FastAPI + uvicorn)
uv pip install eq-chatbot-core[local]     # Local sentence-transformers embeddings

# All optional dependencies
uv pip install eq-chatbot-core[pdf,security,azure,vertex,server,local,dev]
```

### Quick Start

```python
from eq_chatbot_core.providers import get_provider

provider = get_provider("openai", api_key="sk-...")

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gpt-4o",
)
print(response.content)
```

For more — streaming, other providers, ADC for Vertex, error handling — see [docs/providers.md](docs/providers.md).

### Documentation

| Topic | Docs |
|-------|------|
| Multi-provider integration | [docs/providers.md](docs/providers.md#english) |
| CLI commands | [docs/cli.md](docs/cli.md#english) |
| HTTP/SSE server mode | [docs/server-mode.md](docs/server-mode.md#english) |
| Security (encryption, injection, files, rate limit) | [docs/security.md](docs/security.md#english) |
| MCP client (HTTP/SSE + stdio) | [docs/mcp.md](docs/mcp.md#english) |
| RAG pipeline (chunking, embedding, retrieval) | [docs/rag.md](docs/rag.md#english) |
| Testing (markers, integration setup, cost-aware patterns) | [docs/testing.md](docs/testing.md) |

### Realtime Providers

#### ElevenLabs (Recommended GDPR Provider)

ElevenLabs Conversational AI (`"elevenlabs"`) is the recommended provider for EU/GDPR deployments.

```python
from eq_chatbot_core.realtime import get_realtime_provider

provider = get_realtime_provider(
    "elevenlabs",
    api_key="xi-...",
    agent_id="YOUR_AGENT_ID",
)
```

OpenAI Realtime and Gemini Live remain supported providers. ElevenLabs is recommended for
EU-regulated deployments because it offers an enterprise-grade EU data residency path.

##### Full EU Compliance Checklist

Four conditions must ALL be met for complete data residency compliance:

1. **Enterprise plan** — EU data residency is available on the Enterprise plan only.
   Standard and Creator plans route data through US infrastructure.

2. **Zero Retention Mode** — Enable Zero Retention Mode in the ElevenLabs Enterprise
   dashboard and confirm it via the Zero Retention API. Covers TTS, STT, and Conversational
   AI sessions. Voice cloning models are excluded (see caveat below).

3. **EU-hosted Custom LLM backend** — ElevenLabs Agents orchestrate an LLM under the
   hood. For full EU residency, configure a Custom LLM endpoint hosted in the EU
   (e.g. Azure OpenAI EU region, or a self-hosted model in an EU data centre).
   Configure this in the ElevenLabs dashboard, not in the adapter.

4. **EU data-residency endpoint** — Pass the EU base URL as `base_url`:

   ```python
   from eq_chatbot_core.realtime import get_realtime_provider

   provider = get_realtime_provider(
       "elevenlabs",
       api_key="YOUR_EU_API_KEY",   # EU key — different from global key
       agent_id="YOUR_AGENT_ID",
       base_url="wss://api.eu.residency.elevenlabs.io",
   )
   ```

   > **Important:** The EU API key is a **separate key** provisioned by ElevenLabs
   > Enterprise support. Your global `xi-api-key` will return 403 Forbidden on the
   > EU endpoint.

##### Voice Cloning Caveat

Voice cloning models are **not eligible for Zero Retention Mode** — cloned voice
model data persists in ElevenLabs infrastructure. If your use case requires voice
cloning, assess whether that data qualifies as personal data under GDPR before
deploying in an EU-regulated context.

### Security: caller responsibilities

The `eq_chatbot_core.security` module provides **caller-invoked primitives, not
automatic guardrails**. Provider calls perform no implicit prompt-injection
filtering or rate limiting — you must invoke these explicitly when handling
untrusted input:

```python
from eq_chatbot_core.providers import get_provider
from eq_chatbot_core.security import check_rate_limit, detect_injection

# 1. Rate-limit per user BEFORE calling the provider
result = check_rate_limit(user_id, config, storage, estimated_tokens=tokens)
if not result.allowed:
    raise RuntimeError(f"Rate limit exceeded, retry after {result.retry_after}s")

# 2. Screen untrusted input for prompt injection
if detect_injection(user_message):
    raise ValueError("Potential prompt injection detected")

provider = get_provider("openai", api_key="sk-...")
response = provider.chat_completion([{"role": "user", "content": user_message}])
```

Additional hardening notes:

- **File uploads:** `FileValidator` falls back to extension-only checks when the
  `[security]` extra (puremagic) is not installed. For untrusted uploads, construct
  it with `FileValidator(require_magic=True)` to fail closed, or inspect
  `FileValidationResult.mime_verified`.
- **Local provider `base_url`:** validated against non-HTTP schemes and
  cloud-metadata / link-local targets; private LAN ranges remain allowed since
  local model servers legitimately live there.
- **API keys / secrets** are never logged by the library; upstream error bodies
  surfaced in logs and exceptions are scrubbed via `utils.scrub_secrets`.

---

## Deutsch

### Überblick

**eq-chatbot-core** ist eine Python-Bibliothek zur Integration von Large Language Models (LLMs) in Anwendungen. Bietet eine einheitliche Schnittstelle über Cloud- und lokale Provider, Security-Primitives, einen MCP-Client, eine RAG-Pipeline und einen optionalen HTTP/SSE-Sidecar — aus jeder Sprache nutzbar.

Ursprünglich aus einer Odoo-18-Chatbot-Integration extrahiert; funktioniert standalone ohne Odoo-Abhängigkeit.

### Hauptfunktionen

- **Multi-Provider-Unterstützung** — OpenAI, Anthropic, Azure AI, Google Vertex AI, LangDock, OpenRouter, Mammouth AI, LiteLLM-Gateway, IONOS AI Model Hub (EU-gehostet), Local (LM Studio/Ollama)
- **Einheitliche API** — gleiche Schnittstelle unabhängig vom Provider
- **Temperature-Sicherheit** — automatisches modellspezifisches Temperature-Clamping
- **Sicherheit** — Fernet-Verschlüsselung, Prompt-Injection-Erkennung, File-Upload-Validierung, Token-Bucket-Rate-Limiting
- **RAG-Pipeline** — Chunking, Embeddings, Qdrant-basiertes Retrieval, Context-Window-Management
- **MCP-Client** — HTTP/SSE und stdio Transports, gehärtet gegen DNS-Rebinding und SSRF
- **CLI-Tool** — Provider-Tests, Modell-Discovery, programmatische JSON-I/O-Chat-Calls
- **HTTP/SSE-Server-Mode** (v1.7.0) — lokaler Sidecar (`eq-chatbot serve`) für Cross-Language-Integrationen (Avalonia/.NET, Electron, native Mobile)

### Installation

```bash
# Basis-Installation
uv pip install eq-chatbot-core
# (oder: pip install eq-chatbot-core)

# Mit optionalen Extras
uv pip install eq-chatbot-core[pdf]       # PDF→Bild-Konvertierung (Vision)
uv pip install eq-chatbot-core[security]  # MIME-Type-File-Validation
uv pip install eq-chatbot-core[azure]     # Azure AI Foundry
uv pip install eq-chatbot-core[vertex]    # Google Vertex AI
uv pip install eq-chatbot-core[server]    # HTTP/SSE-Sidecar (FastAPI + uvicorn)
uv pip install eq-chatbot-core[local]     # Lokale sentence-transformers-Embeddings

# Alle optionalen Abhängigkeiten
uv pip install eq-chatbot-core[pdf,security,azure,vertex,server,local,dev]
```

### Quick Start

```python
from eq_chatbot_core.providers import get_provider

provider = get_provider("openai", api_key="sk-...")

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="gpt-4o",
)
print(response.content)
```

Für mehr — Streaming, andere Provider, ADC für Vertex, Error-Handling — siehe [docs/providers.md](docs/providers.md).

### Dokumentation

| Thema | Docs |
|-------|------|
| Multi-Provider-Integration | [docs/providers.md](docs/providers.md#deutsch) |
| CLI-Befehle | [docs/cli.md](docs/cli.md#deutsch) |
| HTTP/SSE-Server-Mode | [docs/server-mode.md](docs/server-mode.md#deutsch) |
| Security (Verschlüsselung, Injection, Files, Rate-Limit) | [docs/security.md](docs/security.md#deutsch) |
| MCP-Client (HTTP/SSE + stdio) | [docs/mcp.md](docs/mcp.md#deutsch) |
| RAG-Pipeline (Chunking, Embedding, Retrieval) | [docs/rag.md](docs/rag.md#deutsch) |
| Testing (Marker, Integration-Setup, Cost-Aware-Patterns) | [docs/testing.md](docs/testing.md) |

### Sicherheit: Verantwortung des Aufrufers

Das Modul `eq_chatbot_core.security` stellt **vom Aufrufer aktiv aufzurufende
Primitive bereit, keine automatischen Schutzmechanismen**. Provider-Aufrufe
filtern Eingaben weder auf Prompt-Injection noch erzwingen sie Rate-Limits — bei
nicht vertrauenswürdigen Eingaben müssen `detect_injection` und
`check_rate_limit` vor dem Provider-Call explizit aufgerufen werden (Beispiel
siehe englische Sektion „Security: caller responsibilities" oben).

Weitere Härtungshinweise:

- **Datei-Uploads:** Für nicht vertrauenswürdige Uploads `FileValidator(require_magic=True)`
  verwenden (fail-closed ohne `puremagic`) bzw. `FileValidationResult.mime_verified` prüfen.
- **Local-Provider `base_url`:** gegen Nicht-HTTP-Schemes und Cloud-Metadata-/Link-Local-Ziele
  validiert; private LAN-Ranges bleiben erlaubt.
- **API-Keys/Secrets** werden nie geloggt; geleakte Upstream-Error-Bodies werden via
  `utils.scrub_secrets` maskiert.

---

## Technical Information

| Field | Value |
|-------|-------|
| **Package Name** | eq-chatbot-core |
| **Version** | 1.10.0 |
| **Author** | Equitania Software GmbH |
| **Contact** | info@ownerp.com |
| **License** | MIT |
| **Python** | >=3.10 |
| **Homepage** | https://www.ownerp.com |
| **Repository** | https://github.com/equitania/eq-chatbot-core |

## Contributing

Contributions are welcome. Please open an issue or submit a pull request.

## License

MIT — see [LICENSE](LICENSE).
