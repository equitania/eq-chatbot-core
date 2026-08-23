"""
Integration tests for the Privatemode.ai provider (end-to-end encrypted).

Privatemode has no public API. These tests talk to the local privatemode-proxy,
which performs the client-side encryption and the remote attestation::

    docker run -p 8080:8080 \\
        ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest \\
        --apiKey <your-api-key>

Configuration in tests/.env.test (all optional):
- PRIVATEMODE_BASE_URL   — proxy endpoint; defaults to http://localhost:8080/v1
- PRIVATEMODE_API_KEY    — only needed when the proxy runs WITHOUT --apiKey
- PRIVATEMODE_TEST_MODEL — overrides the registry primary model

Every test skips when the proxy is not reachable, so the suite stays green on
machines that do not run it.

Run with: pytest -m integration tests/integration/test_privatemode_live.py -v
"""

import pytest

from eq_chatbot_core.providers import get_provider


@pytest.mark.integration
class TestPrivatemodeLive:
    @pytest.fixture
    def provider(self, test_config, privatemode_base_url):
        # api_key stays optional: in the documented setup the proxy holds it.
        return get_provider(
            "privatemode",
            api_key=test_config.get("privatemode_api_key"),
            base_url=privatemode_base_url,
        )

    def test_simple_completion(self, provider, test_config, privatemode_resolved_model):
        # Kimi is a reasoning model: it spends a variable number of tokens
        # thinking before emitting visible content, so give generous headroom.
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=privatemode_resolved_model,
            max_tokens=max(test_config.get("max_tokens", 300), 1024),
            temperature=0.0,
        )
        assert response.content
        assert response.input_tokens > 0
        assert response.output_tokens > 0
        print(f"\n  Model: {response.model}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_streaming_completion(self, provider, test_config, privatemode_resolved_model):
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=privatemode_resolved_model,
                max_tokens=max(test_config.get("max_tokens", 300), 1024),
            )
        )
        assert len(chunks) > 0
        assert "".join(c.content for c in chunks if c.content)
        assert chunks[-1].is_final is True
        assert chunks[-1].output_tokens > 0

    def test_thinking_can_be_disabled_via_chat_template_kwargs(self, provider, test_config, privatemode_resolved_model):
        # Vendor-documented extra_body field, surfaced as a plain keyword here.
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=privatemode_resolved_model,
            max_tokens=max(test_config.get("max_tokens", 300), 1024),
            temperature=0.0,
            chat_template_kwargs={"thinking": False},
        )
        assert response.content

    def test_list_models(self, provider, privatemode_resolved_model):
        models = provider.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        # The resolved test model must appear in the proxy's catalog.
        assert privatemode_resolved_model in [m.get("id", "") for m in models]

    def test_context_manager(self, test_config, privatemode_base_url, privatemode_resolved_model):
        with get_provider(
            "privatemode",
            api_key=test_config.get("privatemode_api_key"),
            base_url=privatemode_base_url,
        ) as provider:
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=privatemode_resolved_model,
                max_tokens=max(test_config.get("max_tokens", 300), 1024),
            )
            assert response.content
