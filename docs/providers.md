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
| `langdock` | `LangDockProvider` | `api_key` | EU/US gateway, all models via single endpoint |
| `openrouter` | `OpenRouterProvider` | `api_key` | 400+ models via gateway |
| `mammouth` | `MammouthProvider` | `api_key` | 30+ models via unified API |
| `litellm` | `LiteLLMProvider` | `api_key` + `base_url` | Any OpenAI-compatible gateway (LiteLLM proxy, vLLM). **No default URL** — `base_url` is required. Also supports TTS/STT |
| `ionos` | `IonosProvider` | `api_key` | IONOS AI Model Hub — EU-hosted (Berlin/de-txl), OpenAI-compatible. `base_url` defaults to the official endpoint |
| `melious` | `MeliousProvider` | `api_key` | Melious.ai — sovereign EU-hosted, OpenAI-compatible (60+ open-weight models). `base_url` defaults to the official endpoint |
| `privatemode` | `PrivatemodeProvider` | — (proxy holds it) | Privatemode.ai — end-to-end encrypted via confidential computing. Talks to a **local** privatemode-proxy; `base_url` defaults to `http://localhost:8080/v1` |
| `local` | `LocalLLMProvider` | `base_url` | Custom OpenAI-compatible endpoint |
| `lm_studio` / `lmstudio` | `LocalLLMProvider` | — | Defaults to `localhost:1234/v1` |
| `ollama` | `LocalLLMProvider` | — | Defaults to `localhost:11434/v1` |

### Quick start

```python
from eq_chatbot_core.providers import get_provider

# Cloud providers
provider = get_provider("openai", api_key="sk-...")
provider = get_provider("anthropic", api_key="sk-ant-...")
provider = get_provider("langdock", api_key="ld-...", region="eu")
provider = get_provider("openrouter", api_key="sk-or-...")
provider = get_provider("mammouth", api_key="mm-...")

# Local providers (no API key needed)
provider = get_provider("lm_studio")    # localhost:1234
provider = get_provider("ollama")       # localhost:11434

# Chat completion
response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="your-model-id",
)
print(response.content)
print(f"Tokens used: {response.total_tokens}")

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Tell me a story"}],
    model="your-model-id",
):
    print(chunk.content, end="", flush=True)

# List available models
for m in provider.list_models():
    print(f"{m.id} - vision: {m.supports_vision}")
```

### Choosing a model

There is no default model. Pass `model=` per call, or once to `get_provider(..., model=...)`;
without either, the call raises `ModelNotSpecifiedError` (a `ProviderError`) before anything
is sent. Image generation takes `image_model=` (OpenAI, OpenRouter), LiteLLM's audio takes
`tts_model=`, `tts_voice=` and `stt_model=`. LangDock's `agent` backend needs no model — the
agent's model is configured in LangDock.

`list_models()` returns every model the provider lists — nothing is filtered by name, so
OpenAI's list includes embedding and audio models. Metadata the provider does not report is
`None` (unknown), never a guess; Anthropic's capability fields and OpenRouter's context and
modality data are passed through where the API reports them. Treat
`supports_temperature is None` as "allowed — the library adapts"; it becomes `False` once a
model rejected `temperature`.

### Response types

- `LLMResponse` — complete response: `content`, `model`, `input_tokens`, `output_tokens`, `total_tokens`, `tool_calls`
- `StreamChunk` — streaming delta: `content`, `is_final`, `tool_call_delta`, accumulated `tool_calls`
- `ModelInfo` — model metadata: `id`, `context_length`, `supports_vision`, `supports_tools`

### Exception hierarchy

```
ProviderError                  # base for all provider errors
├── ModelNotSpecifiedError     # no model per call or per provider instance
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

### LiteLLM / OpenAI-compatible gateway setup

The `litellm` provider talks to any OpenAI-compatible endpoint — a LiteLLM proxy, vLLM, or a custom
gateway. Unlike the cloud providers it has **no default `base_url`**: you must pass the endpoint
explicitly. The API key is sent as `Authorization: Bearer <api_key>`.

```python
provider = get_provider(
    "litellm",
    api_key="YOUR_KEY",
    base_url="https://litellm.example.com/v1",   # required — no default
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
    model="nemotron-3-nano-30b-a3b",  # optional default (overridable per call)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hallo!"}])
```

Melious serves 60+ open-weight models (e.g. MiniMax, DeepSeek, Llama, Mistral, Qwen, GLM,
`gpt-oss-120b`). Model ids are resolved dynamically — use `provider.list_models()` for the live
catalogue. Melious-specific extras (`preset`, the `:flavor` model suffix) and response metadata
(`environment_impact`, `billing_cost`) pass through transparently via `**kwargs`.

> **GDPR:** Melious runs on sovereign European infrastructure (GDPR, ISO 27001 in progress, green
> hosting), making it suitable for EU-regulated workloads.

### Privatemode.ai setup

[Privatemode.ai](https://www.privatemode.ai) (Edgeless Systems) is an end-to-end encrypted GenAI
service built on confidential computing. Prompts and responses are encrypted on the client side and
decrypted only inside a hardware-isolated Confidential Computing Environment (CCE). Neither Edgeless
Systems nor the infrastructure provider (Scaleway, EU) can read the data.

**This provider is different from every other one here: there is no public API to call.** The
encryption and the remote attestation are done by a proxy you run yourself:

```bash
docker run -p 8080:8080 \
    ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest \
    --apiKey <your-api-key>
```

The library then speaks ordinary OpenAI Chat Completions to that proxy:

```python
provider = get_provider("privatemode")          # base_url defaults to http://localhost:8080/v1

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="kimi-latest",                        # model for this call; `list_models()` shows the current ids
)
```

`api_key` is **optional** — the proxy normally holds it (`--apiKey`) and authenticates upstream on
your behalf. Pass a key only when the proxy was started without one, in which case it forwards your
`Authorization` header.

**The end-to-end guarantee is only as strong as the hop to the proxy**, and misconfiguring that hop
would fail silently. The provider therefore classifies `base_url` at construction:

| `base_url` | Behaviour |
|------------|-----------|
| `https://…` (anywhere) | allowed — TLS protects the hop |
| loopback (the default) | allowed, no DNS lookup |
| plain HTTP → private/cluster-internal address | allowed, logged at INFO (the documented Helm deployment) |
| plain HTTP → **public** address | **`ValueError`** — would put prompts on the wire in cleartext |

The last case can be overridden with `allow_insecure_transport=True` when that hop is protected by
other means (VPN, service mesh, IPsec); it then logs a warning naming the exposure.

Two vendor extras are accepted as ordinary keyword arguments and routed into the request body for
you: `cache_salt` (prompt-cache isolation between tenants) and `chat_template_kwargs`
(e.g. `{"thinking": False}` to skip Kimi's reasoning pass).

Model ids are discovered live via `provider.list_models()` — no static catalogue is bundled, because
the vendor retires concrete ids over time. At the time of writing: `kimi-latest` / `kimi-k2.6`
(256k context, vision) and `gpt-oss-120b` (128k, text).

> **GDPR:** Confidential computing means the operator itself cannot access the plaintext. Hosted in
> the EU (Scaleway); suitable for the strictest EU-regulated workloads.

### Parameter learning

Whether a model accepts `temperature`, wants `max_completion_tokens` instead of `max_tokens`, or takes `reasoning_effort` is not kept in a model list: the library learns it at runtime. This applies to every OpenAI-wire provider (OpenAI, Mammouth, OpenRouter, Local, IONOS, Melious, LiteLLM, Privatemode, LangDock's `openai` backend) and, for `temperature`, to Anthropic and LangDock's `anthropic` backend.

- If the endpoint rejects `temperature` as unsupported (Anthropic says "deprecated"), the request is repeated once without it.
- If it rejects `max_tokens`, the request is repeated once with `max_completion_tokens`. OpenAI itself always gets `max_completion_tokens`.
- If it rejects `reasoning_effort` (passed per call, or LangDock's constructor setting), the request is repeated once without it.
- Each parameter is retried at most once. The answer is remembered per endpoint and model for the rest of the process, so the cost is one extra request the first time a model is used.
- A range error ("temperature: range: 0..1") is not a rejection: it reaches the caller.
- On OpenRouter, `list_models()` pre-seeds "temperature unsupported" for models whose metadata does not offer `temperature`; a learned rejection always wins over the list.

Errors are mapped by HTTP status: 429 `RateLimitError` (with `retry_after`), 401/403 `AuthenticationError` (403 is new in this release), 503/529 `OverloadedError`, and 400 with code `context_length_exceeded` or a context-length phrase `ContextLengthError`. For LangDock this mapping applies to the `openai` backend only; the anthropic, google and agent backends keep their previous mapping.

### Temperature clamping

Only provider-level ranges are applied; there is no per-model table.

| Provider | Range | Behavior |
|----------|-------|----------|
| OpenAI-wire providers, LangDock `google` | 0–2 | Clamped to `[0, 2]` |
| Anthropic, LangDock `anthropic` | 0–1 | Clamped to `[0, 1]`, sent in `extra_body` |

A model that takes no temperature at all rejects it once; the library drops it and remembers that (see Parameter learning).

### Capability matrix

| Provider | Vision | Streaming | Tool calls | Temperature range |
|----------|:------:|:---------:|:----------:|:-------------------:|
| OpenAI | ✓ | ✓ | ✓ | ✓ |
| Anthropic | ✓ | ✓ | ✓ | ✓ |
| LangDock | ✓ | ✓ | ✓ | ✓ |
| OpenRouter | ✓ | ✓ | ✓ | ✓ |
| Mammouth | ✓ | ✓ | ✓ | ✓ |
| LiteLLM (gateway) | model-dependent | ✓ | model-dependent | ✓ |
| IONOS (EU) | model-dependent | ✓ | ✓ | ✓ |
| Melious (EU) | model-dependent | ✓ | ✓ | ✓ |
| Privatemode (EU, E2E) | model-dependent | ✓ | ✓ | ✓ |
| Local (LM Studio/Ollama) | model-dependent | ✓ | model-dependent | — |

### See also

- [Reasoning & thinking modes](reasoning.md#english) — the four mechanisms per provider, trace handling, capability catalog
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
| `langdock` | `LangDockProvider` | `api_key` | EU/US-Gateway, alle Modelle über einen Endpoint |
| `openrouter` | `OpenRouterProvider` | `api_key` | 400+ Modelle via Gateway |
| `mammouth` | `MammouthProvider` | `api_key` | 30+ Modelle via Unified API |
| `litellm` | `LiteLLMProvider` | `api_key` + `base_url` | Beliebiges OpenAI-kompatibles Gateway (LiteLLM-Proxy, vLLM). **Keine Default-URL** — `base_url` ist Pflicht. Unterstützt auch TTS/STT |
| `ionos` | `IonosProvider` | `api_key` | IONOS AI Model Hub — EU-gehostet (Berlin/de-txl), OpenAI-kompatibel. `base_url` hat einen Default |
| `melious` | `MeliousProvider` | `api_key` | Melious.ai — souverän EU-gehostet, OpenAI-kompatibel (60+ Open-Weight-Modelle). `base_url` hat einen Default |
| `privatemode` | `PrivatemodeProvider` | — (hält der Proxy) | Privatemode.ai — Ende-zu-Ende-verschlüsselt über Confidential Computing. Spricht einen **lokalen** privatemode-proxy an; `base_url` default `http://localhost:8080/v1` |
| `local` | `LocalLLMProvider` | `base_url` | Beliebiger OpenAI-kompatibler Endpoint |
| `lm_studio` / `lmstudio` | `LocalLLMProvider` | — | Default `localhost:1234/v1` |
| `ollama` | `LocalLLMProvider` | — | Default `localhost:11434/v1` |

### Quick Start

```python
from eq_chatbot_core.providers import get_provider

# Cloud-Provider
provider = get_provider("openai", api_key="sk-...")
provider = get_provider("anthropic", api_key="sk-ant-...")
provider = get_provider("langdock", api_key="ld-...", region="eu")
provider = get_provider("openrouter", api_key="sk-or-...")
provider = get_provider("mammouth", api_key="mm-...")

# Lokale Provider (kein API-Key nötig)
provider = get_provider("lm_studio")    # localhost:1234
provider = get_provider("ollama")       # localhost:11434

# Chat-Completion
response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="your-model-id",
)
print(response.content)
print(f"Tokens verwendet: {response.total_tokens}")

# Streaming
for chunk in provider.stream_completion(
    messages=[{"role": "user", "content": "Erzähle mir eine Geschichte"}],
    model="your-model-id",
):
    print(chunk.content, end="", flush=True)

# Verfügbare Modelle auflisten
for m in provider.list_models():
    print(f"{m.id} - Vision: {m.supports_vision}")
```

### Modell wählen

Es gibt kein Standardmodell. `model=` wird pro Aufruf übergeben oder einmal an `get_provider(..., model=...)`; fehlt beides, wirft der Aufruf `ModelNotSpecifiedError` (ein `ProviderError`), bevor etwas gesendet wird. Bildgenerierung nimmt `image_model=` (OpenAI, OpenRouter), die Audio-Funktionen von LiteLLM nehmen `tts_model=`, `tts_voice=` und `stt_model=`. Das `agent`-Backend von LangDock braucht kein Modell — das Modell des Agenten ist in LangDock eingestellt.

`list_models()` liefert jedes Modell, das der Provider auflistet — nichts wird nach Namen gefiltert, die Liste von OpenAI enthält also auch Embedding- und Audio-Modelle. Metadaten, die der Provider nicht meldet, sind `None` (unbekannt), nie geraten; die Fähigkeitsfelder von Anthropic und die Kontext- und Modalitätsdaten von OpenRouter werden durchgereicht, wo die API sie meldet. `supports_temperature is None` heißt „erlaubt — die Bibliothek passt sich an“; nach einer Ablehnung wird daraus `False`.

### Response-Typen

- `LLMResponse` — vollständige Antwort: `content`, `model`, `input_tokens`, `output_tokens`, `total_tokens`, `tool_calls`
- `StreamChunk` — Streaming-Delta: `content`, `is_final`, `tool_call_delta`, akkumulierte `tool_calls`
- `ModelInfo` — Modell-Metadaten: `id`, `context_length`, `supports_vision`, `supports_tools`

### Exception-Hierarchie

```
ProviderError                  # Basis für alle Provider-Fehler
├── ModelNotSpecifiedError     # kein Modell pro Aufruf oder pro Provider-Instanz
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

### LiteLLM / OpenAI-kompatibles Gateway Setup

Der `litellm`-Provider spricht beliebige OpenAI-kompatible Endpunkte an — einen LiteLLM-Proxy, vLLM
oder ein eigenes Gateway. Anders als die Cloud-Provider hat er **keine Default-`base_url`**: der
Endpunkt muss explizit übergeben werden. Der API-Key wird als `Authorization: Bearer <api_key>`
gesendet.

```python
provider = get_provider(
    "litellm",
    api_key="DEIN_KEY",
    base_url="https://litellm.example.com/v1",   # Pflicht — kein Default
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
    model="nemotron-3-nano-30b-a3b",  # optionales Default (pro Call überschreibbar)
)

response = provider.chat_completion(messages=[{"role": "user", "content": "Hallo!"}])
```

Melious bietet 60+ Open-Weight-Modelle (u. a. MiniMax, DeepSeek, Llama, Mistral, Qwen, GLM,
`gpt-oss-120b`). Modell-IDs werden dynamisch aufgelöst — den Live-Katalog liefert
`provider.list_models()`. Melious-spezifische Extras (`preset`, `:flavor`-Suffix am Modellnamen) und
Antwort-Metadaten (`environment_impact`, `billing_cost`) werden transparent über `**kwargs` durchgereicht.

> **DSGVO:** Melious läuft auf souveräner europäischer Infrastruktur (DSGVO, ISO 27001 in Arbeit,
> Green Hosting) und eignet sich damit für EU-regulierte Workloads.

### Privatemode.ai Setup

[Privatemode.ai](https://www.privatemode.ai) (Edgeless Systems) ist ein Ende-zu-Ende-verschlüsselter
GenAI-Dienst auf Basis von Confidential Computing. Prompts und Antworten werden clientseitig
verschlüsselt und erst innerhalb einer hardware-isolierten Confidential Computing Environment (CCE)
entschlüsselt. Weder Edgeless Systems noch der Infrastrukturbetreiber (Scaleway, EU) können die Daten
lesen.

**Dieser Provider unterscheidet sich von allen anderen: Es gibt keine öffentliche API.**
Verschlüsselung und Remote Attestation übernimmt ein Proxy, den man selbst betreibt:

```bash
docker run -p 8080:8080 \
    ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest \
    --apiKey <dein-api-key>
```

Die Library spricht dann ganz normales OpenAI Chat Completions gegen diesen Proxy:

```python
provider = get_provider("privatemode")          # base_url default: http://localhost:8080/v1

response = provider.chat_completion(
    messages=[{"role": "user", "content": "Hallo!"}],
    model="kimi-latest",                        # Modell für diesen Aufruf; `list_models()` zeigt die aktuellen IDs
)
```

`api_key` ist **optional** — normalerweise hält der Proxy den Schlüssel (`--apiKey`) und
authentifiziert stellvertretend. Nur wenn der Proxy ohne Key gestartet wurde, muss der Key hier
übergeben werden; der Proxy reicht dann den `Authorization`-Header weiter.

**Die Ende-zu-Ende-Garantie ist nur so stark wie der Weg zum Proxy** — und eine Fehlkonfiguration
dieses Wegs würde stillschweigend scheitern. Der Provider klassifiziert `base_url` deshalb schon beim
Konstruieren:

| `base_url` | Verhalten |
|------------|-----------|
| `https://…` (beliebig) | erlaubt — TLS schützt den Hop |
| Loopback (der Default) | erlaubt, ohne DNS-Lookup |
| Klartext-HTTP → private/cluster-interne Adresse | erlaubt, INFO-Log (das dokumentierte Helm-Deployment) |
| Klartext-HTTP → **öffentliche** Adresse | **`ValueError`** — Prompts gingen im Klartext über die Leitung |

Der letzte Fall lässt sich mit `allow_insecure_transport=True` übersteuern, wenn der Hop anderweitig
geschützt ist (VPN, Service Mesh, IPsec); dann wird die Exposition als Warnung protokolliert.

Zwei herstellerspezifische Extras werden als normale Keyword-Argumente akzeptiert und automatisch in
den Request-Body geroutet: `cache_salt` (Prompt-Cache-Isolation zwischen Mandanten) und
`chat_template_kwargs` (z. B. `{"thinking": False}`, um Kimis Reasoning-Durchlauf zu überspringen).

Modell-IDs werden live über `provider.list_models()` ermittelt — ein statischer Katalog ist bewusst
nicht mitgeliefert, da der Hersteller konkrete IDs über die Zeit abkündigt. Zum Zeitpunkt der
Erstellung: `kimi-latest` / `kimi-k2.6` (256k Kontext, Vision) und `gpt-oss-120b` (128k, Text).

> **DSGVO:** Confidential Computing bedeutet, dass selbst der Betreiber nicht an den Klartext kommt.
> Hosting in der EU (Scaleway); geeignet für die strengsten EU-regulierten Workloads.

### Parameter-Lernen

Ob ein Modell `temperature` annimmt, statt `max_tokens` lieber `max_completion_tokens` will oder `reasoning_effort` versteht, steht in keiner Modellliste: Die Bibliothek lernt es zur Laufzeit. Das gilt für jeden Provider mit OpenAI-Protokoll (OpenAI, Mammouth, OpenRouter, Local, IONOS, Melious, LiteLLM, Privatemode, LangDocks `openai`-Backend) und für `temperature` auch für Anthropic und LangDocks `anthropic`-Backend.

- Lehnt der Endpunkt `temperature` als nicht unterstützt ab (Anthropic schreibt „deprecated“), wird die Anfrage einmal ohne wiederholt.
- Lehnt er `max_tokens` ab, wird sie einmal mit `max_completion_tokens` wiederholt. OpenAI selbst bekommt immer `max_completion_tokens`.
- Lehnt er `reasoning_effort` ab (pro Aufruf oder als LangDock-Konstruktorwert), wird sie einmal ohne wiederholt.
- Jeder Parameter wird höchstens einmal wiederholt. Das Ergebnis gilt je Endpunkt und Modell für den Rest des Prozesses — es kostet also eine zusätzliche Anfrage beim ersten Einsatz eines Modells.
- Ein Bereichsfehler („temperature: range: 0..1“) ist keine Ablehnung: Er erreicht den Aufrufer.
- Bei OpenRouter setzt `list_models()` „temperature nicht unterstützt“ vorab für Modelle, deren Metadaten `temperature` nicht anbieten; eine gelernte Ablehnung hat immer Vorrang vor der Liste.

Fehler werden nach HTTP-Status abgebildet: 429 `RateLimitError` (mit `retry_after`), 401/403 `AuthenticationError` (403 neu in diesem Release), 503/529 `OverloadedError`, 400 mit Code `context_length_exceeded` oder einer Kontextlängen-Formulierung `ContextLengthError`. Bei LangDock gilt diese Abbildung nur für das `openai`-Backend; die Backends anthropic, google und agent behalten ihre bisherige Abbildung.

### Temperature-Clamping

Es gelten nur Bereiche auf Provider-Ebene; eine Tabelle je Modell gibt es nicht.

| Provider | Bereich | Verhalten |
|----------|---------|-----------|
| Provider mit OpenAI-Protokoll, LangDock `google` | 0–2 | Auf `[0, 2]` begrenzt |
| Anthropic, LangDock `anthropic` | 0–1 | Auf `[0, 1]` begrenzt, in `extra_body` gesendet |

Ein Modell, das gar keine Temperatur annimmt, lehnt sie einmal ab; die Bibliothek lässt sie dann weg und merkt sich das (siehe Parameter-Lernen).

### Capability-Matrix

| Provider | Vision | Streaming | Tool-Calls | Temperaturbereich |
|----------|:------:|:---------:|:----------:|:--------------------:|
| OpenAI | ✓ | ✓ | ✓ | ✓ |
| Anthropic | ✓ | ✓ | ✓ | ✓ |
| LangDock | ✓ | ✓ | ✓ | ✓ |
| OpenRouter | ✓ | ✓ | ✓ | ✓ |
| Mammouth | ✓ | ✓ | ✓ | ✓ |
| LiteLLM (Gateway) | modellabhängig | ✓ | modellabhängig | ✓ |
| IONOS (EU) | modellabhängig | ✓ | ✓ | ✓ |
| Melious (EU) | modellabhängig | ✓ | ✓ | ✓ |
| Privatemode (EU, E2E) | modellabhängig | ✓ | ✓ | ✓ |
| Local (LM Studio/Ollama) | modellabhängig | ✓ | modellabhängig | — |

### Siehe auch

- [Reasoning- & Thinking-Modi](reasoning.md#deutsch) — die vier Mechanismen je Provider, Trace-Handling, Capability-Katalog
- [CLI-Referenz](cli.md#deutsch) — `eq-chatbot test-provider` und `eq-chatbot list-models`
- [Server-Mode](server-mode.md#deutsch) — Provider über HTTP/SSE exponieren
- [RAG-Pipeline](rag.md#deutsch) — Provider werden auch vom Embedder verwendet

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
