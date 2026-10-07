# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

Standalone Python library for LLM chatbot integration. Provides unified API across multiple providers (OpenAI, Anthropic, LangDock, OpenRouter, local servers). Originally extracted from v18-chatbot Odoo project for independent PyPI publishing.

## Commands

### Development Setup

```bash
uv venv && source .venv/bin/activate  # or: venv+
uv pip install -e ".[dev,pdf,security]"
```

### Testing

```bash
# Run all unit tests (fast, mocked)
pytest tests/unit/ -v

# Run all tests with coverage
pytest tests/ -v --cov=eq_chatbot_core --cov-report=html
# Coverage gate: any --cov run fails below fail_under in [tool.coverage.report] (pyproject.toml).
# The baseline is measured with the CI extras set; raise it when coverage rises, never lower it.

# Run single test file
pytest tests/unit/test_openai.py -v

# Run single test function
pytest tests/unit/test_openai.py::TestOpenAIProviderInit::test_basic_init -v

# Run tests by marker
pytest -m unit -v                    # Unit tests only (mocked)
pytest -m integration -v             # Integration tests (real API calls)
pytest -m local -v                   # Local server tests

# Skip expensive tests
SKIP_LIVE_TESTS=true pytest tests/ -v
```

### Linting

```bash
ruff check src/ && ruff format src/ --check   # Check only
ruff check src/ --fix && ruff format src/     # Auto-fix
mypy src/                               # Type checking
```

### Building

```bash
python -m build                         # Build package
twine check dist/*                      # Verify package
```

## Architecture

### Provider Factory Pattern

All providers use a factory function with consistent interface:

```python
from eq_chatbot_core.providers import get_provider

# Cloud providers
provider = get_provider("openai", api_key="sk-...")
provider = get_provider("anthropic", api_key="sk-ant-...")
provider = get_provider("langdock", api_key="ld-...")
provider = get_provider("openrouter", api_key="sk-or-...")
provider = get_provider("mammouth", api_key="mm-...")
provider = get_provider("litellm", api_key="...", base_url="https://gateway/v1")  # OpenAI-compatible gateway
provider = get_provider("ionos", api_key="...")  # IONOS AI Model Hub (EU-hosted, base_url has a default)
provider = get_provider("melious", api_key="sk-mel-...")  # Melious.ai (sovereign EU-hosted, base_url has a default)
provider = get_provider("privatemode")  # Privatemode.ai (end-to-end encrypted; needs the local privatemode-proxy on :8080)

# Local providers (LM Studio, Ollama)
provider = get_provider("lm_studio")  # defaults to localhost:1234
provider = get_provider("ollama")      # defaults to localhost:11434
provider = get_provider("local", base_url="http://custom:port/v1")
```

There is no default model. Pass `model=` per call or to `get_provider(..., model=...)`
(images: `image_model=`; LiteLLM audio: `tts_model=`, `tts_voice=`, `stt_model=`); otherwise
calls raise `ModelNotSpecifiedError` (a `ProviderError`). LangDock's `agent` backend is the
exception: the agent's model is configured in LangDock. Never add a model ID, family prefix
or model-specific value to `src/` — `tests/unit/test_no_model_ids_in_source.py` fails on it.
Tests take models from `tests/model_registry.py`.

### Provider Base Class

All providers inherit from `BaseLLMProvider` and must implement:

```python
class BaseLLMProvider(ABC):
    provider_name: str              # Property: "openai", "anthropic", etc.
    default_model: str | None       # Property: the constructor's model, or None

    def chat_completion(messages, model, temperature, max_tokens, tools) -> LLMResponse
    def stream_completion(messages, model, ...) -> Iterator[StreamChunk]
    def list_models() -> list[dict]
    def resolve_model(model) -> str          # call model > constructor model > ModelNotSpecifiedError
```

Every OpenAI-wire provider (OpenAI, Mammouth, OpenRouter, Local, IONOS, Melious, LiteLLM,
Privatemode, LangDock's `openai` backend) inherits `OpenAICompatibleProvider`. Do not add a
provider with its own request/stream/error code — subclass and override a hook
(`_build_params`, `_token_param`, `_default_headers`, `_client_kwargs`, `list_models`,
`_error_from_message`). Whether a model accepts `temperature`, wants `max_completion_tokens` or
takes `reasoning_effort` is learned at runtime (`providers/param_learning.py`, for Anthropic via
`providers/anthropic_shared.py`); never add a model to a list to fix it. `list_models()` reports
what the provider says — unknown is `None`.

### Response Types

- `LLMResponse`: Complete response with content, token counts, tool_calls
- `StreamChunk`: Streaming delta with is_final flag and accumulated tool_calls
- `ModelInfo`: Model metadata (id, context_length, supports_vision, etc.)

### Exception Hierarchy

```
ProviderError (base)
├── ModelNotSpecifiedError # no model per call or per instance
├── RateLimitError     # 429 errors, has retry_after
├── AuthenticationError # 401/403 errors
├── ContextLengthError  # Token limit exceeded
└── OverloadedError     # 529/503 transient errors (retryable)
```

### Module Structure

```
src/eq_chatbot_core/
├── providers/              # LLM adapters
│   ├── base.py             # BaseLLMProvider, response types, exceptions
│   ├── openai_compatible.py # OpenAICompatibleProvider: shared base for every OpenAI-wire provider
│   ├── param_learning.py   # Learns per endpoint/model whether temperature / max_tokens / reasoning_effort are accepted
│   ├── anthropic_shared.py # Temperature learning + model listing for Anthropic and LangDock-anthropic
│   ├── openai_provider.py  # OpenAI
│   ├── anthropic_provider.py
│   ├── langdock_provider.py # LangDock gateway (EU/US regions)
│   ├── openrouter_provider.py # OpenRouter (400+ models)
│   ├── mammouth_provider.py # Mammouth AI
│   ├── litellm_provider.py  # LiteLLM / any OpenAI-compatible gateway
│   ├── ionos_provider.py    # IONOS AI Model Hub (EU-hosted, OpenAI-compatible)
│   ├── melious_provider.py  # Melious.ai (sovereign EU-hosted, OpenAI-compatible)
│   ├── privatemode_provider.py # Privatemode.ai (E2E-encrypted, via local attesting proxy)
│   ├── local_provider.py   # LM Studio, Ollama (OpenAI-compatible)
│   ├── stream_accumulator.py # Assembles streamed OpenAI-style tool-call deltas
│   └── temperature_constraints.py # Provider-level clamp, apply_anthropic_temperature(), strip_provider_prefix()
├── realtime/               # Realtime voice providers (requires [realtime])
│   ├── abc.py, contracts.py # Adapter contract and event types (constants frozen, shared with GlassAgents)
│   ├── factory.py          # get_realtime_provider()
│   ├── websocket_client.py # WebSocket lifecycle base class
│   ├── mock.py             # In-process queue-backed provider for consumer tests
│   └── providers/          # openai, gemini_live, elevenlabs
├── server/                 # `eq-chatbot serve`: localhost HTTP/SSE sidecar (requires [server])
│   ├── app.py, models.py   # FastAPI app factory, Pydantic schemas
│   ├── auth.py             # Bearer-token middleware
│   ├── lifecycle.py        # Ephemeral-port binding, parent-PID watchdog
│   └── streaming.py        # StreamChunk -> Server-Sent Events
├── security/
│   ├── encryption.py       # FernetEncryption for API key storage
│   ├── injection.py        # Prompt injection detection
│   ├── rate_limit.py       # Token bucket rate limiter
│   └── file_validator.py   # MIME type validation (requires [security])
├── rag/
│   ├── chunker.py          # Text chunking strategies
│   ├── embedder.py         # Embedding generation (OpenAI, LangDock, Melious); model required, size discovered
│   ├── retriever.py        # Qdrant vector retrieval (requires [rag])
│   └── context_manager.py  # RAG context assembly
├── mcp/
│   ├── client.py           # MCP client (legacy HTTP/SSE and stdio transports)
│   └── streamable_http.py  # MCP client (Streamable HTTP, the current remote transport)
├── services/
│   ├── error_handler.py    # Centralized error handling
│   ├── knowledge_service.py # Knowledge export for vector DBs
│   ├── capability_catalog.py # Per-model capabilities (vision, tools, reasoning, ...)
│   └── document_extractor.py # Office/PDF -> Markdown for knowledge ingestion (requires [docs])
├── utils/
│   ├── url_validation.py   # SSRF / DNS-rebinding guard (shared by providers, embedders, MCP)
│   ├── secret_scrub.py     # Strips secrets from logs and error surfaces
│   ├── config.py           # ~/.config/eq-chatbot/config.toml loader
│   ├── image.py            # Generated-image processing and saving
│   └── pdf.py              # PDF to image (requires [pdf])
├── data/                   # config.toml.example (no bundled capability catalog)
├── cli.py                  # Click CLI: eq-chatbot
└── version.py              # Version string
```

## Testing Patterns

### Unit Test Structure

Unit tests mock SDK clients at module level to avoid API calls:

```python
import sys
from unittest.mock import MagicMock

# Mock before importing provider
mock_openai_module = MagicMock()
sys.modules["openai"] = mock_openai_module

from eq_chatbot_core.providers.openai_provider import OpenAIProvider
```

### Test Markers

- `@pytest.mark.unit` - Mocked tests, no external dependencies
- `@pytest.mark.integration` - Real API calls, requires keys
- `@pytest.mark.local` - Requires running LM Studio/Ollama
- `@pytest.mark.expensive` - Uses expensive models, skipped in CI
- `@pytest.mark.slow` - Long-running tests

### Test Configuration

API keys come from `~/.config/eq-chatbot/config.toml` (`[providers.<name>].api_key`),
the same file the CLI uses. `conftest.py` mirrors them into `<NAME>_API_KEY` at
import; a real environment variable wins. `tests/.env.test` was removed in 3.1.0 —
it lived inside the repository, so the keys were one `git add -f` from publication.

- Keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`, `MAMMOUTH_API_KEY`, `IONOS_API_KEY`, `MELIOUS_API_KEY`, `PRIVATEMODE_API_KEY`, `LITELLM_API_KEY`, `OPENROUTER_API_KEY`
- `SKIP_LIVE_TESTS=true` - Skip integration tests (default false)
- `SKIP_LOCAL_TESTS=true` - Skip local server tests (default false)
- `<PROVIDER>_TEST_MODEL` - Override a model choice; defaults in `tests/model_registry.py`

### Fixtures (conftest.py)

- `test_config` - Session config from environment
- `mock_openai_client`, `mock_anthropic_client` - Pre-configured mocks
- `sample_messages`, `minimal_test_messages` - Test data
- `openai_provider`, `anthropic_provider` - Live provider instances

## Git Commit Conventions

- `[ADD]` - New features
- `[CHG]` - Modifications
- `[FIX]` - Bug fixes

## Dependencies

### Core (always installed)

openai (>=3), anthropic (>=1), httpx2, pydantic, cryptography, tiktoken, click

Floors track the current release (`uv lock --upgrade`, then raise every floor to the locked
version); ceilings stay at the next major. qdrant-client is not core — it lives in `[rag]`.

Every outbound HTTP client — providers, embedders, MCP — goes through `utils/url_validation.py`:
pass `http_client=httpx2.Client(transport=build_pinned_transport_for_url(url))` instead of letting
an SDK build its own client, which follows redirects and re-resolves DNS unchecked.

One HTTP client library: `httpx2` (Pydantic's maintained continuation of httpx) carries this
library's own requests, the OpenAI SDK and — since anthropic 1.0.0 — the Anthropic SDK too.
The separate `httpx<1` dependency is gone; anthropic 1.0.0 rejects an httpx client with
`TypeError: Expected an instance of httpx2.Client`, so the floor must never drop below 1.0.0.
`build_pinned_transport_for_url()` still takes an `http=` argument and works against either
module, which is why one guard implementation covers a future SDK that diverges again.

That release also removed `temperature`, `top_p` and `top_k` from `messages.create()` and
`messages.stream()`. Never write `params["temperature"]` for an Anthropic call — use
`apply_anthropic_temperature(params, temperature)` from `providers/temperature_constraints.py`,
which clamps to 0–1 and routes the value into `extra_body`; whether a model takes it at all is
learned (`providers/anthropic_shared.py`).

### Optional

- `[dev]` - pytest, ruff, mypy, twine, pytest-cov, pytest-asyncio, pre-commit, pip-audit, python-dotenv
- `[security]` - puremagic (MIME validation)
- `[pdf]` - pymupdf (PDF to image conversion)
- `[docs]` - markitdown, pymupdf, openpyxl (document extraction)
- `[image]` - Pillow
- `[rag]` - qdrant-client (Qdrant vector retrieval; optional since v3.0.0)
- `[local]` - sentence-transformers (local embeddings)
- `[realtime]` - websockets
- `[server]` - fastapi, uvicorn, sse-starlette

The mypy floor in `pyproject.toml` and the `rev:` of the mypy hook in `.pre-commit-config.yaml`
move together. CI type-checks `src/` only.
