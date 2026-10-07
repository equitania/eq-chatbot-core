"""Token estimate, context window, capability catalog and realtime configs carry no model tables."""

import tomllib
from importlib import resources
from pathlib import Path

import pytest

from tests.wire_server import Reply

pytestmark = pytest.mark.unit


def test_estimate_tokens_is_the_same_for_every_model():
    from eq_chatbot_core.security.rate_limit import estimate_tokens

    text = "Hallo Welt, dies ist ein Test."
    assert estimate_tokens(text) == estimate_tokens(text, model="anything") == estimate_tokens(text, "other") > 0


def test_context_length_is_passed_not_looked_up():
    from eq_chatbot_core.rag.context_manager import ContextWindowManager

    assert ContextWindowManager(model="any").max_tokens == ContextWindowManager.DEFAULT_CONTEXT_LENGTH
    assert ContextWindowManager(model="any", context_length=32000).max_tokens == 32000
    assert not hasattr(ContextWindowManager, "MODEL_LIMITS")


@pytest.mark.parametrize("bad", [0, -1])
def test_context_length_must_be_positive(bad):
    """A zero or negative window must not silently become the 128000 fallback."""
    from eq_chatbot_core.rag.context_manager import ContextWindowManager

    with pytest.raises(ValueError, match="context_length"):
        ContextWindowManager(model="any", context_length=bad)


def test_context_length_fallback_is_logged(caplog):
    """Without context_length the 128000 fallback is used, and said so — never silently."""
    from eq_chatbot_core.rag.context_manager import ContextWindowManager

    with caplog.at_level("WARNING", logger="eq_chatbot_core.rag.context_manager"):
        ContextWindowManager(model="any")
    assert "128000" in caplog.text and "context_length=" in caplog.text

    caplog.clear()
    with caplog.at_level("WARNING", logger="eq_chatbot_core.rag.context_manager"):
        ContextWindowManager(model="any", context_length=32000)
    assert caplog.text == ""


def test_catalog_is_empty_when_the_remote_fetch_fails(wire_server, caplog):
    from eq_chatbot_core.services.capability_catalog import CapabilityCatalog

    wire_server.expect("GET", "/catalog.json", Reply(500, {"error": "down"}))
    with caplog.at_level("WARNING", logger="eq_chatbot_core.services.capability_catalog"):
        catalog = CapabilityCatalog.from_remote(f"{wire_server.root_url}/catalog.json")
    assert catalog.lookup("any-model") is None
    assert "catalog is empty" in caplog.text


def test_no_catalog_snapshot_ships_with_the_package():
    from eq_chatbot_core.services.capability_catalog import CapabilityCatalog

    data = resources.files("eq_chatbot_core") / "data"
    assert not (data / "capability_catalog.json").is_file()
    assert not (data / "capability_overrides.json").is_file()
    assert not hasattr(CapabilityCatalog, "from_snapshot")

    pyproject = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    packaged = [*wheel.get("artifacts", []), *wheel.get("exclude", []), *wheel.get("force-include", {})]
    assert not [p for p in packaged if "capability_" in p]


def test_realtime_configs_have_no_default_model():
    from eq_chatbot_core.realtime.providers.gemini_live import GeminiLiveClient, GeminiLiveConfig
    from eq_chatbot_core.realtime.providers.openai import OpenAIRealtimeClient, OpenAIRealtimeConfig

    assert OpenAIRealtimeConfig(api_key="k").model == ""
    assert GeminiLiveConfig(api_key="k").model == ""
    with pytest.raises(ValueError, match="model"):
        OpenAIRealtimeClient(OpenAIRealtimeConfig(api_key="k"))
    with pytest.raises(ValueError, match="model"):
        GeminiLiveClient(GeminiLiveConfig(api_key="k"))
