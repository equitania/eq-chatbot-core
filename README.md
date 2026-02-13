# eq-chatbot-core

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyPI](https://img.shields.io/pypi/v/eq-chatbot-core.svg)

Core library for LLM chatbot integration with multi-provider support.

---

## English

### Overview

**eq-chatbot-core** is a Python library for integrating Large Language Models (LLMs) into your applications. It provides a unified interface for multiple LLM providers, security features, and RAG (Retrieval-Augmented Generation) capabilities.

Originally developed for Odoo 18 chatbot integration, but works standalone without any Odoo dependencies.

### Key Features

- **Multi-Provider Support**: OpenAI, Anthropic, Azure AI, LangDock, OpenRouter, Mammouth AI, Local (LM Studio/Ollama)
- **Unified API**: Same interface regardless of provider
- **Temperature Safety**: Automatic model-specific temperature clamping (GPT-4.1 min=1.0, Claude max=1.0, reasoning models skip)
- **Security**:
  - Fernet encryption for API key storage
  - Prompt injection protection
  - File upload validation
- **RAG Pipeline**:
  - Text chunking with configurable strategies
  - Embedding generation
  - Vector retrieval integration
- **MCP Client**: HTTP/SSE and stdio transports for Model Context Protocol
- **CLI Tool**: Command-line interface for provider testing

### Installation

```bash
# Basic installation
pip install eq-chatbot-core
# Or with UV (recommended)
uv pip install eq-chatbot-core

# With PDF support (for OpenAI/LangDock vision)
pip install eq-chatbot-core[pdf]

# With file validation
pip install eq-chatbot-core[security]

# With Azure AI support
pip install eq-chatbot-core[azure]

# All optional dependencies
pip install eq-chatbot-core[pdf,security,azure,dev]
```

### CLI Usage

```bash
# Test provider connection
eq-chatbot test-provider -p openai -k YOUR_API_KEY

# List available models
eq-chatbot list-models -p anthropic -k YOUR_API_KEY

# Show only vision-capable models
eq-chatbot list-models -p langdock -k YOUR_KEY --vision-only

# Output as JSON
eq-chatbot list-models -p openai -k YOUR_KEY --json

# Show package info
eq-chatbot info
```

### Python Usage

```python
from eq_chatbot_core.providers import get_provider

# Initialize provider
provider = get_provider("openai", api_key="sk-...")

# Simple chat completion
response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gpt-4o"
)
print(response.content)
print(f"Tokens used: {response.total_tokens}")

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Tell me a story"}],
    model="gpt-4o"
):
    print(chunk.content, end="", flush=True)

# List available models
models = provider.list_models()
for model in models:
    print(f"{model.id} - Vision: {model.supports_vision}")
```

### Encryption Example

```python
from eq_chatbot_core.security.encryption import FernetEncryption

# Encrypt API keys for safe storage
encryption = FernetEncryption()
key = encryption.generate_key()

encrypted = encryption.encrypt("sk-your-api-key", key)
decrypted = encryption.decrypt(encrypted, key)
```

### Supported Providers

| Provider | Models | Vision | Streaming | Temp. Clamping |
|----------|--------|--------|-----------|----------------|
| OpenAI | GPT-4, GPT-4o, GPT-4.1, GPT-5, o1, o3, o4 | Yes | Yes | Yes |
| Anthropic | Claude 3, Claude 3.5, Claude 4 | Yes | Yes | Yes |
| Azure AI | GPT-4o, GPT-4.1, o1, o3, o4, Claude, Mistral, Llama, Phi, DeepSeek | Depends on model | Yes | Yes |
| LangDock | All via gateway | Yes | Yes | Yes |
| OpenRouter | 400+ models via gateway | Yes | Yes | Yes |
| Mammouth AI | 30+ models via unified API | Yes | Yes | Yes |
| Local (LM Studio/Ollama) | Local models | No | Yes | No |

---

## Deutsch

### Überblick

**eq-chatbot-core** ist eine Python-Bibliothek zur Integration von Large Language Models (LLMs) in Anwendungen. Sie bietet eine einheitliche Schnittstelle für mehrere LLM-Anbieter, Sicherheitsfunktionen und RAG-Fähigkeiten (Retrieval-Augmented Generation).

Ursprünglich für die Odoo 18 Chatbot-Integration entwickelt, funktioniert aber standalone ohne Odoo-Abhängigkeiten.

### Hauptfunktionen

- **Multi-Provider-Unterstützung**: OpenAI, Anthropic, Azure AI, LangDock, OpenRouter, Mammouth AI, Local (LM Studio/Ollama)
- **Einheitliche API**: Gleiche Schnittstelle unabhängig vom Provider
- **Temperature-Sicherheit**: Automatisches modellspezifisches Temperature-Clamping (GPT-4.1 min=1.0, Claude max=1.0, Reasoning-Modelle werden übersprungen)
- **Sicherheit**:
  - Fernet-Verschlüsselung für API-Key-Speicherung
  - Schutz vor Prompt-Injection
  - Datei-Upload-Validierung
- **RAG-Pipeline**:
  - Text-Chunking mit konfigurierbaren Strategien
  - Embedding-Generierung
  - Vektor-Retrieval-Integration
- **MCP-Client**: HTTP/SSE und stdio Transports für Model Context Protocol
- **CLI-Tool**: Kommandozeilen-Interface für Provider-Tests

### Installation

```bash
# Basis-Installation
pip install eq-chatbot-core
# Oder mit UV (empfohlen)
uv pip install eq-chatbot-core

# Mit PDF-Unterstützung (für OpenAI/LangDock Vision)
pip install eq-chatbot-core[pdf]

# Mit Datei-Validierung
pip install eq-chatbot-core[security]

# Mit Azure AI Unterstützung
pip install eq-chatbot-core[azure]

# Alle optionalen Abhängigkeiten
pip install eq-chatbot-core[pdf,security,azure,dev]
```

### CLI-Verwendung

```bash
# Provider-Verbindung testen
eq-chatbot test-provider -p openai -k YOUR_API_KEY

# Verfügbare Modelle auflisten
eq-chatbot list-models -p anthropic -k YOUR_API_KEY

# Nur Vision-fähige Modelle anzeigen
eq-chatbot list-models -p langdock -k YOUR_KEY --vision-only

# Ausgabe als JSON
eq-chatbot list-models -p openai -k YOUR_KEY --json

# Paket-Informationen anzeigen
eq-chatbot info
```

### Python-Verwendung

```python
from eq_chatbot_core.providers import get_provider

# Provider initialisieren
provider = get_provider("openai", api_key="sk-...")

# Einfache Chat-Completion
response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="gpt-4o"
)
print(response.content)
print(f"Tokens verwendet: {response.total_tokens}")

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Erzähle mir eine Geschichte"}],
    model="gpt-4o"
):
    print(chunk.content, end="", flush=True)
```

---

## Technical Information

| Field | Value |
|-------|-------|
| **Package Name** | eq-chatbot-core |
| **Version** | 1.1.0 |
| **Author** | Equitania Software GmbH |
| **License** | MIT |
| **Python** | >=3.10 |
| **Homepage** | https://www.ownerp.com |

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
