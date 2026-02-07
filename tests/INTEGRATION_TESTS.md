# Integration Test Overview

Comprehensive overview of all integration tests that require real API keys or running services.

## Quick Start

```bash
# 1. Copy environment template
cp tests/.env.example tests/.env.test

# 2. Fill in your API keys in tests/.env.test

# 3. Run all integration tests
pytest -m integration -v

# 4. Run only local server tests
pytest -m local -v

# 5. Run everything (unit + integration)
pytest tests/ -v
```

## Environment Configuration

| Variable | Required For | Default | Description |
|----------|-------------|---------|-------------|
| `OPENAI_API_KEY` | OpenAI tests | - | API key from platform.openai.com |
| `ANTHROPIC_API_KEY` | Anthropic tests | - | API key from console.anthropic.com |
| `LANGDOCK_API_KEY` | LangDock tests | - | API key from app.langdock.com |
| `MCP_TEST_URL` | MCP SSE tests | - | MCP server URL (e.g. `http://localhost:8000/sse`) |
| `LM_STUDIO_URL` | LM Studio tests | `http://localhost:1234/v1` | LM Studio server URL |
| `OLLAMA_URL` | Ollama tests | `http://localhost:11434/v1` | Ollama server URL |
| `SKIP_LIVE_TESTS` | - | `false` | Set `true` to skip all cloud API tests |
| `SKIP_LOCAL_TESTS` | - | `true` | Set `false` to enable local server tests |
| `TEST_MAX_TOKENS` | - | `20` | Max tokens per test request (cost control) |
| `TEST_TIMEOUT` | - | `30` | Test timeout in seconds |

## Test Markers

| Marker | Meaning | Command |
|--------|---------|---------|
| `unit` | Mocked tests, no external dependencies | `pytest -m unit` |
| `integration` | Real API calls, requires keys | `pytest -m integration` |
| `local` | Requires running local LLM server | `pytest -m local` |
| `expensive` | Uses expensive models, skipped in CI | `pytest -m expensive` |
| `slow` | Long-running tests | `pytest -m slow` |

## Skip Behavior

- Tests without API key: **Automatically skipped** (via `pytest.skip()`)
- Tests with unavailable local server: **Automatically skipped** (via `skipif` markers)
- `SKIP_LIVE_TESTS=true`: Skips all `@pytest.mark.integration` tests
- `SKIP_LOCAL_TESTS=true` (default): Skips all `@pytest.mark.local` tests
- CI environment (`CI=true`): Skips `@pytest.mark.expensive` tests

---

## Cloud Provider Tests

### File: `tests/integration/test_openai_live.py`

**Required Key:** `OPENAI_API_KEY`
**Default Model:** `gpt-4o-mini` ($0.15/1M input, $0.60/1M output)

| # | Test Class | Test Method | What It Does | Tokens Used |
|---|-----------|-------------|--------------|-------------|
| 1 | `TestOpenAILive` | `test_simple_completion` | Chat completion with "Say 'test' only." | ~10 in / ~5 out |
| 2 | `TestOpenAILive` | `test_list_models` | Lists all available OpenAI models | 0 (metadata call) |
| 3 | `TestOpenAILive` | `test_streaming_completion` | Streaming with "Count: 1, 2, 3" | ~10 in / ~20 out |
| 4 | `TestOpenAILive` | `test_system_message` | System message forcing "ACKNOWLEDGED" response | ~20 in / ~5 out |
| 5 | `TestOpenAILive` | `test_json_mode` | JSON response format (`response_format`) | ~30 in / ~15 out |

**Estimated cost per full run:** < $0.001

---

**Required Key:** `ANTHROPIC_API_KEY`
**Default Model:** `claude-3-haiku-20240307` ($0.25/1M input, $1.25/1M output)

| # | Test Class | Test Method | What It Does | Tokens Used |
|---|-----------|-------------|--------------|-------------|
| 6 | `TestAnthropicLive` | `test_simple_completion` | Chat completion with "Say 'test' only." | ~10 in / ~5 out |
| 7 | `TestAnthropicLive` | `test_list_models` | Lists all available Anthropic models | 0 (metadata call) |
| 8 | `TestAnthropicLive` | `test_streaming_completion` | Streaming with "Count: 1, 2, 3" | ~10 in / ~20 out |
| 9 | `TestAnthropicLive` | `test_system_message` | System message forcing number-only response | ~20 in / ~5 out |

**Estimated cost per full run:** < $0.001

---

**Required Key:** `LANGDOCK_API_KEY`
**Default Model:** `gpt-4o-mini` (OpenAI backend), `claude-haiku-4-5-20251001` (Anthropic backend)
**Region:** EU (GDPR-compliant)

| # | Test Class | Test Method | What It Does | Tokens Used |
|---|-----------|-------------|--------------|-------------|
| 10 | `TestLangDockLive` | `test_simple_completion` | Chat completion via LangDock OpenAI backend | ~10 in / ~5 out |
| 11 | `TestLangDockLive` | `test_list_models` | Lists available models via LangDock | 0 (metadata call) |
| 12 | `TestLangDockLive` | `test_streaming_completion` | Streaming via LangDock | ~10 in / ~20 out |
| 13 | `TestLangDockLive` | `test_system_message` | System message via LangDock | ~20 in / ~5 out |
| 14 | `TestLangDockLive` | `test_eu_region` | Validates EU region config + simple call | ~5 in / ~5 out |
| 15 | `TestLangDockAnthropicBackend` | `test_anthropic_completion` | Chat via LangDock Anthropic backend | ~10 in / ~5 out |
| 16 | `TestLangDockAnthropicBackend` | `test_anthropic_list_models` | Lists Anthropic models via LangDock | 0 (metadata call) |

**Estimated cost per full run:** < $0.002

---

### Cost-Effective Testing Pattern

| # | Test Class | Test Method | What It Does | Tokens Used |
|---|-----------|-------------|--------------|-------------|
| 17 | `TestCostEffectivePatterns` | `test_minimal_token_usage` | Demonstrates minimal API usage pattern (1 token in, 1 out) | ~5 in / ~1 out |

**Estimated cost:** < $0.0001

---

## Local Server Tests

### File: `tests/integration/test_local_live.py`

**Required:** Running LM Studio or Ollama server (no API keys needed)
**Cost:** Free (local inference)

#### LM Studio Tests (localhost:1234)

| # | Test Class | Test Method | What It Does |
|---|-----------|-------------|--------------|
| 18 | `TestLMStudioLive` | `test_connection` | Verifies server availability |
| 19 | `TestLMStudioLive` | `test_list_models` | Lists loaded models |
| 20 | `TestLMStudioLive` | `test_simple_completion` | Simple chat completion |
| 21 | `TestLMStudioLive` | `test_system_message` | System message handling |
| 22 | `TestLMStudioLive` | `test_streaming_completion` | Streaming response |
| 23 | `TestLMStudioLive` | `test_multiple_turns` | Multi-turn conversation (remembers "42") |

#### Ollama Tests (localhost:11434)

| # | Test Class | Test Method | What It Does |
|---|-----------|-------------|--------------|
| 24 | `TestOllamaLive` | `test_connection` | Verifies server availability |
| 25 | `TestOllamaLive` | `test_list_models` | Lists downloaded models |
| 26 | `TestOllamaLive` | `test_simple_completion` | Simple chat completion |
| 27 | `TestOllamaLive` | `test_streaming_completion` | Streaming response |

#### Generic Local Provider Tests (uses first available server)

| # | Test Class | Test Method | What It Does |
|---|-----------|-------------|--------------|
| 28 | `TestLocalProviderGeneric` | `test_provider_properties` | Validates provider_name, timeout, availability |
| 29 | `TestLocalProviderGeneric` | `test_chat_completion_returns_llm_response` | Validates LLMResponse structure |
| 30 | `TestLocalProviderGeneric` | `test_stream_completion_yields_chunks` | Validates StreamChunk structure |
| 31 | `TestLocalProviderGeneric` | `test_temperature_parameter` | Temperature=0.0 consistency check |

#### Error Handling Tests

| # | Test Class | Test Method | What It Does |
|---|-----------|-------------|--------------|
| 32 | `TestLocalProviderErrorsLive` | `test_invalid_url_connection_error` | Validates ProviderError on bad URL |

---

## MCP (Model Context Protocol) Tests

### File: `tests/integration/test_mcp_live.py`

**Required:** Running MCP server (`MCP_TEST_URL` environment variable)
**Cost:** Free (no API keys for MCP)

#### SSE Transport Tests

| # | Test Class | Test Method | What It Does |
|---|-----------|-------------|--------------|
| 33 | `TestMCPLive` | `test_connect_to_server` | Establishes SSE connection, verifies initialization |
| 34 | `TestMCPLive` | `test_list_tools_live` | Lists available MCP tools |
| 35 | `TestMCPLive` | `test_list_tools_detailed` | Lists all tools with parameters and schema |
| 36 | `TestMCPLive` | `test_call_tool_live` | Calls first available tool with empty args |
| 37 | `TestMCPLive` | `test_connection_error_handling` | Validates error on non-existent server |

#### stdio Transport Tests

| # | Test Class | Test Method | What It Does |
|---|-----------|-------------|--------------|
| 38 | `TestMCPStdioLive` | `test_stdio_client_not_installed` | Validates error on unavailable command |

---

## Unit Tests (No API Keys Required)

18 test files in `tests/unit/` with ~940 tests total. All mocked, no external dependencies.

| File | Module Tested | Key Coverage |
|------|--------------|--------------|
| `test_openai.py` | OpenAI provider | Init, completion, streaming, error handling |
| `test_anthropic.py` | Anthropic provider | Init, completion, streaming, system messages |
| `test_langdock.py` | LangDock provider | Both backends, regions, model listing |
| `test_openrouter.py` | OpenRouter provider | Init, completion, model routing |
| `test_local.py` | Local provider | LM Studio, Ollama, connection errors |
| `test_factory.py` | Provider factory | `get_provider()` routing for all providers |
| `test_exceptions.py` | Exception hierarchy | All exception types, attributes |
| `test_mcp.py` | MCP client | URL validation, command whitelist, SSRF protection |
| `test_encryption.py` | Fernet encryption | Encrypt/decrypt, key generation |
| `test_injection.py` | Prompt injection | 68+ detection patterns, Unicode normalization |
| `test_rate_limit.py` | Rate limiter | Token bucket algorithm, refill logic |
| `test_file_validator.py` | File validation | MIME check, extension check, size limits |
| `test_chunker.py` | Text chunking | Split strategies, overlap handling |
| `test_retriever.py` | Qdrant retriever | Search, filter, score thresholds |
| `test_context_manager.py` | RAG context | Context assembly, token limits |
| `test_cost_service.py` | Cost calculation | Token pricing for all providers |
| `test_error_handler.py` | Error handler | Timeout, rate limit, fallback chains |
| `test_knowledge_service.py` | Knowledge export | Vector DB export, chunking |

---

## Cost Summary

| Provider | Tests | Model | Estimated Cost/Run |
|----------|-------|-------|--------------------|
| OpenAI | 5 | gpt-4o-mini | < $0.001 |
| Anthropic | 4 | claude-3-haiku | < $0.001 |
| LangDock (OpenAI) | 5 | gpt-4o-mini | < $0.001 |
| LangDock (Anthropic) | 2 | claude-haiku-4-5 | < $0.001 |
| Cost Pattern | 1 | gpt-4o-mini | < $0.0001 |
| Local (LM Studio) | 6 | local model | Free |
| Local (Ollama) | 4 | local model | Free |
| Local (Generic) | 5 | local model | Free |
| MCP (SSE) | 5 | - | Free |
| MCP (stdio) | 1 | - | Free |
| **Total** | **38** | | **< $0.005** |

All cloud API tests use `TEST_MAX_TOKENS=20` by default to minimize costs.

---

## Running Specific Provider Tests

```bash
# Only OpenAI
pytest tests/integration/test_openai_live.py::TestOpenAILive -v

# Only Anthropic
pytest tests/integration/test_openai_live.py::TestAnthropicLive -v

# Only LangDock (both backends)
pytest tests/integration/test_openai_live.py::TestLangDockLive tests/integration/test_openai_live.py::TestLangDockAnthropicBackend -v

# Only LM Studio
pytest tests/integration/test_local_live.py::TestLMStudioLive -v

# Only Ollama
pytest tests/integration/test_local_live.py::TestOllamaLive -v

# Only MCP
pytest tests/integration/test_mcp_live.py -v

# All cloud tests (no local server needed)
SKIP_LOCAL_TESTS=true pytest -m integration -v

# All local tests (no API keys needed)
SKIP_LIVE_TESTS=true pytest -m local -v
```
