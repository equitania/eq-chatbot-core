"""Unit tests for the FastAPI application factory and endpoints.

The provider layer is mocked via ``unittest.mock.patch`` on
``eq_chatbot_core.server.app.get_provider`` so tests don't hit any real LLM.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from eq_chatbot_core.providers.base import (  # noqa: E402
    AuthenticationError,
    ContextLengthError,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
)
from eq_chatbot_core.server.app import create_app  # noqa: E402

TOKEN = "test-token-with-enough-entropy-aaaaaaaa"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """sse-starlette stores a singleton ``AppStatus.should_exit_event`` that
    binds itself to the asyncio loop of the *first* test that hits an SSE
    endpoint. Subsequent tests run on a fresh TestClient loop and the stale
    Event raises ``RuntimeError: bound to a different event loop``. Reset the
    singleton between tests to dodge the cross-test contamination."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None  # type: ignore[assignment]
    yield
    AppStatus.should_exit_event = None  # type: ignore[assignment]


@pytest.fixture
def client():
    app = create_app(auth_token=TOKEN)
    return TestClient(app)


@pytest.mark.unit
class TestHealthAndProviders:
    def test_health_returns_ok_without_auth(self, client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "version" in body
        assert body["uptime_seconds"] >= 0

    def test_providers_requires_auth(self, client) -> None:
        assert client.get("/providers").status_code == 401

    def test_providers_lists_known_names(self, client) -> None:
        resp = client.get("/providers", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()
        # Spot-check a couple of expected entries from each bucket
        assert "openai" in body["cloud"]
        assert "anthropic" in body["cloud"]
        assert "lm_studio" in body["local"]


@pytest.mark.unit
class TestChatEndpoint:
    def test_chat_returns_provider_response(self, client) -> None:
        mock_provider = MagicMock()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Hello back!",
            model="gpt-4o-mini",
            input_tokens=5,
            output_tokens=3,
            finish_reason="stop",
            tool_calls=[],
        )
        with patch("eq_chatbot_core.server.app.get_provider", return_value=mock_provider) as m:
            resp = client.post(
                "/chat",
                headers=AUTH,
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "provider": "openai",
                    "api_key": "sk-test",
                    "model": "gpt-4o-mini",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "Hello back!"
        assert body["model"] == "gpt-4o-mini"
        assert body["input_tokens"] == 5
        assert body["output_tokens"] == 3
        # provider was constructed with our credentials
        m.assert_called_once_with("openai", api_key="sk-test", base_url=None)

    def test_chat_authentication_error_returns_401(self, client) -> None:
        mock_provider = MagicMock()
        mock_provider.chat_completion.side_effect = AuthenticationError("bad key", provider="openai", status_code=401)
        with patch("eq_chatbot_core.server.app.get_provider", return_value=mock_provider):
            resp = client.post(
                "/chat",
                headers=AUTH,
                json={
                    "messages": [{"role": "user", "content": "x"}],
                    "provider": "openai",
                    "api_key": "sk-bad",
                },
            )
        assert resp.status_code == 401
        body = resp.json()
        assert body["detail"]["type"] == "AuthenticationError"
        assert body["detail"]["provider"] == "openai"

    def test_chat_rate_limit_returns_429_with_retry_after(self, client) -> None:
        mock_provider = MagicMock()
        mock_provider.chat_completion.side_effect = RateLimitError(
            "slow down", provider="anthropic", status_code=429, retry_after=42
        )
        with patch("eq_chatbot_core.server.app.get_provider", return_value=mock_provider):
            resp = client.post(
                "/chat",
                headers=AUTH,
                json={
                    "messages": [{"role": "user", "content": "x"}],
                    "provider": "anthropic",
                    "api_key": "sk-x",
                },
            )
        assert resp.status_code == 429
        assert resp.json()["detail"]["retry_after"] == 42

    def test_chat_context_length_returns_413(self, client) -> None:
        mock_provider = MagicMock()
        mock_provider.chat_completion.side_effect = ContextLengthError("too big", provider="openai", status_code=400)
        with patch("eq_chatbot_core.server.app.get_provider", return_value=mock_provider):
            resp = client.post(
                "/chat",
                headers=AUTH,
                json={
                    "messages": [{"role": "user", "content": "x"}],
                    "provider": "openai",
                    "api_key": "sk-x",
                },
            )
        assert resp.status_code == 413

    def test_chat_unknown_provider_returns_400(self, client) -> None:
        # get_provider raises ValueError for unknown names — surface as 400.
        resp = client.post(
            "/chat",
            headers=AUTH,
            json={
                "messages": [{"role": "user", "content": "x"}],
                "provider": "no-such-thing",
                "api_key": "sk-x",
            },
        )
        assert resp.status_code == 400

    def test_chat_with_tools_forwards_to_provider(self, client) -> None:
        mock_provider = MagicMock()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="",
            model="gpt-4o",
            input_tokens=10,
            output_tokens=2,
            tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "f", "arguments": "{}"}}],
            finish_reason="tool_calls",
        )
        with patch("eq_chatbot_core.server.app.get_provider", return_value=mock_provider):
            resp = client.post(
                "/chat",
                headers=AUTH,
                json={
                    "messages": [{"role": "user", "content": "x"}],
                    "provider": "openai",
                    "api_key": "sk-x",
                    "tools": [
                        {
                            "type": "function",
                            "function": {"name": "f", "description": "", "parameters": {}},
                        }
                    ],
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["finish_reason"] == "tool_calls"
        assert len(body["tool_calls"]) == 1
        # Provider was called with the tools list
        call_kwargs = mock_provider.chat_completion.call_args.kwargs
        assert call_kwargs["tools"] is not None
        assert call_kwargs["tools"][0]["function"]["name"] == "f"


@pytest.mark.unit
class TestChatStreamEndpoint:
    def test_stream_chat_emits_chunk_and_done(self, client) -> None:
        mock_provider = MagicMock()
        mock_provider.stream_completion.return_value = iter(
            [
                StreamChunk(content="Hello"),
                StreamChunk(content=" world"),
                StreamChunk(content="", is_final=True, finish_reason="stop", input_tokens=4, output_tokens=2),
            ]
        )
        with patch("eq_chatbot_core.server.app.get_provider", return_value=mock_provider):
            with client.stream(
                "POST",
                "/chat/stream",
                headers=AUTH,
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "provider": "openai",
                    "api_key": "sk-x",
                },
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                lines = [line for line in resp.iter_lines() if line]

        # Reconstruct event/data pairs from the SSE stream
        events = []
        cur_event = None
        for line in lines:
            if line.startswith("event:"):
                cur_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                events.append((cur_event, line.split(":", 1)[1].strip()))

        event_types = [e for e, _ in events]
        assert event_types[:2] == ["chunk", "chunk"]
        # Final group should contain usage + done
        assert "usage" in event_types
        assert event_types[-1] == "done"

    def test_stream_provider_error_emits_error_event(self, client) -> None:
        mock_provider = MagicMock()

        def boom(*_args, **_kwargs):
            yield StreamChunk(content="partial")
            raise ProviderError("boom", provider="openai", status_code=500)

        mock_provider.stream_completion.side_effect = lambda **_: boom()
        with patch("eq_chatbot_core.server.app.get_provider", return_value=mock_provider):
            with client.stream(
                "POST",
                "/chat/stream",
                headers=AUTH,
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "provider": "openai",
                    "api_key": "sk-x",
                },
            ) as resp:
                assert resp.status_code == 200
                lines = [line for line in resp.iter_lines() if line]

        # Last event must be `error`
        event_types = [line.split(":", 1)[1].strip() for line in lines if line.startswith("event:")]
        assert event_types[-1] == "error"

    def test_stream_unknown_provider_returns_400(self, client) -> None:
        # Bad provider name is caught eagerly before SSE starts.
        resp = client.post(
            "/chat/stream",
            headers=AUTH,
            json={
                "messages": [{"role": "user", "content": "x"}],
                "provider": "bogus-provider",
                "api_key": "sk-x",
            },
        )
        assert resp.status_code == 400

    def test_stream_requires_auth(self, client) -> None:
        resp = client.post(
            "/chat/stream",
            json={
                "messages": [{"role": "user", "content": "x"}],
                "provider": "openai",
                "api_key": "sk-x",
            },
        )
        assert resp.status_code == 401
