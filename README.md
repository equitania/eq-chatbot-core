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

- **Multi-Provider Support** — OpenAI, Anthropic, Azure AI, Google Vertex AI, LangDock, OpenRouter, Mammouth AI, Local (LM Studio/Ollama)
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

---

## Deutsch

### Überblick

**eq-chatbot-core** ist eine Python-Bibliothek zur Integration von Large Language Models (LLMs) in Anwendungen. Bietet eine einheitliche Schnittstelle über Cloud- und lokale Provider, Security-Primitives, einen MCP-Client, eine RAG-Pipeline und einen optionalen HTTP/SSE-Sidecar — aus jeder Sprache nutzbar.

Ursprünglich aus einer Odoo-18-Chatbot-Integration extrahiert; funktioniert standalone ohne Odoo-Abhängigkeit.

### Hauptfunktionen

- **Multi-Provider-Unterstützung** — OpenAI, Anthropic, Azure AI, Google Vertex AI, LangDock, OpenRouter, Mammouth AI, Local (LM Studio/Ollama)
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

---

## Technical Information

| Field | Value |
|-------|-------|
| **Package Name** | eq-chatbot-core |
| **Version** | 1.7.0 |
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
