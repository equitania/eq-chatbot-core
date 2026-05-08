"""
Integration tests for Mammouth AI provider.

These tests require a valid API key in .env.test:
- MAMMOUTH_API_KEY for Mammouth AI tests

Run with: pytest -m integration tests/integration/test_mammouth_live.py -v

Set SKIP_LIVE_TESTS=false in .env.test to enable these tests.
"""

import pytest

from eq_chatbot_core.providers import get_provider

# =============================================================================
# Mammouth AI Integration Tests
# =============================================================================


@pytest.mark.integration
class TestMammouthLive:
    """Live integration tests for Mammouth AI provider."""

    @pytest.fixture
    def provider(self, mammouth_api_key):
        """Create Mammouth provider (skips if no API key)."""
        if not mammouth_api_key:
            pytest.skip("MAMMOUTH_API_KEY not set")
        return get_provider("mammouth", api_key=mammouth_api_key)

    def test_simple_completion(self, provider, test_config, mammouth_resolved_model):
        """Test simple chat completion with the resolved cheapest model via Mammouth."""
        model = mammouth_resolved_model

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
        """Test listing available models from Mammouth."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        model_ids = [m.get("id", "") for m in models]
        # Should include common models
        assert any("gpt" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:10]}")

    def test_list_models_has_temperature_constraints(self, provider):
        """Test that list_models returns temperature constraint data."""
        models = provider.list_models()

        for model in models:
            assert "supports_temperature" in model, f"Missing supports_temperature for {model['id']}"
            assert "min_temperature" in model, f"Missing min_temperature for {model['id']}"
            assert "max_temperature" in model, f"Missing max_temperature for {model['id']}"

        # Print constraint summary for a few models
        for model in models[:5]:
            print(
                f"\n  {model['id']}: temp={model['min_temperature']}-{model['max_temperature']}, "
                f"supports_temp={model['supports_temperature']}"
            )

    def test_streaming_completion(self, provider, test_config, mammouth_resolved_model):
        """Test streaming chat completion via Mammouth."""
        model = mammouth_resolved_model

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

    def test_system_message(self, provider, test_config, mammouth_resolved_model):
        """Test completion with system message via Mammouth."""
        model = mammouth_resolved_model

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

    def test_context_manager(self, mammouth_api_key, mammouth_resolved_model):
        """Test provider works as context manager."""
        if not mammouth_api_key:
            pytest.skip("MAMMOUTH_API_KEY not set")

        with get_provider("mammouth", api_key=mammouth_api_key) as provider:
            # max_tokens=20 (not 5): newer Azure-backed models like gpt-5.4-nano
            # enforce a minimum max_output_tokens of 16.
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=mammouth_resolved_model,
                max_tokens=20,
            )
            assert response.content
