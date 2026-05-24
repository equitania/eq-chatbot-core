# Realtime package — import guard and public re-exports.
# websockets-dependent symbols are gated behind get_realtime_provider().
from eq_chatbot_core.realtime.abc import RealtimeEvent, RealtimeProvider
from eq_chatbot_core.realtime.contracts import (
    INPUT_AUDIO_SAMPLE_RATE,
    NormalizedRealtimeEvent,
    NormalizedRealtimeEventTypes,
    RealtimeAdapterContract,
    RealtimeProviderCapabilities,
)

REALTIME_PROVIDERS: list[str] = ["openai", "gemini_live", "nova_sonic", "mock"]

__all__ = [
    "INPUT_AUDIO_SAMPLE_RATE",
    "NormalizedRealtimeEvent",
    "NormalizedRealtimeEventTypes",
    "RealtimeAdapterContract",
    "RealtimeProviderCapabilities",
    "RealtimeEvent",
    "RealtimeProvider",
    "REALTIME_PROVIDERS",
]
