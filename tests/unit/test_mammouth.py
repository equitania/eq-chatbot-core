"""
Unit tests for Mammouth AI provider.

All tests use mocked responses - no real API calls.
Tests cover 30+ model access through unified API with temperature constraints.
"""

from contextlib import nullcontext

import pytest

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
