"""
Integration tests for Google Vertex AI provider.

Requires:
- VERTEX_PROJECT environment variable set
- Google Cloud ADC configured (gcloud auth application-default login)

Run with: pytest tests/integration/test_vertex_live.py -v
"""

import pytest

from eq_chatbot_core.providers import get_provider


@pytest.mark.integration
class TestVertexLive:
    """Live integration tests for Vertex AI."""

    @pytest.fixture
    def provider(self, test_config):
        """Create a live Vertex provider."""
        project = test_config.get("vertex_project")
        if not project:
            pytest.skip("VERTEX_PROJECT not set")
        location = test_config.get("vertex_location", "europe-west1")
        return get_provider("vertex", project=project, location=location)

    @pytest.fixture
    def test_model(self, test_config):
        """Get test model name."""
        return test_config.get("vertex_model", "gemini-2.5-flash")

    def test_simple_completion(self, provider, test_model):
        """Test simple chat completion with real API."""
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'hello' and nothing else."}],
            model=test_model,
            max_tokens=20,
        )
        assert response.content
        assert response.input_tokens > 0
        assert response.output_tokens > 0

    def test_streaming_completion(self, provider, test_model):
        """Test streaming completion with real API."""
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Say 'hi' and nothing else."}],
                model=test_model,
                max_tokens=20,
            )
        )
        assert len(chunks) > 0
        assert any(c.is_final for c in chunks)

        # Final chunk should have token counts
        final = [c for c in chunks if c.is_final][0]
        assert final.input_tokens > 0

    def test_system_message(self, provider, test_model):
        """Test system message handling."""
        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "You only respond with the word 'PONG'."},
                {"role": "user", "content": "PING"},
            ],
            model=test_model,
            max_tokens=10,
        )
        assert response.content
        assert "PONG" in response.content.upper()

    def test_list_models(self, provider):
        """Test model listing returns known models."""
        models = provider.list_models()
        assert len(models) >= 4
        ids = [m["id"] for m in models]
        assert "gemini-2.5-flash" in ids

    def test_context_manager(self, test_config):
        """Test context manager protocol."""
        project = test_config.get("vertex_project")
        if not project:
            pytest.skip("VERTEX_PROJECT not set")

        with get_provider("vertex", project=project) as provider:
            models = provider.list_models()
            assert len(models) >= 4
