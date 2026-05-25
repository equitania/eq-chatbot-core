"""ElevenLabs Agents Conversational AI realtime provider.

Port of the ElevenLabs convai WebSocket protocol adapted to the
eq-chatbot-core library conventions and Phase 1 BaseRealtimeWebsocketClient.

Key differences from OpenAI Realtime:
  (1) Server-side VAD — commit_client_turn() and create_response() are no-ops;
      ElevenLabs detects turn boundaries and triggers responses automatically.
  (2) Audio sample rate is 16 kHz (not 24 kHz) — set via session_sample_rate=16_000
      in both ElevenLabsRealtimeConfig and ELEVENLABS_REALTIME_CAPABILITIES.
  (3) user_audio_chunk is a bare top-level key — NOT a type-discriminated message.
      Sending {"type": "user_audio_chunk", ...} is WRONG and silently ignored.

Authentication note:
  xi-api-key is used ONLY in the REST signed-URL flow for private agents.
  Public agents connect directly via agent_id in the WebSocket URL — no header needed.
  The xi-api-key MUST NEVER appear in the WebSocket URL or in any log output.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from eq_chatbot_core.providers.base import ToolDefinition  # noqa: F401 — available for callers
from eq_chatbot_core.realtime.abc import RealtimeProvider
from eq_chatbot_core.realtime.contracts import (
    NormalizedRealtimeEventFull,
    NormalizedRealtimeEventTypes,
    RealtimeProviderCapabilities,
)
from eq_chatbot_core.realtime.websocket_client import BaseRealtimeWebsocketClient

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ElevenLabsRealtimeConfig:
    """Configuration for the ElevenLabs Agents Conversational AI realtime provider.

    GDPR / EU residency:
      Set base_url="wss://api.eu.residency.elevenlabs.io" for EU data residency (PROV-FUT-03).
      Default endpoint is the global endpoint (suitable for public/test agents).
    """

    api_key: str
    """xi-api-key for REST signed-URL call; NEVER placed in the WebSocket URL."""

    agent_id: str
    """pre-existing agent in ElevenLabs dashboard"""

    # EU Enterprise override: wss://api.eu.residency.elevenlabs.io
    base_url: str = "wss://api.elevenlabs.io"

    voice: str | None = None

    instructions: str | None = None
    """maps to conversation_config_override.agent.prompt.prompt"""

    # PROV-FUT-03 — 16 kHz; differs from 24 kHz default
    session_sample_rate: int = 16_000


# Provider capability metadata — immutable constant registered once at module level.
ELEVENLABS_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=True,
    manual_turn_commit_required=False,
    tool_calling=True,
    tool_result_submission_mode="elevenlabs_native",
    voice_selection=True,
    interruption_cancel=True,
    startup_validation=True,
    session_sample_rate=16_000,
)


class ElevenLabsRealtimeClient(BaseRealtimeWebsocketClient, RealtimeProvider):
    """ElevenLabs Agents Conversational AI provider — speech-to-speech, server VAD, tool calling.

    Subclasses BaseRealtimeWebsocketClient for transport (connect/retry/backoff)
    and implements all 11 RealtimeAdapterContract methods plus RealtimeProvider ABC.

    Authentication:
      Public agents: agent_id in URL only — no auth header required.
      Private agents: caller must pre-fetch a signed URL via the REST API using xi-api-key
        and pass the resulting wss://... URL as base_url before calling connect().
        The xi-api-key MUST NOT be placed in the WebSocket URL or headers.
    """

    def __init__(self, config: ElevenLabsRealtimeConfig, *, trace_events: bool = False) -> None:
        # D-03: fail fast with library-native exceptions before any network I/O
        if not config.api_key.strip():
            raise ValueError("ElevenLabsRealtimeConfig.api_key must be non-empty.")
        if not config.agent_id.strip():
            raise ValueError("ElevenLabsRealtimeConfig.agent_id must be non-empty.")

        # xi-api-key is NOT a WebSocket header — it is only used in the REST signed-URL flow
        # for private agents. Public agents require no auth header.
        url = f"{config.base_url}/v1/convai/conversation?agent_id={config.agent_id}"
        super().__init__(url=url, headers={})

        self._config = config
        self._trace_events = trace_events

    # ------------------------------------------------------------------
    # RealtimeProvider ABC
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    @property
    def capabilities(self) -> RealtimeProviderCapabilities:
        return ELEVENLABS_REALTIME_CAPABILITIES

    # ------------------------------------------------------------------
    # Abstract method overrides (all three required by Phase 1 base)
    # ------------------------------------------------------------------

    async def _on_connected(self) -> None:
        """Logging-only hook — ElevenLabs sends conversation_initiation_metadata server-side.

        IMPORTANT: Do NOT call initialize_session() here.
        ElevenLabs sends conversation_initiation_metadata automatically on connect.
        The Gemini pattern (NOT OpenAI) applies: consumer calls initialize_session() explicitly
        when it needs to override agent defaults (prompt, voice, tools).
        """
        if self._trace_events:
            _logger.info(
                "ElevenLabs convai websocket connected endpoint=%s",
                self._connection_error_endpoint(),
            )

    async def _on_message(self, raw: str) -> None:
        """Not used in iter_normalized_events flow — required for ABC conformance only."""
        pass

    def _connection_error_endpoint(self) -> str:
        """Return URL without API key for error messages (T-03.1-01 security requirement).

        api_key never appears in the WebSocket URL — no redaction needed on URL.
        agent_id is not a secret and is safe to include.
        """
        return f"{self._config.base_url}/v1/convai/conversation?agent_id={self._config.agent_id}"

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        """Send conversation_initiation_client_data to configure the ElevenLabs session.

        Called explicitly by consumers to override agent defaults. The server sends
        conversation_initiation_metadata independently — this is an override, not a trigger.
        """
        payload: dict[str, Any] = {
            "type": "conversation_initiation_client_data",
            "conversation_config_override": {},
        }

        resolved_instructions = instructions or self._config.instructions
        if resolved_instructions:
            payload["conversation_config_override"]["agent"] = {"prompt": {"prompt": resolved_instructions}}

        resolved_voice = voice or self._config.voice
        if resolved_voice:
            payload["conversation_config_override"]["tts"] = {"voice_id": resolved_voice}

        if tools:
            payload["conversation_config_override"]["tools"] = tools

        await self.send_json(payload)

    async def update_session(self, payload: dict[str, Any]) -> None:
        """Send an arbitrary session payload (for advanced consumers)."""
        await self.send_json(payload)

    async def append_client_audio(self, pcm16_audio: bytes) -> None:
        """Base64-encode and send a PCM16 audio chunk.

        No-op on empty input — protects against accidental empty-buffer sends.

        CRITICAL: ElevenLabs uses a bare top-level key — NOT a type-discriminated message.
        Sending {"type": "user_audio_chunk", ...} is WRONG and will be silently ignored
        by the server. The correct wire format has NO "type" field.
        """
        if not pcm16_audio:
            return
        # CRITICAL: send bare top-level key with NO "type" field
        await self.send_json({"user_audio_chunk": base64.b64encode(pcm16_audio).decode("ascii")})

    async def commit_client_turn(self) -> None:
        """No-op — ElevenLabs performs server-side VAD turn-taking; no client commit needed."""
        pass

    async def create_response(self) -> None:
        """No-op — ElevenLabs generates responses server-side after VAD turn detection."""
        pass

    async def cancel_response(self, *, response_id: str | None = None) -> None:
        """No-op — ElevenLabs handles interruption server-side via VAD."""
        pass

    async def register_tools(self, tools: list[Any]) -> None:
        """Register tools by re-initializing the session with the tool list."""
        await self.initialize_session(tools=tools)

    async def submit_tool_result(self, *, call_id: str, output: str) -> None:
        """Submit a tool call result using the ElevenLabs native client_tool_result schema.

        ElevenLabs uses 'client_tool_result' — NOT 'conversation.item.create'.
        CRITICAL: field name is 'tool_call_id' (NOT 'call_id');
        contract parameter is call_id, wire format field is tool_call_id.
        """
        await self.send_json(
            {
                "type": "client_tool_result",
                "tool_call_id": call_id,
                "result": output,
                "is_error": False,
            }
        )

    # ------------------------------------------------------------------
    # Event normalization
    # ------------------------------------------------------------------

    def _to_normalized_runtime_event(self, event: dict[str, Any]) -> NormalizedRealtimeEventFull | None:
        """Route ElevenLabs wire event types to NormalizedRealtimeEventTypes constants.

        Returns None as a sentinel for ping events — caller sends pong and skips yield.
        """
        event_type = event.get("type")

        if not isinstance(event_type, str):
            return {
                "type": NormalizedRealtimeEventTypes.UNHANDLED,
                "payload": event,
                "source": "missing_type",
                "raw": event,
            }

        if event_type == "conversation_initiation_metadata":
            return {
                "type": NormalizedRealtimeEventTypes.SESSION_READY,
                "payload": event,
                "source": event_type,
                "raw": event,
            }

        if event_type == "audio":
            audio_b64 = event.get("audio_event", {}).get("audio_base_64", "")
            return {
                "type": NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA,
                "payload": {"audio": audio_b64, **event},
                "source": event_type,
                "raw": event,
            }

        if event_type == "agent_response":
            # TODO: agent_response_complete may become canonical RESPONSE_DONE signal once
            # SDK wire dispatch includes it (April 2026 schema addition, not yet in v2.49.1
            # wire dispatch). For now agent_response is the primary RESPONSE_DONE trigger.
            return {
                "type": NormalizedRealtimeEventTypes.RESPONSE_DONE,
                "payload": event,
                "source": event_type,
                "raw": event,
            }

        if event_type == "agent_response_complete":
            # Forward-compatible — not in current SDK wire dispatch (v2.49.1) but safe to handle.
            return {
                "type": NormalizedRealtimeEventTypes.RESPONSE_DONE,
                "payload": event,
                "source": event_type,
                "raw": event,
            }

        if event_type == "user_transcript":
            return {
                "type": NormalizedRealtimeEventTypes.INPUT_AUDIO_COMMITTED,
                "payload": event,
                "source": event_type,
                "raw": event,
            }

        if event_type == "interruption":
            # User interrupted agent via server VAD
            return {
                "type": NormalizedRealtimeEventTypes.INPUT_SPEECH_STARTED,
                "payload": event,
                "source": event_type,
                "raw": event,
            }

        if event_type == "ping":
            # Return None sentinel — caller sends pong and skips yield
            return None

        if event_type == "client_tool_call":
            tool_info = event.get("client_tool_call", {})
            return {
                "type": NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED,
                "payload": {
                    "call_id": tool_info.get("tool_call_id"),
                    "name": tool_info.get("tool_name"),
                    "arguments": tool_info.get("parameters", "{}"),
                },
                "source": event_type,
                "raw": event,
            }

        # agent_response_correction and all other unknown event types
        return {
            "type": NormalizedRealtimeEventTypes.UNHANDLED,
            "payload": event,
            "source": event_type or "unknown",
            "raw": event,
        }

    async def iter_normalized_events(self) -> AsyncIterator[NormalizedRealtimeEventFull]:
        """Yield normalized events from the ElevenLabs convai stream.

        Handles ping/pong keepalive transparently — ping events trigger a pong send
        and are NOT yielded to the consumer.
        """
        async for event in self.iter_events():
            if event.get("type") == "ping":
                event_id = event.get("ping_event", {}).get("event_id")
                await self.send_json({"type": "pong", "event_id": event_id})
                continue
            normalized = self._to_normalized_runtime_event(event)
            if normalized is not None:
                yield normalized


__all__ = [
    "ElevenLabsRealtimeClient",
    "ElevenLabsRealtimeConfig",
    "ELEVENLABS_REALTIME_CAPABILITIES",
]
