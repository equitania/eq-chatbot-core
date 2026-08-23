"""Google and Codestral must not swallow the upstream reason.

Both paths logged the response body and then called `raise_for_status()`, so the
caller received a bare "Client error '400 Bad Request' for url …" while the
actual cause sat in a log line nobody reads. Verified live on 23.08.2026: a
retired model id produced
`{"message":"Invalid model, available models are: gemini-3.5-flash, …"}` and a
missing workspace entitlement produced
`{"message":"... was not found or your project does not have access to it"}` —
both invisible to the caller, both immediately actionable once surfaced.
"""

from unittest.mock import MagicMock, patch

import httpx2
import pytest

from eq_chatbot_core.providers.base import AuthenticationError, ProviderError, RateLimitError

pytestmark = pytest.mark.unit


def _provider(**kwargs):
    with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        return LangDockProvider(api_key="test-key", **kwargs)


def _failing(provider, status, body):
    response = MagicMock()
    response.status_code = status
    response.text = body
    response.raise_for_status.side_effect = httpx2.HTTPStatusError(
        f"Client error '{status}' for url 'https://example/x'",
        request=MagicMock(),
        response=MagicMock(status_code=status),
    )
    client = MagicMock()
    client.post.return_value = response
    provider._http_client = client
    return client


class TestGoogleErrorDetail:
    def test_invalid_model_reason_reaches_the_caller(self):
        provider = _provider(backend="google")
        _failing(provider, 400, '{"message":"Invalid model, available models are: gemini-3.5-flash"}')

        with pytest.raises(ProviderError) as exc:
            provider.chat_completion([{"role": "user", "content": "hi"}], model="gemini-2.5-flash")

        assert "Invalid model" in str(exc.value)
        assert "gemini-3.5-flash" in str(exc.value)
        assert exc.value.status_code == 400

    def test_401_still_maps_to_authentication_error(self):
        provider = _provider(backend="google")
        _failing(provider, 401, '{"message":"The provided API key is invalid."}')

        with pytest.raises(AuthenticationError):
            provider.chat_completion([{"role": "user", "content": "hi"}], model="gemini-3.5-flash")

    def test_429_still_maps_to_rate_limit_error(self):
        provider = _provider(backend="google")
        _failing(provider, 429, '{"message":"rate limit exceeded"}')

        with pytest.raises(RateLimitError):
            provider.chat_completion([{"role": "user", "content": "hi"}], model="gemini-3.5-flash")


class TestCodestralErrorDetail:
    def test_no_access_reason_reaches_the_caller(self):
        provider = _provider(backend="codestral")
        _failing(
            provider,
            400,
            '{"message":"Publisher model codestral-2501 was not found or your project does not have access to it."}',
        )

        with pytest.raises(ProviderError) as exc:
            provider.chat_completion([{"role": "user", "content": "def f():"}])

        assert "does not have access" in str(exc.value)
        assert exc.value.status_code == 400
