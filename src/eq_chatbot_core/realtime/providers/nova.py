"""AWS Nova Sonic realtime provider stub. Production implementation planned for v1.9.0.
get_realtime_provider("nova_sonic") resolves correctly (D-08) but every method raises
NotImplementedError pointing to the target version. Stdlib-only (Pitfall 7)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

_MSG = "Nova Sonic not implemented; available in v1.9.0"
class NovaSonicStub:
    """AWS Nova Sonic placeholder. Production implementation in v1.9.0."""
    async def connect(self) -> None: raise NotImplementedError(_MSG)
    async def close(self) -> None: raise NotImplementedError(_MSG)
    async def initialize_session(
        self, *, instructions: str | None = None, voice: str | None = None, tools: list[Any] | None = None
    ) -> None: raise NotImplementedError(_MSG)
    async def update_session(self, payload: dict[str, Any]) -> None: raise NotImplementedError(_MSG)
    async def append_client_audio(self, pcm16_audio: bytes) -> None: raise NotImplementedError(_MSG)
    async def commit_client_turn(self) -> None: raise NotImplementedError(_MSG)
    async def create_response(self) -> None: raise NotImplementedError(_MSG)
    async def cancel_response(self, *, response_id: str | None = None) -> None: raise NotImplementedError(_MSG)
    async def register_tools(self, tools: list[Any]) -> None: raise NotImplementedError(_MSG)
    async def submit_tool_result(self, *, call_id: str, output: str) -> None: raise NotImplementedError(_MSG)
    def iter_normalized_events(self) -> AsyncIterator[Any]: raise NotImplementedError(_MSG)
__all__ = ["NovaSonicStub"]
