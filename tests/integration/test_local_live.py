"""
Integration tests for local LLM providers (LM Studio, Ollama).

These tests require a running local LLM server:
- LM Studio: http://localhost:1234
- Ollama: http://localhost:11434

Run with: pytest -m local tests/integration/test_local_live.py

Local tests run by default; export SKIP_LOCAL_TESTS=true to skip them.
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


# Locally hosted models are frequently reasoning models: they spend a variable,
# sometimes large share of the budget on internal thinking before emitting any
# visible content. With the suite-wide 300-token budget a run could come back
# with finish_reason="length" and content="" — and because the split varies per
# call, the same test passed and failed on consecutive runs. Observed with
# glm-4.7-flash on Ollama (300 tokens spent, empty content). Mirrors the
# headroom privatemode_live already grants for Kimi.
_LOCAL_MAX_TOKENS = 1024


def has_chat_model(provider_name: str) -> bool:
    """True when the server offers at least one non-embedding model.

    A reachable server is not the same as a usable one: LM Studio is commonly
    run with only an embedding model loaded, and chatting against one returns
    HTTP 400. Treating that as a test failure makes the suite red for a normal
    setup, so the callers skip instead.
    """
    try:
        provider = get_provider(provider_name)
        if not provider.is_server_available():
            return False
        ids = [m.get("id", "") for m in provider.list_models()]
        return any("embed" not in mid.lower() for mid in ids if mid)
    except Exception:
        return False


def is_ollama_available() -> bool:
    """Check if Ollama server is available."""
    try:
        provider = get_provider("ollama")
        return provider.is_server_available()
    except Exception:
        return False


def active_local_provider() -> str | None:
    """Return the name of the local server that is actually running, or None.

    Ollama and LM Studio both serve a single machine and are usually not run at
    the same time, so the suite targets whichever one answers. Ollama is probed
    first because it is the one started from the CLI on demand; LM Studio is the
    long-running desktop app. Tests used to hardcode LM Studio, which meant a
    machine running only Ollama got failures against an endpoint that was not
    even in use.
    """
    if has_chat_model("ollama"):
        return "ollama"
    if has_chat_model("lm_studio"):
        return "lm_studio"
    return None


ACTIVE_LOCAL_PROVIDER = active_local_provider()

skip_if_no_local = pytest.mark.skipif(
    ACTIVE_LOCAL_PROVIDER is None,
    reason="no local LLM server reachable (Ollama :11434 / LM Studio :1234)",
)

# Skip markers
skip_if_no_lm_studio = pytest.mark.skipif(
    not is_lm_studio_available() or not has_chat_model("lm_studio"),
    reason="LM Studio unreachable at localhost:1234, or running without a chat model loaded",
)

skip_if_no_ollama = pytest.mark.skipif(
    not is_ollama_available() or not has_chat_model("ollama"),
    reason="Ollama unreachable at localhost:11434, or running without a chat model loaded",
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
            max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
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
            max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
        )

        assert response.content
        # Should contain "4" somewhere in response
        assert "4" in response.content

    def test_streaming_completion(self, provider, test_config):
        """Test streaming chat completion."""
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count from 1 to 3."}],
                max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
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
            max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
        )

        messages.append({"role": "assistant", "content": response1.content})
        messages.append({"role": "user", "content": "What number did I mention?"})

        response2 = provider.chat_completion(
            messages=messages,
            max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
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
@skip_if_no_local
class TestLocalProviderGeneric:
    """Generic tests that work with any available local provider."""

    @pytest.fixture
    def provider(self):
        """Whichever local server is actually running (Ollama or LM Studio)."""
        if ACTIVE_LOCAL_PROVIDER is None:
            pytest.skip("no local LLM server reachable")
        return get_provider(ACTIVE_LOCAL_PROVIDER)

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
            max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
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
                max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
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
            max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
        )

        response2 = provider.chat_completion(
            messages=[{"role": "user", "content": "What is 1+1?"}],
            model=local_resolved_model,
            temperature=0.0,
            max_tokens=max(test_config.get("max_tokens", 300), _LOCAL_MAX_TOKENS),
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
