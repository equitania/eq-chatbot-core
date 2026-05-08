"""
Integration tests for local LLM providers (LM Studio, Ollama).

These tests require a running local LLM server:
- LM Studio: http://localhost:1234
- Ollama: http://localhost:11434

Run with: pytest -m local tests/integration/test_local_live.py

Set SKIP_LOCAL_TESTS=false in .env.test to enable these tests.
"""

import pytest

from eq_chatbot_core.providers import get_provider
from eq_chatbot_core.providers.local_provider import LocalLLMProvider

# =============================================================================
# Test Configuration
# =============================================================================


def is_lm_studio_available() -> bool:
    """Check if LM Studio server is available."""
    try:
        provider = get_provider("lm_studio")
        return provider.is_server_available()
    except Exception:
        return False


def is_ollama_available() -> bool:
    """Check if Ollama server is available."""
    try:
        provider = get_provider("ollama")
        return provider.is_server_available()
    except Exception:
        return False


# Skip markers
skip_if_no_lm_studio = pytest.mark.skipif(
    not is_lm_studio_available(),
    reason="LM Studio server not available at localhost:1234",
)

skip_if_no_ollama = pytest.mark.skipif(
    not is_ollama_available(),
    reason="Ollama server not available at localhost:11434",
)


# =============================================================================
# LM Studio Integration Tests
# =============================================================================


@pytest.mark.local
@pytest.mark.integration
@skip_if_no_lm_studio
class TestLMStudioLive:
    """Live integration tests for LM Studio."""

    @pytest.fixture
    def provider(self):
        """Create LM Studio provider."""
        return get_provider("lm_studio")

    def test_connection(self, provider):
        """Test basic connection to LM Studio."""
        assert provider.is_server_available()

    def test_list_models(self, provider):
        """Test listing available models."""
        models = provider.list_models()

        assert isinstance(models, list)
        # LM Studio should have at least one model loaded
        if models:
            assert "id" in models[0]
            print(f"\n  Available models: {[m['id'] for m in models]}")

    def test_simple_completion(self, provider, test_config):
        """Test simple chat completion with minimal tokens."""
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            max_tokens=test_config.get("max_tokens", 20),
            temperature=0.1,  # Low temperature for consistent output
        )

        assert response.content
        assert len(response.content) > 0
        print(f"\n  Response: {response.content[:100]}")

    def test_system_message(self, provider, test_config):
        """Test completion with system message."""
        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Be very brief."},
                {"role": "user", "content": "What is 2+2?"},
            ],
            max_tokens=test_config.get("max_tokens", 20),
        )

        assert response.content
        # Should contain "4" somewhere in response
        assert "4" in response.content

    def test_streaming_completion(self, provider, test_config):
        """Test streaming chat completion."""
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count from 1 to 3."}],
                max_tokens=test_config.get("max_tokens", 50),
            )
        )

        # Should have received some chunks
        assert len(chunks) > 0

        # Combine content
        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        print(f"\n  Streamed content: {full_content[:100]}")

        # Last chunk should be marked as final
        final_chunks = [c for c in chunks if c.is_final]
        assert len(final_chunks) >= 1

    def test_multiple_turns(self, provider, test_config):
        """Test multi-turn conversation."""
        messages = [
            {"role": "user", "content": "Remember the number 42."},
        ]

        response1 = provider.chat_completion(
            messages=messages,
            max_tokens=test_config.get("max_tokens", 30),
        )

        messages.append({"role": "assistant", "content": response1.content})
        messages.append({"role": "user", "content": "What number did I mention?"})

        response2 = provider.chat_completion(
            messages=messages,
            max_tokens=test_config.get("max_tokens", 30),
        )

        assert response2.content
        # Model should remember the number
        assert "42" in response2.content


# =============================================================================
# Ollama Integration Tests (disabled - using LM Studio on macOS instead)
# =============================================================================

# @pytest.mark.local
# @pytest.mark.integration
# @skip_if_no_ollama
# class TestOllamaLive:
#     """Live integration tests for Ollama."""
#
#     @pytest.fixture
#     def provider(self):
#         """Create Ollama provider."""
#         return get_provider("ollama")
#
#     def test_connection(self, provider):
#         """Test basic connection to Ollama."""
#         assert provider.is_server_available()
#
#     def test_list_models(self, provider):
#         """Test listing available models."""
#         models = provider.list_models()
#
#         assert isinstance(models, list)
#         if models:
#             assert "id" in models[0]
#             print(f"\n  Available models: {[m['id'] for m in models]}")
#
#     def test_simple_completion(self, provider, test_config):
#         """Test simple chat completion."""
#         models = provider.list_models()
#         model = test_config.get("local_model", models[0]["id"] if models else "phi:latest")
#
#         response = provider.chat_completion(
#             messages=[{"role": "user", "content": "Say 'hello' only."}],
#             model=model,
#             max_tokens=test_config.get("max_tokens", 20),
#             temperature=0.1,
#         )
#
#         assert response.content
#         assert len(response.content) > 0
#         print(f"\n  Model: {model}")
#         print(f"  Response: {response.content[:100]}")
#
#     def test_streaming_completion(self, provider, test_config):
#         """Test streaming chat completion."""
#         models = provider.list_models()
#         model = test_config.get("local_model", models[0]["id"] if models else "phi:latest")
#
#         chunks = list(
#             provider.stream_completion(
#                 messages=[{"role": "user", "content": "Say 'test' only."}],
#                 model=model,
#                 max_tokens=test_config.get("max_tokens", 20),
#             )
#         )
#
#         assert len(chunks) > 0
#
#         full_content = "".join(c.content for c in chunks if c.content)
#         assert len(full_content) > 0
#         print(f"\n  Streamed: {full_content[:100]}")


# =============================================================================
# Generic Local Provider Tests
# =============================================================================


@pytest.mark.local
@pytest.mark.integration
class TestLocalProviderGeneric:
    """Generic tests that work with any available local provider."""

    @pytest.fixture
    def provider(self):
        """Get first available local provider (LM Studio preferred)."""
        if is_lm_studio_available():
            return get_provider("lm_studio")
        else:
            pytest.skip("LM Studio server not available")

    def test_provider_properties(self, provider):
        """Test provider has correct properties."""
        assert provider.provider_name == "local"
        assert provider.timeout == LocalLLMProvider.DEFAULT_TIMEOUT
        assert provider.is_server_available()

    def test_chat_completion_returns_llm_response(self, provider, test_config, local_resolved_model):
        """Test that chat_completion returns proper LLMResponse object."""
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model=local_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
        )

        # Check LLMResponse structure
        assert hasattr(response, "content")
        assert hasattr(response, "model")
        assert hasattr(response, "input_tokens")
        assert hasattr(response, "output_tokens")
        assert hasattr(response, "finish_reason")

        # Content should be non-empty string
        assert isinstance(response.content, str)
        assert len(response.content) > 0

    def test_stream_completion_yields_chunks(self, provider, test_config, local_resolved_model):
        """Test that stream_completion yields StreamChunk objects."""
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=local_resolved_model,
                max_tokens=test_config.get("max_tokens", 10),
            )
        )

        assert len(chunks) > 0

        for chunk in chunks:
            assert hasattr(chunk, "content")
            assert hasattr(chunk, "is_final")

    def test_temperature_parameter(self, provider, test_config, local_resolved_model):
        """Test that temperature parameter works."""
        # Low temperature should give more consistent results
        response1 = provider.chat_completion(
            messages=[{"role": "user", "content": "What is 1+1?"}],
            model=local_resolved_model,
            temperature=0.0,
            max_tokens=test_config.get("max_tokens", 10),
        )

        response2 = provider.chat_completion(
            messages=[{"role": "user", "content": "What is 1+1?"}],
            model=local_resolved_model,
            temperature=0.0,
            max_tokens=test_config.get("max_tokens", 10),
        )

        # Both should contain "2"
        assert "2" in response1.content
        assert "2" in response2.content


# =============================================================================
# Error Handling Tests (Live)
# =============================================================================


@pytest.mark.local
@pytest.mark.integration
class TestLocalProviderErrorsLive:
    """Test error handling with live servers."""

    def test_invalid_url_connection_error(self):
        """Test that invalid URL raises connection error."""
        from eq_chatbot_core.providers.base import ProviderError

        provider = get_provider("local", base_url="http://localhost:59999/v1")

        # Should not be available
        assert not provider.is_server_available()

        # Should raise ProviderError on API call
        with pytest.raises(ProviderError):
            provider.chat_completion(
                messages=[{"role": "user", "content": "test"}],
            )
