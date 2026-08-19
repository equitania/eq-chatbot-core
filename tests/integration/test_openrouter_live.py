"""
Integration tests for OpenRouter provider.

These tests require a valid OPENROUTER_API_KEY in .env.test.

Run with: pytest -m integration tests/integration/test_openrouter_live.py

Set SKIP_LIVE_TESTS=false in .env.test to enable these tests.

Costs are minimized by using openai/gpt-4o-mini and max_tokens<=20.
"""

import pytest

from eq_chatbot_core.providers import get_provider

# =============================================================================
# OpenRouter Integration Tests
# =============================================================================


@pytest.mark.integration
class TestOpenRouterLive:
    """Live integration tests for OpenRouter provider (gateway to 400+ models)."""

    @pytest.fixture
    def provider(self, openrouter_api_key, test_config):
        """Create OpenRouter provider (skips if no API key)."""
        if not openrouter_api_key:
            pytest.skip("OPENROUTER_API_KEY not set")
        return get_provider(
            "openrouter",
            api_key=openrouter_api_key,
            site_url=test_config.get("openrouter_site_url"),
            site_name=test_config.get("openrouter_site_name"),
        )

    def test_simple_completion(self, provider, test_config, openrouter_resolved_model):
        """Test simple chat completion via OpenRouter."""
        model = openrouter_resolved_model

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
        """Test listing the OpenRouter model catalog."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 100, "OpenRouter exposes 400+ models — got fewer than 100"

        # Every entry must carry a slash-prefixed id (provider/model)
        model_ids = [m["id"] for m in models]
        assert all("/" in mid for mid in model_ids), "OpenRouter model ids should be 'provider/model'"

        # Sanity: at least one OpenAI and one Anthropic route should exist
        assert any(mid.startswith("openai/") for mid in model_ids)
        assert any(mid.startswith("anthropic/") for mid in model_ids)

        # Constraints must be present per model dict
        sample = models[0]
        assert "supports_temperature" in sample
        assert sample["provider"] == "openrouter"

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:5]}")

    def test_streaming_completion(self, provider, test_config, openrouter_resolved_model):
        """Test SSE streaming completion via OpenRouter."""
        model = openrouter_resolved_model

        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=model,
                max_tokens=test_config.get("max_tokens", 20),
            )
        )

        assert len(chunks) > 0

        # At least one chunk must carry content; final chunk must signal completion
        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        assert any(c.is_final for c in chunks), "Stream must yield a final chunk"

        print(f"\n  Streamed: {full_content[:100]}")

    def test_system_message(self, provider, test_config, openrouter_resolved_model):
        """Test completion with system message."""
        model = openrouter_resolved_model

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

    def test_provider_prefix_routing(self, provider, test_config, openrouter_resolved_model):
        """OpenRouter routes via provider/model prefix; verify response model echoes the prefix."""
        model = openrouter_resolved_model

        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Reply: ok"}],
            model=model,
            max_tokens=5,
            temperature=0.0,
        )

        # OpenRouter echoes the routed model id (may be normalized but keeps the prefix)
        assert "/" in response.model, f"Expected provider/model format, got: {response.model}"
        assert response.model.startswith(model.split("/")[0])
