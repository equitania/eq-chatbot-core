"""Test model registry with fallback chains.

Single source of truth for which models the integration tests should use.
Each provider declares a primary model plus a fallback chain ordered by
ascending cost (cheapest first). The resolver in conftest.py validates the
primary against the live ``provider.list_models()`` response and walks the
fallback chain when the primary is unavailable.

This file is committed to the repository on purpose so model choices live
under version control. API keys and behaviour flags stay in tests/.env.test.

Conventions
-----------
- ``primary`` MUST be the cheapest available model in the chain.
- ``fallbacks`` are ordered by ascending cost.
- Update the registry when the test report shows a "WARN: primary deprecated"
  row in the Models In Use section. The fallback chain prevents test breakage
  in the meantime, but a fallback means action is required.
- ``cost_hint`` is a free-form label. Where the model is in
  ``eq_chatbot_core.services.cost_service`` PRICING, show concrete prices
  (e.g. ``"$0.15 / $0.60 per 1M tok"``). For gateways or deployment-dependent
  models, use ``"gateway"`` / ``"deployment-dependent"``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelChain:
    """A primary model with an ordered fallback chain.

    Attributes:
        primary: Model id used by default. MUST be cheapest available.
        fallbacks: Models tried (in order) when ``primary`` is unavailable.
            Ordered by ascending cost.
        cost_hint: Free-form pricing label rendered in the Markdown test
            report. e.g. ``"$0.15 / $0.60 per 1M tok"`` or ``"gateway"``.
        notes: Free-form rationale (model rotation cadence, caveats).
    """

    primary: str
    fallbacks: tuple[str, ...] = ()
    cost_hint: str = ""
    notes: str = ""

    @property
    def candidates(self) -> tuple[str, ...]:
        """Primary first, then fallbacks — the order the resolver tries."""
        return (self.primary, *self.fallbacks)


# Keys map to fixtures and report rows in conftest.py.
# Two-level keys (e.g. "langdock.anthropic") denote sub-backends within
# a provider that share the same API key but draw from different model
# namespaces.
MODELS: dict[str, ModelChain] = {
    "openai": ModelChain(
        primary="gpt-4o-mini",
        fallbacks=("gpt-4.1-nano",),
        cost_hint="$0.15 / $0.60 per 1M tok",
        notes="Cheapest tier; gpt-4.1-nano ($0.10/$0.40) would be cheaper "
        "but is positioned as fallback because gpt-4o-mini has wider "
        "feature support (e.g. response_format json_object).",
    ),
    "anthropic": ModelChain(
        primary="claude-haiku-4-5-20251001",
        fallbacks=("claude-haiku-4-5",),
        cost_hint="$1.00 / $5.00 per 1M tok",
        notes="Anthropic's /v1/models returns dated aliases. The dated "
        "claude-haiku-4-5-20251001 is the cataloged primary; the unversioned "
        "claude-haiku-4-5 floats to the latest minor and stays a fallback "
        "(it works for chat but isn't in list_models, so it triggers INFO). "
        "claude-3-haiku-20240307 retired 2026-04.",
    ),
    "langdock.openai": ModelChain(
        primary="gpt-5.2",
        fallbacks=("gpt-5.4-mini", "gpt-5.4", "gpt-5.5", "gpt-5.1"),
        cost_hint="LangDock gateway (see langdock.com pricing)",
        notes="LangDock rotates GPT-5.x slugs frequently. Snapshot 2026-05-08.",
    ),
    "langdock.anthropic": ModelChain(
        primary="claude-sonnet-4-6-default",
        fallbacks=("claude-opus-4-7-default", "claude-opus-4-6-default"),
        cost_hint="LangDock gateway (see langdock.com pricing)",
        notes="LangDock uses '-default' suffix for stable Anthropic aliases.",
    ),
    "openrouter": ModelChain(
        primary="deepseek/deepseek-v4-flash",
        fallbacks=("openai/gpt-4o-mini",),
        cost_hint="OpenRouter gateway (see openrouter.ai/models)",
        notes="Reasoning models truncate at low max_tokens (see test_system_message).",
    ),
    "mammouth": ModelChain(
        primary="gpt-4.1-nano",
        fallbacks=("gpt-4.1-mini",),
        cost_hint="$0.10 / $0.40 per 1M tok",
    ),
    "azure": ModelChain(
        primary="Phi-4",
        fallbacks=("gpt-4o", "DeepSeek-R1"),
        cost_hint="deployment-dependent",
        notes="Use the exact deployed model name in your Azure resource.",
    ),
    "vertex": ModelChain(
        primary="gemini-2.5-flash",
        fallbacks=("gemini-1.5-flash",),
        cost_hint="$0.15 / $0.60 per 1M tok",
    ),
    "local": ModelChain(
        primary="phi-4-mini",
        fallbacks=("nvidia/nemotron-3-nano",),
        cost_hint="$0 (local)",
        notes="Match what is downloaded in your local LM Studio / Ollama.",
    ),
}


# Test behaviour constants (formerly env vars in .env.test).
# These are not secrets and benefit from version control.
#
# 300 tokens is calibrated for reasoning-heavy models: gemma-4-e4b can
# consume 95+ tokens on internal reasoning for a one-word prompt, leaving
# the visible "content" empty if max_tokens is below ~200. 300 gives
# breathing room for reasoning + actual response. Cost stays negligible
# (~$0.002 per integration run on gpt-4o-mini).
TEST_MAX_TOKENS = 300
TEST_TIMEOUT = 30
