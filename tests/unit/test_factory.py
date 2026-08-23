"""
Unit tests for the provider factory (get_provider function).

Tests provider instantiation, alias handling, and error cases.
"""

import pytest

from eq_chatbot_core.providers import get_provider
from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
from eq_chatbot_core.providers.langdock_provider import LangDockProvider
from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from eq_chatbot_core.providers.openai_provider import OpenAIProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

# =============================================================================
# Cloud Provider Tests
# =============================================================================


@pytest.mark.unit
class TestFactoryCloudProviders:
    """Test factory for cloud providers."""

    def test_get_openai_provider(self):
        """Test creating OpenAI provider."""
        provider = get_provider("openai", api_key="sk-test-key")

        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "sk-test-key"
        assert provider.provider_name == "openai"

    def test_get_anthropic_provider(self):
        """Test creating Anthropic provider."""
        provider = get_provider("anthropic", api_key="sk-ant-test-key")

        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == "sk-ant-test-key"
        assert provider.provider_name == "anthropic"

    def test_get_langdock_provider(self):
        """Test creating LangDock provider."""
        provider = get_provider("langdock", api_key="ld-test-key")

        assert isinstance(provider, LangDockProvider)
        assert provider.api_key == "ld-test-key"
        assert provider.provider_name == "langdock"

    def test_get_openrouter_provider(self):
        """Test creating OpenRouter provider."""
        provider = get_provider("openrouter", api_key="sk-or-test-key")

        assert isinstance(provider, OpenRouterProvider)
        assert provider.api_key == "sk-or-test-key"
        assert provider.provider_name == "openrouter"

    def test_get_ionos_provider(self):
        """Test creating IONOS provider — base_url defaults to the IONOS endpoint."""
        from eq_chatbot_core.providers.ionos_provider import DEFAULT_BASE_URL, IonosProvider

        provider = get_provider("ionos", api_key="ionos-test-key")

        assert isinstance(provider, IonosProvider)
        assert provider.api_key == "ionos-test-key"
        assert provider.provider_name == "ionos"
        assert provider.base_url == DEFAULT_BASE_URL

    def test_get_melious_provider(self):
        """Test creating Melious provider — base_url defaults to the Melious endpoint."""
        from eq_chatbot_core.providers.melious_provider import DEFAULT_BASE_URL, MeliousProvider

        provider = get_provider("melious", api_key="sk-mel-test-key")

        assert isinstance(provider, MeliousProvider)
        assert provider.api_key == "sk-mel-test-key"
        assert provider.provider_name == "melious"
        assert provider.base_url == DEFAULT_BASE_URL

    def test_provider_name_case_insensitive(self):
        """Test that provider names are case insensitive."""
        provider1 = get_provider("OPENAI", api_key="test")
        provider2 = get_provider("OpenAI", api_key="test")
        provider3 = get_provider("openai", api_key="test")

        assert isinstance(provider1, OpenAIProvider)
        assert isinstance(provider2, OpenAIProvider)
        assert isinstance(provider3, OpenAIProvider)

    def test_custom_base_url(self):
        """Test provider with custom base URL."""
        # Loopback URL keeps the SSRF guard's validate_url hermetic (no DNS).
        custom_url = "http://localhost:8080/v1"
        provider = get_provider("openai", api_key="test", base_url=custom_url)

        assert provider.base_url == custom_url

    def test_custom_base_url_ssrf_blocked(self):
        """The factory must not let a caller-supplied base_url reach internal targets."""
        with pytest.raises(ValueError):
            get_provider("openai", api_key="test", base_url="http://169.254.169.254/v1")


# =============================================================================
# Local Provider Tests
# =============================================================================


@pytest.mark.unit
class TestFactoryLocalProviders:
    """Test factory for local providers."""

    def test_get_local_provider(self):
        """Test creating generic local provider."""
        provider = get_provider("local", base_url="http://localhost:8080/v1")

        assert isinstance(provider, LocalLLMProvider)
        assert provider.base_url == "http://localhost:8080/v1"
        assert provider.provider_name == "local"

    def test_get_local_provider_default_api_key(self):
        """Test that local provider gets default API key."""
        provider = get_provider("local", base_url="http://localhost:1234/v1")

        assert provider.api_key == "not-used"

    def test_get_lm_studio_alias(self):
        """Test lm_studio alias creates local provider with correct URL."""
        provider = get_provider("lm_studio")

        assert isinstance(provider, LocalLLMProvider)
        assert provider.base_url == LocalLLMProvider.LM_STUDIO_URL
        assert provider.base_url == "http://localhost:1234/v1"

    def test_get_lmstudio_alias(self):
        """Test lmstudio alias (without underscore) works."""
        provider = get_provider("lmstudio")

        assert isinstance(provider, LocalLLMProvider)
        assert provider.base_url == LocalLLMProvider.LM_STUDIO_URL

    def test_get_ollama_alias(self):
        """Test ollama alias creates local provider with correct URL."""
        provider = get_provider("ollama")

        assert isinstance(provider, LocalLLMProvider)
        assert provider.base_url == LocalLLMProvider.OLLAMA_URL
        assert provider.base_url == "http://localhost:11434/v1"

    def test_local_alias_custom_base_url_override(self):
        """Test that custom base_url overrides alias default."""
        custom_url = "http://custom:9999/v1"
        provider = get_provider("lm_studio", base_url=custom_url)

        assert isinstance(provider, LocalLLMProvider)
        assert provider.base_url == custom_url

    def test_local_provider_with_api_key(self):
        """Test local provider with explicit API key."""
        provider = get_provider("local", api_key="custom-key", base_url="http://localhost:1234/v1")

        assert provider.api_key == "custom-key"

    def test_local_alias_case_insensitive(self):
        """Test that local aliases are case insensitive."""
        provider1 = get_provider("LM_STUDIO")
        provider2 = get_provider("Lm_Studio")
        provider3 = get_provider("OLLAMA")

        assert isinstance(provider1, LocalLLMProvider)
        assert isinstance(provider2, LocalLLMProvider)
        assert isinstance(provider3, LocalLLMProvider)


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestFactoryErrors:
    """Test factory error handling."""

    def test_unknown_provider_raises_error(self):
        """Test that unknown provider name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_provider("unknown_provider", api_key="test")

        assert "Unknown provider: unknown_provider" in str(exc_info.value)

    def test_error_message_lists_available_providers(self):
        """Test that error message includes available providers."""
        with pytest.raises(ValueError) as exc_info:
            get_provider("invalid", api_key="test")

        error_msg = str(exc_info.value)
        assert "openai" in error_msg
        assert "anthropic" in error_msg
        assert "langdock" in error_msg
        assert "openrouter" in error_msg
        assert "melious" in error_msg
        assert "privatemode" in error_msg
        assert "local" in error_msg
        assert "lm_studio" in error_msg
        assert "ollama" in error_msg

    def test_none_api_key_for_cloud_provider(self):
        """Test that None API key is passed to cloud provider (they handle validation)."""
        # Cloud providers should receive the None and handle it themselves
        provider = get_provider("openai", api_key=None)

        # Provider is created, but will fail on actual API call
        assert isinstance(provider, OpenAIProvider)

    def test_none_api_key_for_local_provider(self):
        """Test that None API key defaults to 'not-used' for local provider."""
        provider = get_provider("local", api_key=None, base_url="http://localhost:1234/v1")

        assert provider.api_key == "not-used"


# =============================================================================
# Additional Arguments Tests
# =============================================================================


@pytest.mark.unit
class TestFactoryKwargs:
    """Test factory with additional keyword arguments."""

    def test_timeout_passed_to_provider(self):
        """Test that timeout is passed to provider."""
        provider = get_provider("local", base_url="http://localhost:1234/v1", timeout=60.0)

        assert provider.timeout == 60.0

    def test_max_retries_passed_to_provider(self):
        """Test that max_retries is passed to provider."""
        provider = get_provider("local", base_url="http://localhost:1234/v1", max_retries=5)

        assert provider.max_retries == 5

    def test_multiple_kwargs(self):
        """Test multiple kwargs passed to provider."""
        provider = get_provider(
            "local",
            base_url="http://localhost:1234/v1",
            timeout=120.0,
            max_retries=3,
        )

        assert provider.timeout == 120.0
        assert provider.max_retries == 3


# =============================================================================
# Provider Properties Tests
# =============================================================================


@pytest.mark.unit
class TestFactoryProviderProperties:
    """Test that created providers have correct properties."""

    def test_openai_default_model(self):
        """Test OpenAI provider has correct default model."""
        provider = get_provider("openai", api_key="test")

        assert provider.default_model is not None
        assert "gpt" in provider.default_model.lower()

    def test_anthropic_default_model(self):
        """Test Anthropic provider has correct default model."""
        provider = get_provider("anthropic", api_key="test")

        assert provider.default_model is not None
        assert "claude" in provider.default_model.lower()

    def test_local_default_model(self):
        """Test local provider has fallback default model."""
        provider = get_provider("local", base_url="http://localhost:1234/v1")

        assert provider.default_model == "local-model"

    def test_provider_names_correct(self):
        """Test that provider_name property is set correctly."""
        openai = get_provider("openai", api_key="test")
        anthropic = get_provider("anthropic", api_key="test")
        langdock = get_provider("langdock", api_key="test")
        openrouter = get_provider("openrouter", api_key="test")
        local = get_provider("local", base_url="http://localhost:1234/v1")
        lm_studio = get_provider("lm_studio")
        ollama = get_provider("ollama")

        assert openai.provider_name == "openai"
        assert anthropic.provider_name == "anthropic"
        assert langdock.provider_name == "langdock"
        assert openrouter.provider_name == "openrouter"
        assert local.provider_name == "local"
        assert lm_studio.provider_name == "local"
        assert ollama.provider_name == "local"

    def test_openrouter_default_model(self):
        """Test OpenRouter provider has correct default model."""
        provider = get_provider("openrouter", api_key="test")

        assert provider.default_model is not None
        assert provider.default_model == "openai/gpt-5.6-luna"
