"""Model pricing catalog.

Resolves per-1k-token prices for any model across all supported providers.

Data source: the community-maintained LiteLLM pricing database
(``model_prices_and_context_window.json``, MIT-licensed, updated daily). A
snapshot is bundled under ``data/model_prices.json`` as an offline fallback;
``from_remote()`` fetches the live file and degrades gracefully to the snapshot
on any network error.

Each upstream entry quotes ``input_cost_per_token`` / ``output_cost_per_token``
in USD per single token; this module exposes them as USD per 1,000 tokens
(:class:`ModelPricing`) to match the rest of the codebase.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, TypedDict

from eq_chatbot_core.providers.temperature_constraints import strip_provider_prefix

_logger = logging.getLogger(__name__)

LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

_SNAPSHOT_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "model_prices.json"))

# eq_chatbot provider key -> preferred ``litellm_provider`` values used to
# disambiguate when the same model id exists under several providers. An empty
# tuple means "do not scope by provider" (match purely on the model id).
_PROVIDER_MAP: dict[str, tuple[str, ...]] = {
    "openai": ("openai", "text-completion-openai"),
    "anthropic": ("anthropic",),
    "vertex": ("vertex_ai", "vertex_ai-language-models", "gemini"),
    "azure": ("azure", "azure_ai"),
    "openrouter": ("openrouter",),
    "mammouth": (),
    "langdock": (),  # LangDock proxies base models -> match by id only
    "ollama": (),
    "lm_studio": (),
}

# Local providers run on-device; there is no cloud token price to resolve.
_LOCAL_PROVIDERS = frozenset({"ollama", "lm_studio"})


class ModelPricing(TypedDict):
    """Per-1k-token price for a model."""

    input: float  # USD per 1k input tokens
    output: float  # USD per 1k output tokens


class PricingCatalog:
    """Lookup of per-1k-token prices, backed by the LiteLLM pricing database."""

    def __init__(self, raw: dict[str, Any]):
        # Index as {normalized_model_id: [(litellm_provider, ModelPricing), ...]}.
        # A model id may appear under multiple providers, so we keep a list and
        # disambiguate at lookup time.
        self._entries: dict[str, list[tuple[str, ModelPricing]]] = {}
        for key, val in (raw or {}).items():
            if not isinstance(val, dict):
                continue
            in_tok = val.get("input_cost_per_token")
            out_tok = val.get("output_cost_per_token")
            if in_tok is None and out_tok is None:
                continue
            pricing: ModelPricing = {
                "input": round((in_tok or 0.0) * 1000, 6),
                "output": round((out_tok or 0.0) * 1000, 6),
            }
            lprov = str(val.get("litellm_provider") or "")
            norm = strip_provider_prefix(key).lower()
            self._entries.setdefault(norm, []).append((lprov, pricing))
            full = key.lower()
            if full != norm:
                self._entries.setdefault(full, []).append((lprov, pricing))

    # ----- Constructors ---------------------------------------------------

    @classmethod
    def from_snapshot(cls) -> PricingCatalog:
        """Build the catalog from the bundled offline snapshot."""
        with open(_SNAPSHOT_PATH, encoding="utf-8") as fh:
            return cls(json.load(fh))

    @classmethod
    def from_remote(cls, timeout: float = 10.0) -> PricingCatalog:
        """Fetch the live LiteLLM database; fall back to the bundled snapshot."""
        try:
            import httpx

            resp = httpx.get(LITELLM_PRICING_URL, timeout=timeout)
            resp.raise_for_status()
            return cls(resp.json())
        except Exception as e:  # network/parse failure -> offline fallback
            _logger.warning("Pricing catalog remote fetch failed, using snapshot: %s", e)
            return cls.from_snapshot()

    # ----- Lookup ---------------------------------------------------------

    def lookup(self, model_id: str, provider: str | None = None) -> ModelPricing | None:
        """Return per-1k-token pricing for ``model_id`` or ``None`` if unknown.

        Resolution order: exact (provider-prefixed) id -> exact normalized id ->
        longest-prefix match. When ``provider`` is given, entries whose
        ``litellm_provider`` matches the mapped values are preferred.
        """
        if not model_id:
            return None
        if provider in _LOCAL_PROVIDERS:
            return None

        norm = strip_provider_prefix(model_id).lower()
        full = model_id.lower()
        preferred = _PROVIDER_MAP.get(provider or "", ())

        for key in (full, norm):
            hit = self._match_key(key, preferred)
            if hit is not None:
                return hit

        # Longest-prefix fallback (e.g. "claude-sonnet-4-5-20250929" -> "claude-sonnet-4-5").
        best_key = ""
        for key in self._entries:
            if len(key) > 2 and norm.startswith(key) and len(key) > len(best_key):
                best_key = key
        if best_key:
            return self._match_key(best_key, preferred)
        return None

    def _match_key(self, key: str, preferred: tuple[str, ...]) -> ModelPricing | None:
        candidates = self._entries.get(key)
        if not candidates:
            return None
        if preferred:
            for lprov, pricing in candidates:
                if lprov in preferred:
                    return pricing
        return candidates[0][1]
