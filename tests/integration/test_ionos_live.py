"""
Integration tests for the IONOS AI Model Hub provider (EU-hosted, OpenAI-compatible).

These tests require valid credentials in ~/.config/eq-chatbot/config.toml:
- IONOS_API_KEY   — Bearer token from the IONOS DCD Token Manager
- IONOS_BASE_URL  — optional; defaults to the official IONOS endpoint
- IONOS_TEST_MODEL — optional; overrides the registry primary model

Run with: pytest -m integration tests/integration/test_ionos_live.py -v
Live tests run by default; export SKIP_LIVE_TESTS=true to skip them.
"""

import pytest

from eq_chatbot_core.providers import get_provider


@pytest.mark.integration
class TestIonosLive:
    @pytest.fixture
    def provider(self, ionos_api_key, ionos_base_url):
        if not ionos_api_key:
            pytest.skip("IONOS_API_KEY not set")
        # base_url is optional — the provider defaults to the IONOS endpoint.
        return get_provider("ionos", api_key=ionos_api_key, base_url=ionos_base_url)

    def test_simple_completion(self, provider, test_config, ionos_resolved_model):
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=ionos_resolved_model,
            max_tokens=test_config.get("max_tokens", 300),
            temperature=0.0,
        )
        assert response.content
        assert response.input_tokens > 0
        assert response.output_tokens > 0
        print(f"\n  Model: {response.model}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_streaming_completion(self, provider, test_config, ionos_resolved_model):
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=ionos_resolved_model,
                max_tokens=test_config.get("max_tokens", 300),
            )
        )
        assert len(chunks) > 0
        full_content = "".join(c.content for c in chunks if c.content)
        assert full_content
        # The authoritative final chunk carries finish_reason + usage totals.
        assert chunks[-1].is_final is True
        assert chunks[-1].output_tokens > 0

    def test_list_models(self, provider, ionos_resolved_model):
        models = provider.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        model_ids = [m.get("id", "") for m in models]
        # The resolved test model must appear in the IONOS catalog.
        assert ionos_resolved_model in model_ids

    def test_context_manager(self, ionos_api_key, ionos_base_url, ionos_resolved_model, test_config):
        if not ionos_api_key:
            pytest.skip("IONOS_API_KEY not set")
        with get_provider("ionos", api_key=ionos_api_key, base_url=ionos_base_url) as provider:
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=ionos_resolved_model,
                max_tokens=test_config.get("max_tokens", 300),
            )
            assert response.content
