"""
Pytest fixtures and configuration for eq_chatbot_core tests.

This module provides:
- Environment-based test configuration via .env.test
- Provider-specific fixtures for cloud and local LLM testing
- Mock fixtures for unit tests
- Skip markers for conditional test execution
- Markdown test report generation (auto-generated on every run)
"""

import os
import platform
import shutil
import sys
import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.model_registry import MODELS, ModelChain
from tests.model_registry import TEST_MAX_TOKENS as _TEST_MAX_TOKENS
from tests.model_registry import TEST_TIMEOUT as _TEST_TIMEOUT

# Load test environment from .env.test if it exists
_env_file = Path(__file__).parent / ".env.test"
if _env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
    except ImportError:
        # python-dotenv not installed, read manually
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


# =============================================================================
# Model Resolution
# =============================================================================
#
# Live providers rotate models constantly (deprecation, renaming). Hardcoded
# model names in tests fail with cryptic 400/404 errors. The resolver reads
# tests/model_registry.py for primary + fallback chains, validates against
# the live ``provider.list_models()`` response, and picks the first available
# candidate. When a fallback is used, a DeprecationWarning is emitted and the
# Markdown report surfaces an ACTION row. An env-var override (e.g.
# ``LANGDOCK_TEST_MODEL=...``) bypasses the registry primary.


@dataclass(frozen=True)
class ResolvedModel:
    """Outcome of resolving a model chain against a live provider.

    ``actual`` is the model the test should use. The state combines:

    - ``error`` set: ``list_models()`` raised — hard failure, treat as ERR.
    - ``unvalidated`` true: ``list_models()`` returned but no chain candidate
      matched. Some providers (Anthropic) ship versioned aliases that work
      for chat but are absent from the public model list. Treat as INFO —
      the chat call itself will surface a real failure if the model is gone.
    - ``fallback_level > 0``: registry primary missing, a fallback rescued
      the run — treat as WARN.
    - Otherwise: registry primary found in live list — OK.
    """

    requested_primary: str
    actual: str
    fallback_level: int  # 0 = primary, 1+ = fallback chain index
    available_count: int
    error: str | None = None
    unvalidated: bool = False

    @property
    def is_fallback(self) -> bool:
        return self.fallback_level > 0

    @property
    def has_error(self) -> bool:
        return self.error is not None


def _extract_model_id(entry: Any) -> str | None:
    """Pull a model id from list_models() output (dict or ModelInfo-like)."""
    if isinstance(entry, dict):
        return entry.get("id") or entry.get("model_id")
    return getattr(entry, "model_id", None) or getattr(entry, "id", None)


def _resolve_test_model(
    chain: ModelChain,
    list_models_fn: Callable[[], list[Any]],
    provider_key: str,
) -> ResolvedModel:
    """Find the first chain candidate present in the live model list.

    Behaviour:
    - If list_models_fn() raises (network, auth) → return primary with error
      annotation; downstream test surfaces the real failure with proper
      pytest skip/fail wiring instead of a cryptic 400.
    - If primary missing but fallback found → emit DeprecationWarning and
      record the fallback level for the report.
    - If nothing found → return primary with error so the next API call
      produces an actionable message pointing at the registry.
    """
    try:
        raw = list_models_fn()
        available: set[str] = {mid for mid in (_extract_model_id(m) for m in raw) if mid}
    except Exception as exc:  # pragma: no cover - exercised via integration
        return ResolvedModel(
            requested_primary=chain.primary,
            actual=chain.primary,
            fallback_level=0,
            available_count=0,
            error=f"list_models failed: {exc}",
        )

    for level, model in enumerate(chain.candidates):
        if model in available:
            if level > 0:
                warnings.warn(
                    f"[{provider_key}] primary model {chain.primary!r} unavailable. "
                    f"Using fallback {model!r} (level {level}). "
                    f"Update tests/model_registry.py.",
                    DeprecationWarning,
                    stacklevel=2,
                )
            return ResolvedModel(
                requested_primary=chain.primary,
                actual=model,
                fallback_level=level,
                available_count=len(available),
            )

    # list_models() returned but no candidate matched. This is an info
    # state, not an error: some providers (Anthropic) ship versioned aliases
    # that are valid for chat but absent from list_models(). Use the primary
    # as-is; the chat call will surface a real failure if the model is gone.
    return ResolvedModel(
        requested_primary=chain.primary,
        actual=chain.primary,
        fallback_level=0,
        available_count=len(available),
        unvalidated=True,
    )


def _select_chain(provider_key: str, env_var: str) -> ModelChain:
    """Resolve a registry chain, allowing an env-var override of the primary.

    When ``env_var`` is set, it replaces the registry primary while keeping
    the registry fallbacks. This keeps ad-hoc debugging cheap without
    forcing a registry edit.
    """
    base = MODELS[provider_key]
    override = os.getenv(env_var)
    if override:
        return ModelChain(
            primary=override,
            fallbacks=base.candidates,  # registry primary + its fallbacks
            notes=f"override via {env_var}; underlying chain = {provider_key}",
        )
    return base


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_config() -> dict[str, Any]:
    """Session-scoped test configuration from environment variables."""
    return {
        # Cloud API Keys
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
        "langdock_api_key": os.getenv("LANGDOCK_API_KEY"),
        "mammouth_api_key": os.getenv("MAMMOUTH_API_KEY"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "openrouter_site_url": os.getenv("OPENROUTER_SITE_URL"),
        "openrouter_site_name": os.getenv("OPENROUTER_SITE_NAME"),
        "azure_api_key": os.getenv("AZURE_API_KEY"),
        "azure_endpoint": os.getenv("AZURE_ENDPOINT"),
        # Vertex AI
        "vertex_project": os.getenv("VERTEX_PROJECT"),
        "vertex_location": os.getenv("VERTEX_LOCATION", "europe-west1"),
        # Local Server URLs
        "lm_studio_url": os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        # Test Settings — test models live in tests/model_registry.py.
        # *_TEST_MODEL env vars override the registry primary at the
        # resolver fixtures (langdock_resolved_model, openai_resolved_model, ...).
        "skip_live_tests": os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        "skip_local_tests": os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true",
        "max_tokens": int(os.getenv("TEST_MAX_TOKENS", str(_TEST_MAX_TOKENS))),
        "timeout": int(os.getenv("TEST_TIMEOUT", str(_TEST_TIMEOUT))),
    }


@pytest.fixture
def openai_api_key(test_config) -> str | None:
    """OpenAI API key from environment."""
    return test_config["openai_api_key"]


@pytest.fixture
def anthropic_api_key(test_config) -> str | None:
    """Anthropic API key from environment."""
    return test_config["anthropic_api_key"]


@pytest.fixture
def langdock_api_key(test_config) -> str | None:
    """LangDock API key from environment."""
    return test_config["langdock_api_key"]


@pytest.fixture
def mammouth_api_key(test_config) -> str | None:
    """Mammouth AI API key from environment."""
    return test_config["mammouth_api_key"]


@pytest.fixture
def openrouter_api_key(test_config) -> str | None:
    """OpenRouter API key from environment."""
    return test_config["openrouter_api_key"]


@pytest.fixture
def azure_api_key(test_config) -> str | None:
    """Azure API key from environment."""
    return test_config["azure_api_key"]


@pytest.fixture
def skip_live_tests(test_config) -> bool:
    """Whether to skip live API tests."""
    return test_config["skip_live_tests"]


@pytest.fixture
def skip_local_tests(test_config) -> bool:
    """Whether to skip local server tests."""
    return test_config["skip_local_tests"]


# =============================================================================
# Skip Condition Helpers
# =============================================================================


def skip_if_no_openai_key():
    """Skip test if OPENAI_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )


def skip_if_no_anthropic_key():
    """Skip test if ANTHROPIC_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set",
    )


def skip_if_no_langdock_key():
    """Skip test if LANGDOCK_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("LANGDOCK_API_KEY"),
        reason="LANGDOCK_API_KEY not set",
    )


def skip_if_no_mammouth_key():
    """Skip test if MAMMOUTH_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("MAMMOUTH_API_KEY"),
        reason="MAMMOUTH_API_KEY not set",
    )


def skip_if_no_openrouter_key():
    """Skip test if OPENROUTER_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY not set",
    )


def skip_if_no_azure_key():
    """Skip test if AZURE_API_KEY is not set."""
    return pytest.mark.skipif(
        not os.getenv("AZURE_API_KEY"),
        reason="AZURE_API_KEY not set",
    )


def skip_if_live_tests_disabled():
    """Skip test if SKIP_LIVE_TESTS is true."""
    return pytest.mark.skipif(
        os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        reason="SKIP_LIVE_TESTS is true",
    )


def skip_if_local_tests_disabled():
    """Skip test if SKIP_LOCAL_TESTS is true."""
    return pytest.mark.skipif(
        os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true",
        reason="SKIP_LOCAL_TESTS is true",
    )


# =============================================================================
# Resolved Model Fixtures (live registry validation)
# =============================================================================


@pytest.fixture(scope="session")
def resolved_models(request) -> dict[str, ResolvedModel]:
    """Session-scoped cache of resolved test models.

    Populated lazily by per-provider fixtures below. Stored on the session
    object so the Markdown report writer can render the Model Resolution
    section even after fixture teardown.
    """
    cache: dict[str, ResolvedModel] = {}
    # Stash on config so pytest_terminal_summary can render the Model
    # Resolution section without coupling to the live fixture object.
    request.config._resolved_models = cache
    return cache


@pytest.fixture(scope="session")
def langdock_resolved_model(test_config, resolved_models) -> str:
    """Resolve the LangDock OpenAI-backend test model.

    Reads ``tests/model_registry.py`` -> ``MODELS['langdock.openai']`` and
    validates against ``langdock.list_models()``. ``LANGDOCK_TEST_MODEL`` env
    var overrides the primary while keeping the registry fallbacks.
    """
    api_key = test_config.get("langdock_api_key")
    if not api_key:
        pytest.skip("LANGDOCK_API_KEY not set")

    cache_key = "langdock.openai"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("langdock", api_key=api_key, backend="openai", region="eu")
        chain = _select_chain(cache_key, "LANGDOCK_TEST_MODEL")
        resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def langdock_anthropic_resolved_model(test_config, resolved_models) -> str:
    """Resolve the LangDock Anthropic-backend test model.

    LangDock's Anthropic backend uses a different model namespace
    (``claude-*-default`` aliases) than direct Anthropic. Registry key
    is ``langdock.anthropic``; override via ``LANGDOCK_ANTHROPIC_TEST_MODEL``.
    """
    api_key = test_config.get("langdock_api_key")
    if not api_key:
        pytest.skip("LANGDOCK_API_KEY not set")

    cache_key = "langdock.anthropic"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("langdock", api_key=api_key, backend="anthropic", region="eu")
        chain = _select_chain(cache_key, "LANGDOCK_ANTHROPIC_TEST_MODEL")
        resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def openai_resolved_model(test_config, resolved_models) -> str:
    """Resolve OpenAI test model from registry against live API."""
    api_key = test_config.get("openai_api_key")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    cache_key = "openai"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("openai", api_key=api_key)
        chain = _select_chain(cache_key, "OPENAI_TEST_MODEL")
        resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def anthropic_resolved_model(test_config, resolved_models) -> str:
    """Resolve Anthropic test model from registry against live API."""
    api_key = test_config.get("anthropic_api_key")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    cache_key = "anthropic"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("anthropic", api_key=api_key)
        chain = _select_chain(cache_key, "ANTHROPIC_TEST_MODEL")
        resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def openrouter_resolved_model(test_config, resolved_models) -> str:
    """Resolve OpenRouter test model from registry against live API.

    Passes optional attribution headers (site_url, site_name) so OpenRouter
    analytics attribute the test traffic correctly.
    """
    api_key = test_config.get("openrouter_api_key")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    cache_key = "openrouter"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        kwargs: dict[str, Any] = {"api_key": api_key}
        if test_config.get("openrouter_site_url"):
            kwargs["site_url"] = test_config["openrouter_site_url"]
        if test_config.get("openrouter_site_name"):
            kwargs["site_name"] = test_config["openrouter_site_name"]
        provider = get_provider("openrouter", **kwargs)
        chain = _select_chain(cache_key, "OPENROUTER_TEST_MODEL")
        resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def mammouth_resolved_model(test_config, resolved_models) -> str:
    """Resolve Mammouth AI test model from registry against live API."""
    api_key = test_config.get("mammouth_api_key")
    if not api_key:
        pytest.skip("MAMMOUTH_API_KEY not set")

    cache_key = "mammouth"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("mammouth", api_key=api_key)
        chain = _select_chain(cache_key, "MAMMOUTH_TEST_MODEL")
        resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def azure_resolved_model(test_config, resolved_models) -> str:
    """Resolve Azure AI test model from registry against live API.

    Skips gracefully when the optional ``[azure]`` extra is not installed
    (azure-ai-inference SDK missing) instead of failing with ImportError.
    """
    api_key = test_config.get("azure_api_key")
    endpoint = test_config.get("azure_endpoint")
    if not api_key:
        pytest.skip("AZURE_API_KEY not set")
    if not endpoint:
        pytest.skip("AZURE_ENDPOINT not set")

    cache_key = "azure"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        try:
            provider = get_provider("azure", api_key=api_key, base_url=endpoint)
            chain = _select_chain(cache_key, "AZURE_TEST_MODEL")
            resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)
        except ImportError as exc:
            pytest.skip(f"Azure SDK not installed (use [azure] extra): {exc}")

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def vertex_resolved_model(test_config, resolved_models) -> str:
    """Resolve Vertex AI test model from registry against live API.

    Skips gracefully when the optional ``[vertex]`` extra is not installed
    (google-genai SDK missing) instead of failing with ImportError.
    """
    project = test_config.get("vertex_project")
    if not project:
        pytest.skip("VERTEX_PROJECT not set")

    cache_key = "vertex"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        location = test_config.get("vertex_location") or "europe-west1"
        try:
            provider = get_provider("vertex", project=project, location=location)
            chain = _select_chain(cache_key, "VERTEX_TEST_MODEL")
            resolved_models[cache_key] = _resolve_test_model(chain, provider.list_models, cache_key)
        except ImportError as exc:
            pytest.skip(f"Vertex SDK not installed (use [vertex] extra): {exc}")

    return resolved_models[cache_key].actual


@pytest.fixture(scope="session")
def local_resolved_model(test_config, resolved_models) -> str:
    """Resolve local server (LM Studio / Ollama) test model from registry.

    Skips when the local server is unreachable so the resolver does not hang
    on a network timeout.

    Local-specific behaviour: LM Studio model selection is user-specific
    (whichever model the user has downloaded and loaded). When the registry
    chain does not match, fall back to the first non-embedding model the
    server reports — this keeps the suite green across diverse local setups
    while the registry still documents preferred models.
    """
    if test_config.get("skip_local_tests"):
        pytest.skip("SKIP_LOCAL_TESTS is true")

    cache_key = "local"
    if cache_key not in resolved_models:
        from eq_chatbot_core.providers import get_provider

        provider = get_provider("lm_studio")
        if not provider.is_server_available():
            pytest.skip(f"LM Studio server unreachable at {test_config.get('lm_studio_url')}")
        chain = _select_chain(cache_key, "LOCAL_TEST_MODEL")
        resolved = _resolve_test_model(chain, provider.list_models, cache_key)

        # Local-only: when registry chain didn't match, pick the first loaded
        # chat model. Embeddings are filtered (they can't handle chat).
        if resolved.unvalidated:
            raw = provider.list_models()
            ids = [mid for mid in (_extract_model_id(m) for m in raw) if mid]
            chat_ids = [mid for mid in ids if "embed" not in mid.lower()]
            if chat_ids:
                resolved = ResolvedModel(
                    requested_primary=resolved.requested_primary,
                    actual=chat_ids[0],
                    fallback_level=0,
                    available_count=len(chat_ids),
                    unvalidated=True,
                )

        resolved_models[cache_key] = resolved

    return resolved_models[cache_key].actual


# =============================================================================
# Provider Fixtures
# =============================================================================


@pytest.fixture
def openai_provider(openai_api_key, test_config):
    """Create OpenAI provider for testing (requires API key)."""
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set")

    from eq_chatbot_core.providers import get_provider

    return get_provider("openai", api_key=openai_api_key)


@pytest.fixture
def anthropic_provider(anthropic_api_key, test_config):
    """Create Anthropic provider for testing (requires API key)."""
    if not anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    from eq_chatbot_core.providers import get_provider

    return get_provider("anthropic", api_key=anthropic_api_key)


@pytest.fixture
def local_provider_lm_studio(test_config):
    """Create LM Studio provider for testing."""
    if test_config["skip_local_tests"]:
        pytest.skip("SKIP_LOCAL_TESTS is true")

    from eq_chatbot_core.providers import get_provider

    provider = get_provider("lm_studio")

    # Check if server is available
    if not provider.is_server_available():
        pytest.skip(f"LM Studio server not available at {test_config['lm_studio_url']}")

    return provider


@pytest.fixture
def local_provider_ollama(test_config):
    """Create Ollama provider for testing."""
    if test_config["skip_local_tests"]:
        pytest.skip("SKIP_LOCAL_TESTS is true")

    from eq_chatbot_core.providers import get_provider

    provider = get_provider("ollama")

    # Check if server is available
    if not provider.is_server_available():
        pytest.skip(f"Ollama server not available at {test_config['ollama_url']}")

    return provider


# =============================================================================
# Mock Fixtures (for Unit Tests)
# =============================================================================


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for unit testing."""
    client = MagicMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(content="Hello! How can I help?", tool_calls=None),
            finish_reason="stop",
        )
    ]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=8)
    mock_response.model = "gpt-4o"
    mock_response.model_dump.return_value = {"id": "test"}

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for unit testing."""
    client = MagicMock()

    # Mock message response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Hello! How can I help?")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=8)
    mock_response.model = "claude-3-5-sonnet-20241022"

    client.messages.create.return_value = mock_response

    return client


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for local provider unit testing."""
    import httpx

    client = MagicMock(spec=httpx.Client)

    # Mock chat completion response
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test-123",
        "object": "chat.completion",
        "model": "local-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from local model!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }

    client.post.return_value = mock_response
    client.get.return_value = mock_response

    return client


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_messages() -> list[dict[str, str]]:
    """Sample message list for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]


@pytest.fixture
def minimal_test_messages() -> list[dict[str, str]]:
    """Minimal messages for cost-effective API testing."""
    return [{"role": "user", "content": "Say 'test' only."}]


@pytest.fixture
def encryption_key() -> str:
    """Generate encryption key for tests."""
    from eq_chatbot_core.security.encryption import FernetEncryption

    return FernetEncryption.generate_key()


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (mocked, fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (real API calls, requires keys)")
    config.addinivalue_line("markers", "local: Local LLM server tests (requires running server)")
    config.addinivalue_line("markers", "expensive: Tests with expensive models (skip in CI by default)")
    config.addinivalue_line("markers", "slow: Slow-running tests")


def pytest_collection_modifyitems(config, items):
    """Apply skip markers based on environment configuration."""
    skip_live = os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true"
    skip_local = os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true"

    for item in items:
        # Skip integration tests if SKIP_LIVE_TESTS is true
        if "integration" in item.keywords and skip_live:
            item.add_marker(pytest.mark.skip(reason="SKIP_LIVE_TESTS is true"))

        # Skip local tests if SKIP_LOCAL_TESTS is true
        if "local" in item.keywords and skip_local:
            item.add_marker(pytest.mark.skip(reason="SKIP_LOCAL_TESTS is true"))

        # Skip expensive tests in CI environments
        if "expensive" in item.keywords and os.getenv("CI"):
            item.add_marker(pytest.mark.skip(reason="Expensive tests skipped in CI"))


# =============================================================================
# Markdown Test Report Generator
# =============================================================================

# Store session start time
_session_start_time = None


def _get_version() -> str:
    """Read version from eq_chatbot_core."""
    try:
        from eq_chatbot_core.version import __version__

        return __version__
    except ImportError:
        return "unknown"


def _get_test_category(nodeid: str, markers: list[str]) -> str:
    """Determine test category from markers or path."""
    if "integration" in markers:
        return "integration"
    if "local" in markers:
        return "local"
    if "unit" in markers:
        return "unit"
    # Fallback: infer from path
    if "/integration/" in nodeid or "integration" in nodeid:
        return "integration"
    if "/local/" in nodeid or "local" in nodeid:
        return "local"
    return "unit"


# Module-to-group mapping for report structure
_MODULE_GROUPS = {
    "OpenAI": {
        "label": "Provider: OpenAI",
        "modules": ["test_openai", "test_openai_live"],
    },
    "Anthropic": {
        "label": "Provider: Anthropic",
        "modules": ["test_anthropic", "test_anthropic_live"],
    },
    "LangDock": {
        "label": "Provider: LangDock",
        "modules": ["test_langdock", "test_langdock_live"],
    },
    "OpenRouter": {
        "label": "Provider: OpenRouter",
        "modules": ["test_openrouter", "test_openrouter_live"],
    },
    "Mammouth": {
        "label": "Provider: Mammouth AI",
        "modules": ["test_mammouth", "test_mammouth_live"],
    },
    "Azure": {
        "label": "Provider: Azure AI",
        "modules": ["test_azure", "test_azure_live"],
    },
    "Vertex": {
        "label": "Provider: Google Vertex AI",
        "modules": ["test_vertex", "test_vertex_live"],
    },
    "Local": {
        "label": "Provider: Local (LM Studio / Ollama)",
        "modules": ["test_local", "test_local_live"],
    },
    "Security": {
        "label": "Security",
        "modules": ["test_encryption", "test_injection", "test_rate_limit", "test_file_validator"],
    },
    "RAG": {
        "label": "RAG Pipeline",
        "modules": ["test_chunker", "test_retriever", "test_context_manager", "test_knowledge_service"],
    },
    "Services": {
        "label": "Services & Core",
        "modules": [
            "test_cost_service",
            "test_error_handler",
            "test_factory",
            "test_exceptions",
            "test_temperature_constraints",
        ],
    },
    "MCP": {
        "label": "MCP Client",
        "modules": ["test_mcp", "test_mcp_live"],
    },
}

# Display labels and override env-vars for each resolver cache key.
# Drives the Markdown report's Models In Use section. Order = report row order.
_RESOLUTION_LABELS: dict[str, tuple[str, str]] = {
    "openai": ("OpenAI", "OPENAI_TEST_MODEL"),
    "anthropic": ("Anthropic", "ANTHROPIC_TEST_MODEL"),
    "langdock.openai": ("LangDock (OpenAI backend)", "LANGDOCK_TEST_MODEL"),
    "langdock.anthropic": ("LangDock (Anthropic backend)", "LANGDOCK_ANTHROPIC_TEST_MODEL"),
    "openrouter": ("OpenRouter", "OPENROUTER_TEST_MODEL"),
    "mammouth": ("Mammouth AI", "MAMMOUTH_TEST_MODEL"),
    "azure": ("Azure AI", "AZURE_TEST_MODEL"),
    "vertex": ("Google Vertex AI", "VERTEX_TEST_MODEL"),
    "local": ("Local (LM Studio / Ollama)", "LOCAL_TEST_MODEL"),
}

# What env vars must be set for each resolver to even attempt list_models().
# Used by the Models In Use section to render SKIPPED rows with actionable
# reasons when a provider was not exercised this run.
_RESOLVER_REQUIREMENTS: dict[str, list[str]] = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "langdock.openai": ["LANGDOCK_API_KEY"],
    "langdock.anthropic": ["LANGDOCK_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "mammouth": ["MAMMOUTH_API_KEY"],
    "azure": ["AZURE_API_KEY", "AZURE_ENDPOINT"],
    "vertex": ["VERTEX_PROJECT"],
    "local": [],  # gated by SKIP_LOCAL_TESTS / server-availability
}

# Module group key (used in _MODULE_GROUPS) → primary resolver key.
# Used to surface "Model: <id>" in per-provider detail sections.
# LangDock has two backends; the OpenAI one is shown in the per-group rollup
# while both appear in the main Models In Use table.
_GROUP_TO_PRIMARY_RESOLVER: dict[str, str] = {
    "OpenAI": "openai",
    "Anthropic": "anthropic",
    "LangDock": "langdock.openai",
    "OpenRouter": "openrouter",
    "Mammouth": "mammouth",
    "Azure": "azure",
    "Vertex": "vertex",
    "Local": "local",
}


# Mapping from module group to required environment variables (auth credentials).
# Used by the configuration-status section of the Markdown report so missing
# credentials are surfaced as actionable items instead of silent skips.
_GROUP_REQUIRED_ENV = {
    "OpenAI": ["OPENAI_API_KEY"],
    "Anthropic": ["ANTHROPIC_API_KEY"],
    "LangDock": ["LANGDOCK_API_KEY"],
    "OpenRouter": ["OPENROUTER_API_KEY"],
    "Mammouth": ["MAMMOUTH_API_KEY"],
    "Azure": ["AZURE_API_KEY", "AZURE_ENDPOINT"],
    "Vertex": ["VERTEX_PROJECT"],  # auth via gcloud ADC, project still required
    "Local": [],  # no key — uses local servers
}


def _resolution_row(
    cache_key: str,
    resolved_models_cache: dict[str, ResolvedModel],
) -> tuple[str, str, str, str, str]:
    """Build one row of the Models In Use table.

    Returns ``(provider_label, model_cell, cost_cell, source_cell, status_cell)``
    based on the resolver cache state for ``cache_key``. When the resolver was
    not invoked (provider not exercised this run), shows SKIPPED with the
    missing env var as actionable hint.
    """
    label, env_var = _RESOLUTION_LABELS[cache_key]
    chain = MODELS[cache_key]
    cost_cell = chain.cost_hint or "—"
    resolved = resolved_models_cache.get(cache_key)

    if resolved is None:
        # Resolver never ran. Compute likely reason for the report.
        required = _RESOLVER_REQUIREMENTS.get(cache_key, [])
        missing = [v for v in required if not os.getenv(v)]
        if missing:
            status = f"SKIPPED — set `{missing[0]}` in `tests/.env.test`"
        elif cache_key == "local":
            if os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true":
                status = "SKIPPED — `SKIP_LOCAL_TESTS=true`"
            else:
                status = "SKIPPED — provider not exercised this run"
        else:
            status = "SKIPPED — provider not exercised this run"
        return (label, "—", cost_cell, "—", status)

    model_cell = f"`{resolved.actual}`"
    env_value = os.getenv(env_var) if env_var else None
    is_override = bool(env_value) and env_value == resolved.requested_primary

    if resolved.has_error:
        source_cell = "Env override" if is_override else "Registry primary"
        err_text = _escape_md(resolved.error or "unknown")[:120]
        status_cell = f"**ERR** — {err_text}"
    elif resolved.unvalidated:
        source_cell = "Env override" if is_override else "Registry primary"
        status_cell = (
            f"INFO — `list_models()` does not list `{resolved.actual}` "
            f"({resolved.available_count} listed); chat call will validate"
        )
    elif resolved.is_fallback:
        if is_override:
            source_cell = f"Env override (fallback L{resolved.fallback_level})"
            status_cell = f"**WARN** — override `{resolved.requested_primary}` unavailable, using registry fallback"
        else:
            source_cell = f"Registry fallback L{resolved.fallback_level}"
            status_cell = (
                f"**WARN: primary deprecated** — update `tests/model_registry.py` (was `{resolved.requested_primary}`)"
            )
    else:
        source_cell = "Env override" if is_override else "Registry primary"
        status_cell = "OK"

    return (label, model_cell, cost_cell, source_cell, status_cell)


def _get_module_group(nodeid: str) -> str:
    """Determine module group from test file name."""
    # Extract filename without extension from nodeid
    # e.g. "tests/unit/test_openai.py::TestClass::test_method" -> "test_openai"
    parts = nodeid.split("::")
    filepath = parts[0]  # "tests/unit/test_openai.py"
    filename = filepath.rsplit("/", 1)[-1].replace(".py", "")  # "test_openai"

    for group_key, group_info in _MODULE_GROUPS.items():
        if filename in group_info["modules"]:
            return group_key
    return "Other"


def _format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 0.01:
        return "<0.01s"
    return f"{seconds:.2f}s"


def _escape_md(text: str) -> str:
    """Escape pipe characters for Markdown table cells."""
    return text.replace("|", "\\|").replace("\n", " ")


def _short_nodeid(nodeid: str) -> str:
    """Shorten nodeid by removing common prefixes."""
    # Remove tests/ prefix for brevity
    if nodeid.startswith("tests/"):
        return nodeid[6:]
    return nodeid


def _format_skip_reason(reason: str) -> str:
    """
    Turn ambiguous skip messages into actionable instructions.

    Specifically: any reason mentioning "<VAR>_API_KEY not set" or
    "<VAR>_KEY not set" (with or without a "Skipped: " prefix from pytest)
    becomes "ACTION — set <VAR> in tests/.env.test". Other reasons
    (SKIP_LIVE_TESTS, SKIP_LOCAL_TESTS, server unreachable) pass through
    unchanged so existing behavior isn't masked.
    """
    import re

    match = re.search(r"\b([A-Z][A-Z0-9_]*_KEY)\s+not\s+set\b", reason)
    if match:
        var_name = match.group(1)
        return f"**ACTION** — set `{var_name}` in `tests/.env.test` to enable this test"
    return reason


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect test results for Markdown report generation."""
    outcome = yield
    report = outcome.get_result()

    # Only process the 'call' phase (not setup/teardown) for pass/fail
    # but also capture 'setup' phase for skip (skips happen during setup)
    if report.when == "call" or (report.when == "setup" and report.skipped):
        results = getattr(item.config, "_md_report_results", None)
        if results is None:
            item.config._md_report_results = []
            results = item.config._md_report_results

        # Determine outcome
        test_outcome = report.outcome  # "passed", "failed", "skipped"

        # Check for xfail
        wasxfail = getattr(report, "wasxfail", "")
        if wasxfail:
            test_outcome = "xfailed"

        # Extract skip reason
        skip_reason = ""
        if report.skipped:
            if hasattr(report, "longrepr") and isinstance(report.longrepr, tuple):
                skip_reason = str(report.longrepr[2]) if len(report.longrepr) > 2 else ""
            elif wasxfail:
                skip_reason = wasxfail

        # Extract error message for failures
        error_msg = ""
        if report.failed and report.longrepr:
            longrepr_str = str(report.longrepr)
            # Take last line (usually the assertion error)
            lines = longrepr_str.strip().split("\n")
            error_msg = lines[-1].strip() if lines else longrepr_str[:200]

        # Collect markers
        markers = [m.name for m in item.iter_markers()]

        results.append(
            {
                "nodeid": item.nodeid,
                "outcome": test_outcome,
                "duration": getattr(report, "duration", 0.0),
                "skip_reason": skip_reason,
                "error_msg": error_msg,
                "markers": markers,
                "category": _get_test_category(item.nodeid, markers),
                "group": _get_module_group(item.nodeid),
            }
        )


def pytest_sessionstart(session):
    """Record session start time."""
    global _session_start_time
    _session_start_time = time.time()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Generate Markdown test report at end of test session."""
    results = getattr(config, "_md_report_results", [])
    if not results:
        return

    # Surface Model Resolution issues prominently before the rest of the
    # summary. WARN rows reuse the run via fallback; ERR rows mean the next
    # CI run will likely fail unless tests/model_registry.py is updated.
    resolution_cache: dict[str, ResolvedModel] = getattr(config, "_resolved_models", {})
    resolution_issues = [(key, r) for key, r in resolution_cache.items() if r.is_fallback or r.has_error]
    if resolution_issues:
        terminalreporter.write_sep("=", "Model Resolution Warnings", red=True)
        for cache_key, resolved in resolution_issues:
            label, env_var = _RESOLUTION_LABELS.get(cache_key, (cache_key, ""))
            if resolved.has_error:
                terminalreporter.write_line(f"ERR  {label}: {resolved.error}")
            else:
                terminalreporter.write_line(
                    f"WARN {label}: primary {resolved.requested_primary!r} "
                    f"missing, using fallback {resolved.actual!r} "
                    f"(level {resolved.fallback_level})."
                )
        terminalreporter.write_line("ACTION: update tests/model_registry.py with current model ids.")

    global _session_start_time
    total_duration = time.time() - _session_start_time if _session_start_time else 0.0

    # Prepare report directory
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = report_dir / f"test-report-{timestamp}.md"
    latest_path = report_dir / "latest.md"

    # Count results by outcome
    counts = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "error": 0}
    for r in results:
        outcome = r["outcome"]
        if outcome in counts:
            counts[outcome] += 1
        else:
            counts["error"] += 1

    total = sum(counts.values())
    version = _get_version()

    # Build Markdown content
    lines = []

    # Overall result line
    if counts["failed"] > 0 or counts["error"] > 0:
        result_text = f"FAILED - {counts['failed']} failure(s), {counts['error']} error(s)"
    else:
        result_text = f"ALL PASSED - {counts['passed']} tests OK"
        if counts["xfailed"] > 0:
            result_text += f", {counts['xfailed']} expected failures"
        if counts["skipped"] > 0:
            result_text += f", {counts['skipped']} skipped"

    report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Header with date
    lines.append(f"# Test Report - {report_date}")
    lines.append("")
    lines.append(
        f"**eq_chatbot_core v{version}** | {_format_duration(total_duration)} | "
        f"Python {platform.python_version()} | {platform.platform()}"
    )
    lines.append("")
    lines.append(f"> **Result: {result_text}**")
    lines.append("")
    lines.append(f"Command: `{' '.join(sys.argv)}`")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")

    status_labels = {
        "passed": "Passed",
        "failed": "Failed",
        "skipped": "Skipped",
        "xfailed": "XFailed (expected)",
        "error": "Error",
    }
    for status, label in status_labels.items():
        count = counts[status]
        if count > 0 or status in ("passed", "failed"):
            lines.append(f"| {label} | {count} |")
    lines.append(f"| **Total** | **{total}** |")
    lines.append("")

    # Configuration Status section - flag missing credentials per provider
    # so silent skips become actionable: shows which env vars to set in
    # tests/.env.test and how many tests are blocked by each gap.
    skipped_by_group: dict[str, int] = {}
    for r in results:
        if r["outcome"] == "skipped":
            skipped_by_group[r["group"]] = skipped_by_group.get(r["group"], 0) + 1

    config_gaps: list[tuple[str, list[str], int]] = []
    config_ok: list[str] = []
    for group_key, required_vars in _GROUP_REQUIRED_ENV.items():
        if not required_vars:
            continue
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            blocked = skipped_by_group.get(group_key, 0)
            config_gaps.append((group_key, missing, blocked))
        else:
            config_ok.append(group_key)

    lines.append("## Configuration Status")
    lines.append("")
    if config_gaps:
        lines.append(
            "**Action required** — missing API credentials cause tests to be skipped. "
            "Set the variables below in `tests/.env.test` to enable the affected tests:"
        )
        lines.append("")
        lines.append("| Provider | Missing variable(s) | Tests skipped | Action |")
        lines.append("|----------|---------------------|---------------|--------|")
        for group_key, missing, blocked in config_gaps:
            missing_cell = ", ".join(f"`{v}`" for v in missing)
            action = f"Add `{missing[0]}=...` to `tests/.env.test`"
            lines.append(f"| **{group_key}** | {missing_cell} | {blocked} | {action} |")
        lines.append("")
    if config_ok:
        ok_cells = ", ".join(f"`{p}`" for p in config_ok)
        lines.append(f"Credentials configured: {ok_cells}")
        lines.append("")
    if not config_gaps and not config_ok:
        lines.append("_(no provider credentials required for this run)_")
        lines.append("")

    # Models In Use section — single source of truth per run. For every
    # provider in the registry: which model was actually used, what does it
    # cost, where did the choice come from (registry primary / fallback /
    # env override), and was it OK / WARN / ERR / SKIPPED. Replaces the
    # old "Test Configuration" + "Model Resolution" pair.
    resolution_cache: dict[str, ResolvedModel] = getattr(config, "_resolved_models", {})
    lines.append("## Models In Use")
    lines.append("")
    lines.append(
        "Resolved live from `tests/model_registry.py` against each provider's "
        "`list_models()`. By convention the `primary` in each chain is the "
        "cheapest available model; fallbacks rescue the run when the primary "
        "is deprecated."
    )
    lines.append("")
    lines.append("| Provider | Model Used | Cost (per 1M tok) | Source | Status |")
    lines.append("|----------|-----------|-------------------|--------|--------|")
    for cache_key in _RESOLUTION_LABELS:
        if cache_key not in MODELS:
            continue
        label, model_cell, cost_cell, source_cell, status_cell = _resolution_row(cache_key, resolution_cache)
        lines.append(f"| {label} | {model_cell} | {cost_cell} | {source_cell} | {status_cell} |")
    lines.append("")

    # Failed tests section
    failed = [r for r in results if r["outcome"] == "failed"]
    if failed:
        lines.append("## Failed Tests")
        lines.append("")
        lines.append("| Test | Error |")
        lines.append("|------|-------|")
        for r in failed:
            nodeid = _escape_md(_short_nodeid(r["nodeid"]))
            error = _escape_md(r["error_msg"][:200])
            lines.append(f"| `{nodeid}` | {error} |")
        lines.append("")

    # Skipped tests section
    skipped = [r for r in results if r["outcome"] == "skipped"]
    if skipped:
        lines.append("## Skipped Tests")
        lines.append("")
        lines.append("| Test | Reason / Action |")
        lines.append("|------|-----------------|")
        for r in skipped:
            nodeid = _escape_md(_short_nodeid(r["nodeid"]))
            raw_reason = r["skip_reason"] or "No reason given"
            # Translate "<X>_API_KEY not set" into an actionable instruction
            # so the report tells the user exactly what to fix in .env.test.
            reason = _escape_md(_format_skip_reason(raw_reason))
            lines.append(f"| `{nodeid}` | {reason} |")
        lines.append("")

    # Module group overview table
    lines.append("## Results by Module")
    lines.append("")
    lines.append("| Module | Test Model | Passed | Failed | Skipped | XFailed | Total | Duration |")
    lines.append("|--------|------------|--------|--------|---------|---------|-------|----------|")

    # Build group stats - ordered by _MODULE_GROUPS definition
    all_group_keys = list(_MODULE_GROUPS.keys())
    # Add "Other" if there are ungrouped tests
    if any(r["group"] == "Other" for r in results):
        all_group_keys.append("Other")

    for group_key in all_group_keys:
        group_results = [r for r in results if r["group"] == group_key]
        if not group_results:
            continue

        label = _MODULE_GROUPS[group_key]["label"] if group_key in _MODULE_GROUPS else "Other"
        # Look up actually-used model from resolver cache via primary resolver key.
        resolver_key = _GROUP_TO_PRIMARY_RESOLVER.get(group_key)
        resolved = resolution_cache.get(resolver_key) if resolver_key else None
        model_cell = f"`{resolved.actual}`" if resolved else "-"
        g_passed = sum(1 for r in group_results if r["outcome"] == "passed")
        g_failed = sum(1 for r in group_results if r["outcome"] == "failed")
        g_skipped = sum(1 for r in group_results if r["outcome"] == "skipped")
        g_xfailed = sum(1 for r in group_results if r["outcome"] == "xfailed")
        g_total = len(group_results)
        g_duration = sum(r["duration"] for r in group_results)

        # Mark failed groups
        status_marker = " **!!**" if g_failed > 0 else ""
        lines.append(
            f"| **{label}**{status_marker} | {model_cell} | {g_passed} | {g_failed} | "
            f"{g_skipped} | {g_xfailed} | {g_total} | {_format_duration(g_duration)} |"
        )

    lines.append("")

    # Detailed results by module group, then by category
    lines.append("## Detailed Results")
    lines.append("")

    categories = {"unit": "Unit Tests", "integration": "Integration Tests", "local": "Local Server Tests"}

    for cat_key, cat_label in categories.items():
        cat_results = [r for r in results if r["category"] == cat_key]
        if not cat_results:
            continue

        cat_passed = sum(1 for r in cat_results if r["outcome"] == "passed")
        cat_failed = sum(1 for r in cat_results if r["outcome"] == "failed")
        cat_skipped = sum(1 for r in cat_results if r["outcome"] == "skipped")
        cat_xfailed = sum(1 for r in cat_results if r["outcome"] == "xfailed")

        parts = []
        if cat_passed:
            parts.append(f"{cat_passed} passed")
        if cat_failed:
            parts.append(f"{cat_failed} failed")
        if cat_skipped:
            parts.append(f"{cat_skipped} skipped")
        if cat_xfailed:
            parts.append(f"{cat_xfailed} xfailed")

        lines.append(f"### {cat_label} ({', '.join(parts)})")
        lines.append("")

        # Sub-group by module group within this category
        for group_key in all_group_keys:
            group_info = _MODULE_GROUPS.get(group_key, {"label": "Other"})
            group_cat_results = [r for r in cat_results if r["group"] == group_key]
            if not group_cat_results:
                continue

            gp = sum(1 for r in group_cat_results if r["outcome"] == "passed")
            gf = sum(1 for r in group_cat_results if r["outcome"] == "failed")
            gs = sum(1 for r in group_cat_results if r["outcome"] == "skipped")
            gx = sum(1 for r in group_cat_results if r["outcome"] == "xfailed")
            g_dur = sum(r["duration"] for r in group_cat_results)

            sub_parts = []
            if gp:
                sub_parts.append(f"{gp} passed")
            if gf:
                sub_parts.append(f"{gf} failed")
            if gs:
                sub_parts.append(f"{gs} skipped")
            if gx:
                sub_parts.append(f"{gx} xfailed")

            model_suffix = ""
            resolver_key = _GROUP_TO_PRIMARY_RESOLVER.get(group_key)
            resolved = resolution_cache.get(resolver_key) if resolver_key else None
            if resolved:
                model_suffix = f" | Model: `{resolved.actual}`"

            lines.append(
                f"#### {group_info['label']} ({', '.join(sub_parts)}) - {_format_duration(g_dur)}{model_suffix}"
            )
            lines.append("")

            has_details = any(r["skip_reason"] or r["error_msg"] for r in group_cat_results)

            if has_details:
                lines.append("| Test | Status | Duration | Detail |")
                lines.append("|------|--------|----------|--------|")
            else:
                lines.append("| Test | Status | Duration |")
                lines.append("|------|--------|----------|")

            for r in group_cat_results:
                nodeid = _escape_md(_short_nodeid(r["nodeid"]))
                status = r["outcome"].upper()
                duration = _format_duration(r["duration"]) if r["outcome"] != "skipped" else "-"
                detail = _escape_md(r["skip_reason"] or r["error_msg"])

                if has_details:
                    lines.append(f"| `{nodeid}` | {status} | {duration} | {detail} |")
                else:
                    lines.append(f"| `{nodeid}` | {status} | {duration} |")

            lines.append("")

    # Write report
    report_content = "\n".join(lines)
    report_path.write_text(report_content, encoding="utf-8")

    # Copy to latest.md
    shutil.copy2(report_path, latest_path)

    # Print path in terminal
    terminalreporter.write_sep("=", "Markdown Test Report")
    terminalreporter.write_line(f"Report: {report_path}")
    terminalreporter.write_line(f"Latest: {latest_path}")
