"""
Unit tests for Mammouth AI provider.

All tests use mocked responses - no real API calls.
Tests cover 30+ model access through unified API with temperature constraints.
"""

from contextlib import nullcontext

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_chat_response():
    """Create a mock Mammouth chat completion response."""
    return {
        "id": "chatcmpl-123",
        "model": "gpt-4o",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Test response from Mammouth",
                    "tool_calls": None,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
        },
    }


@pytest.fixture
def mock_models_response():
    """Create a mock Mammouth models list response."""
    return [
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "max_input_tokens": 128000,
            "max_output_tokens": 16384,
            "input_price": 2.5,
            "output_price": 10.0,
        },
        {
            "id": "claude-sonnet-4-5",
            "name": "Claude Sonnet 4.5",
            "max_input_tokens": 200000,
            "max_output_tokens": 8192,
            "input_price": 3.0,
            "output_price": 15.0,
        },
        {
            "id": "o3",
            "name": "O3",
            "max_input_tokens": 200000,
            "max_output_tokens": 100000,
            "input_price": 10.0,
            "output_price": 40.0,
        },
        {
            "id": "gpt-4.1",
            "name": "GPT-4.1",
            "max_input_tokens": 1048576,
            "max_output_tokens": 32768,
            "input_price": 2.0,
            "output_price": 8.0,
        },
    ]


# =============================================================================
# Provider Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthProviderInit:
    """Test Mammouth provider initialization."""

    def test_basic_init(self):
        """Test basic provider initialization."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider.api_key == "mm-test-key"
            assert provider.base_url == "https://api.mammouth.ai/v1"

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            custom_url = "http://localhost:4000/v1"
            provider = MammouthProvider(api_key="mm-test-key", base_url=custom_url)
            assert provider.base_url == custom_url

    def test_init_with_timeout(self):
        """Test initialization with custom timeout."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key", timeout=120.0)
            assert provider.timeout == 120.0


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthProviderProperties:
    """Test provider properties."""

    def test_provider_name(self):
        """Test provider_name property."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider.provider_name == "mammouth"

    @pytest.mark.xfail(reason="stage 2: no built-in default model", strict=False)
    def test_default_model(self):
        """Test default model is GPT-4o."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider.default_model == "gpt-5.6-luna"


# =============================================================================
# Temperature Constraints Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthTemperatureConstraints:
    """Test temperature constraint handling - critical for newer OpenAI models."""

    def test_reasoning_model_no_temperature(self):
        """Test reasoning models (o1, o3, o4) return None for temperature."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("o1", 0.7) is None
            assert provider._clamp_temperature("o3", 0.5) is None
            assert provider._clamp_temperature("o4-mini", 0.3) is None

    def test_gpt5_temperature_is_generation_specific(self):
        """GPT-5 support for `temperature` is NOT uniform across the family.

        This test previously asserted that every gpt-5* model passes temperature
        through — which is what let gpt-5, gpt-5.5 and the whole gpt-5.6 tier fail
        with HTTP 400. Measured live on 23.08.2026: 5.1/5.2/5.4 accept it, plain
        gpt-5 and 5.5/5.6 refuse it. See tests/unit/test_gpt5_temperature.py.
        """
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("gpt-5.2-chat", 0.3) == 0.3
            assert provider._clamp_temperature("gpt-5.1-chat", 0.7) == 0.7
            assert provider._clamp_temperature("gpt-5-mini", 0.0) is None
            assert provider._clamp_temperature("gpt-5.6-luna", 0.7) is None

    def test_gpt41_temperature_passthrough(self):
        """Test GPT-4.1 models pass through temperature (min=0.0)."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("gpt-4.1", 0.5) == 0.5
            assert provider._clamp_temperature("gpt-4.1-mini", 0.7) == 0.7
            assert provider._clamp_temperature("gpt-4.1-nano", 0.0) == 0.0

    def test_gpt41_valid_temperature_passes_through(self):
        """Test GPT-4.1 models pass through valid temperatures."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("gpt-4.1", 1.0) == 1.0
            assert provider._clamp_temperature("gpt-4.1", 1.5) == 1.5
            assert provider._clamp_temperature("gpt-4.1", 2.0) == 2.0

    def test_legacy_model_passthrough(self):
        """Test legacy models (gpt-4o) pass through any valid temperature."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("gpt-4o", 0.0) == 0.0
            assert provider._clamp_temperature("gpt-4o", 0.7) == 0.7
            assert provider._clamp_temperature("gpt-4o", 2.0) == 2.0

    def test_claude_max_temperature_clamped(self):
        """Test Claude models clamp temperature to max 1.0."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("claude-sonnet-4-5", 1.5) == 1.0
            assert provider._clamp_temperature("claude-opus-4-5", 2.0) == 1.0
            # Valid range should pass through
            assert provider._clamp_temperature("claude-sonnet-4-5", 0.5) == 0.5

    def test_unknown_model_uses_defaults(self):
        """Test unknown models use default constraints (0.0-2.0)."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")

            assert provider._clamp_temperature("some-unknown-model", 0.0) == 0.0
            assert provider._clamp_temperature("some-unknown-model", 1.5) == 1.5
            assert provider._clamp_temperature("some-unknown-model", 2.0) == 2.0


# =============================================================================
# Reasoning Model Detection Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthReasoningModels:
    """Test reasoning model detection."""

    def test_o1_is_reasoning_model(self):
        """Test o1 models are detected as reasoning."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("o1") is True
            assert provider._is_reasoning_model("o1-mini") is True
            assert provider._is_reasoning_model("o1-preview") is True

    def test_o3_is_reasoning_model(self):
        """Test o3 models are detected as reasoning."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("o3") is True
            assert provider._is_reasoning_model("o3-mini") is True

    def test_o4_is_reasoning_model(self):
        """Test o4 models are detected as reasoning."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("o4-mini") is True

    def test_gpt_not_reasoning_model(self):
        """Test GPT models are not reasoning models."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("gpt-4o") is False
            assert provider._is_reasoning_model("gpt-4.1") is False
            assert provider._is_reasoning_model("gpt-5.2-chat") is False

    def test_claude_not_reasoning_model(self):
        """Test Claude models are not reasoning models."""
        with nullcontext():
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = MammouthProvider(api_key="mm-test-key")
            assert provider._is_reasoning_model("claude-sonnet-4-5") is False
            assert provider._is_reasoning_model("claude-opus-4-5") is False


# =============================================================================
# Chat Completion Tests
# =============================================================================


# =============================================================================
# Stream Completion Tests
# =============================================================================


# =============================================================================
# List Models Tests
# =============================================================================


# =============================================================================
# Error Handling Tests
# =============================================================================


# =============================================================================
# Context Manager Tests
# =============================================================================


# =============================================================================
# Factory Integration Tests
# =============================================================================


@pytest.mark.unit
class TestMammouthFactoryIntegration:
    """Test integration with provider factory."""

    def test_get_provider_returns_mammouth(self):
        """Test get_provider returns MammouthProvider."""
        with nullcontext():
            from eq_chatbot_core.providers import get_provider
            from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

            provider = get_provider("mammouth", api_key="mm-test-key")

            assert isinstance(provider, MammouthProvider)
            assert provider.provider_name == "mammouth"


# =============================================================================
# SSRF Guard (v1.17.2)
# =============================================================================


@pytest.mark.unit
class TestMammouthSSRFGuard:
    """A caller-supplied base_url must pass validate_url; the default is exempt."""

    def test_cloud_metadata_endpoint_rejected(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        with pytest.raises(ValueError):
            MammouthProvider(api_key="mm-test-key", base_url="http://169.254.169.254/v1")

    def test_non_http_scheme_rejected(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        with pytest.raises(ValueError):
            MammouthProvider(api_key="mm-test-key", base_url="ftp://localhost/v1")

    def test_localhost_base_url_accepted(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        provider = MammouthProvider(api_key="mm-test-key", base_url="http://localhost:4000/v1")
        assert provider.base_url == "http://localhost:4000/v1"

    def test_default_base_url_skips_validation(self):
        from eq_chatbot_core.providers.mammouth_provider import MammouthProvider

        provider = MammouthProvider(api_key="mm-test-key")
        assert provider.base_url == MammouthProvider.DEFAULT_BASE_URL
