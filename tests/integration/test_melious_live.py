"""
Integration tests for the Melious.ai provider (sovereign EU-hosted, OpenAI-compatible).

These tests require valid credentials in tests/.env.test:
- MELIOUS_API_KEY    — API key (prefix ``sk-mel-``) from the Melious account dashboard
- MELIOUS_BASE_URL   — optional; defaults to the official Melious endpoint
- MELIOUS_TEST_MODEL — optional; overrides the registry primary model

Run with: pytest -m integration tests/integration/test_melious_live.py -v
Set SKIP_LIVE_TESTS=false in tests/.env.test to enable these tests.
"""

import pytest

from eq_chatbot_core.providers import get_provider


@pytest.mark.integration
class TestMeliousLive:
    @pytest.fixture
    def provider(self, melious_api_key, melious_base_url):
        if not melious_api_key:
            pytest.skip("MELIOUS_API_KEY not set")
        # base_url is optional — the provider defaults to the Melious endpoint.
        return get_provider("melious", api_key=melious_api_key, base_url=melious_base_url)

    def test_simple_completion(self, provider, test_config, melious_resolved_model):
        # Melious's open-weight models are typically reasoning models (e.g. the
        # gpt-oss family and minimax-428b-m3) — give headroom so visible content
        # (not just reasoning tokens) lands within budget. See streaming test.
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=melious_resolved_model,
            max_tokens=max(test_config.get("max_tokens", 300), 1024),
            temperature=0.0,
        )
        assert response.content
        assert response.input_tokens > 0
        assert response.output_tokens > 0
        print(f"\n  Model: {response.model}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_streaming_completion(self, provider, test_config, melious_resolved_model):
        # Melious's open-weight models are typically reasoning models (e.g. the
        # gpt-oss family, minimax-428b-m3): they spend an initial, variable number
        # of tokens "thinking" (server-side reasoning, streamed as empty content
        # deltas) before emitting visible content. A tight max_tokens makes this
        # flaky — give generous headroom so the visible answer lands within budget.
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=melious_resolved_model,
                max_tokens=max(test_config.get("max_tokens", 300), 1024),
            )
        )
        assert len(chunks) > 0
        full_content = "".join(c.content for c in chunks if c.content)
        assert full_content
        # The authoritative final chunk carries finish_reason + usage totals.
        assert chunks[-1].is_final is True
        assert chunks[-1].output_tokens > 0

    def test_list_models(self, provider, melious_resolved_model):
        models = provider.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        model_ids = [m.get("id", "") for m in models]
        # The resolved test model must appear in the Melious catalog.
        assert melious_resolved_model in model_ids

    def test_context_manager(self, melious_api_key, melious_base_url, melious_resolved_model, test_config):
        if not melious_api_key:
            pytest.skip("MELIOUS_API_KEY not set")
        with get_provider("melious", api_key=melious_api_key, base_url=melious_base_url) as provider:
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=melious_resolved_model,
                max_tokens=max(test_config.get("max_tokens", 300), 1024),
            )
            assert response.content
