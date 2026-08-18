"""Model capability catalog.

Resolves per-model *capabilities* (vision, audio, files, tools, reasoning),
context/output *limits* and per-1k-token *pricing* across all supported
providers from a single, curated Equitania catalog.

Data source: the Equitania-hosted ``capability_catalog.json`` (Single Source of
Truth, maintained centrally by the ``eq-model-catalog`` sync tool). A snapshot
is bundled under ``data/capability_catalog.json`` as an offline fallback;
:meth:`CapabilityCatalog.from_remote` fetches the live file and degrades
gracefully to the snapshot on any network error.

Unlike the runtime provider adapters (which guess capabilities from the model
name), this catalog carries hand-verified flags and unifies the pricing source.
Each model entry lists ``aliases`` — the per-provider technical model ids — so a
configured ``model_id`` maps back to the canonical entry regardless of provider.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, TypedDict

from eq_chatbot_core.providers.temperature_constraints import strip_provider_prefix

_logger = logging.getLogger(__name__)

# Default hosting location. Overridable per deployment (e.g. via an Odoo
# ``ir.config_parameter``) by passing an explicit URL to ``from_remote``.
DEFAULT_CATALOG_URL = "https://data.ownerp.io/ai/capability_catalog.json"

_SNAPSHOT_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "capability_catalog.json"))

# Capability keys the catalog tracks (order defines the canonical output shape).
CAPABILITY_KEYS: tuple[str, ...] = (
    "image_input",
    "audio_input",
    "file_input",
    "audio_output",
    "image_output",
    "tools",
    "reasoning",
    "streaming",
)


class ModelCapabilities(TypedDict, total=False):
    """Resolved capability/limit/pricing bundle for a single model."""

    # Capabilities (booleans)
    image_input: bool
    audio_input: bool
    file_input: bool
    audio_output: bool
    image_output: bool
    tools: bool
    reasoning: bool
    streaming: bool
    # Limits
    context_length: int
    max_output_tokens: int
    # Pricing (USD per 1k tokens)
    input_per_1k: float
    output_per_1k: float
    # Provenance
    canonical_id: str
    display_name: str


class CapabilityCatalog:
    """Lookup of model capabilities/limits/pricing, backed by the Equitania catalog."""

    def __init__(self, raw: dict[str, Any]):
        self._raw = raw or {}
        self._defaults: dict[str, Any] = dict(self._raw.get("capability_defaults") or {})
        self.capability_meta: dict[str, Any] = dict(self._raw.get("capability_meta") or {})
        self.providers: dict[str, Any] = dict(self._raw.get("providers") or {})
        self.currency: str = str(self._raw.get("currency") or "USD")

        # Index by normalized alias/id -> list of (preferred_providers, entry).
        # A canonical id may be reachable through several providers, so we keep a
        # list and disambiguate on the requested provider at lookup time.
        self._entries: dict[str, list[tuple[frozenset[str], dict[str, Any]]]] = {}
        for model in self._raw.get("models") or []:
            if not isinstance(model, dict):
                continue
            providers = frozenset(str(p) for p in (model.get("providers") or []))
            keys = set()
            if model.get("id"):
                keys.add(str(model["id"]))
                keys.add(strip_provider_prefix(str(model["id"])))
            for alias in model.get("aliases") or []:
                keys.add(str(alias))
                keys.add(strip_provider_prefix(str(alias)))
            for key in keys:
                norm = key.lower()
                if norm:
                    self._entries.setdefault(norm, []).append((providers, model))

    # ----- Constructors ---------------------------------------------------

    @classmethod
    def from_snapshot(cls) -> CapabilityCatalog:
        """Build the catalog from the bundled offline snapshot."""
        with open(_SNAPSHOT_PATH, encoding="utf-8") as fh:
            return cls(json.load(fh))

    @classmethod
    def from_remote(cls, url: str | None = None, timeout: float = 10.0) -> CapabilityCatalog:
        """Fetch the hosted Equitania catalog; fall back to the bundled snapshot."""
        try:
            import httpx

            from eq_chatbot_core.utils.url_validation import build_validating_transport

            # `url` is caller-supplied, so the request is SSRF-checked instead of
            # being trusted to point at the Equitania catalog.
            with httpx.Client(transport=build_validating_transport(), timeout=timeout) as client:
                resp = client.get(url or DEFAULT_CATALOG_URL)
            resp.raise_for_status()
            return cls(resp.json())
        except Exception as e:  # network/parse failure -> offline fallback
            _logger.warning("Capability catalog remote fetch failed, using snapshot: %s", e)
            return cls.from_snapshot()

    # ----- Lookup ---------------------------------------------------------

    def lookup(self, model_id: str, provider: str | None = None) -> ModelCapabilities | None:
        """Return the capability/limit/pricing bundle for ``model_id``.

        Resolution order: exact (provider-prefixed) id -> exact normalized id ->
        longest-prefix match. When several catalog entries share an id, the one
        whose ``providers`` contains ``provider`` is preferred.
        Returns ``None`` if the model is unknown to the catalog.
        """
        if not model_id:
            return None

        norm = strip_provider_prefix(model_id).lower()
        full = model_id.lower()

        for key in (full, norm):
            entry = self._match_key(key, provider)
            if entry is not None:
                return self._build(entry)

        # Longest-prefix fallback (e.g. "claude-3-7-sonnet-20250219" -> "claude-3-7-sonnet").
        best_key = ""
        for key in self._entries:
            if len(key) > 2 and norm.startswith(key) and len(key) > len(best_key):
                best_key = key
        if best_key:
            entry = self._match_key(best_key, provider)
            if entry is not None:
                return self._build(entry)
        return None

    def _match_key(self, key: str, provider: str | None) -> dict[str, Any] | None:
        candidates = self._entries.get(key)
        if not candidates:
            return None
        if provider:
            for providers, entry in candidates:
                if provider in providers:
                    return entry
        return candidates[0][1]

    def _build(self, entry: dict[str, Any]) -> ModelCapabilities:
        caps = dict(entry.get("capabilities") or {})
        limits = dict(entry.get("limits") or {})
        pricing = dict(entry.get("pricing") or {})
        result: ModelCapabilities = {}
        for cap in CAPABILITY_KEYS:
            # CAPABILITY_KEYS holds exactly the TypedDict's keys, but mypy
            # cannot prove that for a loop variable.
            result[cap] = bool(caps.get(cap, self._defaults.get(cap, False)))  # type: ignore[literal-required]
        if limits.get("context_length") is not None:
            result["context_length"] = int(limits["context_length"])
        if limits.get("max_output_tokens") is not None:
            result["max_output_tokens"] = int(limits["max_output_tokens"])
        result["input_per_1k"] = round(float(pricing.get("input_per_1k") or 0.0), 6)
        result["output_per_1k"] = round(float(pricing.get("output_per_1k") or 0.0), 6)
        result["canonical_id"] = str(entry.get("id") or "")
        result["display_name"] = str(entry.get("display_name") or entry.get("id") or "")
        return result
