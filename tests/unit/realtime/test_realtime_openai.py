"""Unit tests for OpenAIRealtimeClient.

Uses session-scoped mock_websockets_module from conftest.py (autouse=True).
Import provider AFTER the session fixture installs the mock into sys.modules.

Coverage:
  - PROV-01: connect lifecycle, event normalization, close lifecycle
  - PROV-02: OpenAIRealtimeConfig defaults, OPENAI_REALTIME_CAPABILITIES
  - PROV-03: PITFALL-28 VAD session payload (turn_detection present/absent)
  - PROV-04: model default "gpt-realtime" exact string
  - QUAL-01: tool call payload shape (PITFALL-05 item sub-dict + top-level fields)
"""
import dataclasses

import pytest

from eq_chatbot_core.providers.base import ToolDefinition
from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes, RealtimeAdapterContract
from eq_chatbot_core.realtime.providers.openai import (
    OPENAI_REALTIME_CAPABILITIES,
    OpenAIRealtimeClient,
    OpenAIRealtimeConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_KEY = "test-key"


def _make_client(include_turn_detection: bool = True) -> OpenAIRealtimeClient:
    """Construct a client with a fake API key (no real network I/O)."""
    config = OpenAIRealtimeConfig(
        api_key=_FAKE_KEY,
        include_turn_detection=include_turn_detection,
    )
    return OpenAIRealtimeClient(config)


# ===========================================================================
# TestOpenAIRealtimeConfig
# ===========================================================================


class TestOpenAIRealtimeConfig:
    """PROV-02: OpenAIRealtimeConfig is a frozen+slots dataclass with correct defaults."""

    def test_frozen(self) -> None:
        """Mutating a frozen dataclass must raise FrozenInstanceError (PROV-02)."""
        config = OpenAIRealtimeConfig(api_key=_FAKE_KEY)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            config.api_key = "new-value"

    def test_default_model_is_gpt_realtime(self) -> None:
        """Exact string 'gpt-realtime' — PROV-04 model default assertion."""
        config = OpenAIRealtimeConfig(api_key=_FAKE_KEY)
        assert config.model == "gpt-realtime"

    def test_default_voice_is_ash(self) -> None:
        """Default voice must be exact string 'ash'."""
        config = OpenAIRealtimeConfig(api_key=_FAKE_KEY)
        assert config.voice == "ash"

    def test_default_include_turn_detection_true(self) -> None:
        """include_turn_detection defaults to True (PITFALL-28 session-level opt-in)."""
        config = OpenAIRealtimeConfig(api_key=_FAKE_KEY)
        assert config.include_turn_detection is True

    def test_default_instructions_is_none(self) -> None:
        """instructions defaults to None."""
        config = OpenAIRealtimeConfig(api_key=_FAKE_KEY)
        assert config.instructions is None

    def test_custom_fields(self) -> None:
        """All fields set via constructor are stored correctly."""
        config = OpenAIRealtimeConfig(
            api_key="sk-custom",
            model="gpt-realtime-2025-08-28",
            voice="coral",
            instructions="Be concise",
            include_turn_detection=False,
        )
        assert config.api_key == "sk-custom"
        assert config.model == "gpt-realtime-2025-08-28"
        assert config.voice == "coral"
        assert config.instructions == "Be concise"
        assert config.include_turn_detection is False


# ===========================================================================
# TestCapabilities
# ===========================================================================


class TestCapabilities:
    """PROV-02: OPENAI_REALTIME_CAPABILITIES values match handoff spec."""

    def test_server_vad_true(self) -> None:
        """Provider SUPPORTS server VAD (hardware capability, static — PITFALL-28)."""
        assert OPENAI_REALTIME_CAPABILITIES.server_vad is True

    def test_manual_turn_commit_required_false(self) -> None:
        """When VAD is active (default), manual turn commit is not required."""
        assert OPENAI_REALTIME_CAPABILITIES.manual_turn_commit_required is False

    def test_tool_result_mode_conversation_item(self) -> None:
        """Tool result submission uses 'conversation_item' schema (exact string)."""
        assert OPENAI_REALTIME_CAPABILITIES.tool_result_submission_mode == "conversation_item"

    def test_all_streaming_flags(self) -> None:
        """Both streaming_audio_input and streaming_audio_output must be True."""
        assert OPENAI_REALTIME_CAPABILITIES.streaming_audio_input is True
        assert OPENAI_REALTIME_CAPABILITIES.streaming_audio_output is True

    def test_tool_calling_true(self) -> None:
        """OpenAI Realtime provider supports tool calling."""
        assert OPENAI_REALTIME_CAPABILITIES.tool_calling is True

    def test_voice_selection_true(self) -> None:
        assert OPENAI_REALTIME_CAPABILITIES.voice_selection is True

    def test_interruption_cancel_true(self) -> None:
        assert OPENAI_REALTIME_CAPABILITIES.interruption_cancel is True

    def test_startup_validation_true(self) -> None:
        assert OPENAI_REALTIME_CAPABILITIES.startup_validation is True


# ===========================================================================
# TestConstructorValidation
# ===========================================================================


class TestConstructorValidation:
    """D-03: fail fast with library-native exception before any network I/O."""

    def test_empty_api_key_raises_value_error(self) -> None:
        """Empty api_key must raise ValueError immediately (D-03)."""
        config = OpenAIRealtimeConfig(api_key="")
        with pytest.raises(ValueError, match="api_key"):
            OpenAIRealtimeClient(config)

    def test_whitespace_api_key_raises_value_error(self) -> None:
        """Whitespace-only api_key must raise ValueError (D-03)."""
        config = OpenAIRealtimeConfig(api_key="   ")
        with pytest.raises(ValueError, match="api_key"):
            OpenAIRealtimeClient(config)

    def test_empty_model_raises_value_error(self) -> None:
        """Empty model must raise ValueError immediately (D-03)."""
        config = OpenAIRealtimeConfig(api_key=_FAKE_KEY, model="")
        with pytest.raises(ValueError, match="model"):
            OpenAIRealtimeClient(config)

    def test_whitespace_model_raises_value_error(self) -> None:
        """Whitespace-only model must raise ValueError (D-03)."""
        config = OpenAIRealtimeConfig(api_key=_FAKE_KEY, model="  ")
        with pytest.raises(ValueError, match="model"):
            OpenAIRealtimeClient(config)

    def test_valid_key_and_model_does_not_raise(self) -> None:
        """Valid api_key and model do not raise on construction."""
        _make_client()  # should not raise


# ===========================================================================
# TestVADSessionPayload
# ===========================================================================


class TestVADSessionPayload:
    """PROV-03 / PITFALL-28: VAD turn_detection key present when True, absent when False."""

    def test_turn_detection_present_when_include_true(self) -> None:
        """include_turn_detection=True must include 'turn_detection' in audio.input."""
        client = _make_client(include_turn_detection=True)
        event = client._build_session_update_event(
            instructions=None,
            voice=None,
            tools=None,
        )
        audio_input = event["session"]["audio"]["input"]
        assert "turn_detection" in audio_input, (
            "turn_detection must be present when include_turn_detection=True (PITFALL-28)"
        )

    def test_turn_detection_absent_when_include_false(self) -> None:
        """include_turn_detection=False must NOT include 'turn_detection' in audio.input."""
        client = _make_client(include_turn_detection=False)
        event = client._build_session_update_event(
            instructions=None,
            voice=None,
            tools=None,
        )
        audio_input = event["session"]["audio"]["input"]
        assert "turn_detection" not in audio_input, (
            "turn_detection must be absent when include_turn_detection=False (PITFALL-28)"
        )

    def test_turn_detection_type_is_server_vad(self) -> None:
        """When present, turn_detection.type must be 'server_vad'."""
        client = _make_client(include_turn_detection=True)
        event = client._build_session_update_event(
            instructions=None,
            voice=None,
            tools=None,
        )
        turn = event["session"]["audio"]["input"]["turn_detection"]
        assert turn["type"] == "server_vad"
        assert turn["create_response"] is True
        assert turn["interrupt_response"] is True

    def test_session_update_event_type(self) -> None:
        """Top-level event type must be 'session.update'."""
        client = _make_client()
        event = client._build_session_update_event(
            instructions=None,
            voice=None,
            tools=None,
        )
        assert event["type"] == "session.update"

    def test_session_model_matches_config(self) -> None:
        """session.model must match config.model."""
        client = _make_client()
        event = client._build_session_update_event(
            instructions=None,
            voice=None,
            tools=None,
        )
        assert event["session"]["model"] == "gpt-realtime"


# ===========================================================================
# TestConnectionErrorEndpoint
# ===========================================================================


class TestConnectionErrorEndpoint:
    """Security: _connection_error_endpoint must not expose the API key."""

    def test_does_not_contain_api_key(self) -> None:
        """API key must NEVER appear in the error endpoint URL (PITFALL-04 / T-02T-01)."""
        config = OpenAIRealtimeConfig(api_key="secret")
        client = OpenAIRealtimeClient(config)
        endpoint = client._connection_error_endpoint()
        assert "secret" not in endpoint, (
            "API key must be stripped from connection error endpoint (security requirement)"
        )

    def test_contains_model(self) -> None:
        """Error endpoint must include the model name (for diagnostics)."""
        client = _make_client()
        endpoint = client._connection_error_endpoint()
        assert "gpt-realtime" in endpoint

    def test_is_wss_url(self) -> None:
        """Error endpoint must be a valid WSS URL."""
        client = _make_client()
        endpoint = client._connection_error_endpoint()
        assert endpoint.startswith("wss://")


# ===========================================================================
# TestNormalizeTools
# ===========================================================================


class TestNormalizeTools:
    """_normalize_tools converts ToolDefinition/dict/None to OpenAI wire format."""

    def test_tool_definition_conversion(self) -> None:
        """ToolDefinition instance is converted to OpenAI function dict with required keys."""
        tool = ToolDefinition(
            name="my_fn",
            description="Does something useful",
            parameters={"type": "object", "properties": {}},
            strict=True,
        )
        result = OpenAIRealtimeClient._normalize_tools([tool])
        assert result is not None
        assert len(result) == 1
        normalized = result[0]
        assert normalized["type"] == "function"
        assert normalized["name"] == "my_fn"
        assert normalized["description"] == "Does something useful"
        assert normalized["parameters"] == {"type": "object", "properties": {}}
        assert normalized["strict"] is True

    def test_dict_passthrough(self) -> None:
        """Raw dict is passed through unchanged (as a copy)."""
        raw = {"type": "function", "name": "raw_fn", "custom_field": 42}
        result = OpenAIRealtimeClient._normalize_tools([raw])
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "raw_fn"
        assert result[0]["custom_field"] == 42

    def test_none_returns_none(self) -> None:
        """None input returns None (no tools registered)."""
        assert OpenAIRealtimeClient._normalize_tools(None) is None

    def test_empty_list_returns_none(self) -> None:
        """Empty list returns None (same semantic as no tools)."""
        assert OpenAIRealtimeClient._normalize_tools([]) is None

    def test_mixed_list(self) -> None:
        """List with both ToolDefinition and dict items is handled correctly."""
        tool = ToolDefinition(
            name="td_fn",
            description="From ToolDefinition",
            parameters={},
            strict=False,
        )
        raw = {"type": "function", "name": "raw_fn"}
        result = OpenAIRealtimeClient._normalize_tools([tool, raw])
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "td_fn"
        assert result[1]["name"] == "raw_fn"


# ===========================================================================
# TestIterNormalizedEvents
# ===========================================================================


class TestIterNormalizedEvents:
    """PROV-01: _to_normalized_runtime_event routes all wire types to correct constants.

    Called directly (no WS needed) — validates the Stage 1+2 pipeline.
    """

    def test_session_created_maps_to_session_ready(self) -> None:
        """session.created → SESSION_READY (PROV-01)."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "session.created"})
        assert result["type"] == NormalizedRealtimeEventTypes.SESSION_READY

    def test_session_updated_maps_to_session_ready(self) -> None:
        """session.updated also maps to SESSION_READY (PROV-01)."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "session.updated"})
        assert result["type"] == NormalizedRealtimeEventTypes.SESSION_READY

    def test_response_audio_delta_normalized(self) -> None:
        """response.audio.delta → RESPONSE_AUDIO_DELTA via Stage 1 alias + Stage 2 routing."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "response.audio.delta"})
        assert result["type"] == NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA

    def test_response_audio_done_normalized(self) -> None:
        """response.audio.done → RESPONSE_AUDIO_DONE via alias normalization."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "response.audio.done"})
        assert result["type"] == NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DONE

    def test_response_done_normalized(self) -> None:
        """response.done → RESPONSE_DONE."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "response.done"})
        assert result["type"] == NormalizedRealtimeEventTypes.RESPONSE_DONE

    def test_input_speech_started_normalized(self) -> None:
        """input_audio_buffer.speech_started → INPUT_SPEECH_STARTED."""
        client = _make_client()
        result = client._to_normalized_runtime_event(
            {"type": "input_audio_buffer.speech_started"}
        )
        assert result["type"] == NormalizedRealtimeEventTypes.INPUT_SPEECH_STARTED

    def test_input_speech_stopped_normalized(self) -> None:
        """input_audio_buffer.speech_stopped → INPUT_SPEECH_STOPPED."""
        client = _make_client()
        result = client._to_normalized_runtime_event(
            {"type": "input_audio_buffer.speech_stopped"}
        )
        assert result["type"] == NormalizedRealtimeEventTypes.INPUT_SPEECH_STOPPED

    def test_response_created_normalized(self) -> None:
        """response.created → RESPONSE_CREATED."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "response.created"})
        assert result["type"] == NormalizedRealtimeEventTypes.RESPONSE_CREATED

    def test_input_audio_committed_normalized(self) -> None:
        """input_audio_buffer.committed → INPUT_AUDIO_COMMITTED."""
        client = _make_client()
        result = client._to_normalized_runtime_event(
            {"type": "input_audio_buffer.committed"}
        )
        assert result["type"] == NormalizedRealtimeEventTypes.INPUT_AUDIO_COMMITTED

    def test_error_normalized(self) -> None:
        """error → ERROR."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "error", "message": "oops"})
        assert result["type"] == NormalizedRealtimeEventTypes.ERROR

    def test_unknown_event_normalized(self) -> None:
        """Unknown wire type → UNHANDLED."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "some.unknown.event"})
        assert result["type"] == NormalizedRealtimeEventTypes.UNHANDLED

    def test_missing_type_normalized(self) -> None:
        """Event with no 'type' key → UNHANDLED (missing_type source)."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"data": "no-type-key"})
        assert result["type"] == NormalizedRealtimeEventTypes.UNHANDLED

    def test_raw_and_source_fields_present(self) -> None:
        """NormalizedRealtimeEventFull includes 'source' and 'raw' metadata fields."""
        client = _make_client()
        result = client._to_normalized_runtime_event({"type": "response.done"})
        assert "source" in result
        assert "raw" in result


# ===========================================================================
# TestToolCallNormalization
# ===========================================================================


class TestToolCallNormalization:
    """QUAL-01 / PITFALL-05: response.function_call_arguments.done → TOOL_CALL_COMPLETED
    with custom payload shape (item sub-dict + top-level fields for GlassAgents bridge).
    """

    _TOOL_CALL_EVENT = {
        "type": "response.function_call_arguments.done",
        "item_id": "item-1",
        "call_id": "call-1",
        "name": "my_fn",
        "arguments": "{}",
        "response_id": "resp-1",
    }

    def test_function_call_arguments_done_maps_to_tool_call_completed(self) -> None:
        """response.function_call_arguments.done → TOOL_CALL_COMPLETED (QUAL-01)."""
        client = _make_client()
        result = client._to_normalized_runtime_event(dict(self._TOOL_CALL_EVENT))
        assert result["type"] == NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED

    def test_function_call_arguments_done_has_item_sub_dict(self) -> None:
        """Payload must contain item sub-dict with call_id, name, arguments (PITFALL-05)."""
        client = _make_client()
        result = client._to_normalized_runtime_event(dict(self._TOOL_CALL_EVENT))
        payload = result["payload"]
        assert "item" in payload, "payload must contain 'item' sub-dict (PITFALL-05)"
        item = payload["item"]
        assert item["call_id"] == "call-1", "payload.item.call_id must match wire call_id"
        assert item["name"] == "my_fn", "payload.item.name must match wire name"
        assert item["arguments"] == "{}", "payload.item.arguments must match wire arguments"

    def test_function_call_top_level_fields(self) -> None:
        """Payload must also have top-level call_id and name for backward compat (PITFALL-05)."""
        client = _make_client()
        result = client._to_normalized_runtime_event(dict(self._TOOL_CALL_EVENT))
        payload = result["payload"]
        assert payload["call_id"] == "call-1", "payload.call_id top-level field required"
        assert payload["name"] == "my_fn", "payload.name top-level field required"

    def test_function_call_item_id_in_item(self) -> None:
        """item.id maps from wire-level item_id field."""
        client = _make_client()
        result = client._to_normalized_runtime_event(dict(self._TOOL_CALL_EVENT))
        item = result["payload"]["item"]
        assert item["id"] == "item-1"

    def test_function_call_response_id_in_payload(self) -> None:
        """payload.response_id must be present for correlation."""
        client = _make_client()
        result = client._to_normalized_runtime_event(dict(self._TOOL_CALL_EVENT))
        assert result["payload"]["response_id"] == "resp-1"

    def test_function_call_item_type_is_function_call(self) -> None:
        """item.type must be 'function_call' for GlassAgents dispatch compatibility."""
        client = _make_client()
        result = client._to_normalized_runtime_event(dict(self._TOOL_CALL_EVENT))
        assert result["payload"]["item"]["type"] == "function_call"

    def test_response_output_item_done_with_function_call_maps_to_tool_call_completed(
        self,
    ) -> None:
        """response.output_item.done with item.type=function_call → TOOL_CALL_COMPLETED."""
        client = _make_client()
        event = {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "call_id": "c1", "name": "fn"},
        }
        result = client._to_normalized_runtime_event(event)
        assert result["type"] == NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED

    def test_response_output_item_done_non_function_call_maps_to_unhandled(self) -> None:
        """response.output_item.done with item.type=message → UNHANDLED."""
        client = _make_client()
        event = {
            "type": "response.output_item.done",
            "item": {"type": "message"},
        }
        result = client._to_normalized_runtime_event(event)
        assert result["type"] == NormalizedRealtimeEventTypes.UNHANDLED


# ===========================================================================
# TestConnectLifecycle
# ===========================================================================


class TestConnectLifecycle:
    """PROV-01: Connect lifecycle — _on_connected fires initialize_session."""

    async def test_on_connected_calls_initialize_session(self) -> None:
        """_on_connected() must await initialize_session() (PROV-01)."""
        from unittest.mock import AsyncMock, patch

        client = _make_client()
        with patch.object(client, "initialize_session", new_callable=AsyncMock) as mock_init:
            await client._on_connected()
            mock_init.assert_awaited_once()

    def test_implements_contract(self) -> None:
        """OpenAIRealtimeClient must satisfy the RealtimeAdapterContract protocol."""
        client = _make_client()
        assert isinstance(client, RealtimeAdapterContract), (
            "OpenAIRealtimeClient must implement RealtimeAdapterContract (PROV-01)"
        )


# ===========================================================================
# TestCloseLifecycle
# ===========================================================================


class TestCloseLifecycle:
    """PROV-01: Close lifecycle — close() does not raise when not connected."""

    async def test_close_does_not_raise_when_not_connected(self) -> None:
        """Calling close() before connect() must not raise any exception."""
        client = _make_client()
        # Should complete without raising (client has no active WS)
        await client.close()
