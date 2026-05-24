"""Realtime provider type contracts.

String constants are frozen — any change requires a coordinated GlassAgents migration PR.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict, runtime_checkable

# PCM16 24 kHz — matches OpenAI and Gemini defaults;
# prep for ElevenLabs 16kHz via session_sample_rate override
INPUT_AUDIO_SAMPLE_RATE: int = 24_000


class NormalizedRealtimeEventTypes:
    """String constants for normalized realtime event types.

    These values are FROZEN — any change requires a coordinated GlassAgents migration PR.
    Source: GlassAgents/backend/realtime/contracts.py (verified 2026-05-24).
    """

    SESSION_READY = "session.ready"
    RESPONSE_AUDIO_DELTA = "response.audio.delta"
    RESPONSE_AUDIO_DONE = "response.audio.done"
    RESPONSE_DONE = "response.done"
    RESPONSE_CREATED = "response.created"
    INPUT_SPEECH_STARTED = "input.speech.started"
    INPUT_SPEECH_STOPPED = "input.speech.stopped"
    INPUT_AUDIO_COMMITTED = "input.audio.committed"
    TOOL_CALL_COMPLETED = "tool.call.completed"
    TOOL_CALL_CANCELLED = "tool.call.cancelled"
    ERROR = "error"
    UNHANDLED = "provider.event.unhandled"


class NormalizedRealtimeEvent(TypedDict, total=False):
    """Envelope for normalized events from any realtime provider."""

    type: str
    payload: dict[str, Any]
    source: str
    raw: Any


@dataclass(frozen=True, slots=True)
class RealtimeProviderCapabilities:
    """Capabilities advertised by a realtime provider at registration time."""

    streaming_audio_input: bool
    streaming_audio_output: bool
    server_vad: bool
    manual_turn_commit_required: bool
    tool_calling: bool
    tool_result_submission_mode: str  # "conversation_item" | "provider_call_id"
    voice_selection: bool
    interruption_cancel: bool
    startup_validation: bool = True
    session_sample_rate: int = 24_000  # ElevenLabs 16kHz prep — do not remove (PROV-FUT-03)


@runtime_checkable
class RealtimeAdapterContract(Protocol):
    """Structural protocol for realtime provider adapters.

    Production providers implement this via structural typing (duck-typing).
    @runtime_checkable enables isinstance checks for mock conformance tests.
    """

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None: ...

    async def update_session(self, payload: dict[str, Any]) -> None: ...

    async def append_client_audio(self, pcm16_audio: bytes) -> None: ...

    async def commit_client_turn(self) -> None: ...

    async def create_response(self) -> None: ...

    async def cancel_response(self, *, response_id: str | None = None) -> None: ...

    async def register_tools(self, tools: list[Any]) -> None: ...

    async def submit_tool_result(self, *, call_id: str, output: str) -> None: ...

    def iter_normalized_events(self) -> AsyncIterator[NormalizedRealtimeEvent]: ...


__all__ = [
    "INPUT_AUDIO_SAMPLE_RATE",
    "NormalizedRealtimeEventTypes",
    "NormalizedRealtimeEvent",
    "RealtimeProviderCapabilities",
    "RealtimeAdapterContract",
]
