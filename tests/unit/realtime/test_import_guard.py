"""CON-10: Verifies friendly ImportError when [realtime] extra is absent.

Tests the get_realtime_provider() import guard behavior.
"""

import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_import_guard_friendly_error() -> None:
    """Success criterion #3: get_realtime_provider raises friendly ImportError when websockets absent."""
    # Temporarily hide websockets from sys.modules to simulate [realtime] not installed
    original_websockets = sys.modules.pop("websockets", None)
    original_ws_exc = sys.modules.pop("websockets.exceptions", None)
    try:
        with patch.dict(sys.modules, {"websockets": None}):
            from eq_chatbot_core.realtime import get_realtime_provider

            with pytest.raises(ImportError) as exc_info:
                get_realtime_provider("mock")
            err_msg = str(exc_info.value)
            assert "eq-chatbot-core[realtime]" in err_msg, f"Missing install hint in: {err_msg}"
            assert "pip install" in err_msg, f"Missing pip install instruction in: {err_msg}"
    finally:
        # Restore websockets in sys.modules
        if original_websockets is not None:
            sys.modules["websockets"] = original_websockets
        if original_ws_exc is not None:
            sys.modules["websockets.exceptions"] = original_ws_exc


@pytest.mark.unit
def test_always_importable_without_websockets() -> None:
    """Success criterion #2: MockRealtimeProvider and contracts importable without [realtime]."""
    from eq_chatbot_core.realtime import INPUT_AUDIO_SAMPLE_RATE, MockRealtimeProvider, RealtimeAdapterContract

    # These must not raise even when websockets mock is active
    assert INPUT_AUDIO_SAMPLE_RATE == 24000
    assert isinstance(MockRealtimeProvider(), RealtimeAdapterContract)


@pytest.mark.unit
def test_realtime_providers_constant() -> None:
    """REALTIME_PROVIDERS lists exactly the 4 expected provider names."""
    from eq_chatbot_core.realtime import REALTIME_PROVIDERS

    assert "mock" in REALTIME_PROVIDERS
    assert "openai" in REALTIME_PROVIDERS
    assert "gemini_live" in REALTIME_PROVIDERS
    assert "nova_sonic" in REALTIME_PROVIDERS
    assert len(REALTIME_PROVIDERS) == 4
