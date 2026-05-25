"""Unit tests for GeminiLiveClient.

Uses session-scoped mock_websockets_module from conftest.py (autouse=True).
Import provider AFTER the session fixture installs the mock into sys.modules.

Coverage:
  - PROV-05: connect lifecycle, event normalization, manual turn commit, tool schema
  - PROV-06: GeminiLiveConfig defaults, GEMINI_LIVE_REALTIME_CAPABILITIES
  - PROV-07: _redact_sensitive_url strips key=, _redact_sensitive_text strips bearer token
  - QUAL-01: both endpoint modes URL shape, all wire types normalized
"""
import dataclasses

import pytest
from unittest.mock import AsyncMock, patch

from eq_chatbot_core.providers.base import ToolDefinition
from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes, RealtimeAdapterContract
from eq_chatbot_core.realtime.providers.gemini_live import (
    GEMINI_LIVE_REALTIME_CAPABILITIES,
    GeminiLiveClient,
    GeminiLiveConfig,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_FAKE_KEY = "test-api-key"
_FAKE_TOKEN = "ya29.fake-bearer-token"

# Wire frames for TestIterNormalizedEvents (no mocking of iter_events needed)
_SETUP_COMPLETE_FRAME = {"setupComplete": {}}
_SERVER_CONTENT_AUDIO_FRAME = {
    "serverContent": {
        "modelTurn": {
            "parts": [
                {"inlineData": {"mimeType": "audio/pcm", "data": "AAAA"}}
            ]
        }
    }
}
_SERVER_CONTENT_TURN_COMPLETE_FRAME = {
    "serverContent": {"turnComplete": True}
}
_TOOL_CALL_FRAME = {
    "toolCall": {
        "functionCalls": [
            {"id": "call-1", "name": "my_fn", "args": {"x": 1}}
        ]
    }
}
_TOOL_CALL_CANCELLATION_FRAME = {"toolCallCancellation": {"ids": ["call-1"]}}
_ERROR_FRAME = {"error": {"code": 500, "message": "internal error"}}
_UNKNOWN_FRAME = {"someUnknownKey": {"data": "xyz"}}


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_developer_client() -> GeminiLiveClient:
    """Construct a developer-mode client with a fake API key (no real network I/O)."""
    config = GeminiLiveConfig(api_key=_FAKE_KEY, mode="developer")
    return GeminiLiveClient(config)


def _make_vertex_client() -> GeminiLiveClient:
    """Construct a vertex-mode client with a fake bearer token."""
    config = GeminiLiveConfig(
        access_token=_FAKE_TOKEN,
        project="my-gcp-project",
        region="europe-west4",
        mode="vertex",
    )
    return GeminiLiveClient(config)


# ===========================================================================
# TestGeminiLiveConfig
# ===========================================================================


class TestGeminiLiveConfig:
    """PROV-06: GeminiLiveConfig is a frozen+slots dataclass with correct defaults."""

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """Mutating a frozen dataclass must raise FrozenInstanceError (PROV-06)."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            config.api_key = "new-value"  # type: ignore[misc]

    @pytest.mark.unit
    def test_has_dataclass_fields(self) -> None:
        """GeminiLiveConfig must be a proper dataclass (slots present via dataclasses.fields)."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY)
        fields = {f.name for f in dataclasses.fields(config)}
        assert "api_key" in fields
        assert "access_token" in fields
        assert "model" in fields
        assert "mode" in fields

    @pytest.mark.unit
    def test_default_model_contains_gemini(self) -> None:
        """Default model must contain 'gemini' and NOT contain '2.0-flash' (CRITICAL ALIAS)."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY)
        assert "gemini" in config.model
        assert "2.0-flash" not in config.model

    @pytest.mark.unit
    def test_default_model_is_verified_alias(self) -> None:
        """Default model must be exactly 'gemini-3.1-flash-live-preview' (verified 2026-05-25)."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY)
        assert config.model == "gemini-3.1-flash-live-preview"

    @pytest.mark.unit
    def test_default_mode_is_developer(self) -> None:
        """mode defaults to 'developer'."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY)
        assert config.mode == "developer"

    @pytest.mark.unit
    def test_default_region_is_europe_west4(self) -> None:
        """region defaults to 'europe-west4' (DSGVO-compliant EU endpoint)."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY)
        assert config.region == "europe-west4"

    @pytest.mark.unit
    def test_custom_fields(self) -> None:
        """All fields set via constructor are stored correctly."""
        config = GeminiLiveConfig(
            access_token=_FAKE_TOKEN,
            project="my-project",
            region="europe-west1",
            mode="vertex",
            model="gemini-3.1-flash-live-preview",
            instructions="Be helpful",
        )
        assert config.access_token == _FAKE_TOKEN
        assert config.project == "my-project"
        assert config.region == "europe-west1"
        assert config.mode == "vertex"
        assert config.instructions == "Be helpful"


# ===========================================================================
# TestCapabilities
# ===========================================================================


class TestCapabilities:
    """PROV-06: GEMINI_LIVE_REALTIME_CAPABILITIES values match handoff spec."""

    @pytest.mark.unit
    def test_server_vad_is_false(self) -> None:
        """Gemini has NO server VAD — server_vad must be False (PROV-06)."""
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.server_vad is False

    @pytest.mark.unit
    def test_manual_turn_commit_required_is_true(self) -> None:
        """Gemini always requires manual turn commit — manual_turn_commit_required must be True."""
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.manual_turn_commit_required is True

    @pytest.mark.unit
    def test_tool_result_mode_is_provider_call_id(self) -> None:
        """Tool result submission uses 'provider_call_id' schema (exact string)."""
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.tool_result_submission_mode == "provider_call_id"

    @pytest.mark.unit
    def test_all_streaming_flags(self) -> None:
        """Both streaming_audio_input and streaming_audio_output must be True."""
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.streaming_audio_input is True
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.streaming_audio_output is True

    @pytest.mark.unit
    def test_tool_calling_true(self) -> None:
        """Gemini Live provider supports tool calling."""
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.tool_calling is True

    @pytest.mark.unit
    def test_voice_selection_false(self) -> None:
        """Gemini Live does not expose voice selection via this API."""
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.voice_selection is False

    @pytest.mark.unit
    def test_interruption_cancel_false(self) -> None:
        """cancel_response is a no-op — interruption_cancel must be False."""
        assert GEMINI_LIVE_REALTIME_CAPABILITIES.interruption_cancel is False


# ===========================================================================
# TestConstructorValidation
# ===========================================================================


class TestConstructorValidation:
    """D-06: fail fast with library-native exception before any network I/O."""

    @pytest.mark.unit
    def test_empty_api_key_for_developer_raises_value_error(self) -> None:
        """Empty api_key in developer mode must raise ValueError (D-06)."""
        config = GeminiLiveConfig(api_key="", mode="developer")
        with pytest.raises(ValueError, match="api_key"):
            GeminiLiveClient(config)

    @pytest.mark.unit
    def test_whitespace_api_key_for_developer_raises_value_error(self) -> None:
        """Whitespace-only api_key in developer mode must raise ValueError (D-06)."""
        config = GeminiLiveConfig(api_key="   ", mode="developer")
        with pytest.raises(ValueError, match="api_key"):
            GeminiLiveClient(config)

    @pytest.mark.unit
    def test_empty_access_token_for_vertex_raises_value_error(self) -> None:
        """Empty access_token in vertex mode must raise ValueError (D-06)."""
        config = GeminiLiveConfig(access_token="", mode="vertex")
        with pytest.raises(ValueError, match="access_token"):
            GeminiLiveClient(config)

    @pytest.mark.unit
    def test_whitespace_access_token_for_vertex_raises_value_error(self) -> None:
        """Whitespace-only access_token in vertex mode must raise ValueError (D-06)."""
        config = GeminiLiveConfig(access_token="   ", mode="vertex")
        with pytest.raises(ValueError, match="access_token"):
            GeminiLiveClient(config)

    @pytest.mark.unit
    def test_unknown_mode_raises_value_error(self) -> None:
        """Unknown mode value must raise ValueError (D-06)."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY, mode="unknown")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="mode"):
            GeminiLiveClient(config)

    @pytest.mark.unit
    def test_empty_model_raises_value_error(self) -> None:
        """Empty model must raise ValueError immediately (D-06)."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY, model="")
        with pytest.raises(ValueError, match="model"):
            GeminiLiveClient(config)

    @pytest.mark.unit
    def test_valid_developer_config_does_not_raise(self) -> None:
        """Valid developer config does not raise on construction."""
        _make_developer_client()  # should not raise

    @pytest.mark.unit
    def test_valid_vertex_config_does_not_raise(self) -> None:
        """Valid vertex config does not raise on construction."""
        _make_vertex_client()  # should not raise


# ===========================================================================
# TestEndpointModes
# ===========================================================================


class TestEndpointModes:
    """QUAL-01: Dual-endpoint URL and header shape verification."""

    @pytest.mark.unit
    def test_developer_mode_url_contains_key_param(self) -> None:
        """Developer mode: URL must embed ?key= query param."""
        client = _make_developer_client()
        assert f"key={_FAKE_KEY}" in client._url

    @pytest.mark.unit
    def test_developer_mode_has_no_authorization_header(self) -> None:
        """Developer mode: no Authorization header (key is in URL)."""
        client = _make_developer_client()
        assert "Authorization" not in client._headers

    @pytest.mark.unit
    def test_developer_mode_url_is_wss(self) -> None:
        """Developer mode URL must use wss:// scheme."""
        client = _make_developer_client()
        assert client._url.startswith("wss://")

    @pytest.mark.unit
    def test_developer_mode_url_contains_generativelanguage(self) -> None:
        """Developer mode URL must target generativelanguage.googleapis.com."""
        client = _make_developer_client()
        assert "generativelanguage.googleapis.com" in client._url

    @pytest.mark.unit
    def test_vertex_mode_url_contains_aiplatform(self) -> None:
        """Vertex mode: URL must use {region}-aiplatform.googleapis.com."""
        client = _make_vertex_client()
        assert "aiplatform.googleapis.com" in client._url

    @pytest.mark.unit
    def test_vertex_mode_url_contains_region(self) -> None:
        """Vertex mode: URL must contain configured region."""
        client = _make_vertex_client()
        assert "europe-west4" in client._url

    @pytest.mark.unit
    def test_vertex_mode_has_authorization_header(self) -> None:
        """Vertex mode: Authorization header must contain Bearer token."""
        client = _make_vertex_client()
        assert client._headers.get("Authorization") == f"Bearer {_FAKE_TOKEN}"

    @pytest.mark.unit
    def test_vertex_mode_has_project_header(self) -> None:
        """Vertex mode: x-goog-user-project header must be set."""
        client = _make_vertex_client()
        assert client._headers.get("x-goog-user-project") == "my-gcp-project"

    @pytest.mark.unit
    def test_vertex_mode_url_does_not_contain_key_param(self) -> None:
        """Vertex mode: URL must NOT embed api_key."""
        client = _make_vertex_client()
        assert "key=" not in client._url


# ===========================================================================
# TestConnectionErrorEndpoint
# ===========================================================================


class TestConnectionErrorEndpoint:
    """PROV-07: _connection_error_endpoint must never expose api_key or access_token."""

    @pytest.mark.unit
    def test_developer_endpoint_does_not_contain_api_key(self) -> None:
        """Developer mode: API key must NEVER appear in connection error endpoint (PROV-07)."""
        client = _make_developer_client()
        endpoint = client._connection_error_endpoint()
        assert _FAKE_KEY not in endpoint

    @pytest.mark.unit
    def test_vertex_endpoint_does_not_contain_access_token(self) -> None:
        """Vertex mode: bearer token must NEVER appear in connection error endpoint (PROV-07)."""
        client = _make_vertex_client()
        endpoint = client._connection_error_endpoint()
        assert _FAKE_TOKEN not in endpoint

    @pytest.mark.unit
    def test_developer_endpoint_is_wss_url(self) -> None:
        """Developer mode: error endpoint must start with wss://."""
        client = _make_developer_client()
        assert client._connection_error_endpoint().startswith("wss://")

    @pytest.mark.unit
    def test_vertex_endpoint_is_wss_url(self) -> None:
        """Vertex mode: error endpoint must start with wss://."""
        client = _make_vertex_client()
        assert client._connection_error_endpoint().startswith("wss://")


# ===========================================================================
# TestRedaction
# ===========================================================================


class TestRedaction:
    """PROV-07 / SC-2: _redact_sensitive_url and _redact_sensitive_text redaction."""

    @pytest.mark.unit
    def test_redact_key_param_from_developer_url(self) -> None:
        """_redact_sensitive_url must replace key= value with [REDACTED] (SC-2)."""
        client = _make_developer_client()
        redacted = GeminiLiveClient._redact_sensitive_url(client._url)
        assert _FAKE_KEY not in redacted, "api_key must not appear in redacted URL"
        assert "key=[REDACTED]" in redacted, "'key=[REDACTED]' must be present"

    @pytest.mark.unit
    def test_redact_url_without_key_param_unchanged(self) -> None:
        """_redact_sensitive_url on vertex URL (no key param) must return URL unchanged."""
        client = _make_vertex_client()
        redacted = GeminiLiveClient._redact_sensitive_url(client._url)
        # Vertex URL has no ?key= param — should be identical
        assert redacted == client._url

    @pytest.mark.unit
    def test_redact_bearer_token_from_error_text(self) -> None:
        """_redact_sensitive_text must remove raw bearer token from error strings (SC-2 Vertex)."""
        client = _make_vertex_client()
        error_text = f"Connection failed: Authorization: Bearer {_FAKE_TOKEN}"
        result = client._redact_sensitive_text(error_text)
        assert _FAKE_TOKEN not in result, "bearer token must be stripped from error text"

    @pytest.mark.unit
    def test_redact_api_key_from_error_text(self) -> None:
        """_redact_sensitive_text must remove raw api_key from error strings (SC-2 Developer)."""
        client = _make_developer_client()
        error_text = f"Connection rejected. URL: wss://example.com/ws?key={_FAKE_KEY}"
        result = client._redact_sensitive_text(error_text)
        assert _FAKE_KEY not in result, "api_key must be stripped from error text"

    @pytest.mark.unit
    def test_redact_empty_text_returns_empty(self) -> None:
        """_redact_sensitive_text with empty string returns empty string."""
        client = _make_developer_client()
        assert client._redact_sensitive_text("") == ""


# ===========================================================================
# TestSetupEvent
# ===========================================================================


class TestSetupEvent:
    """_build_setup_event: models/ prefix handling and systemInstruction inclusion."""

    @pytest.mark.unit
    def test_build_setup_event_adds_models_prefix(self) -> None:
        """_build_setup_event must prepend 'models/' to bare model ID (Pitfall 4)."""
        client = _make_developer_client()
        event = client._build_setup_event(instructions=None, tools=None)
        model_value = event["setup"]["model"]
        assert model_value.startswith("models/"), f"Expected 'models/' prefix, got: {model_value}"
        assert "models/models/" not in model_value, "Must not double-prefix"

    @pytest.mark.unit
    def test_build_setup_event_does_not_double_prefix(self) -> None:
        """_build_setup_event must NOT add second 'models/' if already present."""
        config = GeminiLiveConfig(api_key=_FAKE_KEY, model="models/gemini-3.1-flash-live-preview")
        client = GeminiLiveClient(config)
        event = client._build_setup_event(instructions=None, tools=None)
        model_value = event["setup"]["model"]
        assert model_value.count("models/") == 1, f"Must not double-prefix, got: {model_value}"

    @pytest.mark.unit
    def test_build_setup_event_includes_system_instruction(self) -> None:
        """systemInstruction is included in setup when instructions are provided."""
        client = _make_developer_client()
        event = client._build_setup_event(instructions="Be concise.", tools=None)
        assert "systemInstruction" in event["setup"]
        parts = event["setup"]["systemInstruction"]["parts"]
        assert any(p.get("text") == "Be concise." for p in parts)

    @pytest.mark.unit
    def test_build_setup_event_no_system_instruction_when_none(self) -> None:
        """systemInstruction must NOT be present when instructions=None."""
        client = _make_developer_client()
        event = client._build_setup_event(instructions=None, tools=None)
        assert "systemInstruction" not in event["setup"]

    @pytest.mark.unit
    def test_build_setup_event_top_level_key_is_setup(self) -> None:
        """Top-level key of setup event must be 'setup'."""
        client = _make_developer_client()
        event = client._build_setup_event(instructions=None, tools=None)
        assert "setup" in event

    @pytest.mark.unit
    def test_build_setup_event_contains_model(self) -> None:
        """Setup event must include 'model' field under setup."""
        client = _make_developer_client()
        event = client._build_setup_event(instructions=None, tools=None)
        assert "model" in event["setup"]


# ===========================================================================
# TestToolSchemaConversion
# ===========================================================================


class TestToolSchemaConversion:
    """_to_gemini_function_declaration and _to_gemini_schema behavior."""

    @pytest.mark.unit
    def test_tool_definition_uses_parameters_field(self) -> None:
        """_to_gemini_function_declaration uses tool.parameters (ADAPTATION B — not input_schema)."""
        tool = ToolDefinition(
            name="my_fn",
            description="Does something useful",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
        )
        result = GeminiLiveClient._to_gemini_function_declaration(tool)
        assert result["name"] == "my_fn"
        assert result["description"] == "Does something useful"
        # parameters field must be present (non-empty object schema not stripped)
        assert "parameters" in result

    @pytest.mark.unit
    def test_to_gemini_schema_strips_additional_properties(self) -> None:
        """_to_gemini_schema must strip 'additionalProperties' key."""
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "additionalProperties": False,
        }
        result = GeminiLiveClient._to_gemini_schema(schema)
        assert result is not None
        assert "additionalProperties" not in result

    @pytest.mark.unit
    def test_to_gemini_schema_empty_object_returns_none(self) -> None:
        """_to_gemini_schema returns None for empty object schema (no properties)."""
        schema = {"type": "object"}
        result = GeminiLiveClient._to_gemini_schema(schema)
        assert result is None

    @pytest.mark.unit
    def test_to_gemini_schema_none_input_returns_none(self) -> None:
        """_to_gemini_schema returns None when input is None."""
        assert GeminiLiveClient._to_gemini_schema(None) is None

    @pytest.mark.unit
    def test_dict_tool_passthrough(self) -> None:
        """Raw dict tool is passed through as dict copy."""
        raw = {"name": "raw_fn", "description": "raw", "custom": 42}
        result = GeminiLiveClient._to_gemini_function_declaration(raw)
        assert result["name"] == "raw_fn"
        assert result["custom"] == 42


# ===========================================================================
# TestIterNormalizedEvents
# ===========================================================================


class TestIterNormalizedEvents:
    """QUAL-01: _to_normalized_runtime_events routes all Gemini wire types correctly."""

    @pytest.mark.unit
    def test_setup_complete_maps_to_session_ready(self) -> None:
        """setupComplete → SESSION_READY (QUAL-01)."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_SETUP_COMPLETE_FRAME)
        assert len(results) == 1
        assert results[0]["type"] == NormalizedRealtimeEventTypes.SESSION_READY

    @pytest.mark.unit
    def test_server_content_audio_maps_to_audio_delta(self) -> None:
        """serverContent with modelTurn audio data → RESPONSE_AUDIO_DELTA."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_SERVER_CONTENT_AUDIO_FRAME)
        assert len(results) >= 1
        assert results[0]["type"] == NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA

    @pytest.mark.unit
    def test_server_content_turn_complete_maps_to_response_done(self) -> None:
        """serverContent with turnComplete → RESPONSE_DONE."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_SERVER_CONTENT_TURN_COMPLETE_FRAME)
        assert any(r["type"] == NormalizedRealtimeEventTypes.RESPONSE_DONE for r in results)

    @pytest.mark.unit
    def test_tool_call_maps_to_tool_call_completed(self) -> None:
        """toolCall → TOOL_CALL_COMPLETED (QUAL-01)."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_TOOL_CALL_FRAME)
        assert len(results) == 1
        assert results[0]["type"] == NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED

    @pytest.mark.unit
    def test_tool_call_payload_has_call_id_and_name(self) -> None:
        """toolCall payload must contain call_id, name, arguments."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_TOOL_CALL_FRAME)
        payload = results[0]["payload"]
        assert payload["call_id"] == "call-1"
        assert payload["name"] == "my_fn"
        assert "arguments" in payload

    @pytest.mark.unit
    def test_tool_call_cancellation_maps_to_tool_call_cancelled(self) -> None:
        """toolCallCancellation → TOOL_CALL_CANCELLED (QUAL-01)."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_TOOL_CALL_CANCELLATION_FRAME)
        assert len(results) == 1
        assert results[0]["type"] == NormalizedRealtimeEventTypes.TOOL_CALL_CANCELLED

    @pytest.mark.unit
    def test_error_frame_maps_to_error(self) -> None:
        """error wire frame → ERROR (QUAL-01)."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_ERROR_FRAME)
        assert len(results) == 1
        assert results[0]["type"] == NormalizedRealtimeEventTypes.ERROR

    @pytest.mark.unit
    def test_unknown_key_maps_to_unhandled(self) -> None:
        """Unknown wire frame key → UNHANDLED (QUAL-01)."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_UNKNOWN_FRAME)
        assert len(results) == 1
        assert results[0]["type"] == NormalizedRealtimeEventTypes.UNHANDLED

    @pytest.mark.unit
    def test_all_results_have_source_and_raw_fields(self) -> None:
        """NormalizedRealtimeEventFull includes 'source' and 'raw' metadata."""
        client = _make_developer_client()
        results = client._to_normalized_runtime_events(_SETUP_COMPLETE_FRAME)
        assert len(results) >= 1
        for r in results:
            assert "source" in r
            assert "raw" in r


# ===========================================================================
# TestManualTurnCommit
# ===========================================================================


class TestManualTurnCommit:
    """commit_client_turn sends correct JSON shape (realtimeInput.audioStreamEnd: True)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_commit_client_turn_sends_audio_stream_end(self) -> None:
        """commit_client_turn must send realtimeInput.audioStreamEnd: True."""
        client = _make_developer_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.commit_client_turn()
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args[0][0]
            assert "realtimeInput" in call_args
            assert call_args["realtimeInput"]["audioStreamEnd"] is True


# ===========================================================================
# TestToolResult
# ===========================================================================


class TestToolResult:
    """submit_tool_result sends toolResponse.functionResponses with correct shape."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_tool_result_sends_correct_shape(self) -> None:
        """submit_tool_result must send toolResponse.functionResponses list."""
        client = _make_developer_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="call-1", output='{"result": "ok"}')
            mock_send.assert_awaited_once()
            payload = mock_send.call_args[0][0]
            assert "toolResponse" in payload
            responses = payload["toolResponse"]["functionResponses"]
            assert len(responses) == 1
            assert responses[0]["id"] == "call-1"
            assert "response" in responses[0]
            assert "output" in responses[0]["response"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_tool_result_decodes_json_output(self) -> None:
        """submit_tool_result must JSON-decode valid output string into dict."""
        client = _make_developer_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="c1", output='{"key": "value"}')
            payload = mock_send.call_args[0][0]
            output_value = payload["toolResponse"]["functionResponses"][0]["response"]["output"]
            assert output_value == {"key": "value"}, "Valid JSON output must be decoded to dict"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_tool_result_fallback_for_malformed_json(self) -> None:
        """submit_tool_result falls back to dict wrap when output is not valid JSON."""
        client = _make_developer_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="c2", output="not-json")
            payload = mock_send.call_args[0][0]
            output_value = payload["toolResponse"]["functionResponses"][0]["response"]["output"]
            # Malformed JSON → fallback: {"output": raw_string}
            assert output_value == {"output": "not-json"}, "Malformed JSON must be wrapped"


# ===========================================================================
# TestConnectLifecycle
# ===========================================================================


class TestConnectLifecycle:
    """PROV-05: _on_connected is a logging-only no-op, NOT initialize_session (Pitfall 5)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_on_connected_does_not_call_initialize_session(self) -> None:
        """_on_connected() must NOT await initialize_session() (Gemini anti-pattern / PITFALL-05)."""
        client = _make_developer_client()
        with patch.object(client, "initialize_session", new_callable=AsyncMock) as mock_init:
            await client._on_connected()
            mock_init.assert_not_awaited()  # Opposite of OpenAI

    @pytest.mark.unit
    def test_implements_contract(self) -> None:
        """GeminiLiveClient must satisfy the RealtimeAdapterContract protocol."""
        client = _make_developer_client()
        assert isinstance(client, RealtimeAdapterContract), (
            "GeminiLiveClient must implement RealtimeAdapterContract (PROV-05)"
        )
