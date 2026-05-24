"""Queue-backed in-process realtime provider.

Stdlib-only — no optional extras required. Ships in the installed package for consumer
test suites. Satisfies RealtimeAdapterContract via structural typing (duck-typing).
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any


class MockRealtimeProvider:
    """Queue-backed in-process realtime provider.

    Stdlib-only — no optional extras required. Ships in the installed package for
    consumer test suites. Satisfies RealtimeAdapterContract via structural typing
    (duck-typing).
    """

    def __init__(self) -> None:
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._connected: bool = False

    def enqueue_event(self, event: dict[str, Any]) -> None:
        """Pre-load an event for iter_normalized_events to yield."""
        self._event_queue.put_nowait(event)

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def initialize_session(
        self,
        *,
        instructions: str | None = None,
        voice: str | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        pass

    async def update_session(self, payload: dict[str, Any]) -> None:
        pass

    async def append_client_audio(self, pcm16_audio: bytes) -> None:
        if len(pcm16_audio) % 2 != 0:
            raise ValueError(
                f"PCM16 audio must be even-length bytes, got {len(pcm16_audio)}"
            )

    async def commit_client_turn(self) -> None:
        pass

    async def create_response(self) -> None:
        pass

    async def cancel_response(self, *, response_id: str | None = None) -> None:
        pass

    async def register_tools(self, tools: list[Any]) -> None:
        pass

    async def submit_tool_result(self, *, call_id: str, output: str) -> None:
        pass

    def iter_normalized_events(self) -> AsyncIterator[dict[str, Any]]:
        """Return async generator yielding all queued events then stopping."""
        return self._iter_impl()

    async def _iter_impl(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._event_queue.get()
            yield event
            if self._event_queue.empty():
                break

    async def __aenter__(self) -> "MockRealtimeProvider":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()


__all__ = ["MockRealtimeProvider"]
