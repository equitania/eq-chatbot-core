"""
Integration tests for the LiteLLM provider (OpenAI-compatible gateway).

These tests require valid credentials in tests/.env.test:
- LITELLM_API_KEY  — Bearer token for the gateway
- LITELLM_BASE_URL — gateway endpoint, e.g. https://api.ccsio.ai/v1

Run with: pytest -m integration tests/integration/test_litellm_live.py -v
Set SKIP_LIVE_TESTS=false in tests/.env.test to enable these tests.
"""

import pytest

from eq_chatbot_core.providers import get_provider

# The default CCSolutions model (qwen3.6-35b-a3b) is a reasoning model: it emits a
# long `reasoning_content` trace before the answer and can exhaust a small
# max_tokens budget before any visible content. Disable thinking for the
# content-asserting tests so they are deterministic and cheap. The provider stays
# model-agnostic; only the test injects this gateway-specific flag (passed through
# verbatim to the OpenAI SDK via extra_body / **kwargs).
_NO_THINKING = {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}


@pytest.mark.integration
class TestLiteLLMLive:
    @pytest.fixture
    def provider(self, litellm_api_key, litellm_base_url):
        if not litellm_api_key:
            pytest.skip("LITELLM_API_KEY not set")
        if not litellm_base_url:
            pytest.skip("LITELLM_BASE_URL not set")
        return get_provider("litellm", api_key=litellm_api_key, base_url=litellm_base_url)

    def test_simple_completion(self, provider, test_config, litellm_resolved_model):
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=litellm_resolved_model,
            max_tokens=test_config.get("max_tokens", 300),
            temperature=0.0,
            **_NO_THINKING,
        )
        assert response.content
        assert response.input_tokens > 0
        assert response.output_tokens > 0
        print(f"\n  Model: {response.model}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_streaming_completion(self, provider, test_config, litellm_resolved_model):
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=litellm_resolved_model,
                max_tokens=test_config.get("max_tokens", 300),
                **_NO_THINKING,
            )
        )
        assert len(chunks) > 0
        full_content = "".join(c.content for c in chunks if c.content)
        assert full_content
        # The authoritative final chunk carries finish_reason + usage totals,
        # even though this gateway sends usage in a trailing separate frame.
        assert chunks[-1].is_final is True
        assert chunks[-1].output_tokens > 0

    def test_list_models(self, provider, litellm_resolved_model):
        models = provider.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        model_ids = [m.get("id", "") for m in models]
        # The resolved test model must appear in the gateway catalog.
        assert litellm_resolved_model in model_ids

    def test_tts_stt_roundtrip(self, provider):
        """TTS -> STT roundtrip (optional; skips if the gateway lacks audio models)."""
        try:
            audio = provider.text_to_speech("Hello from ccsolutions.")
        except Exception as exc:  # gateway may not expose audio models
            pytest.skip(f"TTS unavailable on this gateway: {exc}")

        assert isinstance(audio, bytes)
        assert len(audio) > 0

        try:
            text = provider.transcribe(("speech.wav", audio, "audio/wav"))
        except Exception as exc:
            pytest.skip(f"STT unavailable on this gateway: {exc}")

        assert isinstance(text, str)
        assert text.strip()
        print(f"\n  STT transcript: {text!r}")

    def test_context_manager(self, litellm_api_key, litellm_base_url, litellm_resolved_model, test_config):
        if not litellm_api_key:
            pytest.skip("LITELLM_API_KEY not set")
        if not litellm_base_url:
            pytest.skip("LITELLM_BASE_URL not set")
        with get_provider("litellm", api_key=litellm_api_key, base_url=litellm_base_url) as provider:
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=litellm_resolved_model,
                max_tokens=test_config.get("max_tokens", 300),
                **_NO_THINKING,
            )
            assert response.content
