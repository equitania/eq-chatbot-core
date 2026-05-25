"""Unit tests for ElevenLabsRealtimeClient.

Uses session-scoped mock_websockets_module from conftest.py (autouse=True).
Import provider AFTER the session fixture installs the mock into sys.modules.

Coverage:
  - QUAL-01: ElevenLabs unit-test portion — all VALIDATION.md per-task behaviors
  - T-03.1-02-01: xi-api-key never in _connection_error_endpoint() (key redaction guard)
  - T-03.1-02-02: user_audio_chunk wire format has NO "type" key (PITFALL-01 guard)
  - T-03.1-02-03: submit_tool_result uses "tool_call_id" not "call_id" (PITFALL-02 guard)
"""

import base64
import dataclasses
from unittest.mock import AsyncMock, patch

import pytest

from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes, RealtimeAdapterContract
from eq_chatbot_core.realtime.providers.elevenlabs import (
    ELEVENLABS_REALTIME_CAPABILITIES,
    ElevenLabsRealtimeClient,
    ElevenLabsRealtimeConfig,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_FAKE_KEY = "xi-fake-api-key"
_FAKE_AGENT = "agent-fake-id"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_client() -> ElevenLabsRealtimeClient:
    """Construct a client with fake credentials (no real network I/O)."""
    config = ElevenLabsRealtimeConfig(api_key=_FAKE_KEY, agent_id=_FAKE_AGENT)
    return ElevenLabsRealtimeClient(config)


# ===========================================================================
# TestElevenLabsRealtimeConfig
# ===========================================================================


class TestElevenLabsRealtimeConfig:
    """PROV-FUT-03: ElevenLabsRealtimeConfig is a frozen+slots dataclass with correct defaults."""

    @pytest.mark.unit
    def test_frozen_dataclass(self) -> None:
        """Mutating a frozen dataclass must raise FrozenInstanceError (frozen=True)."""
        config = ElevenLabsRealtimeConfig(api_key=_FAKE_KEY, agent_id=_FAKE_AGENT)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            config.api_key = "new-value"  # type: ignore[misc]

    @pytest.mark.unit
    def test_default_sample_rate(self) -> None:
        """session_sample_rate defaults to 16_000 (PROV-FUT-03 — 16 kHz, not 24 kHz)."""
        config = ElevenLabsRealtimeConfig(api_key="k", agent_id="a")
        assert config.session_sample_rate == 16_000

    @pytest.mark.unit
    def test_default_base_url(self) -> None:
        """base_url defaults to global ElevenLabs endpoint."""
        config = ElevenLabsRealtimeConfig(api_key="k", agent_id="a")
        assert config.base_url == "wss://api.elevenlabs.io"

    @pytest.mark.unit
    def test_default_voice_none(self) -> None:
        """voice defaults to None (no voice override)."""
        config = ElevenLabsRealtimeConfig(api_key="k", agent_id="a")
        assert config.voice is None

    @pytest.mark.unit
    def test_default_instructions_none(self) -> None:
        """instructions defaults to None (no prompt override)."""
        config = ElevenLabsRealtimeConfig(api_key="k", agent_id="a")
        assert config.instructions is None

    @pytest.mark.unit
    def test_custom_base_url(self) -> None:
        """EU residency base_url override is stored correctly."""
        config = ElevenLabsRealtimeConfig(
            api_key="k",
            agent_id="a",
            base_url="wss://api.eu.residency.elevenlabs.io",
        )
        assert config.base_url == "wss://api.eu.residency.elevenlabs.io"


# ===========================================================================
# TestElevenLabsCapabilities
# ===========================================================================


class TestElevenLabsCapabilities:
    """ELEVENLABS_REALTIME_CAPABILITIES must reflect the verified ElevenLabs Convai protocol."""

    @pytest.mark.unit
    def test_no_manual_turn_commit(self) -> None:
        """ElevenLabs uses server-side VAD — manual_turn_commit_required must be False."""
        assert ELEVENLABS_REALTIME_CAPABILITIES.manual_turn_commit_required is False

    @pytest.mark.unit
    def test_tool_result_mode_elevenlabs_native(self) -> None:
        """tool_result_submission_mode must be exact string 'elevenlabs_native'."""
        assert ELEVENLABS_REALTIME_CAPABILITIES.tool_result_submission_mode == "elevenlabs_native"

    @pytest.mark.unit
    def test_session_sample_rate_16k(self) -> None:
        """session_sample_rate must be 16_000 (PROV-FUT-03 — differs from 24 kHz OpenAI default)."""
        assert ELEVENLABS_REALTIME_CAPABILITIES.session_sample_rate == 16_000

    @pytest.mark.unit
    def test_server_vad_true(self) -> None:
        """ElevenLabs performs server-side VAD — server_vad must be True."""
        assert ELEVENLABS_REALTIME_CAPABILITIES.server_vad is True

    @pytest.mark.unit
    def test_tool_calling_true(self) -> None:
        """ElevenLabs Convai supports tool calling via client_tool_call / client_tool_result."""
        assert ELEVENLABS_REALTIME_CAPABILITIES.tool_calling is True


# ===========================================================================
# TestConstructorValidation
# ===========================================================================


class TestConstructorValidation:
    """D-03: fail fast with ValueError before any network I/O."""

    @pytest.mark.unit
    def test_empty_api_key_raises(self) -> None:
        """Empty api_key must raise ValueError immediately (D-03)."""
        config = ElevenLabsRealtimeConfig(api_key="", agent_id="a")
        with pytest.raises(ValueError, match="api_key"):
            ElevenLabsRealtimeClient(config)

    @pytest.mark.unit
    def test_whitespace_api_key_raises(self) -> None:
        """Whitespace-only api_key must raise ValueError (D-03)."""
        config = ElevenLabsRealtimeConfig(api_key="   ", agent_id="a")
        with pytest.raises(ValueError, match="api_key"):
            ElevenLabsRealtimeClient(config)

    @pytest.mark.unit
    def test_empty_agent_id_raises(self) -> None:
        """Empty agent_id must raise ValueError immediately (D-03)."""
        config = ElevenLabsRealtimeConfig(api_key="k", agent_id="")
        with pytest.raises(ValueError, match="agent_id"):
            ElevenLabsRealtimeClient(config)

    @pytest.mark.unit
    def test_whitespace_agent_id_raises(self) -> None:
        """Whitespace-only agent_id must raise ValueError (D-03)."""
        config = ElevenLabsRealtimeConfig(api_key="k", agent_id="   ")
        with pytest.raises(ValueError, match="agent_id"):
            ElevenLabsRealtimeClient(config)

    @pytest.mark.unit
    def test_valid_config_does_not_raise(self) -> None:
        """Valid api_key and agent_id do not raise on construction."""
        _make_client()  # should not raise


# ===========================================================================
# TestConnectionErrorEndpoint
# ===========================================================================


class TestConnectionErrorEndpoint:
    """T-03.1-02-01: _connection_error_endpoint must never expose the api_key."""

    @pytest.mark.unit
    def test_api_key_not_in_endpoint(self) -> None:
        """xi-api-key must NEVER appear in the connection error endpoint (T-03.1-02-01).

        ElevenLabs public agents authenticate via agent_id in URL only — the xi-api-key
        is used only in the REST signed-URL flow and must never appear in the WS URL.
        """
        client = _make_client()
        endpoint = client._connection_error_endpoint()
        assert _FAKE_KEY not in endpoint, (
            "xi-api-key must never appear in connection error endpoint (security requirement T-03.1-02-01)"
        )

    @pytest.mark.unit
    def test_agent_id_in_endpoint(self) -> None:
        """agent_id is not a secret and must appear in the endpoint for diagnostics."""
        client = _make_client()
        endpoint = client._connection_error_endpoint()
        assert _FAKE_AGENT in endpoint

    @pytest.mark.unit
    def test_endpoint_starts_with_wss(self) -> None:
        """Connection error endpoint must use WSS scheme."""
        client = _make_client()
        assert client._connection_error_endpoint().startswith("wss://")

    @pytest.mark.unit
    def test_no_auth_header_in_url(self) -> None:
        """Neither 'xi-api-key' nor 'Authorization' must appear in the endpoint URL."""
        client = _make_client()
        endpoint = client._connection_error_endpoint()
        assert "xi-api-key" not in endpoint
        assert "Authorization" not in endpoint


# ===========================================================================
# TestConnectLifecycle
# ===========================================================================


class TestConnectLifecycle:
    """Basic provider identity and contract compliance."""

    @pytest.mark.unit
    def test_isinstance_realtime_adapter_contract(self) -> None:
        """ElevenLabsRealtimeClient must satisfy the RealtimeAdapterContract protocol."""
        assert isinstance(_make_client(), RealtimeAdapterContract), (
            "ElevenLabsRealtimeClient must implement RealtimeAdapterContract"
        )

    @pytest.mark.unit
    def test_provider_name(self) -> None:
        """provider_name property must return exact string 'elevenlabs'."""
        assert _make_client().provider_name == "elevenlabs"

    @pytest.mark.unit
    def test_capabilities_property(self) -> None:
        """capabilities property must return the module-level constant (same object identity)."""
        assert _make_client().capabilities is ELEVENLABS_REALTIME_CAPABILITIES


# ===========================================================================
# TestElevenLabsEventMapping
# ===========================================================================


class TestElevenLabsEventMapping:
    """QUAL-01: _to_normalized_runtime_event routes all ElevenLabs wire types correctly."""

    @pytest.mark.unit
    def test_conversation_initiation_metadata_maps_to_session_ready(self) -> None:
        """conversation_initiation_metadata → SESSION_READY (QUAL-01)."""
        client = _make_client()
        frame = {"type": "conversation_initiation_metadata", "conversation_initiation_metadata_event": {}}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.SESSION_READY

    @pytest.mark.unit
    def test_audio_maps_to_response_audio_delta(self) -> None:
        """audio → RESPONSE_AUDIO_DELTA (QUAL-01)."""
        client = _make_client()
        frame = {"type": "audio", "audio_event": {"audio_base_64": "AAEC"}}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA

    @pytest.mark.unit
    def test_agent_response_maps_to_response_done(self) -> None:
        """agent_response → RESPONSE_DONE (primary trigger — QUAL-01)."""
        client = _make_client()
        frame = {"type": "agent_response", "agent_response_event": {"agent_response": "hello"}}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.RESPONSE_DONE

    @pytest.mark.unit
    def test_agent_response_complete_maps_to_response_done(self) -> None:
        """agent_response_complete → RESPONSE_DONE (forward-compatible — not in v2.49.1 SDK dispatch)."""
        client = _make_client()
        frame = {"type": "agent_response_complete"}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.RESPONSE_DONE

    @pytest.mark.unit
    def test_user_transcript_maps_to_input_audio_committed(self) -> None:
        """user_transcript → INPUT_AUDIO_COMMITTED (QUAL-01)."""
        client = _make_client()
        frame = {"type": "user_transcript"}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.INPUT_AUDIO_COMMITTED

    @pytest.mark.unit
    def test_interruption_maps_to_input_speech_started(self) -> None:
        """interruption (user interrupts agent via server VAD) → INPUT_SPEECH_STARTED (QUAL-01)."""
        client = _make_client()
        frame = {"type": "interruption", "interruption_event": {"event_id": 1}}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.INPUT_SPEECH_STARTED

    @pytest.mark.unit
    def test_client_tool_call_maps_to_tool_call_completed(self) -> None:
        """client_tool_call → TOOL_CALL_COMPLETED (QUAL-01)."""
        client = _make_client()
        frame = {
            "type": "client_tool_call",
            "client_tool_call": {"tool_call_id": "c1", "tool_name": "fn", "parameters": "{}"},
        }
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED

    @pytest.mark.unit
    def test_tool_call_completed_payload_has_call_id(self) -> None:
        """client_tool_call payload must contain call_id mapped from tool_call_id."""
        client = _make_client()
        frame = {
            "type": "client_tool_call",
            "client_tool_call": {"tool_call_id": "c1", "tool_name": "fn", "parameters": "{}"},
        }
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["payload"]["call_id"] == "c1"

    @pytest.mark.unit
    def test_tool_call_completed_payload_has_name(self) -> None:
        """client_tool_call payload must contain 'name' mapped from 'tool_name'."""
        client = _make_client()
        frame = {
            "type": "client_tool_call",
            "client_tool_call": {"tool_call_id": "c1", "tool_name": "fn", "parameters": "{}"},
        }
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["payload"]["name"] == "fn"

    @pytest.mark.unit
    def test_ping_returns_none_sentinel(self) -> None:
        """ping → None sentinel (caller sends pong and skips yield — QUAL-01)."""
        client = _make_client()
        frame = {"type": "ping", "ping_event": {"event_id": 42, "ping_ms": 10}}
        result = client._to_normalized_runtime_event(frame)
        assert result is None, "ping must return None sentinel (not yielded to consumer)"

    @pytest.mark.unit
    def test_agent_response_correction_maps_to_unhandled(self) -> None:
        """agent_response_correction → UNHANDLED (no contract mapping for this event)."""
        client = _make_client()
        frame = {"type": "agent_response_correction"}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.UNHANDLED

    @pytest.mark.unit
    def test_unknown_event_maps_to_unhandled(self) -> None:
        """Unknown wire type → UNHANDLED (QUAL-01 extensibility guard)."""
        client = _make_client()
        frame = {"type": "xyz_unknown_event"}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.UNHANDLED

    @pytest.mark.unit
    def test_missing_type_maps_to_unhandled(self) -> None:
        """Event with no 'type' key → UNHANDLED with source == 'missing_type'."""
        client = _make_client()
        frame = {"payload": "no type key"}
        result = client._to_normalized_runtime_event(frame)
        assert result is not None
        assert result["type"] == NormalizedRealtimeEventTypes.UNHANDLED
        assert result["source"] == "missing_type"


# ===========================================================================
# TestElevenLabsAudioInput
# ===========================================================================


class TestElevenLabsAudioInput:
    """T-03.1-02-02: append_client_audio wire format — user_audio_chunk key, no 'type' key."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_audio_chunk_format_has_user_audio_chunk_key(self) -> None:
        """append_client_audio must send payload with 'user_audio_chunk' as top-level key."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.append_client_audio(b"\x00\x01" * 8)
            mock_send.assert_awaited_once()
            sent = mock_send.call_args[0][0]
            assert "user_audio_chunk" in sent

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_audio_chunk_format_no_type_key(self) -> None:
        """CRITICAL: append_client_audio must NOT include a 'type' key in the payload.

        ElevenLabs uses a bare top-level key — NOT a type-discriminated message.
        Sending {"type": "user_audio_chunk", ...} is WRONG and silently ignored by server.
        (T-03.1-02-02 / PITFALL-01)
        """
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.append_client_audio(b"\x00\x01" * 8)
            sent = mock_send.call_args[0][0]
            assert "type" not in sent, (
                "'type' key must NOT be in user_audio_chunk payload — "
                "ElevenLabs bare key format, NOT type-discriminated message (T-03.1-02-02)"
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_audio_chunk_is_base64(self) -> None:
        """append_client_audio must base64-encode the PCM16 audio bytes."""
        client = _make_client()
        raw_audio = b"\x00\x01" * 8
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.append_client_audio(raw_audio)
            sent = mock_send.call_args[0][0]
            expected = base64.b64encode(raw_audio).decode("ascii")
            assert sent["user_audio_chunk"] == expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_audio_is_noop(self) -> None:
        """append_client_audio with empty bytes must not send any payload (no-op guard)."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.append_client_audio(b"")
            mock_send.assert_not_called()


# ===========================================================================
# TestElevenLabsTurnControl
# ===========================================================================


class TestElevenLabsTurnControl:
    """ElevenLabs server-side VAD — commit_client_turn, create_response, cancel_response are no-ops."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_commit_client_turn_noop(self) -> None:
        """commit_client_turn must NOT send any WS message — server VAD handles turn detection."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.commit_client_turn()
            mock_send.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_response_noop(self) -> None:
        """create_response must NOT send any WS message — ElevenLabs generates responses server-side."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.create_response()
            mock_send.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cancel_response_noop(self) -> None:
        """cancel_response must NOT send any WS message — ElevenLabs handles interruption via VAD."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.cancel_response()
            mock_send.assert_not_called()


# ===========================================================================
# TestElevenLabsToolResult
# ===========================================================================


class TestElevenLabsToolResult:
    """T-03.1-02-03: submit_tool_result wire format — client_tool_result type, tool_call_id field."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tool_result_uses_client_tool_result_type(self) -> None:
        """submit_tool_result must send type='client_tool_result' (ElevenLabs native schema)."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="c1", output="done")
            sent = mock_send.call_args[0][0]
            assert sent["type"] == "client_tool_result"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tool_result_uses_tool_call_id_not_call_id(self) -> None:
        """CRITICAL: wire field must be 'tool_call_id', NOT 'call_id'.

        The contract parameter is call_id; the ElevenLabs wire format field is tool_call_id.
        Sending 'call_id' would be silently ignored by the server.
        (T-03.1-02-03 / PITFALL-02)
        """
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="c1", output="done")
            sent = mock_send.call_args[0][0]
            assert "tool_call_id" in sent, "Wire field must be 'tool_call_id', not 'call_id' (T-03.1-02-03)"
            assert "call_id" not in sent, "Contract parameter 'call_id' must NOT appear as wire field (T-03.1-02-03)"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tool_result_tool_call_id_value(self) -> None:
        """tool_call_id value must match the call_id parameter passed in."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="c1", output="done")
            sent = mock_send.call_args[0][0]
            assert sent["tool_call_id"] == "c1"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tool_result_result_field(self) -> None:
        """submit_tool_result must include 'result' field with the output value."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="c1", output="done")
            sent = mock_send.call_args[0][0]
            assert sent["result"] == "done"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tool_result_is_error_false(self) -> None:
        """submit_tool_result must include 'is_error': False for successful tool results."""
        client = _make_client()
        with patch.object(client, "send_json", new_callable=AsyncMock) as mock_send:
            await client.submit_tool_result(call_id="c1", output="done")
            sent = mock_send.call_args[0][0]
            assert sent["is_error"] is False
