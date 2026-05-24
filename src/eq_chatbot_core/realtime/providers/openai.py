"""OpenAI Realtime API provider.

Port of GlassAgents/backend/realtime/client.py (~391 LOC) adapted to the
eq-chatbot-core library conventions and Phase 1 BaseRealtimeWebsocketClient.

Key differences from the reference:
  - Inherits Phase 1 BaseRealtimeWebsocketClient (url+headers at init, not lazy)
  - _on_connected, _on_message, _connection_error_endpoint are abstract in Phase 1
  - ToolDefinition.to_openai_tool() does not exist — inline conversion used instead
  - GlassAgents ABC connect(config=None) stub NOT ported (Phase 1 ABC is compatible)
"""
from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from eq_chatbot_core.providers.base import ToolDefinition
from eq_chatbot_core.realtime.abc import RealtimeProvider
from eq_chatbot_core.realtime.contracts import (
    INPUT_AUDIO_SAMPLE_RATE,
    NormalizedRealtimeEventFull,
    NormalizedRealtimeEventTypes,
    RealtimeProviderCapabilities,
)
from eq_chatbot_core.realtime.websocket_client import BaseRealtimeWebsocketClient

_logger = logging.getLogger(__name__)

# Both input and output use 24 kHz PCM16 (matches INPUT_AUDIO_SAMPLE_RATE in contracts.py)
OUTPUT_AUDIO_SAMPLE_RATE: int = 24_000


@dataclass(frozen=True)
class RealtimeAudioEventNames:
    """Canonical audio event names — use as named constants, not raw strings.

    The GlassAgents reference uses this dataclass pattern (without slots=True)
    as a named-constant holder for wire-level audio event type strings.
    """

    delta: str = "response.output_audio.delta"
    done: str = "response.output_audio.done"


@dataclass(frozen=True, slots=True)
class OpenAIRealtimeConfig:
    """Configuration for the OpenAI Realtime API provider.

    Source: GlassAgents/backend/realtime/providers/openai.py (adapted for library conventions).
    """

    api_key: str
    # gpt-realtime: floating alias, currently resolves to gpt-realtime-2025-08-28 (verified 2026-05-24).
    # Consumers requiring byte-reproducible behavior should pin a dated snapshot explicitly.
    # Valid dated snapshots: gpt-realtime-2025-08-28
    # Reference: https://platform.openai.com/docs/models/gpt-realtime
    model: str = "gpt-realtime"
    voice: str = "ash"
    instructions: str | None = None
    include_turn_detection: bool = True  # see PITFALL-28 comment in _build_session_update_event


# Provider capability metadata — immutable constant registered once at module level.
# Source: GlassAgents/backend/realtime/providers/openai.py lines 16-26
OPENAI_REALTIME_CAPABILITIES = RealtimeProviderCapabilities(
    streaming_audio_input=True,
    streaming_audio_output=True,
    server_vad=True,  # provider SUPPORTS VAD (hardware capability, static — see PITFALL-28)
    manual_turn_commit_required=False,  # when VAD active (default); see PITFALL-28
    tool_calling=True,
    tool_result_submission_mode="conversation_item",
    voice_selection=True,
    interruption_cancel=True,
    startup_validation=True,
)


class OpenAIRealtimeClient(BaseRealtimeWebsocketClient, RealtimeProvider):
    """OpenAI Realtime API provider — GPT speech-to-speech, server VAD, tool calling.

    Subclasses BaseRealtimeWebsocketClient for transport (connect/retry/backoff)
    and implements all 11 RealtimeAdapterContract methods plus RealtimeProvider ABC.

    Port target: GlassAgents/backend/realtime/client.py (391 LOC)
    Adapted for Phase 1 base class constructor: url+headers at init (not trace_events).
    """

    def __init__(self, config: OpenAIRealtimeConfig, *, trace_events: bool = False) -> None:
        # D-03: fail fast with library-native exceptions before any network I/O
        if not config.api_key.strip():
            raise ValueError(
                "OpenAIRealtimeConfig.api_key must be non-empty. "
                "Provide a valid OpenAI API key."
            )
        if not config.model.strip():
            raise ValueError(
                "OpenAIRealtimeConfig.model must be non-empty. "
                "Valid models: gpt-realtime, gpt-realtime-2025-08-28"
            )

        # Phase 1 base class takes url + headers (NOT trace_events — see RESEARCH.md Pitfall 1)
        url = f"wss://api.openai.com/v1/realtime?{urlencode({'model': config.model})}"
        headers = {"Authorization": f"Bearer {config.api_key}"}
        super().__init__(url=url, headers=headers)

        self._config = config
        self._trace_events = trace_events  # not in base class — store on subclass (Pitfall 7)
        self.audio_event_names = RealtimeAudioEventNames()
        self._input_audio_append_count: int = 0
        self._output_audio_delta_count: int = 0

    # ------------------------------------------------------------------
    # Abstract method overrides (all three are required by Phase 1 base)
    # ------------------------------------------------------------------

    async def _on_connected(self) -> None:
        """Initialize OpenAI session immediately after WebSocket handshake."""
        await self.initialize_session()

    async def _on_message(self, raw: str) -> None:
        """Not used in iter_normalized_events flow — required for ABC conformance only."""
        # The production event loop uses iter_events() / iter_normalized_events().
        # This method exists for ABC compliance only.
        pass

    def _connection_error_endpoint(self) -> str:
        """Return URL without API key for error messages (T-02-01 security requirement).

        NEVER include self._config.api_key or self._headers in the returned string.
        The model param is safe to include — it is not a secret.
        """
        return f"wss://api.openai.com/v1/realtime?model={self._config.model}"

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _build_session_update_event(
        self,
        *,
        instructions: str | None,
        voice: str | None,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        # PITFALL-28 RESOLUTION:
        #
        # OPENAI_REALTIME_CAPABILITIES.server_vad = True
        #   This reflects OpenAI's HARDWARE CAPABILITY — the provider natively supports
        #   server-side Voice Activity Detection. This flag is STATIC and IMMUTABLE.
        #   It answers: "Does this provider have VAD hardware?" → YES, always.
        #
        # OpenAIRealtimeConfig.include_turn_detection = True  (default)
        #   This is a SESSION-LEVEL OPT-IN. When True, the session.update payload
        #   activates VAD via the turn_detection block. When False, the key is
        #   OMITTED entirely — the VAD hardware exists but is NOT activated.
        #   The caller must then invoke commit_client_turn() manually.
        #
        # These are DIFFERENT ABSTRACTIONS at DIFFERENT LEVELS:
        #   server_vad=True             → "The provider CAN do VAD" (static)
        #   include_turn_detection=True → "This session USES VAD" (per-session config)
        #
        # server_vad=True with include_turn_detection=False is a valid intentional state:
        # consumer wants manual turn control on a VAD-capable provider
        # (e.g. for precise turn boundaries in onboarding flows).
        #
        # Reference: GlassAgents/backend/realtime/client.py lines 334-339,
        #            GlassAgents/backend/realtime/providers/openai.py lines 16-26
        resolved_instructions = (
            self._config.instructions if instructions is None else instructions
        )
        resolved_voice = self._config.voice if voice is None else voice

        session: dict[str, Any] = {
            "type": "realtime",
            "model": self._config.model,
            "instructions": resolved_instructions,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": INPUT_AUDIO_SAMPLE_RATE},
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": OUTPUT_AUDIO_SAMPLE_RATE},
                    "voice": resolved_voice,
                },
            },
        }
        if self._config.include_turn_detection:  # PITFALL-28: session-level opt-in
            session["audio"]["input"]["turn_detection"] = {
                "type": "server_vad",
                "create_response": True,
                "interrupt_response": True,
            }
        if tools:
            session["tools"] = tools
            session["tool_choice"] = "auto"

        return {"type": "session.update", "session": session}

    @staticmethod
    def _normalize_tools(
        tools: Sequence[ToolDefinition | dict[str, Any]] | None,
    ) -> list[dict[str, Any]] | None:
        """Convert ToolDefinition instances to OpenAI wire format.

        Inline conversion — Phase 1 ToolDefinition has no to_openai_tool() method.
        Option 2 per RESEARCH.md Pattern 6: keep Phase 2 self-contained.
        """
        if not tools:
            return None
        normalized: list[dict[str, Any]] = []
        for tool in tools:
            if isinstance(tool, ToolDefinition):
                # Inline ToolDefinition → OpenAI tool format
                normalized.append(
                    {
                        "type": "function",
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                        "strict": tool.strict,
                    }
                )
            else:
                normalized.append(dict(tool))
        return normalized

    # ------------------------------------------------------------------
    # Event normalization pipeline (two-stage)
    # ------------------------------------------------------------------

    def normalize_audio_event_type(self, event_type: str) -> str:
        """Stage 1a: Map legacy wire aliases to canonical audio event names."""
        if event_type == "response.audio.delta":
            return self.audio_event_names.delta  # "response.output_audio.delta"
        if event_type == "response.audio.done":
            return self.audio_event_names.done  # "response.output_audio.done"
        return event_type

    def normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Stage 1: Normalize wire event aliases before routing (response.audio.* → canonical)."""
        event_type = event.get("type")
        if not isinstance(event_type, str):
            return event
        normalized_type = self.normalize_audio_event_type(event_type)
        if normalized_type == event_type:
            return event
        normalized = dict(event)
        normalized["type"] = normalized_type
        return normalized

    def _to_normalized_runtime_event(self, event: dict[str, Any]) -> NormalizedRealtimeEventFull:
        """Stage 2: Route canonical wire types to NormalizedRealtimeEventTypes constants.

        Source: GlassAgents/backend/realtime/client.py lines 220-285
        """
        event = self.normalize_event(event)
        event_type = event.get("type")

        if not isinstance(event_type, str):
            return {
                "type": NormalizedRealtimeEventTypes.UNHANDLED,
                "payload": event,
                "source": "missing_type",
                "raw": event,
            }

        if event_type in {"session.created", "session.updated"}:
            normalized_type = NormalizedRealtimeEventTypes.SESSION_READY
        elif event_type == self.audio_event_names.delta:
            normalized_type = NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA
            self._output_audio_delta_count += 1
        elif event_type == self.audio_event_names.done:
            normalized_type = NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DONE
        elif event_type == "response.done":
            normalized_type = NormalizedRealtimeEventTypes.RESPONSE_DONE
        elif event_type == "input_audio_buffer.speech_started":
            normalized_type = NormalizedRealtimeEventTypes.INPUT_SPEECH_STARTED
        elif event_type == "input_audio_buffer.speech_stopped":
            normalized_type = NormalizedRealtimeEventTypes.INPUT_SPEECH_STOPPED
        elif event_type == "response.created":
            normalized_type = NormalizedRealtimeEventTypes.RESPONSE_CREATED
        elif event_type == "input_audio_buffer.committed":
            normalized_type = NormalizedRealtimeEventTypes.INPUT_AUDIO_COMMITTED
        elif event_type == "error":
            normalized_type = NormalizedRealtimeEventTypes.ERROR
        elif event_type == "response.function_call_arguments.done":
            # PITFALL-05: custom payload shape — must include item sub-dict AND top-level fields
            # for GlassAgents bridge compatibility (payload["item"]["call_id"] etc.)
            # Source: GlassAgents/backend/realtime/client.py lines 252-269
            return {
                "type": NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED,
                "payload": {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "function_call",
                        "id": event.get("item_id"),
                        "call_id": event.get("call_id"),
                        "name": event.get("name"),
                        "arguments": event.get("arguments"),
                    },
                    "call_id": event.get("call_id"),
                    "name": event.get("name"),
                    "arguments": event.get("arguments"),
                    "response_id": event.get("response_id"),
                },
                "source": event_type,
                "raw": event,
            }
        elif event_type == "response.output_item.done":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "function_call":
                normalized_type = NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED
            else:
                normalized_type = NormalizedRealtimeEventTypes.UNHANDLED
        else:
            normalized_type = NormalizedRealtimeEventTypes.UNHANDLED

        return {"type": normalized_type, "payload": event, "source": event_type, "raw": event}

    # ------------------------------------------------------------------
    # RealtimeAdapterContract — 11 methods
    # (connect and close are inherited from BaseRealtimeWebsocketClient)
    # ------------------------------------------------------------------

    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        """Send session.update to configure the OpenAI Realtime session."""
        event = self._build_session_update_event(
            instructions=instructions,
            voice=voice,
            tools=self._normalize_tools(tools),
        )
        await self.send_json(event)

    async def update_session(self, payload: dict[str, Any]) -> None:
        """Send an arbitrary session.update payload (for advanced consumers)."""
        await self.send_json(payload)

    async def append_client_audio(self, pcm16_audio: bytes) -> None:
        """Base64-encode and send a PCM16 audio chunk.

        No-op on empty input — protects against accidental empty-buffer sends.
        Source: GlassAgents/backend/realtime/client.py lines 174-181
        """
        if not pcm16_audio:
            return
        self._input_audio_append_count += 1
        await self.send_json(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm16_audio).decode("ascii"),
            }
        )

    async def commit_client_turn(self) -> None:
        """Commit the current input audio buffer (manual turn control).

        Required when include_turn_detection=False — see PITFALL-28 in _build_session_update_event.
        """
        await self.send_json({"type": "input_audio_buffer.commit"})

    async def create_response(self) -> None:
        """Request the model to generate a response."""
        await self.send_json({"type": "response.create"})

    async def cancel_response(self, *, response_id: str | None = None) -> None:
        """Cancel the current or a specific in-progress response."""
        payload: dict[str, Any] = {"type": "response.cancel"}
        if response_id is not None:
            payload["response_id"] = response_id
        await self.send_json(payload)

    async def register_tools(self, tools: list[Any]) -> None:
        """Register tools by re-initializing the session with the tool list."""
        await self.initialize_session(tools=tools)

    async def submit_tool_result(self, *, call_id: str, output: str) -> None:
        """Submit a tool call result using the conversation_item schema.

        Source: GlassAgents/backend/realtime/client.py lines 199-214
        """
        await self.send_json(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            }
        )

    async def iter_normalized_events(self) -> AsyncIterator[NormalizedRealtimeEventFull]:
        """Yield normalized events from the realtime stream.

        Wraps the inherited iter_events() with two-stage normalization:
          Stage 1: normalize_event() — alias mapping (response.audio.* → canonical)
          Stage 2: _to_normalized_runtime_event() — type routing to NormalizedRealtimeEventTypes

        Do NOT override iter_events() — it is inherited from BaseRealtimeWebsocketClient.
        """
        async for event in self.iter_events():
            yield self._to_normalized_runtime_event(event)


__all__ = [
    "OpenAIRealtimeClient",
    "OpenAIRealtimeConfig",
    "OPENAI_REALTIME_CAPABILITIES",
    "RealtimeAudioEventNames",
    "OUTPUT_AUDIO_SAMPLE_RATE",
]
