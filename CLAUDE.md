# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
provider = get_provider("azure", api_key="...", base_url="https://your-resource.openai.azure.com/openai/v1/")
provider = get_provider("litellm", api_key="...", base_url="https://gateway/v1")  # OpenAI-compatible gateway
provider = get_provider("ionos", api_key="...")  # IONOS AI Model Hub (EU-hosted, base_url has a default)
provider = get_provider("melious", api_key="sk-mel-...")  # Melious.ai (sovereign EU-hosted, base_url has a default)

# Local providers (LM Studio, Ollama)
provider = get_provider("lm_studio")  # defaults to localhost:1234
provider = get_provider("ollama")      # defaults to localhost:11434
provider = get_provider("local", base_url="http://custom:port/v1")
```

### Provider Base Class

All providers inherit from `BaseLLMProvider` and must implement:

```python
class BaseLLMProvider(ABC):
    provider_name: str              # Property: "openai", "anthropic", etc.
    default_model: str              # Property: Default model ID

    def chat_completion(messages, model, temperature, max_tokens, tools) -> LLMResponse
    def stream_completion(messages, model, ...) -> Iterator[StreamChunk]
    def list_models() -> list[dict]
```

### Response Types

- `LLMResponse`: Complete response with content, token counts, tool_calls
- `StreamChunk`: Streaming delta with is_final flag and accumulated tool_calls
- `ModelInfo`: Model metadata (id, context_length, supports_vision, etc.)

### Exception Hierarchy

```
ProviderError (base)
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
│   ├── openai_provider.py  # OpenAI
│   ├── anthropic_provider.py
│   ├── azure_provider.py   # Azure AI Foundry (OpenAI /v1 endpoint, no extra)
│   ├── langdock_provider.py # LangDock gateway (EU/US regions)
│   ├── openrouter_provider.py # OpenRouter (400+ models)
│   ├── litellm_provider.py  # LiteLLM / any OpenAI-compatible gateway
│   ├── ionos_provider.py    # IONOS AI Model Hub (EU-hosted, OpenAI-compatible)
│   ├── melious_provider.py  # Melious.ai (sovereign EU-hosted, OpenAI-compatible)
│   └── local_provider.py   # LM Studio, Ollama (OpenAI-compatible)
├── security/
│   ├── encryption.py       # FernetEncryption for API key storage
│   ├── injection.py        # Prompt injection detection
│   ├── rate_limit.py       # Token bucket rate limiter
│   └── file_validator.py   # MIME type validation (requires [security])
├── rag/
│   ├── chunker.py          # Text chunking strategies
│   ├── embedder.py         # Embedding generation
│   ├── retriever.py        # Qdrant vector retrieval
│   └── context_manager.py  # RAG context assembly
├── mcp/
│   └── client.py           # MCP client (HTTP/SSE and stdio transports)
├── services/
│   ├── cost_service.py     # Token cost calculation
│   ├── error_handler.py    # Centralized error handling
│   └── knowledge_service.py # Knowledge export for vector DBs
├── utils/
│   ├── pricing.py          # Model pricing data
│   └── pdf.py              # PDF to image (requires [pdf])
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

Copy `tests/.env.example` to `tests/.env.test` for API keys. Environment variables:

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`, `MAMMOUTH_API_KEY`, `AZURE_API_KEY`, `AZURE_ENDPOINT`
- `SKIP_LIVE_TESTS=true` - Skip integration tests
- `SKIP_LOCAL_TESTS=true` - Skip local server tests
- `TEST_MAX_TOKENS=20` - Limit tokens for cost control

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

openai, anthropic, httpx, pydantic, cryptography, tiktoken, qdrant-client, click

### Optional

- `[dev]` - pytest, ruff, mypy, twine, pytest-cov, pytest-asyncio
- `[security]` - puremagic (MIME validation)
- `[pdf]` - pymupdf (PDF to image conversion)
- `[azure]` - empty since v2.0.0 (kept as a no-op; the Azure provider uses the core `openai` SDK)
- `[local]` - sentence-transformers (local embeddings)
