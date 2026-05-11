# Testing Patterns

**Analysis Date:** 2026-05-11

## Test Framework

**Runner:**
- pytest 8.x–9.x
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`

**Assertion Library:**
- pytest built-in assertions (no external assertion library)

**Async Support:**
- `pytest-asyncio` with `asyncio_mode = "auto"` (no explicit `@pytest.mark.asyncio` needed)

**Coverage:**
- `pytest-cov` — branch coverage enabled
- Source: `src/eq_chatbot_core`
- Exclusions: `pragma: no cover`, `def __repr__`, `raise NotImplementedError`, `if TYPE_CHECKING:`

**Run Commands:**
```bash
pytest tests/unit/ -v                                          # Unit tests only (fast, mocked)
pytest tests/ -v --cov=eq_chatbot_core --cov-report=html       # All tests with coverage
pytest -m unit -v                                              # Unit tests by marker
pytest -m integration -v                                       # Integration tests (real API)
pytest -m local -v                                             # Local server tests
pytest tests/unit/test_openai.py -v                            # Single file
pytest tests/unit/test_openai.py::TestOpenAIProviderInit::test_basic_init -v  # Single test
SKIP_LIVE_TESTS=true pytest tests/ -v                          # Skip integration tests
```

## Test File Organization

**Location:**
- Tests are in a separate `tests/` directory (not co-located with source)
- `tests/unit/` — mocked tests, no external dependencies
- `tests/unit/server/` — sub-package for server/FastAPI tests
- `tests/integration/` — live API tests requiring real credentials

**Naming:**
- `test_{module_name}.py` for unit tests: `test_openai.py`, `test_chunker.py`
- `test_{module_name}_live.py` for integration tests: `test_openai_live.py`, `test_mammouth_live.py`
- Test functions: `test_{description}` — descriptive snake_case
- Test classes: `Test{Subject}{Aspect}` — e.g., `TestOpenAIProviderInit`, `TestOpenAIChatCompletion`

**Structure:**
```
tests/
├── conftest.py              # Fixtures, skip helpers, report generator, model resolution
├── model_registry.py        # Model fallback chains — version-controlled single source of truth
├── .env.example             # Template for test credentials
├── .env.test                # Local credentials (gitignored)
├── INTEGRATION_TESTS.md     # Integration test docs
├── reports/
│   ├── latest.md            # Auto-generated report from last run
│   └── test-report-*.md     # Timestamped reports
├── unit/
│   ├── __init__.py
│   ├── test_openai.py
│   ├── test_anthropic.py
│   ├── test_langdock.py
│   ├── test_openrouter.py
│   ├── test_mammouth.py
│   ├── test_azure.py
│   ├── test_vertex.py
│   ├── test_local.py
│   ├── test_factory.py
│   ├── test_exceptions.py
│   ├── test_temperature_constraints.py
│   ├── test_cost_service.py
│   ├── test_error_handler.py
│   ├── test_encryption.py
│   ├── test_injection.py
│   ├── test_rate_limit.py
│   ├── test_file_validator.py
│   ├── test_chunker.py
│   ├── test_retriever.py
│   ├── test_context_manager.py
│   ├── test_knowledge_service.py
│   ├── test_mcp.py
│   ├── test_cli_chat.py
│   └── server/
│       ├── test_app.py
│       ├── test_auth.py
│       ├── test_cli_serve.py
│       └── test_streaming.py
└── integration/
    ├── __init__.py
    ├── test_openai_live.py
    ├── test_openrouter_live.py
    ├── test_mammouth_live.py
    ├── test_azure_live.py
    ├── test_vertex_live.py
    ├── test_local_live.py
    └── test_mcp_live.py
```

## Test Structure

**Suite Organization:**
```python
@pytest.mark.unit
class TestOpenAIProviderInit:
    """Test OpenAI provider initialization."""

    def test_basic_init(self):
        """Test basic provider initialization."""
        provider = OpenAIProvider(api_key="sk-test-key")
        assert provider.api_key == "sk-test-key"
        assert provider.provider_name == "openai"

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        ...
```

**Patterns:**
- Group related tests into marker-decorated classes; each class has a docstring
- Test methods have short, descriptive docstrings
- `# ===` section separators between class groups in large test files
- Setup via per-test-class fixtures (not `setUp`/`tearDown` — pytest style)
- No global state mutation between tests

## Mocking

**Framework:** `unittest.mock.MagicMock`

**Critical Pattern — Mock SDK before import:**
```python
import sys
from unittest.mock import MagicMock

# MUST happen before importing the provider
mock_openai_module = MagicMock()
sys.modules["openai"] = mock_openai_module

from eq_chatbot_core.providers.openai_provider import OpenAIProvider
```
This prevents `ImportError` and ensures SDK calls hit the mock. Ruff rule E402 is suppressed in test files for exactly this pattern.

**Mock Setup Pattern:**
```python
@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI chat completion response."""
    response = MagicMock()
    response.model = "gpt-4o"
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test response"
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    return response
```

**Client Injection Pattern (per-test):**
```python
def test_simple_completion(self, mock_openai_response):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_openai_response
    mock_openai_module.OpenAI.return_value = mock_client

    provider = OpenAIProvider(api_key="sk-test")
    provider._client = None   # Force lazy re-init to pick up new mock
    response = provider.chat_completion(messages=[...])
    ...
```

**MagicMock `name` caveat:** MagicMock's constructor `name` param is special (sets the mock's own name, not an attribute). Always set `.name` as an attribute afterward:
```python
function_mock = MagicMock()
function_mock.name = "get_weather"   # NOT MagicMock(name="get_weather")
```

**httpx mock:**
```python
@pytest.fixture
def mock_httpx_client():
    import httpx
    client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {...}
    client.post.return_value = mock_response
    return client
```

**What to Mock:**
- All external SDK clients (openai, anthropic, httpx)
- `sys.modules` for optional-extra SDKs (azure-ai-inference, google-genai) in unit tests

**What NOT to Mock:**
- Internal library logic (`temperature_constraints`, `cost_service`, etc.) — test real behavior
- `pytest.skip()` conditions — let conftest handle them

## Fixtures

**Scope:**
- `scope="session"` — `test_config`, `resolved_models`, all `*_resolved_model` fixtures (expensive: calls live APIs once)
- Default (function scope) — provider instances, mock clients, sample data

**Key Fixtures in `tests/conftest.py`:**
```python
test_config          # Session dict of all env-var config (API keys, flags, timeouts)
resolved_models      # Session cache: {provider_key -> ResolvedModel}

# Session-scoped resolved model fixtures (validate against live provider.list_models()):
openai_resolved_model
anthropic_resolved_model
langdock_resolved_model
langdock_anthropic_resolved_model
openrouter_resolved_model
mammouth_resolved_model
azure_resolved_model
vertex_resolved_model
local_resolved_model

# Function-scoped provider instances (skip if no API key):
openai_provider
anthropic_provider
local_provider_lm_studio
local_provider_ollama

# Function-scoped mock clients (unit tests):
mock_openai_client
mock_anthropic_client
mock_httpx_client

# Function-scoped data fixtures:
sample_messages          # [{"role": "system", ...}, {"role": "user", "content": "Hello!"}]
minimal_test_messages    # [{"role": "user", "content": "Say 'test' only."}]
encryption_key           # Generated Fernet key
```

**Test Config Source:**
- `tests/.env.test` loaded at session start via `python-dotenv` (or manual parse fallback)
- Never hardcode API keys or model IDs in test files
- `TEST_MAX_TOKENS = 300` and `TEST_TIMEOUT = 30` defined in `tests/model_registry.py`

## Test Markers

Defined in both `pyproject.toml` and `conftest.pytest_configure`:

| Marker | Meaning | Default |
|--------|---------|---------|
| `unit` | Mocked, no external deps, fast | Always runs |
| `integration` | Real API calls, requires keys | Skipped if `SKIP_LIVE_TESTS=true` |
| `local` | Requires running LM Studio or Ollama | Skipped if `SKIP_LOCAL_TESTS=true` (default) |
| `expensive` | Expensive models, avoid in CI | Skipped if `CI` env var set |
| `slow` | Long-running tests | Informational only |

**Auto-skip logic in `conftest.pytest_collection_modifyitems`:**
```python
if "integration" in item.keywords and skip_live:
    item.add_marker(pytest.mark.skip(reason="SKIP_LIVE_TESTS is true"))
if "local" in item.keywords and skip_local:
    item.add_marker(pytest.mark.skip(reason="SKIP_LOCAL_TESTS is true"))
if "expensive" in item.keywords and os.getenv("CI"):
    item.add_marker(pytest.mark.skip(reason="Expensive tests skipped in CI"))
```

**Skip helpers (function-based, not decorators):**
```python
from tests.conftest import skip_if_no_openai_key, skip_if_live_tests_disabled

@skip_if_no_openai_key()
def test_something(): ...
```

## Model Registry Pattern

`tests/model_registry.py` is the **single source of truth** for which models integration tests use. Never hardcode model IDs in test files.

```python
from tests.model_registry import MODELS, ModelChain

MODELS = {
    "openai": ModelChain(
        primary="gpt-4o-mini",
        fallbacks=("gpt-4.1-nano",),
        cost_hint="$0.15 / $0.60 per 1M tok",
        notes="...",
    ),
    ...
}
```

**Resolver flow:**
1. `*_resolved_model` session fixtures call `provider.list_models()` once
2. Walk `ModelChain.candidates` (primary first, then fallbacks)
3. If primary missing, emit `DeprecationWarning` and use fallback
4. `WARN` rows in the Markdown report signal that `model_registry.py` needs updating

**Env-var override:** `OPENAI_TEST_MODEL=...` in `.env.test` overrides the registry primary for ad-hoc debugging without editing registry.

## Integration Test Structure

```python
@pytest.mark.integration
class TestOpenAILive:
    """Live integration tests for OpenAI provider."""

    @pytest.fixture
    def provider(self, openai_api_key):
        """Create provider — skips if no API key."""
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY not set")
        return get_provider("openai", api_key=openai_api_key)

    def test_simple_completion(self, provider, test_config, openai_resolved_model):
        """Test simple chat completion with resolved cheapest model."""
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=openai_resolved_model,   # from registry, not hardcoded
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )
        assert response.content
        assert "test" in response.content.lower()
        assert response.input_tokens > 0
        print(f"\n  Model: {response.model}")    # print for -v output
```

**Cost control rules:**
- Use `test_config["max_tokens"]` (default 300) — never set `max_tokens` higher in live tests
- Use cheapest model from registry (`primary` is always cheapest)
- `temperature=0.0` for deterministic assertions
- Minimal prompts: `"Say 'test' only."`, `"Count: 1, 2, 3"`, `"1"` (1 token input)

## Error Testing

**Provider error testing pattern:**
```python
def test_rate_limit_error(self):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Error code: 429 - Rate limit exceeded")
    mock_openai_module.OpenAI.return_value = mock_client

    provider = OpenAIProvider(api_key="sk-test")
    provider._client = None

    with pytest.raises(RateLimitError) as exc_info:
        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert exc_info.value.status_code == 429
    assert exc_info.value.provider == "openai"
```

**Exact subtype check:**
```python
assert type(exc_info.value) is ProviderError  # not isinstance — verifies it's NOT a subclass
```

## Async Testing

`asyncio_mode = "auto"` in `pyproject.toml` means async tests work without decoration:
```python
async def test_something():
    result = await some_async_function()
    assert result
```

## Coverage

**Requirements:** No enforced minimum (no `--cov-fail-under` in config)

**Coverage config (`pyproject.toml`):**
```toml
[tool.coverage.run]
source = ["src/eq_chatbot_core"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

**View Coverage:**
```bash
pytest tests/ --cov=eq_chatbot_core --cov-report=html
open htmlcov/index.html
```

## Markdown Test Reports

`conftest.pytest_terminal_summary` auto-generates a Markdown report after every run:
- Timestamped file: `tests/reports/test-report-{YYYY-MM-DD_HH-MM-SS}.md`
- Symlink: `tests/reports/latest.md`
- Sections: Summary table, Configuration Status (missing API keys), Models In Use (with cost hints and fallback status), Failed/Skipped tests, Results by Module, Detailed Results
- `WARN` rows in "Models In Use" → `tests/model_registry.py` needs updating
- `ACTION` rows in skipped tests → missing `*_API_KEY` in `tests/.env.test`

---

*Testing analysis: 2026-05-11*
