"""Realtime provider registry and factory. Use get_realtime_provider() — do not import this module directly."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class RealtimeProviderDefinition:
    """Describes a registered realtime provider."""

    name: str  # canonical name, lowercase
    factory_fn: Callable[..., Any]  # callable(**kwargs) -> provider instance
    description: str = ""


class RealtimeProviderRegistry:
    """Registry of available realtime provider definitions."""

    def __init__(self) -> None:
        self._providers: dict[str, RealtimeProviderDefinition] = {}

    def register(self, definition: RealtimeProviderDefinition) -> None:
        """Register a provider definition under its canonical name."""
        self._providers[definition.name] = definition

    def registered_names(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._providers.keys())

    def get(self, name: str) -> RealtimeProviderDefinition | None:
        """Return the provider definition for the given name, or None."""
        return self._providers.get(name)


def build_default_realtime_provider_registry() -> RealtimeProviderRegistry:
    """Create a new registry pre-populated with the built-in providers.

    Phase 2 adds 'openai'. Phase 3 adds 'gemini_live' and 'nova_sonic'.
    All provider imports are deferred inside factory_fn to keep this module
    importable without any extras installed.
    """
    from eq_chatbot_core.realtime.mock import MockRealtimeProvider  # deferred — stdlib-only

    registry = RealtimeProviderRegistry()
    registry.register(
        RealtimeProviderDefinition(
            name="mock",
            factory_fn=lambda **kwargs: MockRealtimeProvider(),
            description="Queue-backed in-process mock provider for consumer test suites.",
        )
    )
    registry.register(
        RealtimeProviderDefinition(
            name="openai",
            factory_fn=lambda **kwargs: _build_openai_provider(**kwargs),
            description="OpenAI Realtime API — GPT speech-to-speech, server VAD, tool calling.",
        )
    )
    return registry


def _build_openai_provider(**kwargs: Any) -> Any:
    """Build an OpenAIRealtimeClient from keyword arguments.

    Deferred import keeps factory.py importable without the [realtime] extra installed.
    """
    # D-03 fail-fast: validate required kwargs before the deferred import so the
    # caller gets a clear library-native error regardless of [realtime] install state.
    if "api_key" not in kwargs:
        raise ValueError(
            "OpenAI realtime provider requires an 'api_key' keyword argument. "
            'Pass it via get_realtime_provider("openai", api_key="sk-...").'
        )

    from eq_chatbot_core.realtime.providers.openai import (  # noqa: PLC0415
        OpenAIRealtimeClient,
        OpenAIRealtimeConfig,
    )

    api_key = kwargs.pop("api_key")
    config = OpenAIRealtimeConfig(api_key=api_key, **kwargs)
    return OpenAIRealtimeClient(config)


_DEFAULT_REGISTRY: RealtimeProviderRegistry | None = None  # module-level singleton; lazy init
_REGISTRY_LOCK = threading.Lock()


def _get_realtime_provider_impl(name: str, **kwargs: Any) -> Any:
    """Resolve and instantiate a realtime provider by name.

    Called by realtime/__init__.py after the websockets import guard fires.
    Thread-safe via double-checked locking on _REGISTRY_LOCK.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        with _REGISTRY_LOCK:
            if _DEFAULT_REGISTRY is None:
                _DEFAULT_REGISTRY = build_default_realtime_provider_registry()
    name_lower = name.lower()
    definition = _DEFAULT_REGISTRY.get(name_lower)
    if definition is None:
        available = _DEFAULT_REGISTRY.registered_names()
        raise ValueError(
            f"Unknown realtime provider: {name}. Available: {', '.join(available)}"
        )
    return definition.factory_fn(**kwargs)


__all__ = [
    "RealtimeProviderRegistry",
    "RealtimeProviderDefinition",
    "_get_realtime_provider_impl",
    "build_default_realtime_provider_registry",
]
