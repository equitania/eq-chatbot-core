"""Tests for the model pricing catalog.

Value assertions use a small inline raw dict (stable across snapshot refreshes);
the bundled snapshot is only smoke-tested for load + a well-known model.
"""

import pytest

from eq_chatbot_core.services.pricing_catalog import PricingCatalog

# Minimal LiteLLM-shaped fixture (USD per single token).
RAW = {
    "gpt-4o": {
        "input_cost_per_token": 2.5e-06,
        "output_cost_per_token": 1e-05,
        "litellm_provider": "openai",
        "mode": "chat",
    },
    "azure/gpt-4o": {
        "input_cost_per_token": 5e-06,
        "output_cost_per_token": 2e-05,
        "litellm_provider": "azure",
        "mode": "chat",
    },
    "claude-sonnet-4-5": {
        "input_cost_per_token": 3e-06,
        "output_cost_per_token": 1.5e-05,
        "litellm_provider": "anthropic",
        "mode": "chat",
    },
    "text-embedding-3-small": {
        "input_cost_per_token": 2e-08,
        "output_cost_per_token": 0.0,
        "litellm_provider": "openai",
        "mode": "embedding",
    },
    "no-price-model": {"litellm_provider": "openai", "mode": "chat"},
}


@pytest.fixture
def catalog():
    return PricingCatalog(RAW)


class TestUnitConversion:
    """Per-token upstream values become per-1k-token."""

    def test_input_output_converted_to_per_1k(self, catalog):
        p = catalog.lookup("gpt-4o")
        assert p["input"] == pytest.approx(0.0025)
        assert p["output"] == pytest.approx(0.01)

    def test_embedding_zero_output(self, catalog):
        p = catalog.lookup("text-embedding-3-small")
        assert p["input"] == pytest.approx(0.00002)
        assert p["output"] == pytest.approx(0.0)


class TestMatching:
    def test_exact_match(self, catalog):
        assert catalog.lookup("claude-sonnet-4-5")["input"] == pytest.approx(0.003)

    def test_prefix_match_dated_variant(self, catalog):
        # "claude-sonnet-4-5-20250929" -> "claude-sonnet-4-5"
        p = catalog.lookup("claude-sonnet-4-5-20250929")
        assert p["input"] == pytest.approx(0.003)
        assert p["output"] == pytest.approx(0.015)

    def test_openrouter_style_prefix_stripped(self, catalog):
        # "openai/gpt-4o" -> "gpt-4o"
        assert catalog.lookup("openai/gpt-4o")["input"] == pytest.approx(0.0025)

    def test_unknown_returns_none(self, catalog):
        assert catalog.lookup("totally-unknown-xyz") is None

    def test_empty_returns_none(self, catalog):
        assert catalog.lookup("") is None

    def test_entry_without_price_skipped(self, catalog):
        assert catalog.lookup("no-price-model") is None


class TestProviderScoping:
    def test_provider_hint_prefers_matching_litellm_provider(self, catalog):
        # Same id "gpt-4o" exists for azure too; provider hint disambiguates.
        openai_p = catalog.lookup("gpt-4o", provider="openai")
        azure_p = catalog.lookup("gpt-4o", provider="azure")
        assert openai_p["input"] == pytest.approx(0.0025)
        assert azure_p["input"] == pytest.approx(0.005)

    def test_local_provider_returns_none(self, catalog):
        assert catalog.lookup("gpt-4o", provider="ollama") is None
        assert catalog.lookup("llama3", provider="lm_studio") is None


class TestSnapshotAndRemote:
    def test_from_snapshot_loads_known_model(self):
        cat = PricingCatalog.from_snapshot()
        assert cat.lookup("gpt-4o") is not None

    def test_from_remote_falls_back_to_snapshot(self, monkeypatch):
        import httpx

        def boom(*args, **kwargs):
            raise httpx.ConnectError("offline")

        monkeypatch.setattr(httpx, "get", boom)
        cat = PricingCatalog.from_remote(timeout=0.1)
        # Snapshot is bundled, so a well-known model still resolves.
        assert cat.lookup("gpt-4o") is not None
