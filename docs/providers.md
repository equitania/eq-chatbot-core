# Providers — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

`eq-chatbot-core` provides a unified interface across multiple LLM providers via a single factory function:

```python
from eq_chatbot_core.providers import get_provider

provider = get_provider("openai", api_key="sk-...")
```

All providers implement the same `BaseLLMProvider` interface — `chat_completion()`, `stream_completion()`, and `list_models()` — so swapping providers is a one-line change.

### Provider registry

| Name | Class | Auth | Notes |
|------|-------|------|-------|
| `openai` | `OpenAIProvider` | `api_key` | GPT-4, GPT-4o, GPT-4.1, GPT-5, o1/o3/o4 reasoning models |
| `anthropic` | `AnthropicProvider` | `api_key` | Claude 3, Claude 3.5, Claude 4 |
| `azure` | `AzureProvider` | `api_key` + `base_url` | Azure AI Foundry via the OpenAI `/v1` endpoint (no extra needed) |
| `vertex` | `VertexProvider` | ADC (no api_key) | Google Gemini — `project=`, `location=`, needs `[vertex]` extra |
| `langdock` | `LangDockProvider` | `api_key` | EU/US gateway, all models via single endpoint |
| `openrouter` | `OpenRouterProvider` | `api_key` | 400+ models via gateway |
| `mammouth` | `MammouthProvider` | `api_key` | 30+ models via unified API |
| `litellm` | `LiteLLMProvider` | `api_key` + `base_url` | Any OpenAI-compatible gateway (LiteLLM proxy, vLLM). **No default URL** — `base_url` is required. Also supports TTS/STT |
| `ionos` | `IonosProvider` | `api_key` | IONOS AI Model Hub — EU-hosted (Berlin/de-txl), OpenAI-compatible. `base_url` defaults to the official endpoint |
| `melious` | `MeliousProvider` | `api_key` | Melious.ai — sovereign EU-hosted, OpenAI-compatible (60+ open-weight models). `base_url` defaults to the official endpoint |
| `local` | `LocalLLMProvider` | `base_url` | Custom OpenAI-compatible endpoint |
| `lm_studio` / `lmstudio` | `LocalLLMProvider` | — | Defaults to `localhost:1234/v1` |
| `ollama` | `LocalLLMProvider` | — | Defaults to `localhost:11434/v1` |

### Quick start

```python
from eq_chatbot_core.providers import get_provider

# Cloud providers
provider = get_provider("openai", api_key="sk-...")
provider = get_provider("anthropic", api_key="sk-ant-...")
provider = get_provider("azure", api_key="...", base_url="https://your-resource.openai.azure.com/openai/v1/")
provider = get_provider("vertex", project="my-gcp-project", location="europe-west1")
provider = get_provider("langdock", api_key="ld-...", region="eu")
provider = get_provider("openrouter", api_key="sk-or-...")
provider = get_provider("mammouth", api_key="mm-...")

# Local providers (no API key needed)
provider = get_provider("lm_studio")    # localhost:1234
provider = get_provider("ollama")       # localhost:11434

# Chat completion
response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gpt-4o",
)
print(response.content)
print(f"Tokens used: {response.total_tokens}")

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Tell me a story"}],
    model="gpt-4o",
):
    print(chunk.content, end="", flush=True)

# List available models
for m in provider.list_models():
    print(f"{m.id} - vision: {m.supports_vision}")
```

### Response types

- `LLMResponse` — complete response: `content`, `model`, `input_tokens`, `output_tokens`, `total_tokens`, `tool_calls`
- `StreamChunk` — streaming delta: `content`, `is_final`, `tool_call_delta`, accumulated `tool_calls`
- `ModelInfo` — model metadata: `id`, `context_length`, `supports_vision`, `supports_tools`

### Exception hierarchy

```
ProviderError                  # base for all provider errors
├── AuthenticationError        # 401/403 — invalid api_key
├── RateLimitError             # 429 — has retry_after attribute
├── ContextLengthError         # token budget exceeded
└── OverloadedError            # 529/503 — transient, retryable
```

Catch the base `ProviderError` for generic handling, or specific subclasses to react differently:

```python
from eq_chatbot_core.providers.base import (
    ProviderError, RateLimitError, ContextLengthError,
)

try:
    response = provider.chat_completion(messages=..., model="gpt-4o")
except RateLimitError as e:
    time.sleep(e.retry_after or 5)
    # retry
except ContextLengthError:
    # truncate or summarize messages
    pass
except ProviderError as e:
    # generic upstream failure
    log.error("provider failed: %s", e)
```

### Google Vertex AI setup

Vertex AI uses Application Default Credentials (ADC) instead of API keys.

```bash
# Authenticate locally
gcloud auth application-default login
gcloud config set project YOUR-PROJECT-ID

# Or use a service account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

```python
provider = get_provider("vertex", project="my-project", location="europe-west1")

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gemini-2.5-flash",
)
```

**EU regions for GDPR compliance:** `europe-west1` (Belgium), `europe-west3` (Frankfurt), `europe-west4` (Netherlands).

### LiteLLM / OpenAI-compatible gateway setup

The `litellm` provider talks to any OpenAI-compatible endpoint — a LiteLLM proxy, vLLM, or a custom
gateway. Unlike the cloud providers it has **no default `base_url`**: you must pass the endpoint
explicitly. The API key is sent as `Authorization: Bearer <api_key>`.

```python
provider = get_provider(
    "litellm",
    api_key="YOUR_KEY",
    base_url="https://api.ccsio.ai/v1",   # required — no default
    model="qwen3.6-35b-a3b",              # optional default model (overridable per call)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hello!"}])
```

It also exposes audio via the OpenAI Audio API (when the gateway serves audio models):

```python
audio = provider.text_to_speech("Hello world", model="kokoro-tts-1", voice="af_bella")  # -> bytes
text = provider.transcribe(("speech.wav", audio, "audio/wav"), model="whisper-large-v3")  # -> str
```

> **Reasoning models** (e.g. `qwen3.6-35b-a3b`) may emit a non-standard `reasoning_content` field.
> The library returns the answer in `content`; the reasoning trace is preserved in
> `LLMResponse.raw_response` but never merged into `content`.

> **GDPR:** data residency depends entirely on the endpoint you configure. Verify the gateway's
> hosting/residency before processing personal data in an EU-regulated context.

### IONOS AI Model Hub setup

The `ionos` provider talks to the [IONOS Cloud AI Model Hub](https://docs.ionos.com/cloud/ai/ai-model-hub),
a German/EU-hosted (Berlin / `de-txl`), OpenAI-compatible inference gateway. Generate an API token in
the IONOS DCD Token Manager; it is sent as `Authorization: Bearer <api_key>`. Unlike `litellm`, the
`base_url` is **optional** — it defaults to the official IONOS endpoint.

```python
provider = get_provider(
    "ionos",
    api_key="YOUR_IONOS_TOKEN",
    # base_url defaults to https://openai.inference.de-txl.ionos.com/v1
    model="meta-llama/Llama-3.3-70B-Instruct",  # optional default (overridable per call)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hallo!"}])
```

Available models include `meta-llama/Llama-3.3-70B-Instruct`, `meta-llama/Meta-Llama-3.1-8B-Instruct`,
`mistralai/Mistral-Small-24B-Instruct`, `mistralai/Mistral-Nemo-Instruct-2407` and the German
`openGPT-X/Teuken-7B-instruct-commercial`. Use `provider.list_models()` for the live catalogue.

> **GDPR:** IONOS hosts in the EU (Germany), making it suitable for EU-regulated workloads.

### Melious.ai setup

The `melious` provider talks to [Melious.ai](https://melious.ai), a sovereign, EU-hosted,
OpenAI-compatible inference gateway (GDPR-compliant, green hosting, 60+ open-weight models).
Generate an API key (prefix `sk-mel-`) in the Melious account dashboard; it is sent as
`Authorization: Bearer <api_key>`. Like `ionos`, the `base_url` is **optional** — it defaults to
the official Melious endpoint.

```python
provider = get_provider(
    "melious",
    api_key="sk-mel-YOUR_KEY",
    # base_url defaults to https://api.melious.ai/v1
    model="minimax-428b-m3",  # optional default (overridable per call)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hallo!"}])
```

Melious serves 60+ open-weight models (e.g. MiniMax, DeepSeek, Llama, Mistral, Qwen, GLM,
`gpt-oss-120b`). Model ids are resolved dynamically — use `provider.list_models()` for the live
catalogue. Melious-specific extras (`preset`, the `:flavor` model suffix) and response metadata
(`environment_impact`, `billing_cost`) pass through transparently via `**kwargs`.

> **GDPR:** Melious runs on sovereign European infrastructure (GDPR, ISO 27001 in progress, green
> hosting), making it suitable for EU-regulated workloads.

### Temperature clamping

Models reject out-of-range temperatures with HTTP 400. `eq-chatbot-core` clamps automatically to each model's accepted range:

| Model family | Range | Behavior |
|--------------|-------|----------|
| GPT-4.1 | 0–2 | Clamped to `[0, 2]` |
| Claude (3, 3.5, 4) | 0–1 | Clamped to `[0, 1]` |
| Gemini 2.x | 0–2 | Clamped to `[0, 2]` |
| Reasoning (o1, o3, o4) | — | Temperature parameter dropped (not supported) |

This is automatic — pass `temperature=0.7` and the library passes through what the model accepts.

### Capability matrix

| Provider | Vision | Streaming | Tool calls | Temperature clamping |
|----------|:------:|:---------:|:----------:|:-------------------:|
| OpenAI | ✓ | ✓ | ✓ | ✓ |
| Anthropic | ✓ | ✓ | ✓ | ✓ |
| Azure AI | model-dependent | ✓ | ✓ | ✓ |
| Vertex AI | ✓ | ✓ | ✓ | ✓ |
| LangDock | ✓ | ✓ | ✓ | ✓ |
| OpenRouter | ✓ | ✓ | ✓ | ✓ |
| Mammouth | ✓ | ✓ | ✓ | ✓ |
| LiteLLM (gateway) | model-dependent | ✓ | model-dependent | ✓ |
| IONOS (EU) | model-dependent | ✓ | ✓ | ✓ |
| Melious (EU) | model-dependent | ✓ | ✓ | ✓ |
| Local (LM Studio/Ollama) | model-dependent | ✓ | model-dependent | — |

### See also

- [CLI reference](cli.md#english) — `eq-chatbot test-provider` and `eq-chatbot list-models`
- [Server mode](server-mode.md#english) — expose providers over HTTP/SSE
- [RAG pipeline](rag.md#english) — providers also power the embedder

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

`eq-chatbot-core` bietet eine einheitliche Schnittstelle für mehrere LLM-Provider über eine einzelne Factory-Funktion:

```python
from eq_chatbot_core.providers import get_provider

provider = get_provider("openai", api_key="sk-...")
```

Alle Provider implementieren das gleiche `BaseLLMProvider`-Interface — `chat_completion()`, `stream_completion()`, `list_models()` — sodass ein Provider-Wechsel eine Ein-Zeilen-Änderung ist.

### Provider-Registry

| Name | Klasse | Auth | Bemerkung |
|------|--------|------|-----------|
| `openai` | `OpenAIProvider` | `api_key` | GPT-4, GPT-4o, GPT-4.1, GPT-5, o1/o3/o4 Reasoning-Modelle |
| `anthropic` | `AnthropicProvider` | `api_key` | Claude 3, Claude 3.5, Claude 4 |
| `azure` | `AzureProvider` | `api_key` + `base_url` | Azure AI Foundry über den OpenAI-`/v1`-Endpoint (kein Extra nötig) |
| `vertex` | `VertexProvider` | ADC (kein api_key) | Google Gemini — `project=`, `location=`, braucht `[vertex]`-Extra |
| `langdock` | `LangDockProvider` | `api_key` | EU/US-Gateway, alle Modelle über einen Endpoint |
| `openrouter` | `OpenRouterProvider` | `api_key` | 400+ Modelle via Gateway |
| `mammouth` | `MammouthProvider` | `api_key` | 30+ Modelle via Unified API |
| `litellm` | `LiteLLMProvider` | `api_key` + `base_url` | Beliebiges OpenAI-kompatibles Gateway (LiteLLM-Proxy, vLLM). **Keine Default-URL** — `base_url` ist Pflicht. Unterstützt auch TTS/STT |
| `ionos` | `IonosProvider` | `api_key` | IONOS AI Model Hub — EU-gehostet (Berlin/de-txl), OpenAI-kompatibel. `base_url` hat einen Default |
| `melious` | `MeliousProvider` | `api_key` | Melious.ai — souverän EU-gehostet, OpenAI-kompatibel (60+ Open-Weight-Modelle). `base_url` hat einen Default |
| `local` | `LocalLLMProvider` | `base_url` | Beliebiger OpenAI-kompatibler Endpoint |
| `lm_studio` / `lmstudio` | `LocalLLMProvider` | — | Default `localhost:1234/v1` |
| `ollama` | `LocalLLMProvider` | — | Default `localhost:11434/v1` |

### Quick Start

```python
from eq_chatbot_core.providers import get_provider

# Cloud-Provider
provider = get_provider("openai", api_key="sk-...")
provider = get_provider("anthropic", api_key="sk-ant-...")
provider = get_provider("azure", api_key="...", base_url="https://your-resource.openai.azure.com/openai/v1/")
provider = get_provider("vertex", project="my-gcp-project", location="europe-west1")
provider = get_provider("langdock", api_key="ld-...", region="eu")
provider = get_provider("openrouter", api_key="sk-or-...")
provider = get_provider("mammouth", api_key="mm-...")

# Lokale Provider (kein API-Key nötig)
provider = get_provider("lm_studio")    # localhost:1234
provider = get_provider("ollama")       # localhost:11434

# Chat-Completion
response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="gpt-4o",
)
print(response.content)
print(f"Tokens verwendet: {response.total_tokens}")

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Erzähle mir eine Geschichte"}],
    model="gpt-4o",
):
    print(chunk.content, end="", flush=True)

# Verfügbare Modelle auflisten
for m in provider.list_models():
    print(f"{m.id} - Vision: {m.supports_vision}")
```

### Response-Typen

- `LLMResponse` — vollständige Antwort: `content`, `model`, `input_tokens`, `output_tokens`, `total_tokens`, `tool_calls`
- `StreamChunk` — Streaming-Delta: `content`, `is_final`, `tool_call_delta`, akkumulierte `tool_calls`
- `ModelInfo` — Modell-Metadaten: `id`, `context_length`, `supports_vision`, `supports_tools`

### Exception-Hierarchie

```
ProviderError                  # Basis für alle Provider-Fehler
├── AuthenticationError        # 401/403 — ungültiger api_key
├── RateLimitError             # 429 — hat retry_after-Attribut
├── ContextLengthError         # Token-Budget überschritten
└── OverloadedError            # 529/503 — transient, retryable
```

Generisches Handling über die Basis-Klasse, oder spezifische Subklassen für differenzierte Reaktion:

```python
from eq_chatbot_core.providers.base import (
    ProviderError, RateLimitError, ContextLengthError,
)

try:
    response = provider.chat_completion(messages=..., model="gpt-4o")
except RateLimitError as e:
    time.sleep(e.retry_after or 5)
    # retry
except ContextLengthError:
    # Messages kürzen oder zusammenfassen
    pass
except ProviderError as e:
    # generischer Upstream-Fehler
    log.error("provider failed: %s", e)
```

### Google Vertex AI Setup

Vertex AI verwendet Application Default Credentials (ADC) statt API-Keys.

```bash
# Lokal authentifizieren
gcloud auth application-default login
gcloud config set project DEIN-PROJEKT-ID

# Oder Service Account verwenden
export GOOGLE_APPLICATION_CREDENTIALS="/pfad/zum/service-account-key.json"
```

```python
provider = get_provider("vertex", project="mein-projekt", location="europe-west1")

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="gemini-2.5-flash",
)
```

**EU-Regionen für DSGVO-Konformität:** `europe-west1` (Belgien), `europe-west3` (Frankfurt), `europe-west4` (Niederlande).

### LiteLLM / OpenAI-kompatibles Gateway Setup

Der `litellm`-Provider spricht beliebige OpenAI-kompatible Endpunkte an — einen LiteLLM-Proxy, vLLM
oder ein eigenes Gateway. Anders als die Cloud-Provider hat er **keine Default-`base_url`**: der
Endpunkt muss explizit übergeben werden. Der API-Key wird als `Authorization: Bearer <api_key>`
gesendet.

```python
provider = get_provider(
    "litellm",
    api_key="DEIN_KEY",
    base_url="https://api.ccsio.ai/v1",   # Pflicht — kein Default
    model="qwen3.6-35b-a3b",              # optionales Default-Modell (pro Call überschreibbar)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hallo!"}])
```

Audio steht über die OpenAI-Audio-API zur Verfügung (sofern das Gateway Audio-Modelle bereitstellt):

```python
audio = provider.text_to_speech("Hallo Welt", model="kokoro-tts-1", voice="af_bella")  # -> bytes
text = provider.transcribe(("speech.wav", audio, "audio/wav"), model="whisper-large-v3")  # -> str
```

> **Reasoning-Modelle** (z. B. `qwen3.6-35b-a3b`) können ein Nicht-Standard-Feld `reasoning_content`
> liefern. Die Library gibt die Antwort in `content` zurück; der Denkprozess bleibt in
> `LLMResponse.raw_response` erhalten, wird aber nie in `content` gemischt.

> **DSGVO:** Die Daten-Residency hängt vollständig vom konfigurierten Endpunkt ab. Vor der
> Verarbeitung personenbezogener Daten im EU-Kontext das Hosting/die Residency des Gateways prüfen.

### IONOS AI Model Hub Setup

Der `ionos`-Provider spricht den [IONOS Cloud AI Model Hub](https://docs.ionos.com/cloud/ai/ai-model-hub)
an — ein deutsches/EU-gehostetes (Berlin / `de-txl`), OpenAI-kompatibles Inferenz-Gateway. Den API-Token
im IONOS DCD Token Manager erzeugen; er wird als `Authorization: Bearer <api_key>` gesendet. Anders als
`litellm` ist die `base_url` **optional** — sie hat einen Default auf den offiziellen IONOS-Endpunkt.

```python
provider = get_provider(
    "ionos",
    api_key="DEIN_IONOS_TOKEN",
    # base_url default: https://openai.inference.de-txl.ionos.com/v1
    model="meta-llama/Llama-3.3-70B-Instruct",  # optionales Default (pro Call überschreibbar)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hallo!"}])
```

Verfügbare Modelle u. a. `meta-llama/Llama-3.3-70B-Instruct`, `meta-llama/Meta-Llama-3.1-8B-Instruct`,
`mistralai/Mistral-Small-24B-Instruct`, `mistralai/Mistral-Nemo-Instruct-2407` sowie das deutsche
`openGPT-X/Teuken-7B-instruct-commercial`. Den Live-Katalog liefert `provider.list_models()`.

> **DSGVO:** IONOS hostet in der EU (Deutschland) und eignet sich damit für EU-regulierte Workloads.

### Melious.ai Setup

Der `melious`-Provider spricht [Melious.ai](https://melious.ai) an — ein souveränes, EU-gehostetes,
OpenAI-kompatibles Inferenz-Gateway (DSGVO-konform, Green Hosting, 60+ Open-Weight-Modelle). Den
API-Key (Präfix `sk-mel-`) im Melious-Account-Dashboard erzeugen; er wird als
`Authorization: Bearer <api_key>` gesendet. Wie bei `ionos` ist die `base_url` **optional** — sie hat
einen Default auf den offiziellen Melious-Endpunkt.

```python
provider = get_provider(
    "melious",
    api_key="sk-mel-DEIN_KEY",
    # base_url default: https://api.melious.ai/v1
    model="minimax-428b-m3",  # optionales Default (pro Call überschreibbar)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hallo!"}])
```

Melious bietet 60+ Open-Weight-Modelle (u. a. MiniMax, DeepSeek, Llama, Mistral, Qwen, GLM,
`gpt-oss-120b`). Modell-IDs werden dynamisch aufgelöst — den Live-Katalog liefert
`provider.list_models()`. Melious-spezifische Extras (`preset`, `:flavor`-Suffix am Modellnamen) und
Antwort-Metadaten (`environment_impact`, `billing_cost`) werden transparent über `**kwargs` durchgereicht.

> **DSGVO:** Melious läuft auf souveräner europäischer Infrastruktur (DSGVO, ISO 27001 in Arbeit,
> Green Hosting) und eignet sich damit für EU-regulierte Workloads.

### Temperature-Clamping

Modelle lehnen out-of-range-Temperaturen mit HTTP 400 ab. `eq-chatbot-core` clampt automatisch auf den akzeptierten Bereich pro Modell:

| Modell-Familie | Range | Verhalten |
|----------------|-------|-----------|
| GPT-4.1 | 0–2 | Auf `[0, 2]` geclampt |
| Claude (3, 3.5, 4) | 0–1 | Auf `[0, 1]` geclampt |
| Gemini 2.x | 0–2 | Auf `[0, 2]` geclampt |
| Reasoning (o1, o3, o4) | — | Temperature-Parameter wird verworfen (nicht unterstützt) |

Das geschieht automatisch — `temperature=0.7` übergeben, die Library reicht den vom Modell akzeptierten Wert weiter.

### Capability-Matrix

| Provider | Vision | Streaming | Tool-Calls | Temperature-Clamping |
|----------|:------:|:---------:|:----------:|:--------------------:|
| OpenAI | ✓ | ✓ | ✓ | ✓ |
| Anthropic | ✓ | ✓ | ✓ | ✓ |
| Azure AI | modellabhängig | ✓ | ✓ | ✓ |
| Vertex AI | ✓ | ✓ | ✓ | ✓ |
| LangDock | ✓ | ✓ | ✓ | ✓ |
| OpenRouter | ✓ | ✓ | ✓ | ✓ |
| Mammouth | ✓ | ✓ | ✓ | ✓ |
| LiteLLM (Gateway) | modellabhängig | ✓ | modellabhängig | ✓ |
| IONOS (EU) | modellabhängig | ✓ | ✓ | ✓ |
| Melious (EU) | modellabhängig | ✓ | ✓ | ✓ |
| Local (LM Studio/Ollama) | modellabhängig | ✓ | modellabhängig | — |

### Siehe auch

- [CLI-Referenz](cli.md#deutsch) — `eq-chatbot test-provider` und `eq-chatbot list-models`
- [Server-Mode](server-mode.md#deutsch) — Provider über HTTP/SSE exponieren
- [RAG-Pipeline](rag.md#deutsch) — Provider werden auch vom Embedder verwendet

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
