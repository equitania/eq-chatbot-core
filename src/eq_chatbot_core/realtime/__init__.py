"""
Realtime voice provider integration for eq-chatbot-core.

Usage (requires [realtime] extra: pip install eq-chatbot-core[realtime]):
    from eq_chatbot_core.realtime import get_realtime_provider
    provider = get_realtime_provider("openai", api_key="...")

MockRealtimeProvider and type contracts are always importable (no extra needed):
    from eq_chatbot_core.realtime import MockRealtimeProvider, RealtimeAdapterContract
"""

from typing import Any

REALTIME_PROVIDERS: list[str] = ["openai", "gemini_live", "elevenlabs", "mock"]


def get_realtime_provider(name: str, **kwargs: Any) -> Any:
    """Factory for realtime voice providers.

    Args:
        name: Provider name — one of "openai", "gemini_live", "elevenlabs", "mock"
        **kwargs: Provider-specific arguments (api_key, model, voice, ...)

    Returns:
        Provider instance satisfying RealtimeAdapterContract.

    Raises:
        ImportError: When eq-chatbot-core[realtime] is not installed.
        ValueError: When name is not a registered provider.
    """
    try:
        import websockets  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "eq-chatbot-core[realtime] is required for realtime voice support. "
            "Install with: pip install eq-chatbot-core[realtime]"
        ) from exc
    from eq_chatbot_core.realtime.factory import _get_realtime_provider_impl

    return _get_realtime_provider_impl(name, **kwargs)


# OpenAI realtime provider — importable only when [realtime] extra (websockets) is installed
try:
    from eq_chatbot_core.realtime.providers.openai import (  # noqa: E402
        OPENAI_REALTIME_CAPABILITIES,
        OpenAIRealtimeClient,
        OpenAIRealtimeConfig,
    )
except ImportError:
    pass

# Always importable (stdlib-only) — no websockets required for these imports
from eq_chatbot_core.realtime.abc import (  # noqa: E402
    AudioDeltaEvent,
    AudioDoneEvent,
    ErrorEvent,
    RealtimeEvent,
    RealtimeProvider,
    ResponseCreatedEvent,
    ResponseDoneEvent,
    SpeechStartedEvent,
    SpeechStoppedEvent,
)
from eq_chatbot_core.realtime.contracts import (  # noqa: E402
    INPUT_AUDIO_SAMPLE_RATE,
    NormalizedRealtimeEvent,
    NormalizedRealtimeEventTypes,
    RealtimeAdapterContract,
    RealtimeProviderCapabilities,
)
from eq_chatbot_core.realtime.mock import MockRealtimeProvider  # noqa: E402

__all__ = [
    "get_realtime_provider",
    "REALTIME_PROVIDERS",
    # Contracts
    "INPUT_AUDIO_SAMPLE_RATE",
    "NormalizedRealtimeEvent",
    "NormalizedRealtimeEventTypes",
    "RealtimeAdapterContract",
    "RealtimeProviderCapabilities",
    # ABC + events
    "RealtimeProvider",
    "RealtimeEvent",
    "AudioDeltaEvent",
    "AudioDoneEvent",
    "ResponseDoneEvent",
    "ResponseCreatedEvent",
    "SpeechStartedEvent",
    "SpeechStoppedEvent",
    "ErrorEvent",
    # Mock
    "MockRealtimeProvider",
    # OpenAI provider (requires [realtime] extra)
    "OpenAIRealtimeClient",
    "OpenAIRealtimeConfig",
    "OPENAI_REALTIME_CAPABILITIES",
]
