"""
Live integration test for ElevenLabs Conversational AI provider (QUAL-03).

Requires ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID environment variables.
ELEVENLABS_BASE_URL defaults to wss://api.elevenlabs.io (global endpoint).
For EU data residency tests, set ELEVENLABS_BASE_URL=wss://api.eu.residency.elevenlabs.io.
Test is automatically skipped when credentials are absent.

Run with:
    pytest -m integration tests/integration/test_realtime_elevenlabs.py -v
"""

import os

import pytest

# Self-skip when the [realtime] extra (websockets) is not installed.
# Without this guard the provider import / connect fails hard instead of skipping. QUAL-03 is optional.
pytest.importorskip("websockets")

from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes  # noqa: E402
from eq_chatbot_core.realtime.providers.elevenlabs import (  # noqa: E402
    ElevenLabsRealtimeClient,
    ElevenLabsRealtimeConfig,
)

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("ELEVENLABS_API_KEY") or not os.getenv("ELEVENLABS_AGENT_ID"),
    reason="ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID not set — skipping ElevenLabs integration test",
)
@pytest.mark.asyncio
async def test_elevenlabs_session_ready_and_disconnect() -> None:
    """QUAL-03: Connect to real ElevenLabs agent, receive SESSION_READY, send 100ms PCM16 silence, disconnect cleanly.

    No commit_client_turn() — ElevenLabs uses server-side VAD.
    No initialize_session() call needed for this smoke test (server sends conversation_initiation_metadata
    automatically after WebSocket connect; consumer calls initialize_session() only to override defaults).

    Flow:
        1. Open WebSocket connection via async context manager
        2. Iterate normalized events until SESSION_READY is received (server-initiated, no setup call needed)
        3. Send 100ms of PCM16 silence (1600 samples * 2 bytes = 3200 bytes at 16 kHz mono)
        4. Async context manager __aexit__ triggers clean close()

    Note: 16 kHz differs from Gemini/OpenAI 24 kHz — PROV-FUT-03 session_sample_rate=16_000.
    """
    config = ElevenLabsRealtimeConfig(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        agent_id=os.environ["ELEVENLABS_AGENT_ID"],
        base_url=os.getenv("ELEVENLABS_BASE_URL", "wss://api.elevenlabs.io"),
    )
    async with ElevenLabsRealtimeClient(config) as client:
        # Step 2: SESSION_READY arrives from server after WS connect (server-initiated)
        async for event in client.iter_normalized_events():
            assert event["type"] == NormalizedRealtimeEventTypes.SESSION_READY, (
                f"Expected SESSION_READY as first event, got: {event['type']}"
            )
            break

        # Step 3: Send 100ms of silence at 16 kHz mono PCM16 = 1600 samples * 2 bytes = 3200 bytes
        # (16 kHz differs from Gemini/OpenAI 24 kHz — PROV-FUT-03)
        silence = b"\x00\x00" * 1600
        await client.append_client_audio(silence)
        # No commit_client_turn() — ElevenLabs server VAD handles turn detection

    # Step 4: async with __aexit__ calls close() — clean disconnect (QUAL-03 verified)
