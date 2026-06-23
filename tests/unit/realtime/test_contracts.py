"""
Byte-for-byte string assertions for NormalizedRealtimeEventTypes constants.
These values are CANONICAL — any change requires a coordinated GlassAgents migration PR.
See PITFALL-27 / PITFALL-29 in .planning/research/PITFALLS.md.
CON-13 requirement.
"""

import dataclasses

import pytest

from eq_chatbot_core.realtime.contracts import (
    INPUT_AUDIO_SAMPLE_RATE,
    NormalizedRealtimeEvent,
    NormalizedRealtimeEventFull,
    NormalizedRealtimeEventTypes,
    RealtimeAdapterContract,
    RealtimeProviderCapabilities,
)


@pytest.mark.unit
def test_event_type_string_values():
    """Byte-for-byte assertion of all 12 event type constants.

    These strings are the migration-safety gate for GlassAgents.
    Inline asserts (not a loop or helper) so pytest assertion rewriting shows
    exactly which constant drifted on failure.
    """
    assert NormalizedRealtimeEventTypes.SESSION_READY == "session.ready"
    assert NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DELTA == "response.audio.delta"
    assert NormalizedRealtimeEventTypes.RESPONSE_AUDIO_DONE == "response.audio.done"
    assert NormalizedRealtimeEventTypes.RESPONSE_DONE == "response.done"
    assert NormalizedRealtimeEventTypes.RESPONSE_CREATED == "response.created"
    assert NormalizedRealtimeEventTypes.INPUT_SPEECH_STARTED == "input.speech.started"
    assert NormalizedRealtimeEventTypes.INPUT_SPEECH_STOPPED == "input.speech.stopped"
    assert NormalizedRealtimeEventTypes.INPUT_AUDIO_COMMITTED == "input.audio.committed"
    assert NormalizedRealtimeEventTypes.TOOL_CALL_COMPLETED == "tool.call.completed"
    assert NormalizedRealtimeEventTypes.TOOL_CALL_CANCELLED == "tool.call.cancelled"
    assert NormalizedRealtimeEventTypes.ERROR == "error"
    assert NormalizedRealtimeEventTypes.UNHANDLED == "provider.event.unhandled"


@pytest.mark.unit
def test_event_type_count():
    """Verify exactly 12 public string attributes — future additions trigger CI failure."""
    attrs = [k for k, v in vars(NormalizedRealtimeEventTypes).items() if not k.startswith("_") and isinstance(v, str)]
    assert len(attrs) == 12


@pytest.mark.unit
def test_input_audio_sample_rate():
    """INPUT_AUDIO_SAMPLE_RATE must equal 24000."""
    assert INPUT_AUDIO_SAMPLE_RATE == 24_000
    assert INPUT_AUDIO_SAMPLE_RATE == 24000  # same value, decimal form


@pytest.mark.unit
def test_normalized_event_typeddict():
    """NormalizedRealtimeEvent TypedDict must have the expected required and optional keys.

    type and payload are required (defined on NormalizedRealtimeEvent directly).
    source and raw are optional (defined on NormalizedRealtimeEventFull with total=False).
    """
    from typing import get_type_hints

    required_hints = get_type_hints(NormalizedRealtimeEvent)
    assert "type" in required_hints
    assert "payload" in required_hints
    # source and raw are optional keys — live on NormalizedRealtimeEventFull
    assert "source" not in required_hints
    assert "raw" not in required_hints

    full_hints = get_type_hints(NormalizedRealtimeEventFull)
    assert "source" in full_hints
    assert "raw" in full_hints
    # Required keys are inherited
    assert "type" in full_hints
    assert "payload" in full_hints


@pytest.mark.unit
def test_capabilities_defaults():
    """RealtimeProviderCapabilities must have session_sample_rate=24000 and startup_validation=True as defaults."""
    fields = {
        f.name: f.default
        for f in dataclasses.fields(RealtimeProviderCapabilities)
        if f.default is not dataclasses.MISSING
    }
    assert fields["session_sample_rate"] == 24_000
    assert fields["startup_validation"] is True


@pytest.mark.unit
def test_capabilities_frozen():
    """RealtimeProviderCapabilities must be a frozen dataclass."""
    assert RealtimeProviderCapabilities.__dataclass_params__.frozen is True


@pytest.mark.unit
def test_adapter_contract_runtime_checkable():
    """RealtimeAdapterContract must be @runtime_checkable.

    Positive case: a class with all 11 method names satisfies the Protocol.
    Negative case: a class missing methods must NOT satisfy it.
    """

    class _FullImpl:
        async def connect(self): ...  # noqa: E704

        async def close(self): ...  # noqa: E704

        async def initialize_session(self, *, instructions=None, voice=None, tools=None): ...  # noqa: E704

        async def update_session(self, payload): ...  # noqa: E704

        async def append_client_audio(self, pcm16_audio): ...  # noqa: E704

        async def commit_client_turn(self): ...  # noqa: E704

        async def create_response(self): ...  # noqa: E704

        async def cancel_response(self, *, response_id=None): ...  # noqa: E704

        async def register_tools(self, tools): ...  # noqa: E704

        async def submit_tool_result(self, *, call_id, output): ...  # noqa: E704

        def iter_normalized_events(self): ...  # noqa: E704

    assert isinstance(_FullImpl(), RealtimeAdapterContract)

    class _MissingOne:
        async def connect(self): ...  # noqa: E704

        # intentionally missing close and all other methods

    assert not isinstance(_MissingOne(), RealtimeAdapterContract)
