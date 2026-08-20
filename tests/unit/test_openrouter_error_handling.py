"""Regression: an HTTP error during streaming must stay a ProviderError.

Found on 20.08.2026 when OpenRouter answered a live streaming request with a
504. `_handle_http_error` called `error.response.json()` on a response whose
body had never been read, which raises `httpx2.ResponseNotRead` — not a
ValueError, so the `except (ValueError, KeyError)` clause did not catch it. The
caller therefore saw "Attempted to access streaming response content" instead of
"the provider returned 504", and the real cause was lost at exactly the moment
someone needs it.

The Mammouth provider already read the body first; OpenRouter did not. These
tests pin both paths and need no network.
"""

from __future__ import annotations

import httpx2
import pytest

from eq_chatbot_core.providers import get_provider
from eq_chatbot_core.providers.base import ProviderError


@pytest.fixture
def provider():
    return get_provider("openrouter", api_key="test-key-not-used")


def _error(*, streaming: bool, body: bytes, status: int = 504) -> httpx2.HTTPStatusError:
    """Build an HTTPStatusError whose response mimics a streamed or a read body."""
    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    if streaming:
        # A response backed by a stream: .json() fails until .read() is called.
        response = httpx2.Response(status, request=request, stream=httpx2.ByteStream(body))
    else:
        response = httpx2.Response(status, request=request, content=body)
    return httpx2.HTTPStatusError("server error", request=request, response=response)


def test_streaming_error_body_is_read_not_crashed(provider):
    """The bug: this raised ResponseNotRead instead of returning a ProviderError."""
    err = _error(streaming=True, body=b'{"error": {"message": "upstream timed out"}}')

    result = provider._handle_http_error(err)

    assert isinstance(result, ProviderError)
    assert "upstream timed out" in str(result), "the provider's own message must survive"


def test_streaming_error_without_json_body_still_returns_provider_error(provider):
    """A gateway often answers HTML, not JSON — that must not crash either."""
    err = _error(streaming=True, body=b"<html>504 Gateway Timeout</html>")

    result = provider._handle_http_error(err)

    assert isinstance(result, ProviderError)
    assert str(result), "an empty message would leave the caller with nothing"


def test_non_streaming_error_unchanged(provider):
    """The already-working path must keep working."""
    err = _error(streaming=False, body=b'{"error": {"message": "rate limited"}}', status=429)

    result = provider._handle_http_error(err)

    assert isinstance(result, ProviderError)
    assert "rate limited" in str(result)


def test_status_code_is_preserved(provider):
    """Whatever the body says, the HTTP status must reach the caller."""
    err = _error(streaming=True, body=b'{"error": {"message": "boom"}}', status=429)

    result = provider._handle_http_error(err)

    assert getattr(result, "status_code", None) == 429
