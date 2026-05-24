"""Unit tests for the realtime provider factory.

Tests registry population, factory resolution, and error handling.
"""

import pytest

from eq_chatbot_core.realtime.factory import (
    _get_realtime_provider_impl,
    build_default_realtime_provider_registry,
)
from eq_chatbot_core.realtime.mock import MockRealtimeProvider


@pytest.mark.unit
def test_registry_contains_mock() -> None:
    reg = build_default_realtime_provider_registry()
    assert "mock" in reg.registered_names()


@pytest.mark.unit
def test_get_realtime_provider_mock() -> None:
    provider = _get_realtime_provider_impl("mock")
    assert isinstance(provider, MockRealtimeProvider)


@pytest.mark.unit
def test_get_realtime_provider_case_insensitive() -> None:
    provider = _get_realtime_provider_impl("Mock")
    assert isinstance(provider, MockRealtimeProvider)


@pytest.mark.unit
def test_get_realtime_provider_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Available:"):
        _get_realtime_provider_impl("nonexistent_provider_xyz")


@pytest.mark.unit
def test_registry_registered_names_sorted() -> None:
    reg = build_default_realtime_provider_registry()
    names = reg.registered_names()
    assert names == sorted(names)  # must be alphabetically sorted
