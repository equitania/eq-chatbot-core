"""
Pytest fixtures and configuration for eq_chatbot_core tests.

This module provides:
- Environment-based test configuration via .env.test
- Provider-specific fixtures for cloud and local LLM testing
- Mock fixtures for unit tests
- Skip markers for conditional test execution
"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

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
        # Local Server URLs
        "lm_studio_url": os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        # Test Models
        "openai_model": os.getenv("OPENAI_TEST_MODEL", "gpt-4o-mini"),
        "anthropic_model": os.getenv("ANTHROPIC_TEST_MODEL", "claude-3-haiku-20240307"),
        "langdock_model": os.getenv("LANGDOCK_TEST_MODEL", "gpt-4o-mini"),
        "local_model": os.getenv("LOCAL_TEST_MODEL", "phi:latest"),
        # Test Settings
        "skip_live_tests": os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        "skip_local_tests": os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true",
        "max_tokens": int(os.getenv("TEST_MAX_TOKENS", "20")),
        "timeout": int(os.getenv("TEST_TIMEOUT", "30")),
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
    config.addinivalue_line(
        "markers", "unit: Unit tests (mocked, fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (real API calls, requires keys)"
    )
    config.addinivalue_line(
        "markers", "local: Local LLM server tests (requires running server)"
    )
    config.addinivalue_line(
        "markers", "expensive: Tests with expensive models (skip in CI by default)"
    )
    config.addinivalue_line("markers", "slow: Slow-running tests")


def pytest_collection_modifyitems(config, items):
    """Apply skip markers based on environment configuration."""
    skip_live = os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true"
    skip_local = os.getenv("SKIP_LOCAL_TESTS", "true").lower() == "true"

    for item in items:
        # Skip integration tests if SKIP_LIVE_TESTS is true
        if "integration" in item.keywords and skip_live:
            item.add_marker(
                pytest.mark.skip(reason="SKIP_LIVE_TESTS is true")
            )

        # Skip local tests if SKIP_LOCAL_TESTS is true
        if "local" in item.keywords and skip_local:
            item.add_marker(
                pytest.mark.skip(reason="SKIP_LOCAL_TESTS is true")
            )

        # Skip expensive tests in CI environments
        if "expensive" in item.keywords and os.getenv("CI"):
            item.add_marker(
                pytest.mark.skip(reason="Expensive tests skipped in CI")
            )
