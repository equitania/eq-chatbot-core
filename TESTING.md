# Testing Guide - eq_chatbot_core

Comprehensive testing documentation for the eq_chatbot_core Python library.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Configuration](#test-configuration)
- [Test Categories](#test-categories)
- [Running Tests](#running-tests)
- [Cost-Effective Testing](#cost-effective-testing)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Setup virtual environment
cd /Users/picard/gitbase/PyPi-Projects/eq_chatbot_core
uv venv && source .venv/bin/activate

# 2. Install with dev dependencies
uv pip install -e ".[dev]"

# 3. Configure API keys (already done - tests/.env.test)

# 4. Run unit tests (no API calls, fast)
pytest tests/unit/ -v

# 5. Run integration tests (real API calls)
pytest tests/integration/ -v -m integration
```

---

## Test Configuration

### Configuration File Location

The test configuration is loaded from:
```
tests/.env.test
```

**IMPORTANT**: The file must be named `.env.test`, not `.env`!

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for integration tests | - |
| `ANTHROPIC_API_KEY` | Anthropic API key for integration tests | - |
| `LANGDOCK_API_KEY` | LangDock API key for integration tests | - |
| `MAMMOUTH_API_KEY` | Mammouth AI API key for integration tests | - |
| `OPENAI_TEST_MODEL` | Model for OpenAI tests | `gpt-4o-mini` |
| `ANTHROPIC_TEST_MODEL` | Model for Anthropic tests | `claude-3-haiku-20240307` |
| `LANGDOCK_TEST_MODEL` | Model for LangDock tests | `gpt-5.2` |
| `MAMMOUTH_TEST_MODEL` | Model for Mammouth tests | `gpt-4.1-nano` |
| `SKIP_LIVE_TESTS` | Skip integration tests | `false` |
| `SKIP_LOCAL_TESTS` | Skip local LLM tests | `true` |
| `TEST_MAX_TOKENS` | Max tokens per test completion | `20` |
| `TEST_TIMEOUT` | Test timeout in seconds | `30` |

### Local LLM Configuration (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `LM_STUDIO_URL` | LM Studio server URL | `http://localhost:1234/v1` |
| `LOCAL_TEST_MODEL` | Model for local tests | `phi-4-mini` |

---

## Test Categories

### Pytest Markers

| Marker | Description | API Required |
|--------|-------------|--------------|
| `@pytest.mark.unit` | Mocked tests, no external calls | No |
| `@pytest.mark.integration` | Real API calls | Yes |
| `@pytest.mark.local` | Local LLM server tests | Server running |
| `@pytest.mark.expensive` | Expensive model tests | Yes (skipped in CI) |
| `@pytest.mark.slow` | Long-running tests | Depends |

### Test Directory Structure

```
tests/
├── conftest.py                        # Fixtures, configuration loading
├── .env.test                          # API keys (gitignored!)
├── .env.example                       # Template for .env.test
├── unit/                              # Mocked unit tests (1012 tests)
│   ├── test_openai.py                 # OpenAI provider tests
│   ├── test_anthropic.py              # Anthropic provider tests
│   ├── test_langdock.py               # LangDock provider tests
│   ├── test_openrouter.py             # OpenRouter provider tests
│   ├── test_mammouth.py               # Mammouth AI provider tests
│   ├── test_temperature_constraints.py # Shared temperature clamping tests
│   ├── test_local.py                  # Local provider tests
│   ├── test_factory.py                # Provider factory tests
│   ├── test_exceptions.py             # Exception handling tests
│   ├── test_cost_service.py           # Token cost calculation tests
│   ├── test_error_handler.py          # Error handler tests
│   ├── test_injection.py              # Prompt injection tests
│   ├── test_encryption.py             # Encryption tests
│   ├── test_rate_limit.py             # Rate limiting tests
│   ├── test_file_validator.py         # File validation tests
│   ├── test_chunker.py                # Text chunking tests
│   ├── test_retriever.py              # Vector retrieval tests
│   ├── test_context_manager.py        # RAG context tests
│   ├── test_knowledge_service.py      # Knowledge export tests
│   └── test_mcp.py                    # MCP client tests
└── integration/                       # Live API tests
    ├── test_openai_live.py            # OpenAI + Anthropic + LangDock live tests
    ├── test_mammouth_live.py          # Mammouth AI live tests
    ├── test_mcp_live.py               # MCP server live tests
    └── test_local_live.py             # LM Studio local tests
```

---

## Running Tests

### Unit Tests (Recommended for Development)

Fast, no API calls, no costs:

```bash
# All unit tests
pytest tests/unit/ -v

# With coverage report
pytest tests/unit/ -v --cov=eq_chatbot_core --cov-report=html

# Specific provider
pytest tests/unit/test_openai.py -v
pytest tests/unit/test_anthropic.py -v
pytest tests/unit/test_langdock.py -v
pytest tests/unit/test_openrouter.py -v
pytest tests/unit/test_mammouth.py -v

# Temperature constraints (shared module)
pytest tests/unit/test_temperature_constraints.py -v

# Specific test class
pytest tests/unit/test_openai.py::TestOpenAIChatCompletion -v

# Specific test function
pytest tests/unit/test_openai.py::TestOpenAIChatCompletion::test_simple_completion -v
```

### Integration Tests (Real API Calls)

**Caution**: These tests make real API calls and incur costs!

```bash
# All integration tests (OpenAI + Anthropic + LangDock + Mammouth)
pytest tests/integration/ -v -m integration

# OpenAI tests only
pytest tests/integration/test_openai_live.py::TestOpenAILive -v

# Anthropic tests only
pytest tests/integration/test_openai_live.py::TestAnthropicLive -v

# LangDock tests only (OpenAI backend)
pytest tests/integration/test_openai_live.py::TestLangDockLive -v

# LangDock Anthropic backend tests
pytest tests/integration/test_openai_live.py::TestLangDockAnthropicBackend -v

# Mammouth AI tests
pytest tests/integration/test_mammouth_live.py -v

# Cost-effective pattern tests
pytest tests/integration/test_openai_live.py::TestCostEffectivePatterns -v
```

### Local LLM Tests

Requires LM Studio running (recommended for macOS):

```bash
# Enable local tests (set in .env.test)
SKIP_LOCAL_TESTS=false

# Start LM Studio
# 1. Download from https://lmstudio.ai/
# 2. Load phi-4-mini model (recommended)
# 3. Start the local server (port 1234)

# Run local tests
pytest tests/integration/test_local_live.py -v -m local
```

| Test Class | Tests | Description |
|------------|-------|-------------|
| `TestLMStudioLive` | 6 | Connection, models, completion, streaming, multi-turn |
| `TestLocalProviderGeneric` | 4 | Provider properties, response types, temperature |
| `TestLocalProviderErrorsLive` | 1 | Error handling with invalid URL |

**Note:** Tests automatically detect if LM Studio is available and skip if the server is not running.

### Mammouth AI Tests

```bash
# Unit tests (mocked, no API calls)
pytest tests/unit/test_mammouth.py -v

# Integration tests (real API calls, requires MAMMOUTH_API_KEY)
pytest tests/integration/test_mammouth_live.py -v -m integration
```

### All Tests

```bash
# Run everything (unit + integration)
pytest tests/ -v

# Skip expensive models
pytest tests/ -v -m "not expensive"

# Skip slow tests
pytest tests/ -v -m "not slow"
```

### Output Options

```bash
# Verbose output with captured prints
pytest tests/ -v -s

# Short traceback
pytest tests/ -v --tb=short

# Show slowest tests
pytest tests/ -v --durations=10

# Stop on first failure
pytest tests/ -v -x

# Show local variables in traceback
pytest tests/ -v --tb=long
```

---

## Cost-Effective Testing

### Model Pricing (as of 2026)

| Provider | Model | Input $/1M | Output $/1M |
|----------|-------|-----------|-------------|
| OpenAI | gpt-4o-mini | $0.15 | $0.60 |
| OpenAI | gpt-4o | $2.50 | $10.00 |
| Anthropic | claude-3-haiku | $0.25 | $1.25 |
| Anthropic | claude-3-5-sonnet | $3.00 | $15.00 |
| Anthropic | claude-sonnet-4 | $3.00 | $15.00 |
| Mammouth | gpt-4o-mini (via Mammouth) | $0.15 | $0.60 |

### Recommended Test Settings

```bash
# In tests/.env.test
OPENAI_TEST_MODEL=gpt-4o-mini          # Cheapest OpenAI
ANTHROPIC_TEST_MODEL=claude-3-haiku-20240307  # Cheapest Anthropic
TEST_MAX_TOKENS=20                      # Minimize output tokens
```

### Estimated Test Costs

| Test Suite | Estimated Cost |
|------------|----------------|
| Unit tests (all) | $0.00 |
| Integration tests (minimal) | ~$0.01 |
| Full integration suite | ~$0.05 |

### Best Practices

1. **Run unit tests first** - They're free and fast
2. **Use minimal prompts** - "Say 'test'" instead of long prompts
3. **Limit max_tokens** - Keep `TEST_MAX_TOKENS=20`
4. **Use cheapest models** - gpt-4o-mini, claude-3-haiku
5. **Skip in CI without keys** - Set `SKIP_LIVE_TESTS=true`

---

## Test Patterns

### Example: Integration Test with Cost Awareness

```python
@pytest.mark.integration
def test_minimal_token_usage(self, openai_api_key, test_config):
    """Demonstrate minimal token usage pattern."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set")

    provider = get_provider("openai", api_key=openai_api_key)

    response = provider.chat_completion(
        messages=[{"role": "user", "content": "1"}],  # Minimal input
        model="gpt-4o-mini",
        max_tokens=1,  # Minimal output
        temperature=0.0,
    )

    # Estimated cost: < $0.0001
    print(f"Tokens: {response.input_tokens + response.output_tokens}")
```

### Example: Skip Condition

```python
from tests.conftest import skip_if_no_openai_key

@skip_if_no_openai_key()
def test_requires_openai():
    # Only runs if OPENAI_API_KEY is set
    pass
```

---

## Troubleshooting

### Tests are skipped

**Problem**: All integration tests are skipped.

**Solution**: Check `tests/.env.test`:
```bash
# Make sure this is set
SKIP_LIVE_TESTS=false

# Verify API keys are set (not placeholder values)
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Configuration file not loaded

**Problem**: API keys not recognized.

**Solution**: Ensure the file is named `.env.test` (not `.env`):
```bash
ls -la tests/.env*
# Should show: tests/.env.test
```

### Rate limit errors

**Problem**: `RateLimitError` during tests.

**Solution**:
1. Wait a few seconds and retry
2. Reduce concurrent test runs
3. Check your API quota limits

### Local tests failing

**Problem**: Local LLM tests fail with connection errors.

**Solution**:
1. Start LM Studio and load a model (phi-4-mini recommended):
   ```bash
   # Verify server is running
   curl http://localhost:1234/v1/models
   ```
2. Check `SKIP_LOCAL_TESTS=false` in `.env.test`

### Import errors

**Problem**: `ModuleNotFoundError` when running tests.

**Solution**: Install in development mode:
```bash
uv pip install -e ".[dev]"
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=eq_chatbot_core

  integration-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run integration tests
        run: pytest tests/integration/ -v -m integration
```

---

## Summary: Quick Command Reference

| Task | Command |
|------|---------|
| All unit tests | `pytest tests/unit/ -v` |
| All integration tests | `pytest tests/integration/ -v -m integration` |
| OpenAI unit tests | `pytest tests/unit/test_openai.py -v` |
| Anthropic unit tests | `pytest tests/unit/test_anthropic.py -v` |
| LangDock unit tests | `pytest tests/unit/test_langdock.py -v` |
| OpenRouter unit tests | `pytest tests/unit/test_openrouter.py -v` |
| Mammouth unit tests | `pytest tests/unit/test_mammouth.py -v` |
| Temperature constraints | `pytest tests/unit/test_temperature_constraints.py -v` |
| OpenAI live tests | `pytest tests/integration/test_openai_live.py::TestOpenAILive -v` |
| Anthropic live tests | `pytest tests/integration/test_openai_live.py::TestAnthropicLive -v` |
| LangDock live tests | `pytest tests/integration/test_openai_live.py::TestLangDockLive -v` |
| LangDock Anthropic | `pytest tests/integration/test_openai_live.py::TestLangDockAnthropicBackend -v` |
| Mammouth live tests | `pytest tests/integration/test_mammouth_live.py -v` |
| LM Studio live tests | `pytest tests/integration/test_local_live.py -v -m local` |
| With coverage | `pytest tests/ -v --cov=eq_chatbot_core --cov-report=html` |
| Stop on failure | `pytest tests/ -v -x` |
| Show prints | `pytest tests/ -v -s` |
| Specific test | `pytest tests/unit/test_openai.py::TestClassName::test_method -v` |
