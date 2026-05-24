"""
Live integration test for OpenAI Realtime provider.

Requires OPENAI_API_KEY environment variable (or tests/.env.test entry).
Test is automatically skipped when the key is absent.

Run with:
    pytest -m integration tests/integration/test_realtime_openai_live.py -v
"""

import os

import pytest

# Self-skip when the [realtime] extra (websockets) is not installed, even if
# OPENAI_API_KEY is present. Without this guard the provider import / connect
# fails hard instead of skipping. SC-3 is an optional live test.
pytest.importorskip("websockets")

from eq_chatbot_core.realtime.contracts import NormalizedRealtimeEventTypes  # noqa: E402
from eq_chatbot_core.realtime.providers.openai import (  # noqa: E402
    OpenAIRealtimeClient,
    OpenAIRealtimeConfig,
)

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping live integration test",
)
@pytest.mark.asyncio
async def test_openai_realtime_session_ready_and_pcm_chunk() -> None:
    """SC-3: Connect to OpenAI Realtime API, receive SESSION_READY, send PCM16 chunk, close cleanly.

    Flow:
        1. Open WebSocket connection (async context manager)
        2. Iterate normalized events until SESSION_READY is received
        3. Send 100ms of PCM16 silence (4800 bytes at 24kHz mono)
        4. Async context manager __aexit__ triggers clean close()
    """
    config = OpenAIRealtimeConfig(
        api_key=os.environ["OPENAI_API_KEY"],
        include_turn_detection=False,  # manual turn control for predictable test flow
    )
    async with OpenAIRealtimeClient(config) as client:
        # Step 2: Wait for SESSION_READY — first event must be session.created/updated
        async for event in client.iter_normalized_events():
            assert event["type"] == NormalizedRealtimeEventTypes.SESSION_READY, (
                f"Expected SESSION_READY as first event, got: {event['type']}"
            )
            break

        # Step 3: Send 100ms of silence at 24kHz mono PCM16 = 2400 samples * 2 bytes = 4800 bytes
        silence = b"\x00\x00" * 2400
        await client.append_client_audio(silence)

    # Step 4: async with __aexit__ calls close() — clean disconnect (SC-3 verified)
