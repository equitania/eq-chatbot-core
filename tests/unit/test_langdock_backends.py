"""Characterization tests for the LangDock backend dispatch and its five paths.

test_langdock.py covers init, the OpenAI backend and parts of Anthropic. This
module pins down the behaviour that was previously untested — the agent, google
and codestral paths, the message-format converters, model listing, error
mapping and the three manager classes — so the planned consolidation of this
provider onto the shared OpenAI-compatible base has a safety net to refactor
against.
"""

import json
from unittest.mock import MagicMock, patch

import httpx2
import pytest

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
)

pytestmark = pytest.mark.unit


def _provider(**kwargs):
    """Build a provider with the optional SDKs stubbed out."""
    with patch.dict("sys.modules", {"openai": MagicMock(), "anthropic": MagicMock()}):
        from eq_chatbot_core.providers.langdock_provider import LangDockProvider

        return LangDockProvider(api_key="test-key", **kwargs)


def _resp(status=200, payload=None, text=""):
    """Minimal stand-in for an httpx2.Response as this provider consumes it."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.text = text or json.dumps(payload or {})
    return r


def _with_http(provider, response):
    """Attach a mocked pinned http_client returning `response`."""
    client = MagicMock()
    client.post.return_value = response
    client.get.return_value = response
    provider._http_client = client
    return client


# =============================================================================
# Backend dispatch
# =============================================================================


class TestBackendDispatch:
    """chat_completion / stream_completion must route to the configured backend."""

    @pytest.mark.parametrize(
        "backend,method,extra",
        [
            ("openai", "_openai_chat_completion", {}),
            ("anthropic", "_anthropic_chat_completion", {}),
            ("google", "_google_chat_completion", {}),
            ("codestral", "_codestral_completion", {}),
            ("agent", "_agent_chat_completion", {"agent_id": "ag-1"}),
        ],
    )
    def test_chat_completion_routes_to_backend(self, backend, method, extra):
        provider = _provider(backend=backend, **extra)
        with patch.object(provider, method, return_value="routed") as target:
            result = provider.chat_completion([{"role": "user", "content": "hi"}])

        assert result == "routed"
        target.assert_called_once()

    def test_unknown_backend_cannot_be_constructed(self):
        with pytest.raises(ValueError, match="Invalid backend"):
            _provider(backend="does-not-exist")

    def test_agent_backend_requires_agent_id(self):
        with pytest.raises(ValueError, match="agent_id is required"):
            _provider(backend="agent")

    def test_default_model_per_backend(self):
        assert _provider(backend="openai").default_model == "gpt-4o"
        assert _provider(backend="google").default_model == "gemini-2.5-flash"
        assert _provider(backend="codestral").default_model == "codestral-latest"
        assert _provider(backend="anthropic").default_model.startswith("claude-")
        assert _provider(backend="agent", agent_id="ag-1").default_model is None


# =============================================================================
# Agent message conversion
# =============================================================================


class TestAgentMessageFiltering:
    def test_system_messages_are_dropped(self):
        """Agent instructions live in LangDock, so system messages are not sent."""
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._filter_agent_messages(
            [
                {"role": "system", "content": "be nice"},
                {"role": "user", "content": "hi"},
            ]
        )

        assert [m["role"] for m in out] == ["user"]

    def test_user_assistant_tool_are_kept(self):
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._filter_agent_messages(
            [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
                {"role": "tool", "content": "c"},
            ]
        )

        assert [m["role"] for m in out] == ["user", "assistant", "tool"]

    def test_unknown_role_is_dropped(self):
        provider = _provider(backend="agent", agent_id="ag-1")

        assert provider._filter_agent_messages([{"role": "function", "content": "x"}]) == []


class TestAgentMessageConversion:
    def test_converts_to_uimessage_parts(self):
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._convert_to_agent_messages([{"role": "user", "content": "hello"}])

        assert out == [{"id": "msg_0", "role": "user", "parts": [{"type": "text", "text": "hello"}]}]

    def test_ids_are_sequential_after_filtering(self):
        """Indices come from the filtered list, so a dropped system message does not gap them."""
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._convert_to_agent_messages(
            [
                {"role": "system", "content": "ignored"},
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
            ]
        )

        assert [m["id"] for m in out] == ["msg_0", "msg_1"]

    def test_multimodal_list_content_is_flattened_to_text(self):
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._convert_to_agent_messages(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "one"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
                        {"type": "text", "text": "two"},
                    ],
                }
            ]
        )

        assert out[0]["parts"] == [{"type": "text", "text": "one two"}]

    def test_attachment_ids_move_to_metadata(self):
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._convert_to_agent_messages(
            [{"role": "user", "content": "see file", "attachmentIds": ["at-1", "at-2"]}]
        )

        assert out[0]["metadata"] == {"attachments": ["at-1", "at-2"]}

    def test_no_metadata_key_without_attachments(self):
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._convert_to_agent_messages([{"role": "user", "content": "plain"}])

        assert "metadata" not in out[0]

    def test_empty_content_becomes_empty_text_part(self):
        provider = _provider(backend="agent", agent_id="ag-1")

        out = provider._convert_to_agent_messages([{"role": "user", "content": ""}])

        assert out[0]["parts"] == [{"type": "text", "text": ""}]


# =============================================================================
# Agent completion
# =============================================================================


class TestAgentChatCompletion:
    def test_extracts_last_assistant_message(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(
            provider,
            _resp(
                200,
                {
                    "messages": [
                        {"role": "assistant", "content": "first"},
                        {"role": "user", "content": "mid"},
                        {"role": "assistant", "content": "final"},
                    ]
                },
            ),
        )

        result = provider.chat_completion([{"role": "user", "content": "hi"}])

        assert result.content == "final"

    def test_request_goes_through_the_pinned_client(self):
        """Must not use module-level httpx: that would bypass the rebinding guard."""
        provider = _provider(backend="agent", agent_id="ag-1")
        client = _with_http(provider, _resp(200, {"messages": [{"role": "assistant", "content": "x"}]}))

        provider.chat_completion([{"role": "user", "content": "hi"}])

        client.post.assert_called_once()
        path, kwargs = client.post.call_args[0][0], client.post.call_args[1]
        assert path == "/chat/completions"
        assert kwargs["json"]["agentId"] == "ag-1"
        assert kwargs["json"]["stream"] is False

    def test_no_usable_messages_returns_prompt_instead_of_raising(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(200, {}))

        result = provider.chat_completion([{"role": "system", "content": "only system"}])

        assert result.finish_reason == "error"
        assert result.model == "agent:ag-1"

    def test_non_200_raises_provider_error_with_status(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(503, {}, text="upstream down"))

        with pytest.raises(ProviderError) as exc:
            provider.chat_completion([{"role": "user", "content": "hi"}])

        assert exc.value.status_code == 503

    def test_missing_assistant_message_yields_empty_content(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(200, {"messages": [{"role": "user", "content": "echo"}]}))

        assert provider.chat_completion([{"role": "user", "content": "hi"}]).content == ""


class TestAgentStreamCompletion:
    def test_yields_a_single_final_chunk(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(200, {"messages": [{"role": "assistant", "content": "streamed"}]}))

        chunks = list(provider.stream_completion([{"role": "user", "content": "hi"}]))

        assert len(chunks) == 1
        assert chunks[0].content == "streamed"
        assert chunks[0].is_final is True

    def test_no_content_yields_nothing(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(200, {"messages": []}))

        assert list(provider.stream_completion([{"role": "user", "content": "hi"}])) == []


# =============================================================================
# Google / Gemini
# =============================================================================


class TestGeminiPartsConversion:
    def test_plain_string(self):
        provider = _provider(backend="google")

        assert provider._convert_to_gemini_parts("hello") == [{"text": "hello"}]

    def test_empty_string_still_yields_a_part(self):
        provider = _provider(backend="google")

        assert provider._convert_to_gemini_parts("") == [{"text": ""}]

    def test_data_url_image_becomes_inline_data(self):
        provider = _provider(backend="google")

        parts = provider._convert_to_gemini_parts(
            [{"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}]
        )

        assert parts == [{"inlineData": {"mimeType": "image/png", "data": "QUJD"}}]

    def test_external_image_url_is_skipped(self):
        """Gemini cannot take remote URLs here, so they must not be forwarded."""
        provider = _provider(backend="google")

        parts = provider._convert_to_gemini_parts(
            [{"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}]
        )

        assert parts == [{"text": ""}]

    def test_text_and_image_are_both_kept(self):
        provider = _provider(backend="google")

        parts = provider._convert_to_gemini_parts(
            [
                {"type": "text", "text": "look"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,ZZZ"}},
            ]
        )

        assert parts[0] == {"text": "look"}
        assert parts[1]["inlineData"]["mimeType"] == "image/jpeg"

    def test_malformed_data_url_is_dropped_not_raised(self):
        provider = _provider(backend="google")

        parts = provider._convert_to_gemini_parts([{"type": "image_url", "image_url": {"url": "data:broken"}}])

        assert parts == [{"text": ""}]


class TestGoogleChatCompletion:
    def _ok(self):
        return _resp(
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Hi "}, {"text": "there"}]}, "finishReason": "STOP"},
                ],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
            },
        )

    def test_concatenates_all_text_parts(self):
        provider = _provider(backend="google")
        _with_http(provider, self._ok())

        result = provider.chat_completion([{"role": "user", "content": "hi"}], model="gemini-2.5-flash")

        assert result.content == "Hi there"
        assert result.input_tokens == 7
        assert result.output_tokens == 3
        assert result.finish_reason == "STOP"

    def test_request_url_targets_generate_content(self):
        provider = _provider(backend="google")
        client = _with_http(provider, self._ok())

        provider.chat_completion([{"role": "user", "content": "hi"}], model="gemini-2.5-pro")

        assert client.post.call_args[0][0] == "/models/gemini-2.5-pro:generateContent"

    def test_assistant_role_is_mapped_to_model(self):
        provider = _provider(backend="google")
        client = _with_http(provider, self._ok())

        provider.chat_completion(
            [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
            model="gemini-2.5-flash",
        )

        contents = client.post.call_args[1]["json"]["contents"]
        assert [c["role"] for c in contents] == ["user", "model"]

    def test_system_message_becomes_system_instruction(self):
        provider = _provider(backend="google")
        client = _with_http(provider, self._ok())

        provider.chat_completion(
            [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}],
            model="gemini-2.5-flash",
        )

        payload = client.post.call_args[1]["json"]
        assert payload["systemInstruction"] == "be brief"
        assert all(c["role"] != "system" for c in payload["contents"])

    def test_no_system_instruction_key_without_system_message(self):
        provider = _provider(backend="google")
        client = _with_http(provider, self._ok())

        provider.chat_completion([{"role": "user", "content": "hi"}], model="gemini-2.5-flash")

        assert "systemInstruction" not in client.post.call_args[1]["json"]

    def test_max_tokens_defaults_when_not_given(self):
        provider = _provider(backend="google")
        client = _with_http(provider, self._ok())

        provider.chat_completion([{"role": "user", "content": "hi"}], model="gemini-2.5-flash")

        assert client.post.call_args[1]["json"]["generationConfig"]["maxOutputTokens"] == 8192

    def test_empty_candidates_yield_empty_content(self):
        provider = _provider(backend="google")
        _with_http(provider, _resp(200, {"candidates": []}))

        assert provider.chat_completion([{"role": "user", "content": "hi"}]).content == ""


# =============================================================================
# Codestral FIM
# =============================================================================


class TestCodestralCompletion:
    def _ok(self):
        return _resp(
            200,
            {
                "choices": [{"text": "  return a + b", "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 6},
            },
        )

    def test_plain_prompt_without_fim_markers(self):
        provider = _provider(backend="codestral")
        client = _with_http(provider, self._ok())

        result = provider.chat_completion([{"role": "user", "content": "def add(a, b):"}])

        assert result.content == "  return a + b"
        payload = client.post.call_args[1]["json"]
        assert payload["prompt"] == "def add(a, b):"
        assert payload["suffix"] == ""

    def test_fim_markers_split_prompt_and_suffix(self):
        provider = _provider(backend="codestral")
        client = _with_http(provider, self._ok())

        provider.chat_completion(
            [{"role": "user", "content": "<|fim_prefix|>def f():<|fim_suffix|>    return x<|fim_middle|>"}]
        )

        payload = client.post.call_args[1]["json"]
        assert payload["prompt"] == "def f():"
        assert payload["suffix"] == "    return x"

    def test_targets_fim_endpoint(self):
        provider = _provider(backend="codestral")
        client = _with_http(provider, self._ok())

        provider.chat_completion([{"role": "user", "content": "x"}])

        assert client.post.call_args[0][0] == "/fim/completions"

    def test_usage_is_mapped(self):
        provider = _provider(backend="codestral")
        _with_http(provider, self._ok())

        result = provider.chat_completion([{"role": "user", "content": "x"}])

        assert (result.input_tokens, result.output_tokens) == (4, 6)

    def test_max_tokens_default(self):
        provider = _provider(backend="codestral")
        client = _with_http(provider, self._ok())

        provider.chat_completion([{"role": "user", "content": "x"}])

        assert client.post.call_args[1]["json"]["max_tokens"] == 2048


# =============================================================================
# Model constraints and error mapping
# =============================================================================


class TestModelConstraints:
    def test_reasoning_model_reports_no_temperature_support(self):
        provider = _provider()

        c = provider._get_model_constraints("o3-mini")

        assert c["supports_temperature"] is False
        assert c["supports_reasoning"] is True

    def test_gpt4o_supports_vision_and_temperature(self):
        provider = _provider()

        c = provider._get_model_constraints("gpt-4o")

        assert c["supports_vision"] is True
        assert c["supports_temperature"] is True

    def test_gemini_supports_vision(self):
        provider = _provider()

        assert provider._get_model_constraints("gemini-2.5-pro")["supports_vision"] is True

    def test_claude_sonnet_supports_vision(self):
        provider = _provider()

        assert provider._get_model_constraints("claude-sonnet-4-20250514")["supports_vision"] is True

    def test_context_length_from_table(self):
        provider = _provider()

        assert provider._get_model_constraints("gemini-2.5-flash")["context_length"] == 1000000

    def test_unknown_model_gets_a_fallback_context_length(self):
        provider = _provider()

        assert provider._get_model_constraints("some-unknown-model")["context_length"] == 128000

    def test_codestral_output_ceiling(self):
        provider = _provider()

        assert provider._get_model_constraints("codestral-latest")["max_output_tokens"] == 16384


class TestErrorMapping:
    @pytest.mark.parametrize(
        "message,expected",
        [
            ("Rate limit exceeded", RateLimitError),
            ("HTTP 429 returned", RateLimitError),
            ("authentication failed", AuthenticationError),
            ("401 Unauthorized", AuthenticationError),
            ("context length exceeded", ContextLengthError),
            ("too many tokens", ContextLengthError),
            ("something else entirely", ProviderError),
        ],
    )
    def test_exceptions_map_to_typed_errors(self, message, expected):
        provider = _provider()

        result = provider._handle_error(Exception(message))

        assert isinstance(result, expected)
        assert result.provider == "langdock"


# =============================================================================
# Manager classes
# =============================================================================


class TestExportManagerDownloadGuard:
    """download_signed_csv fetches a URL taken from an API response, with redirects."""

    def _manager(self):
        from eq_chatbot_core.providers.langdock_provider import LangDockExportManager

        return LangDockExportManager(api_key="test-key")

    def test_internal_target_is_rejected(self):
        with pytest.raises(ProviderError, match="rejected"):
            self._manager().download_signed_csv("http://169.254.169.254/latest/meta-data/")

    def test_non_http_scheme_is_rejected(self):
        with pytest.raises(ProviderError, match="rejected"):
            self._manager().download_signed_csv("file:///etc/passwd")

    def test_public_url_is_fetched_and_returned(self):
        manager = self._manager()
        transport = httpx2.MockTransport(lambda req: httpx2.Response(200, text="a,b,c"))

        with patch("eq_chatbot_core.utils.url_validation.validate_url", return_value=frozenset({"93.184.216.34"})):
            with patch("eq_chatbot_core.utils.url_validation.build_validating_transport", return_value=transport):
                assert manager.download_signed_csv("https://storage.example.com/x.csv") == "a,b,c"

    def test_non_200_maps_to_provider_error(self):
        manager = self._manager()
        transport = httpx2.MockTransport(lambda req: httpx2.Response(404, text="gone"))

        with patch("eq_chatbot_core.utils.url_validation.validate_url", return_value=frozenset({"93.184.216.34"})):
            with patch("eq_chatbot_core.utils.url_validation.build_validating_transport", return_value=transport):
                with pytest.raises(ProviderError):
                    manager.download_signed_csv("https://storage.example.com/x.csv")


class TestEmptyResponseRegressions:
    """`.get(key, [{}])[0]` only defaults on a MISSING key, not an empty list.

    Both providers legitimately return an empty list — Gemini for a
    safety-blocked response — which used to raise IndexError and surface as
    ProviderError("list index out of range").
    """

    def test_google_empty_candidates_does_not_raise(self):
        provider = _provider(backend="google")
        _with_http(provider, _resp(200, {"candidates": [], "usageMetadata": {}}))

        result = provider.chat_completion([{"role": "user", "content": "hi"}])

        assert result.content == ""
        assert result.finish_reason == "STOP"

    def test_codestral_empty_choices_does_not_raise(self):
        provider = _provider(backend="codestral")
        _with_http(provider, _resp(200, {"choices": [], "usage": {}}))

        result = provider.chat_completion([{"role": "user", "content": "x"}])

        assert result.content == ""
        assert result.finish_reason == "stop"


class TestTypedErrorsSurviveTheHandler:
    """A ProviderError raised inside a backend must keep its status code.

    The blanket `except Exception` used to re-wrap it through _handle_error(),
    flattening it to a bare ProviderError with status_code=None.
    """

    def test_agent_status_code_is_preserved(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(429, {}, text="slow down"))

        with pytest.raises(ProviderError) as exc:
            provider.chat_completion([{"role": "user", "content": "hi"}])

        assert exc.value.status_code == 429

    def test_agent_stream_status_code_is_preserved(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(500, {}, text="boom"))

        with pytest.raises(ProviderError) as exc:
            list(provider.stream_completion([{"role": "user", "content": "hi"}]))

        assert exc.value.status_code == 500


# =============================================================================
# Model listing
# =============================================================================


class TestListModels:
    def test_google_returns_the_two_supported_gemini_models(self):
        provider = _provider(backend="google")

        models = provider.list_models()

        assert {m["id"] for m in models} == {"gemini-2.5-flash", "gemini-2.5-pro"}
        assert all(m["provider"] == "langdock" and m["backend"] == "google" for m in models)

    def test_codestral_listing_is_deliberately_empty(self):
        """Codestral only does FIM completion, so it is not offered for chat."""
        provider = _provider(backend="codestral")

        assert provider.list_models() == []

    def test_agent_listing_is_tagged_for_the_agent_backend(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        _with_http(provider, _resp(200, {"data": [{"id": "gpt-4o", "name": "GPT-4o"}]}))

        models = provider.list_models()

        assert [m["id"] for m in models] == ["gpt-4o"]
        assert all(m["backend"] == "agent" for m in models)

    def test_agent_listing_failure_degrades_to_empty_list(self):
        provider = _provider(backend="agent", agent_id="ag-1")
        client = MagicMock()
        client.get.side_effect = ConnectionError("gateway unreachable")
        provider._http_client = client

        assert provider.list_models() == []

    def test_openai_listing_filters_to_supported_prefixes(self):
        """Embeddings and other non-chat models must not appear."""
        provider = _provider(backend="openai")
        listing = MagicMock()
        listing.data = [
            MagicMock(id="gpt-4o", created=1, owned_by="openai"),
            MagicMock(id="o3-mini", created=1, owned_by="openai"),
            MagicMock(id="text-embedding-ada-002", created=1, owned_by="openai"),
        ]
        client = MagicMock()
        client.models.list.return_value = listing
        provider._openai_client = client

        ids = {m["id"] for m in provider.list_models()}

        assert ids == {"gpt-4o", "o3-mini"}

    def test_anthropic_listing_falls_back_to_known_models(self):
        """The gateway does not always support listing; the fallback must fill in."""
        provider = _provider(backend="anthropic")
        client = MagicMock()
        client.models.list.side_effect = AttributeError("no listing endpoint")
        provider._anthropic_client = client

        models = provider.list_models()

        assert models
        assert all("claude" in m["id"] for m in models)

    def test_models_carry_capability_constraints(self):
        provider = _provider(backend="google")

        model = provider.list_models()[0]

        assert "supports_vision" in model
        assert "context_length" in model


# =============================================================================
# Status mapping shared by the manager classes
# =============================================================================


class TestStatusErrorMapping:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (401, AuthenticationError),
            (403, AuthenticationError),
            (429, RateLimitError),
            (500, ProviderError),
            (404, ProviderError),
        ],
    )
    def test_status_codes_map_to_typed_errors(self, status, expected):
        from eq_chatbot_core.providers.langdock_provider import _map_status_error

        err = _map_status_error(status, "detail")

        assert isinstance(err, expected)
        assert err.status_code == status
        assert err.provider == "langdock"


# =============================================================================
# Export manager
# =============================================================================


def _mock_client(handler, base_url="https://api.langdock.com"):
    return httpx2.Client(transport=httpx2.MockTransport(handler), base_url=base_url)


class TestExportManager:
    def _manager(self):
        from eq_chatbot_core.providers.langdock_provider import LangDockExportManager

        return LangDockExportManager(api_key="test-key")

    def test_get_agent_unwraps_the_agent_envelope(self):
        manager = self._manager()
        manager._client = _mock_client(lambda r: httpx2.Response(200, json={"agent": {"name": "Support"}}))

        assert manager.get_agent("ag-1") == {"name": "Support"}

    def test_get_agent_passes_through_unwrapped_payload(self):
        manager = self._manager()
        manager._client = _mock_client(lambda r: httpx2.Response(200, json={"name": "Support"}))

        assert manager.get_agent("ag-1") == {"name": "Support"}

    def test_get_agent_sends_the_id_as_query_param(self):
        manager = self._manager()
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            return httpx2.Response(200, json={})

        manager._client = _mock_client(handler)
        manager.get_agent("ag-42")

        assert "agentId=ag-42" in seen["url"]

    def test_get_agent_maps_401_to_authentication_error(self):
        manager = self._manager()
        manager._client = _mock_client(lambda r: httpx2.Response(401, text="bad key"))

        with pytest.raises(AuthenticationError):
            manager.get_agent("ag-1")

    def test_export_report_rejects_unknown_report(self):
        with pytest.raises(ProviderError, match="Unknown export report"):
            self._manager().export_report("nonsense", "2026-01-01", "2026-01-02")

    def test_export_report_unwraps_data(self):
        manager = self._manager()
        manager._client = _mock_client(
            lambda r: httpx2.Response(200, json={"success": True, "data": {"downloadUrl": "https://x/y.csv"}})
        )

        assert manager.export_report("agents", "a", "b") == {"downloadUrl": "https://x/y.csv"}

    def test_export_report_sends_from_to_and_timezone(self):
        manager = self._manager()
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            return httpx2.Response(200, json={"data": {}})

        manager._client = _mock_client(handler)
        manager.export_report("users", "2026-01-01", "2026-01-31", timezone="Europe/Berlin")

        assert seen["body"]["from"] == {"date": "2026-01-01", "timezone": "Europe/Berlin"}
        assert seen["body"]["to"]["timezone"] == "Europe/Berlin"

    def test_export_report_maps_429(self):
        manager = self._manager()
        manager._client = _mock_client(lambda r: httpx2.Response(429, text="slow down"))

        with pytest.raises(RateLimitError):
            manager.export_report("agents", "a", "b")


# =============================================================================
# Knowledge manager
# =============================================================================


class TestKnowledgeManager:
    def _manager(self):
        from eq_chatbot_core.providers.langdock_provider import LangDockKnowledgeManager

        return LangDockKnowledgeManager(api_key="test-key")

    def test_list_files_targets_the_folder(self):
        manager = self._manager()
        seen = {}

        def handler(request):
            seen["path"] = request.url.path
            return httpx2.Response(200, json={"files": [{"id": "f1"}]})

        manager._client = _mock_client(handler)
        manager.list_files("folder-9")

        assert "folder-9" in seen["path"]

    def test_delete_file_returns_true_on_success(self):
        manager = self._manager()
        manager._client = _mock_client(lambda r: httpx2.Response(200, json={}))

        assert manager.delete_file("folder-9", "file-1") is True

    def test_delete_file_raises_on_error_status(self):
        manager = self._manager()
        manager._client = _mock_client(lambda r: httpx2.Response(404, json={}))

        with pytest.raises(httpx2.HTTPStatusError):
            manager.delete_file("folder-9", "file-1")

    def test_search_posts_the_query(self):
        manager = self._manager()
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            return httpx2.Response(200, json={"results": []})

        manager._client = _mock_client(handler)
        manager.search("invoice handling")

        assert "invoice handling" in json.dumps(seen["body"])
