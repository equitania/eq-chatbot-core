"""Minimal ABC for realtime providers plus typed event dataclasses.

Production providers implement RealtimeAdapterContract (Protocol);
stubs and mocks inherit RealtimeProvider (ABC).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AudioDeltaEvent:
    """A chunk of audio output from the provider."""

    audio: bytes
    item_id: str
    response_id: str


@dataclass(frozen=True, slots=True)
class AudioDoneEvent:
    """Audio output for a response item is complete."""

    item_id: str
    response_id: str


@dataclass(frozen=True, slots=True)
class ResponseDoneEvent:
    """A response has finished generating."""

    response_id: str
    status: str
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ResponseCreatedEvent:
    """A new response has been created."""

    response_id: str


@dataclass(frozen=True, slots=True)
class SpeechStartedEvent:
    """The provider detected speech started (server VAD)."""

    item_id: str = ""


@dataclass(frozen=True, slots=True)
class SpeechStoppedEvent:
    """The provider detected speech stopped (server VAD)."""

    item_id: str = ""


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """An error occurred during the realtime session."""

    message: str
    error_type: str = "error"
    retriable: bool = False


RealtimeEvent = (
    AudioDeltaEvent
    | AudioDoneEvent
    | ResponseDoneEvent
    | ResponseCreatedEvent
    | SpeechStartedEvent
    | SpeechStoppedEvent
    | ErrorEvent
)
"""Union of all typed realtime event dataclasses."""


class RealtimeProvider(ABC):
    """Base class for realtime stubs and mocks.

    Production providers implement RealtimeAdapterContract via structural typing.
    """

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None: ...

    @abstractmethod
    def iter_normalized_events(self) -> AsyncIterator[Any]: ...


__all__ = [
    "RealtimeProvider",
    "RealtimeEvent",
    "AudioDeltaEvent",
    "AudioDoneEvent",
    "ResponseDoneEvent",
    "ResponseCreatedEvent",
    "SpeechStartedEvent",
    "SpeechStoppedEvent",
    "ErrorEvent",
]
