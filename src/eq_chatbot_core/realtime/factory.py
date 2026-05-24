"""Realtime provider registry and factory. Use get_realtime_provider() — do not import this module directly."""

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
    return registry


_DEFAULT_REGISTRY: RealtimeProviderRegistry | None = None  # module-level singleton; lazy init


def _get_realtime_provider_impl(name: str, **kwargs: Any) -> Any:
    """Resolve and instantiate a realtime provider by name.

    Called by realtime/__init__.py after the websockets import guard fires.
    """
    global _DEFAULT_REGISTRY
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
