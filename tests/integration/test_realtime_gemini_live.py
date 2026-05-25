"""
Live integration test for Gemini Live provider — Vertex AI EU endpoint (QUAL-03 / SC-3).

Requires GEMINI_VERTEX_ACCESS_TOKEN and VERTEX_PROJECT_ID environment variables.
VERTEX_REGION defaults to europe-west4 (DSGVO-compliant Netherlands endpoint).
Test is automatically skipped when credentials are absent.

Run with:
    pytest -m integration tests/integration/test_realtime_gemini_live.py -v
"""

import os

import pytest

# Self-skip when the [realtime] extra (websockets) is not installed — same guard as openai live test.
# Without this guard the provider import / connect fails hard instead of skipping. QUAL-03 is optional.
pytest.importorskip("websockets")

from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes  # noqa: E402
from eq_chatbot_core.realtime.providers.gemini_live import (  # noqa: E402
    GeminiLiveClient,
    GeminiLiveConfig,
)

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("GEMINI_VERTEX_ACCESS_TOKEN") or not os.getenv("VERTEX_PROJECT_ID"),
    reason="GEMINI_VERTEX_ACCESS_TOKEN / VERTEX_PROJECT_ID not set — skipping Vertex EU integration test",
)
@pytest.mark.asyncio
async def test_gemini_live_vertex_eu_session_ready_and_pcm_chunk() -> None:
    """QUAL-03 / SC-3: Connect to Gemini Live Vertex EU, receive SESSION_READY, send PCM16, close cleanly.

    Uses europe-west4 (Netherlands) by default — DSGVO-compliant regional endpoint.
    If VERTEX_REGION is set, that region is used instead (fallback: europe-west1 Belgium).

    Flow:
        1. Open WebSocket connection via async context manager
        2. Call initialize_session() explicitly (Gemini requires explicit setup — differs from OpenAI)
        3. Iterate normalized events until SESSION_READY is received
        4. Send 100ms of PCM16 silence (4800 bytes at 24kHz mono)
        5. Commit audio turn (mandatory — Gemini has no server VAD)
        6. Async context manager __aexit__ triggers clean close()
    """
    config = GeminiLiveConfig(
        mode="vertex",
        access_token=os.environ["GEMINI_VERTEX_ACCESS_TOKEN"],
        project=os.environ["VERTEX_PROJECT_ID"],
        region=os.getenv("VERTEX_REGION", "europe-west4"),
    )
    async with GeminiLiveClient(config) as client:
        # Step 2: Explicitly send setup envelope (Gemini differs from OpenAI — no auto-init in _on_connected)
        await client.initialize_session()

        # Step 3: Wait for SESSION_READY — first normalized event must confirm session is active
        async for event in client.iter_normalized_events():
            assert event["type"] == NormalizedRealtimeEventTypes.SESSION_READY, (
                f"Expected SESSION_READY as first event, got: {event['type']}"
            )
            break

        # Step 4: Send 100ms of silence at 24kHz mono PCM16 = 2400 samples * 2 bytes = 4800 bytes
        silence = b"\x00\x00" * 2400
        await client.append_client_audio(silence)

        # Step 5: Commit audio turn (mandatory — Gemini has no server VAD, always requires manual commit)
        await client.commit_client_turn()

    # Step 6: async with __aexit__ calls close() — clean disconnect (QUAL-03 verified)
