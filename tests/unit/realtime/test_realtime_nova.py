"""Unit tests for NovaSonicStub.

No websockets mock required — NovaSonicStub is stdlib-only.
Coverage: PROV-08 structural conformance, D-07 error message, D-08 factory registration.
"""

import pytest

from eq_chatbot_core.realtime.contracts import RealtimeAdapterContract
from eq_chatbot_core.realtime.providers.nova import NovaSonicStub


class TestContractConformance:
    """PROV-08: NovaSonicStub must satisfy RealtimeAdapterContract structurally."""

    @pytest.mark.unit
    def test_isinstance_realtime_adapter_contract(self) -> None:
        """isinstance(NovaSonicStub(), RealtimeAdapterContract) must be True (PROV-08)."""
        stub = NovaSonicStub()
        assert isinstance(stub, RealtimeAdapterContract), (
            "NovaSonicStub must structurally satisfy RealtimeAdapterContract Protocol"
        )


class TestAllMethodsRaise:
    """PROV-08: Every method must raise NotImplementedError."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,kwargs",
        [
            ("connect", {}),
            ("close", {}),
            ("initialize_session", {}),
            ("update_session", {"payload": {}}),
            ("append_client_audio", {"pcm16_audio": b""}),
            ("commit_client_turn", {}),
            ("create_response", {}),
            ("cancel_response", {}),
            ("register_tools", {"tools": []}),
            ("submit_tool_result", {"call_id": "c1", "output": "{}"}),
        ],
    )
    async def test_async_method_raises(self, method: str, kwargs: dict) -> None:
        """Every async method must raise NotImplementedError immediately."""
        stub = NovaSonicStub()
        with pytest.raises(NotImplementedError):
            await getattr(stub, method)(**kwargs)

    @pytest.mark.unit
    def test_iter_normalized_events_raises(self) -> None:
        """iter_normalized_events is sync (returns AsyncIterator) — raises directly."""
        stub = NovaSonicStub()
        with pytest.raises(NotImplementedError):
            stub.iter_normalized_events()


class TestErrorMessages:
    """D-07: Error messages must reference v1.9.0."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_message_references_v190(self) -> None:
        """Error message must contain 'v1.9.0' (D-07 / PROV-08)."""
        stub = NovaSonicStub()
        with pytest.raises(NotImplementedError, match="v1.9.0"):
            await stub.connect()
