"""Tests for the model capability catalog.

Value assertions use a small inline raw dict (stable across snapshot refreshes);
the bundled snapshot is only smoke-tested for load + a well-known model.
"""

import pytest

from eq_chatbot_core.services.capability_catalog import CapabilityCatalog

# Minimal catalog-shaped fixture.
RAW = {
    "schema_version": "1.0",
    "capability_defaults": {
        "text_input": True,
        "text_output": True,
        "image_input": False,
        "audio_input": False,
        "file_input": False,
        "audio_output": False,
        "image_output": False,
        "tools": False,
        "reasoning": False,
        "streaming": True,
    },
    "capability_meta": {"image_input": {"group": "input", "label_en": "Vision"}},
    "providers": {"openai": {"label": "OpenAI"}, "azure": {"label": "Azure"}},
    "models": [
        {
            "id": "openai/gpt-4o",
            "display_name": "GPT-4o",
            "providers": ["openai", "azure", "openrouter"],
            "aliases": ["gpt-4o", "gpt-4o-2024-11-20", "azure/gpt-4o"],
            "capabilities": {"image_input": True, "audio_input": True, "tools": True},
            "limits": {"context_length": 128000, "max_output_tokens": 16384},
        },
        {
            "id": "anthropic/claude-3.7-sonnet",
            "display_name": "Claude 3.7 Sonnet",
            "providers": ["anthropic", "openrouter"],
            "aliases": ["claude-3-7-sonnet"],
            "capabilities": {"image_input": True, "tools": True, "reasoning": True},
            "limits": {"context_length": 200000, "max_output_tokens": 64000},
        },
    ],
}


@pytest.fixture
def catalog():
    return CapabilityCatalog(RAW)


class TestCapabilities:
    def test_resolved_flags(self, catalog):
        c = catalog.lookup("gpt-4o")
        assert c["image_input"] is True
        assert c["audio_input"] is True
        assert c["tools"] is True
        # Not set on the model -> falls back to defaults (False).
        assert c["audio_output"] is False
        assert c["reasoning"] is False

    def test_limits(self, catalog):
        c = catalog.lookup("gpt-4o")
        assert c["context_length"] == 128000
        assert c["max_output_tokens"] == 16384

    def test_reasoning_model(self, catalog):
        c = catalog.lookup("claude-3-7-sonnet")
        assert c["reasoning"] is True
        assert c["canonical_id"] == "anthropic/claude-3.7-sonnet"
        assert c["display_name"] == "Claude 3.7 Sonnet"


class TestMatching:
    def test_openrouter_style_prefix_stripped(self, catalog):
        assert catalog.lookup("openai/gpt-4o")["image_input"] is True

    def test_prefix_match_dated_variant(self, catalog):
        # "claude-3-7-sonnet-20250219" -> "claude-3-7-sonnet"
        c = catalog.lookup("claude-3-7-sonnet-20250219")
        assert c is not None
        assert c["reasoning"] is True

    def test_alias_match(self, catalog):
        assert catalog.lookup("gpt-4o-2024-11-20")["tools"] is True

    def test_unknown_returns_none(self, catalog):
        assert catalog.lookup("totally-unknown-xyz") is None

    def test_empty_returns_none(self, catalog):
        assert catalog.lookup("") is None


class TestProviderScoping:
    def test_provider_hint_disambiguates(self, catalog):
        # "gpt-4o" reachable via openai and azure; both map to the same entry here,
        # but the provider hint must not break resolution.
        assert catalog.lookup("gpt-4o", provider="azure")["canonical_id"] == "openai/gpt-4o"
        assert catalog.lookup("gpt-4o", provider="openai")["canonical_id"] == "openai/gpt-4o"


class TestMetadataExposed:
    def test_meta_and_providers_available(self, catalog):
        assert "image_input" in catalog.capability_meta
        assert "openai" in catalog.providers


class TestSnapshotAndRemote:
    def test_from_snapshot_loads_known_model(self):
        cat = CapabilityCatalog.from_snapshot()
        assert cat.lookup("gpt-4o") is not None

    def test_from_remote_falls_back_to_snapshot(self, monkeypatch):
        import httpx2

        def boom(*args, **kwargs):
            raise httpx2.ConnectError("offline")

        monkeypatch.setattr(httpx2, "get", boom)
        cat = CapabilityCatalog.from_remote(timeout=0.1)
        assert cat.lookup("gpt-4o") is not None
