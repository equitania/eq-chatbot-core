# eq-chatbot-core

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![PyPI](https://img.shields.io/pypi/v/eq-chatbot-core.svg)

Core library for LLM chatbot integration with multi-provider support.

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

**eq-chatbot-core** is a Python library for integrating Large Language Models (LLMs) into your applications. It provides a unified interface across cloud and local providers, security primitives, an MCP client, a RAG pipeline, and an optional HTTP/SSE sidecar — usable from any language.

Originally extracted from an Odoo 18 chatbot integration; works standalone without any Odoo dependency.

### Key Features

- **Multi-Provider Support** — OpenAI, Anthropic, LangDock, OpenRouter, Mammouth AI, LiteLLM gateway, IONOS AI Model Hub (EU-hosted), Melious.ai (sovereign EU), Privatemode.ai (end-to-end encrypted, EU), Local (LM Studio/Ollama)
- **Unified API** — same interface regardless of provider
- **Temperature Safety** — automatic model-specific temperature clamping
- **Security** — Fernet encryption, prompt-injection detection (direct user input + indirect tool/RAG content), file-upload validation, race-free token-bucket rate limiting
- **RAG Pipeline** — chunking, embeddings (incl. Melious.ai and IONOS embedders), Qdrant-backed retrieval, context-window management
- **MCP Client** — HTTP/SSE and stdio transports, hardened against DNS rebinding, SSRF, and subprocess env injection
- **CLI Tool** — provider testing, model discovery, programmatic JSON I/O chat
- **Text-to-Image Generation** (v1.14.0) — `eq-chatbot image` (single PNG) and `eq-chatbot listing-assets` (batch from a recipe); OpenAI `gpt-image-1` and OpenRouter image models
- **HTTP/SSE Server Mode** (v1.7.0) — run as a local sidecar (`eq-chatbot serve`) for cross-language integrations (Avalonia/.NET, Electron, native mobile)

> **Breaking in v3.0.0 — Azure and Vertex AI providers removed:** `get_provider("azure")` and
> `get_provider("vertex")` now raise `ValueError`. Neither is in day-to-day use here, and both
> were the only providers carrying a hand-maintained static model catalog. Google and Microsoft
> models stay reachable live through `langdock` and `openrouter`. The `gemini_live` realtime
> provider is unaffected. `qdrant-client` also moved out of the core install into a new `[rag]`
> extra (it pulled in ~37 MB of grpcio for every install). See RELEASE_NOTES.md.

> **Breaking in v3.0.0 — cost calculation removed:** `calculate_cost()`, `PRICING`,
> `PricingCatalog`, the bundled price snapshot and the per-model cost fields in `list_models()`
> are gone with no replacement. Some providers reported prices and others did not, and the
> bundled rates went stale between releases, so the numbers were a mix of accurate, missing and
> silently wrong. Every provider shows actual spend in its own dashboard — read it there. See
> RELEASE_NOTES.md for the full list of removed symbols.

> **Breaking in v2.1.0 — two changes:**
> 1. **Minimum Python is now 3.12** (was 3.10), aligned with the interpreter used for Odoo 16.
>    Python 3.10 reaches end of life on 2026-10-31; 3.11 is dropped in the same step so there is
>    one supported baseline. Installs on 3.10/3.11 now fail at resolution time.
> 2. **`openai` floor raised to `>=3.0.0`.** This library's networking moved to `httpx2`
>    (Pydantic's maintained continuation of httpx), which openai 3.x also uses. `httpx` stays a
>    dependency and is not redundant: the Anthropic SDK still requires `httpx<1`, so that one
>    provider keeps using it. Pin `eq-chatbot-core>=2.1.0` only where openai 3.x is acceptable.
>
> **Security:** v2.1.0 closes a DNS-rebinding hole that affected every LLM provider — see
> RELEASE_NOTES.md. Upgrading is recommended for anyone who lets callers supply a `base_url`.

### Installation

```bash
# Basic installation
uv pip install eq-chatbot-core
# (or: pip install eq-chatbot-core)

# With optional extras
uv pip install eq-chatbot-core[pdf]       # PDF→image conversion (vision)
uv pip install eq-chatbot-core[security]  # MIME-type file validation
uv pip install eq-chatbot-core[rag]       # Qdrant vector retrieval
uv pip install eq-chatbot-core[image]     # Text-to-image generation (Pillow)
uv pip install eq-chatbot-core[realtime]  # Realtime voice providers (websockets)
uv pip install eq-chatbot-core[server]    # HTTP/SSE sidecar (FastAPI + uvicorn)
uv pip install eq-chatbot-core[local]     # Local sentence-transformers embeddings

# All optional dependencies
uv pip install eq-chatbot-core[pdf,security,rag,image,realtime,server,local,dev]
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

For more — streaming, other providers, error handling — see [docs/providers.md](docs/providers.md).

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
from eq_chatbot_core.security import enforce_rate_limit, detect_injection, scan_external_content

# 1. Rate-limit per user BEFORE calling the provider (race-free: prefers an
#    atomic storage backend, else falls back to check + record).
result = enforce_rate_limit(user_id, company_id, config, storage, estimated_tokens=tokens)
if not result.allowed:
    raise RuntimeError(f"Rate limit exceeded, retry after {result.retry_after}s")

# 2. Screen untrusted USER input for prompt injection (returns a tuple).
is_suspicious, matched = detect_injection(user_message)
if is_suspicious:
    raise ValueError(f"Potential prompt injection detected: {matched!r}")

# 3. Screen INDIRECT channels too — MCP tool results and retrieved RAG passages.
tool_suspicious, _ = scan_external_content(tool_result, source="tool:get_orders")

provider = get_provider("openai", api_key="sk-...")
response = provider.chat_completion([{"role": "user", "content": user_message}])
```

Additional hardening notes:

- **Indirect injection:** apply `scan_external_content` / `wrap_external_content`
  to tool results and retrieved RAG passages before placing them in the LLM
  context — `detect_injection` covers user input only by convention.
- **File uploads:** `FileValidator` falls back to extension-only checks when the
  `[security]` extra (puremagic) is not installed. For untrusted uploads, construct
  it with `FileValidator(require_magic=True)` to fail closed, or inspect
  `FileValidationResult.mime_verified`.
- **Provider `base_url`:** validated against non-HTTP schemes and
  cloud-metadata / link-local targets. In strict mode an unresolvable hostname is
  rejected (closing a DNS-rebinding gap); LAN mode (local providers) still allows
  private ranges since local model servers legitimately live there.
- **MCP stdio env:** caller-supplied environment variables carrying loader/startup
  code-injection keys (`LD_PRELOAD`, `PYTHONSTARTUP`, …) are refused.
- **API keys / secrets** are never logged by the library; upstream error bodies
  surfaced in logs and exceptions are scrubbed via `utils.scrub_secrets`.

---

## Deutsch

### Überblick

**eq-chatbot-core** ist eine Python-Bibliothek zur Integration von Large Language Models (LLMs) in Anwendungen. Bietet eine einheitliche Schnittstelle über Cloud- und lokale Provider, Security-Primitives, einen MCP-Client, eine RAG-Pipeline und einen optionalen HTTP/SSE-Sidecar — aus jeder Sprache nutzbar.

Ursprünglich aus einer Odoo-18-Chatbot-Integration extrahiert; funktioniert standalone ohne Odoo-Abhängigkeit.

### Hauptfunktionen

- **Multi-Provider-Unterstützung** — OpenAI, Anthropic, LangDock, OpenRouter, Mammouth AI, LiteLLM-Gateway, IONOS AI Model Hub (EU-gehostet), Melious.ai (souverän EU), Privatemode.ai (Ende-zu-Ende-verschlüsselt, EU), Local (LM Studio/Ollama)
- **Einheitliche API** — gleiche Schnittstelle unabhängig vom Provider
- **Temperature-Sicherheit** — automatisches modellspezifisches Temperature-Clamping
- **Sicherheit** — Fernet-Verschlüsselung, Prompt-Injection-Erkennung (direkte Nutzereingaben + indirekte Tool-/RAG-Inhalte), File-Upload-Validierung, Race-freies Token-Bucket-Rate-Limiting
- **RAG-Pipeline** — Chunking, Embeddings (inkl. Melious.ai- und IONOS-Embedder), Qdrant-basiertes Retrieval, Context-Window-Management
- **MCP-Client** — HTTP/SSE und stdio Transports, gehärtet gegen DNS-Rebinding, SSRF und Subprocess-Env-Injection
- **CLI-Tool** — Provider-Tests, Modell-Discovery, programmatische JSON-I/O-Chat-Calls
- **Text-zu-Bild-Generierung** (v1.14.0) — `eq-chatbot image` (einzelnes PNG) und `eq-chatbot listing-assets` (Batch aus einer Recipe); OpenAI `gpt-image-1` und OpenRouter-Bildmodelle
- **HTTP/SSE-Server-Mode** (v1.7.0) — lokaler Sidecar (`eq-chatbot serve`) für Cross-Language-Integrationen (Avalonia/.NET, Electron, native Mobile)

> **Breaking in v3.0.0 — die Provider Azure und Vertex AI entfallen:** `get_provider("azure")`
> und `get_provider("vertex")` werfen jetzt `ValueError`. Beide werden hier im Alltag nicht
> genutzt und waren die einzigen Provider mit handgepflegtem statischem Modellkatalog.
> Google- und Microsoft-Modelle bleiben über `langdock` und `openrouter` live erreichbar. Der
> Realtime-Provider `gemini_live` ist nicht betroffen. `qdrant-client` ist außerdem aus der
> Core-Installation in das neue Extra `[rag]` gewandert (es zog ~37 MB grpcio in jede
> Installation). Details in RELEASE_NOTES.md.

> **Breaking in v3.0.0 — die Kostenberechnung entfällt:** `calculate_cost()`, `PRICING`,
> `PricingCatalog`, der mitgelieferte Preis-Snapshot und die Kostenfelder in `list_models()`
> sind ersatzlos entfernt. Manche Anbieter lieferten Preise, andere nicht, und die
> mitgelieferten Sätze veralteten zwischen den Releases — heraus kam eine Mischung aus
> korrekten, fehlenden und still falschen Zahlen. Jeder Anbieter zeigt die tatsächlichen
> Kosten in seinem eigenen Dashboard. Die vollständige Liste der entfernten Symbole steht in
> RELEASE_NOTES.md.

> **Breaking in v2.1.0 — zwei Änderungen:**
> 1. **Mindest-Python ist jetzt 3.12** (vorher 3.10), abgestimmt auf den unter Odoo 16 verwendeten
>    Interpreter. Python 3.10 erreicht am 31.10.2026 sein Lebensende; 3.11 entfällt im selben
>    Schritt, damit es genau eine unterstützte Basis gibt. Installationen auf 3.10/3.11 schlagen
>    jetzt bereits bei der Auflösung fehl.
> 2. **`openai`-Untergrenze auf `>=3.0.0` angehoben.** Das Networking dieser Bibliothek läuft jetzt
>    über `httpx2` (Pydantics gepflegte Fortführung von httpx), das auch openai 3.x nutzt. `httpx`
>    bleibt als Abhängigkeit bestehen und ist nicht überflüssig: Das Anthropic-SDK verlangt weiterhin
>    `httpx<1`, dieser eine Provider nutzt es also weiter. `eq-chatbot-core>=2.1.0` nur dort pinnen,
>    wo openai 3.x akzeptabel ist.
>
> **Sicherheit:** v2.1.0 schließt eine DNS-Rebinding-Lücke, die alle LLM-Provider betraf — Details in
> RELEASE_NOTES.md. Ein Upgrade ist für alle empfohlen, die Aufrufer eine `base_url` setzen lassen.

### Installation

```bash
# Basis-Installation
uv pip install eq-chatbot-core
# (oder: pip install eq-chatbot-core)

# Mit optionalen Extras
uv pip install eq-chatbot-core[pdf]       # PDF→Bild-Konvertierung (Vision)
uv pip install eq-chatbot-core[security]  # MIME-Type-File-Validation
uv pip install eq-chatbot-core[rag]       # Qdrant vector retrieval
uv pip install eq-chatbot-core[image]     # Text-zu-Bild-Generierung (Pillow)
uv pip install eq-chatbot-core[realtime]  # Realtime-Voice-Provider (websockets)
uv pip install eq-chatbot-core[server]    # HTTP/SSE-Sidecar (FastAPI + uvicorn)
uv pip install eq-chatbot-core[local]     # Lokale sentence-transformers-Embeddings

# Alle optionalen Abhängigkeiten
uv pip install eq-chatbot-core[pdf,security,rag,image,realtime,server,local,dev]
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

Für mehr — Streaming, andere Provider, Error-Handling — siehe [docs/providers.md](docs/providers.md).

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
nicht vertrauenswürdigen Eingaben müssen `detect_injection` /
`scan_external_content` und `enforce_rate_limit` vor dem Provider-Call explizit
aufgerufen werden (Beispiel siehe englische Sektion „Security: caller
responsibilities" oben). Hinweis: `detect_injection` liefert ein Tuple
`(is_suspicious, matched)` — den ersten Wert auswerten, nicht das Tuple selbst.

Weitere Härtungshinweise:

- **Indirekte Injection:** `scan_external_content` / `wrap_external_content` auf Tool-Ergebnisse
  und abgerufene RAG-Passagen anwenden, bevor sie in den LLM-Kontext gelangen — `detect_injection`
  deckt konventionsgemäß nur Nutzereingaben ab.
- **Datei-Uploads:** Für nicht vertrauenswürdige Uploads `FileValidator(require_magic=True)`
  verwenden (fail-closed ohne `puremagic`) bzw. `FileValidationResult.mime_verified` prüfen.
- **Provider `base_url`:** gegen Nicht-HTTP-Schemes und Cloud-Metadata-/Link-Local-Ziele
  validiert; im Strict-Mode wird ein nicht auflösbarer Hostname abgelehnt (schließt eine
  DNS-Rebinding-Lücke), im LAN-Mode (lokale Provider) bleiben private Ranges erlaubt.
- **MCP-stdio-Env:** vom Aufrufer übergebene Umgebungsvariablen mit Loader-/Startup-Code-Injection-
  Schlüsseln (`LD_PRELOAD`, `PYTHONSTARTUP`, …) werden abgelehnt.
- **API-Keys/Secrets** werden nie geloggt; geleakte Upstream-Error-Bodies werden via
  `utils.scrub_secrets` maskiert.

---

## Technical Information

| Field | Value |
|-------|-------|
| **Package Name** | eq-chatbot-core |
| **Version** | 3.0.0 |
| **Author** | Equitania Software GmbH |
| **Contact** | info@ownerp.com |
| **License** | MIT |
| **Python** | >=3.12 |
| **Homepage** | https://www.ownerp.com |
| **Repository** | https://github.com/equitania/eq-chatbot-core |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |

## Contributing

Contributions are welcome. Please open an issue or submit a pull request.

## License

MIT — see [LICENSE](LICENSE).
