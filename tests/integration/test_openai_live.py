"""
Integration tests for OpenAI, Anthropic, and LangDock providers.

These tests require valid API keys in .env.test:
- OPENAI_API_KEY for OpenAI tests
- ANTHROPIC_API_KEY for Anthropic tests
- LANGDOCK_API_KEY for LangDock tests

Run with: pytest -m integration tests/integration/test_openai_live.py

Set SKIP_LIVE_TESTS=false in .env.test to enable these tests.
"""

import pytest

from eq_chatbot_core.providers import get_provider

# =============================================================================
# OpenAI Integration Tests
# =============================================================================


@pytest.mark.integration
class TestOpenAILive:
    """Live integration tests for OpenAI provider."""

    @pytest.fixture
    def provider(self, openai_api_key):
        """Create OpenAI provider (skips if no API key)."""
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY not set")
        return get_provider("openai", api_key=openai_api_key)

    def test_simple_completion(self, provider, test_config):
        """Test simple chat completion with gpt-4o-mini."""
        model = test_config.get("openai_model", "gpt-4o-mini")

        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model
        assert response.input_tokens > 0
        assert response.output_tokens > 0

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_list_models(self, provider):
        """Test listing available models."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # Should include common models
        # list_models() returns ModelInfo dataclass or dict depending on provider
        if hasattr(models[0], "model_id"):
            model_ids = [m.model_id for m in models]
        else:
            model_ids = [m.get("model_id", m.get("id", "")) for m in models]
        # gpt-4o-mini should be available
        assert any("gpt" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:5]}")

    def test_streaming_completion(self, provider, test_config):
        """Test streaming chat completion."""
        model = test_config.get("openai_model", "gpt-4o-mini")

        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=model,
                max_tokens=test_config.get("max_tokens", 20),
            )
        )

        assert len(chunks) > 0

        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        print(f"\n  Streamed: {full_content[:100]}")

    def test_system_message(self, provider, test_config):
        """Test completion with system message."""
        model = test_config.get("openai_model", "gpt-4o-mini")

        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "You only respond with the word 'ACKNOWLEDGED'."},
                {"role": "user", "content": "Hello!"},
            ],
            model=model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "acknowledged" in response.content.lower()

    def test_json_mode(self, provider, test_config):
        """Test JSON response format."""
        model = test_config.get("openai_model", "gpt-4o-mini")

        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "Respond only with valid JSON."},
                {"role": "user", "content": "Give me a JSON object with key 'status' and value 'ok'."},
            ],
            model=model,
            max_tokens=test_config.get("max_tokens", 30),
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        assert response.content
        # Should be valid JSON
        import json

        try:
            data = json.loads(response.content)
            assert "status" in data
        except json.JSONDecodeError:
            pytest.fail(f"Response is not valid JSON: {response.content}")


# =============================================================================
# Anthropic Integration Tests
# =============================================================================


@pytest.mark.integration
class TestAnthropicLive:
    """Live integration tests for Anthropic provider."""

    @pytest.fixture
    def provider(self, anthropic_api_key):
        """Create Anthropic provider (skips if no API key)."""
        if not anthropic_api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")
        return get_provider("anthropic", api_key=anthropic_api_key)

    def test_simple_completion(self, provider, test_config):
        """Test simple chat completion with claude-3-haiku."""
        model = test_config.get("anthropic_model", "claude-3-haiku-20240307")

        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model
        assert response.input_tokens > 0
        assert response.output_tokens > 0

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_list_models(self, provider):
        """Test listing available models."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # list_models() returns ModelInfo dataclass or dict depending on provider
        if hasattr(models[0], "model_id"):
            model_ids = [m.model_id for m in models]
        else:
            model_ids = [m.get("model_id", m.get("id", "")) for m in models]
        # Should include Claude models
        assert any("claude" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:5]}")

    def test_streaming_completion(self, provider, test_config):
        """Test streaming chat completion."""
        model = test_config.get("anthropic_model", "claude-3-haiku-20240307")

        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=model,
                max_tokens=test_config.get("max_tokens", 20),
            )
        )

        assert len(chunks) > 0

        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        print(f"\n  Streamed: {full_content[:100]}")

    def test_system_message(self, provider, test_config):
        """Test completion with system message."""
        model = test_config.get("anthropic_model", "claude-3-haiku-20240307")

        response = provider.chat_completion(
            messages=[
                {"role": "user", "content": "What is 2+2?"},
            ],
            model=model,
            max_tokens=test_config.get("max_tokens", 20),
            temperature=0.0,
            system="You only respond with numbers, nothing else.",
        )

        assert response.content
        assert "4" in response.content


# =============================================================================
# LangDock Integration Tests
# =============================================================================


@pytest.mark.integration
class TestLangDockLive:
    """Live integration tests for LangDock provider (OpenAI backend)."""

    @pytest.fixture
    def provider(self, langdock_api_key):
        """Create LangDock provider with OpenAI backend (skips if no API key)."""
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")
        return get_provider("langdock", api_key=langdock_api_key, backend="openai", region="eu")

    def test_simple_completion(self, provider, test_config):
        """Test simple chat completion via LangDock."""
        model = test_config.get("langdock_model", "gpt-4o-mini")

        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model
        assert response.input_tokens > 0
        assert response.output_tokens > 0

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_list_models(self, provider):
        """Test listing available models via LangDock."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # Should include GPT models
        model_ids = [m.get("id", "") for m in models]
        assert any("gpt" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:5]}")

    def test_streaming_completion(self, provider, test_config):
        """Test streaming chat completion via LangDock."""
        model = test_config.get("langdock_model", "gpt-4o-mini")

        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=model,
                max_tokens=test_config.get("max_tokens", 20),
            )
        )

        assert len(chunks) > 0

        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        print(f"\n  Streamed: {full_content[:100]}")

    def test_system_message(self, provider, test_config):
        """Test completion with system message via LangDock."""
        model = test_config.get("langdock_model", "gpt-4o-mini")

        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "You only respond with the word 'ACKNOWLEDGED'."},
                {"role": "user", "content": "Hello!"},
            ],
            model=model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "acknowledged" in response.content.lower()

    def test_eu_region(self, langdock_api_key, test_config):
        """Test that EU region is used for GDPR compliance."""
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")

        provider = get_provider(
            "langdock",
            api_key=langdock_api_key,
            backend="openai",
            region="eu",
        )

        # Verify region is set correctly
        assert provider.region == "eu"

        # Make a simple API call to verify it works
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model=test_config.get("langdock_model", "gpt-4o-mini"),
            max_tokens=5,
        )

        assert response.content


@pytest.mark.integration
class TestLangDockAnthropicBackend:
    """Live integration tests for LangDock with Anthropic backend."""

    @pytest.fixture
    def provider(self, langdock_api_key):
        """Create LangDock provider with Anthropic backend."""
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")
        return get_provider(
            "langdock",
            api_key=langdock_api_key,
            backend="anthropic",
            region="eu",
        )

    def test_anthropic_completion(self, provider, test_config):
        """Test completion via LangDock Anthropic backend."""
        # Use claude-haiku-4-5 which is available via LangDock
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model="claude-haiku-4-5-20251001",
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")

    def test_anthropic_list_models(self, provider):
        """Test listing Anthropic models via LangDock."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        model_ids = [m.get("id", "") for m in models]
        assert any("claude" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} Anthropic models")
        print(f"  Sample: {model_ids[:5]}")


# =============================================================================
# Cost-Effective Testing Pattern
# =============================================================================


@pytest.mark.integration
class TestCostEffectivePatterns:
    """Examples of cost-effective testing patterns."""

    def test_minimal_token_usage(self, openai_api_key, test_config):
        """Demonstrate minimal token usage pattern."""
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY not set")

        provider = get_provider("openai", api_key=openai_api_key)

        # Use the cheapest model
        model = "gpt-4o-mini"

        # Minimal prompt
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "1"}],  # Minimal input
            model=model,
            max_tokens=1,  # Minimal output
            temperature=0.0,
        )

        # This should cost < $0.0001
        print(f"\n  Tokens used: {response.input_tokens + response.output_tokens}")
        print(f"  Estimated cost: ~${(response.input_tokens * 0.15 + response.output_tokens * 0.60) / 1_000_000:.6f}")
