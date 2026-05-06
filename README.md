# eq-chatbot-core

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyPI](https://img.shields.io/pypi/v/eq-chatbot-core.svg)

Core library for LLM chatbot integration with multi-provider support.

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

**eq-chatbot-core** is a Python library for integrating Large Language Models (LLMs) into your applications. It provides a unified interface for multiple LLM providers, security features, and RAG (Retrieval-Augmented Generation) capabilities.

Originally developed for Odoo 18 chatbot integration, but works standalone without any Odoo dependencies.

### Key Features

- **Multi-Provider Support**: OpenAI, Anthropic, Azure AI, Google Vertex AI, LangDock, OpenRouter, Mammouth AI, Local (LM Studio/Ollama)
- **Unified API**: Same interface regardless of provider
- **Temperature Safety**: Automatic model-specific temperature clamping (GPT-4.1 range 0-2, Claude max=1.0, Gemini 0-2, reasoning models skip)
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

# With Google Vertex AI support
pip install eq-chatbot-core[vertex]

# All optional dependencies
pip install eq-chatbot-core[pdf,security,azure,vertex,dev]
```

### Quick Start

```python
from eq_chatbot_core.providers import get_provider

# Cloud providers
provider = get_provider("openai", api_key="sk-...")
provider = get_provider("anthropic", api_key="sk-ant-...")
provider = get_provider("azure", api_key="...", base_url="https://your-resource.services.ai.azure.com/")
provider = get_provider("vertex", project="my-gcp-project", location="europe-west1")
provider = get_provider("langdock", api_key="ld-...", region="eu")
provider = get_provider("openrouter", api_key="sk-or-...")
provider = get_provider("mammouth", api_key="mm-...")

# Local providers (no API key needed)
provider = get_provider("lm_studio")   # localhost:1234
provider = get_provider("ollama")      # localhost:11434

# Chat completion
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

### Google Vertex AI Usage

Google Vertex AI uses Application Default Credentials (ADC) instead of API keys.

```bash
# Authenticate locally
gcloud auth application-default login
gcloud config set project YOUR-PROJECT-ID

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

```python
from eq_chatbot_core.providers import get_provider

provider = get_provider("vertex", project="my-project", location="europe-west1")

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gemini-2.5-flash",
)
print(response.content)

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Tell me a story"}],
    model="gemini-2.5-pro",
):
    print(chunk.content, end="", flush=True)
```

Available EU regions for GDPR compliance: `europe-west1` (Belgium), `europe-west3` (Frankfurt), `europe-west4` (Netherlands).

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

# Programmatic JSON I/O (for integration with external tools like Rust CLIs)
echo '{"messages":[{"role":"user","content":"Hello"}]}' | eq-chatbot chat -p openai -k YOUR_API_KEY
# Output: {"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}

# With custom model and temperature
echo '{"messages":[{"role":"user","content":"Summarize this"}]}' | eq-chatbot chat -p anthropic -m claude-3-5-sonnet-20241022 -t 0.3

# Using environment variable
LLM_API_KEY=sk-... eq-chatbot chat -p openai -m gpt-4o-mini
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
| Vertex AI | Gemini 2.0, Gemini 2.5 Flash/Pro | Yes | Yes | Yes |
| LangDock | All via gateway | Yes | Yes | Yes |
| OpenRouter | 400+ models via gateway | Yes | Yes | Yes |
| Mammouth AI | 30+ models via unified API | Yes | Yes | Yes |
| Local (LM Studio/Ollama) | Local models | No | Yes | No |

---

## Deutsch

### Ueberblick

**eq-chatbot-core** ist eine Python-Bibliothek zur Integration von Large Language Models (LLMs) in Anwendungen. Sie bietet eine einheitliche Schnittstelle fuer mehrere LLM-Anbieter, Sicherheitsfunktionen und RAG-Faehigkeiten (Retrieval-Augmented Generation).

Urspruenglich fuer die Odoo 18 Chatbot-Integration entwickelt, funktioniert aber standalone ohne Odoo-Abhaengigkeiten.

### Hauptfunktionen

- **Multi-Provider-Unterstuetzung**: OpenAI, Anthropic, Azure AI, Google Vertex AI, LangDock, OpenRouter, Mammouth AI, Local (LM Studio/Ollama)
- **Einheitliche API**: Gleiche Schnittstelle unabhaengig vom Provider
- **Temperature-Sicherheit**: Automatisches modellspezifisches Temperature-Clamping (GPT-4.1 Bereich 0-2, Claude max=1.0, Gemini 0-2, Reasoning-Modelle werden uebersprungen)
- **Sicherheit**:
  - Fernet-Verschluesselung fuer API-Key-Speicherung
  - Schutz vor Prompt-Injection
  - Datei-Upload-Validierung
- **RAG-Pipeline**:
  - Text-Chunking mit konfigurierbaren Strategien
  - Embedding-Generierung
  - Vektor-Retrieval-Integration
- **MCP-Client**: HTTP/SSE und stdio Transports fuer Model Context Protocol
- **CLI-Tool**: Kommandozeilen-Interface fuer Provider-Tests

### Installation

```bash
# Basis-Installation
pip install eq-chatbot-core
# Oder mit UV (empfohlen)
uv pip install eq-chatbot-core

# Mit PDF-Unterstuetzung (fuer OpenAI/LangDock Vision)
pip install eq-chatbot-core[pdf]

# Mit Datei-Validierung
pip install eq-chatbot-core[security]

# Mit Azure AI Unterstuetzung
pip install eq-chatbot-core[azure]

# Mit Google Vertex AI Unterstuetzung
pip install eq-chatbot-core[vertex]

# Alle optionalen Abhaengigkeiten
pip install eq-chatbot-core[pdf,security,azure,vertex,dev]
```

### Google Vertex AI Verwendung

Google Vertex AI verwendet Application Default Credentials (ADC) anstelle von API-Keys.

```bash
# Lokal authentifizieren
gcloud auth application-default login
gcloud config set project DEIN-PROJEKT-ID

# Oder Service Account verwenden
export GOOGLE_APPLICATION_CREDENTIALS="/pfad/zum/service-account-key.json"
```

```python
from eq_chatbot_core.providers import get_provider

provider = get_provider("vertex", project="mein-projekt", location="europe-west1")

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="gemini-2.5-flash",
)
print(response.content)

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Erzaehle mir eine Geschichte"}],
    model="gemini-2.5-pro",
):
    print(chunk.content, end="", flush=True)
```

Verfuegbare EU-Regionen fuer DSGVO-Konformitaet: `europe-west1` (Belgien), `europe-west3` (Frankfurt), `europe-west4` (Niederlande).

### CLI-Verwendung

```bash
# Provider-Verbindung testen
eq-chatbot test-provider -p openai -k YOUR_API_KEY

# Verfuegbare Modelle auflisten
eq-chatbot list-models -p anthropic -k YOUR_API_KEY

# Nur Vision-faehige Modelle anzeigen
eq-chatbot list-models -p langdock -k YOUR_KEY --vision-only

# Ausgabe als JSON
eq-chatbot list-models -p openai -k YOUR_KEY --json

# Paket-Informationen anzeigen
eq-chatbot info

# Programmatische JSON-Ein-/Ausgabe (fuer Integration mit externen Tools wie Rust CLIs)
echo '{"messages":[{"role":"user","content":"Hallo"}]}' | eq-chatbot chat -p openai -k YOUR_API_KEY
# Ausgabe: {"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}

# Mit benutzerdefiniertem Modell und Temperatur
echo '{"messages":[{"role":"user","content":"Fasse das zusammen"}]}' | eq-chatbot chat -p anthropic -m claude-3-5-sonnet-20241022 -t 0.3
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
    messages=[{"role": "user", "content": "Erzaehle mir eine Geschichte"}],
    model="gpt-4o"
):
    print(chunk.content, end="", flush=True)
```

### Unterstuetzte Provider

| Provider | Modelle | Vision | Streaming | Temp. Clamping |
|----------|---------|--------|-----------|----------------|
| OpenAI | GPT-4, GPT-4o, GPT-4.1, GPT-5, o1, o3, o4 | Ja | Ja | Ja |
| Anthropic | Claude 3, Claude 3.5, Claude 4 | Ja | Ja | Ja |
| Azure AI | GPT-4o, GPT-4.1, o1, o3, o4, Claude, Mistral, Llama, Phi, DeepSeek | Modellabhaengig | Ja | Ja |
| Vertex AI | Gemini 2.0, Gemini 2.5 Flash/Pro | Ja | Ja | Ja |
| LangDock | Alle via Gateway | Ja | Ja | Ja |
| OpenRouter | 400+ Modelle via Gateway | Ja | Ja | Ja |
| Mammouth AI | 30+ Modelle via Unified API | Ja | Ja | Ja |
| Local (LM Studio/Ollama) | Lokale Modelle | Nein | Ja | Nein |

---

## Technical Information

| Field | Value |
|-------|-------|
| **Package Name** | eq-chatbot-core |
| **Version** | 1.6.0 |
| **Author** | Equitania Software GmbH |
| **Contact** | info@ownerp.com |
| **License** | MIT |
| **Python** | >=3.10 |
| **Homepage** | https://www.ownerp.com |
| **Repository** | https://github.com/equitania/eq-chatbot-core |

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
