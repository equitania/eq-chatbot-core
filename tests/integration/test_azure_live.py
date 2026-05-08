"""
Integration tests for Azure AI provider.

These tests require valid credentials in .env.test:
- AZURE_API_KEY for Azure AI tests
- AZURE_ENDPOINT for Azure AI endpoint URL

Run with: pytest -m integration tests/integration/test_azure_live.py -v

Set SKIP_LIVE_TESTS=false in .env.test to enable these tests.
"""

import pytest

from eq_chatbot_core.providers import get_provider

# =============================================================================
# Azure AI Integration Tests
# =============================================================================


@pytest.mark.integration
class TestAzureLive:
    """Live integration tests for Azure AI provider."""

    @pytest.fixture
    def provider(self, azure_api_key, test_config):
        """Create Azure provider (skips if no API key, endpoint, or [azure] extra)."""
        if not azure_api_key:
            pytest.skip("AZURE_API_KEY not set")
        endpoint = test_config.get("azure_endpoint")
        if not endpoint:
            pytest.skip("AZURE_ENDPOINT not set")
        try:
            return get_provider("azure", api_key=azure_api_key, base_url=endpoint)
        except ImportError as exc:
            pytest.skip(f"Azure SDK not installed (use [azure] extra): {exc}")

    def test_simple_completion(self, provider, test_config, azure_resolved_model):
        """Test simple chat completion via Azure AI."""
        model = azure_resolved_model

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

    def test_streaming_completion(self, provider, test_config, azure_resolved_model):
        """Test streaming chat completion via Azure AI."""
        model = azure_resolved_model

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

    def test_system_message(self, provider, test_config, azure_resolved_model):
        """Test completion with system message via Azure AI."""
        model = azure_resolved_model

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

    def test_list_models(self, provider):
        """Test listing known Azure AI models."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        model_ids = [m.get("id", "") for m in models]
        assert any("gpt" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} known models")
        print(f"  Models: {model_ids}")

    def test_context_manager(self, azure_api_key, test_config, azure_resolved_model):
        """Test provider works as context manager.

        ``azure_resolved_model`` already skips when the [azure] extra is
        missing, so the get_provider call here cannot raise ImportError.
        """
        if not azure_api_key:
            pytest.skip("AZURE_API_KEY not set")
        endpoint = test_config.get("azure_endpoint")
        if not endpoint:
            pytest.skip("AZURE_ENDPOINT not set")

        with get_provider("azure", api_key=azure_api_key, base_url=endpoint) as provider:
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=azure_resolved_model,
                max_tokens=5,
            )
            assert response.content
