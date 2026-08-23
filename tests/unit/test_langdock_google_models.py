"""The Google and Codestral backends must not carry a hand-maintained catalogue.

Verified live on 23.08.2026: the provider advertised `gemini-2.5-flash` and
defaulted to it, but LangDock answered
`400 {"message":"Invalid model, available models are: gemini-3.5-flash,
gemini-2.5-pro, gemini-3.7-flash"}` — the static list had gone stale and every
default-model call to the Google backend failed. Codestral had the same problem:
the default `codestral-latest` does not exist, only `codestral-2501`.

Both backends do expose a live model endpoint, so nothing has to be maintained
by hand:
    GET /google/eu/v1beta/models -> {"models":[{"name":"models/gemini-3.5-flash"}]}
    GET /mistral/eu/v1/models    -> {"data":[{"id":"codestral-2501"}]}
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

GOOGLE_PAYLOAD = {
    "models": [
        {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.7-flash", "supportedGenerationMethods": ["generateContent"]},
    ]
}


def _provider(**kwargs):
    with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        return LangDockProvider(api_key="test-key", **kwargs)


def _with_json(provider, payload, status=200):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client = MagicMock()
    client.get.return_value = response
    provider._http_client = client
    return client


class TestGoogleModelListing:
    def test_models_come_from_the_live_endpoint(self):
        provider = _provider(backend="google")
        _with_json(provider, GOOGLE_PAYLOAD)

        ids = [m["id"] for m in provider.list_models()]

        assert ids == ["gemini-3.5-flash", "gemini-2.5-pro", "gemini-3.7-flash"]

    def test_models_prefix_is_stripped(self):
        """Gemini's endpoint returns `models/<id>`; sending that back is a 400."""
        provider = _provider(backend="google")
        _with_json(provider, GOOGLE_PAYLOAD)

        assert all(not m["id"].startswith("models/") for m in provider.list_models())

    def test_entries_keep_the_provider_metadata(self):
        provider = _provider(backend="google")
        _with_json(provider, GOOGLE_PAYLOAD)

        first = provider.list_models()[0]

        assert first["provider"] == "langdock"
        assert first["backend"] == "google"

    def test_no_hardcoded_25_flash_anywhere(self):
        """The stale id must not survive as a fallback — it 400s at LangDock."""
        provider = _provider(backend="google")
        _with_json(provider, {"models": []})

        assert provider.list_models() == []

    def test_default_model_is_one_langdock_actually_serves(self):
        assert _provider(backend="google").default_model == "gemini-3.7-flash"


class TestCodestralDefaults:
    def test_default_model_is_the_served_id(self):
        assert _provider(backend="codestral").default_model == "codestral-2501"

    def test_chat_listing_stays_empty_on_purpose(self):
        """Codestral only does FIM; offering it in a chat model picker is wrong."""
        provider = _provider(backend="codestral")
        _with_json(provider, {"data": [{"id": "codestral-2501"}]})

        assert provider.list_models() == []


class TestGoogleStreaming:
    """The Gemini endpoint only speaks SSE when asked.

    Verified live on 23.08.2026: without `?alt=sse` LangDock answers
    `Content-Type: application/json` with a single JSON *array* of chunks. The
    parser looks for `data: ` lines, found none, and yielded nothing at all — a
    silent empty stream, no error anywhere. With `?alt=sse` the same endpoint
    returns `text/event-stream` and the parser works as written.
    """

    SSE_LINES = [
        'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"4 "}]},"index":0}]}',
        'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"5 6"}]},"index":0}]}',
        'data: {"candidates":[{"content":{"role":"model","parts":[]},"finishReason":"STOP","index":0}],'
        '"usageMetadata":{"promptTokenCount":7,"candidatesTokenCount":4}}',
    ]

    def _with_sse(self, provider, lines):
        response = MagicMock()
        response.status_code = 200
        response.iter_lines.return_value = iter(lines)
        response.raise_for_status.return_value = None
        ctx = MagicMock()
        ctx.__enter__.return_value = response
        ctx.__exit__.return_value = False
        client = MagicMock()
        client.stream.return_value = ctx
        provider._http_client = client
        return client

    def test_request_asks_for_sse(self):
        provider = _provider(backend="google")
        client = self._with_sse(provider, self.SSE_LINES)

        list(provider.stream_completion([{"role": "user", "content": "hi"}], model="gemini-3.5-flash"))

        url = client.stream.call_args[0][1]
        assert "alt=sse" in url, "without this the endpoint returns a JSON array and the stream is silently empty"

    def test_text_arrives_in_chunks(self):
        provider = _provider(backend="google")
        self._with_sse(provider, self.SSE_LINES)

        chunks = list(provider.stream_completion([{"role": "user", "content": "hi"}], model="gemini-3.5-flash"))

        assert "".join(c.content or "" for c in chunks) == "4 5 6"
        assert chunks[-1].is_final is True
        assert chunks[-1].finish_reason == "STOP"

    def test_usage_lands_on_the_final_chunk(self):
        provider = _provider(backend="google")
        self._with_sse(provider, self.SSE_LINES)

        final = list(provider.stream_completion([{"role": "user", "content": "hi"}], model="gemini-3.5-flash"))[-1]

        assert final.input_tokens == 7
        assert final.output_tokens == 4
