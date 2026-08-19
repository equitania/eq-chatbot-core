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
- ``cost_hint`` is a free-form label shown in the Markdown test report to keep
  model choices cost-aware (e.g. ``"$0.15 / $0.60 per 1M tok"``). For gateways
  or deployment-dependent models, use ``"gateway"`` /
  ``"deployment-dependent"``. It is documentation only — the library does not
  calculate costs.
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
        primary="mistralai/mistral-nemo",
        fallbacks=("meta-llama/llama-3.1-8b-instruct", "openai/gpt-4o-mini"),
        cost_hint="$0.02 / $0.03 per 1M tok",
        notes="Picked the cheapest model that passes the test "
        "contract (simple completion + ACKNOWLEDGED system message). "
        "mistral-nemo is 12B and tokenizes English compactly. Avoid reasoning "
        "models like deepseek/deepseek-v4-flash here; they cost more and "
        "burn most of max_tokens on internal reasoning_content.",
    ),
    "mammouth": ModelChain(
        primary="gpt-5.4-nano",
        fallbacks=("gpt-4.1-nano", "gemini-2.5-flash-lite", "gpt-4.1-mini"),
        cost_hint="~$0.05 / $0.40 per 1M tok (gateway, passthrough)",
        notes="Mammouth is a unified gateway; its rates follow the upstream "
        "provider rates approximately. gpt-5.4-nano "
        "is the newer / cheaper-input GPT nano variant, verified to pass the "
        "test contract (simple completion + ACKNOWLEDGED). gpt-5-nano is "
        "skipped: Mammouth metadata reports supports_reasoning=False but the "
        "model burns through max_tokens=20 with empty content, suggesting "
        "the catalog flag is wrong for that variant.",
    ),
    "local": ModelChain(
        primary="phi-4-mini",
        fallbacks=("nvidia/nemotron-3-nano",),
        cost_hint="$0 (local)",
        notes="Match what is downloaded in your local LM Studio / Ollama.",
    ),
    "litellm": ModelChain(
        primary="qwen3.6-35b-a3b",
        fallbacks=(),
        cost_hint="gateway (deployment-dependent)",
        notes="OpenAI-compatible gateway with no fixed endpoint. Primary matches "
        "the CCSolutions.io LiteLLM proxy chat model; override per deployment via "
        "LITELLM_TEST_MODEL. The resolver validates against the gateway's "
        "list_models(), so set this to a model your endpoint actually serves.",
    ),
    "ionos": ModelChain(
        primary="meta-llama/Meta-Llama-3.1-8B-Instruct",
        fallbacks=("mistralai/Mistral-Nemo-Instruct-2407", "meta-llama/Llama-3.3-70B-Instruct"),
        cost_hint="~$0.16 per 1M tok (EU-hosted, Berlin/de-txl)",
        notes="IONOS AI Model Hub — OpenAI-compatible EU gateway. Primary is the "
        "cheapest 8B chat model; override via IONOS_TEST_MODEL. The resolver "
        "validates against the live /v1/models response. Requires IONOS_API_KEY "
        "(base_url defaults to the official IONOS endpoint).",
    ),
    "melious": ModelChain(
        primary="nemotron-3-nano-30b-a3b",
        fallbacks=("gpt-oss-120b", "deepseek-v3.1"),
        cost_hint="not published by the API (sovereign EU gateway, 30B MoE / 3B active)",
        notes="Melious.ai — OpenAI-compatible sovereign EU gateway (60+ open-weight "
        "models). Primary is the captain-chosen 'nemotron-3-nano-30b-a3b' (19.08.2026), "
        "replacing 'minimax-428b-m3' which the gateway had silently retired — the "
        "resolver was falling back on every run and printing an ACTION warning. "
        "Verified live against /v1/models (73 entries) before the change; override "
        "via MELIOUS_TEST_MODEL. The resolver validates against the live /v1/models "
        "response and walks the fallback chain if the primary is unavailable. "
        "Primary + fallback ids verified live against /v1/models (71-model catalog). "
        "Requires MELIOUS_API_KEY (base_url defaults to the official Melious endpoint).",
    ),
    "privatemode": ModelChain(
        primary="kimi-latest",
        fallbacks=("gpt-oss-120b",),
        cost_hint="local proxy (confidential computing, EU)",
        notes="Privatemode.ai — end-to-end encrypted via a LOCAL privatemode-proxy "
        "container; there is no public API to reach directly. The primary uses the "
        "'-latest' alias on purpose: the vendor retires concrete model ids over time. "
        "Override via PRIVATEMODE_TEST_MODEL. Tests skip unless the proxy answers at "
        "PRIVATEMODE_BASE_URL (default http://localhost:8080/v1).",
    ),
}


# ---------------------------------------------------------------------------
# Retired overrides from tests/.env.test (removed 19.08.2026)
# ---------------------------------------------------------------------------
# Until 3.1.0 these values overrode the primaries above via <PROVIDER>_TEST_MODEL
# in tests/.env.test. That file was dropped when credentials moved to
# ~/.config/eq-chatbot/config.toml; the overrides are preserved here so nothing
# is lost, but deliberately NOT applied — they date from 21.06.2026 and conflict
# with the reasoning recorded in the entries above:
#
#   openai      gpt-5.4-mini               (registry: gpt-4o-mini, chosen for
#                                           wider feature support)
#   openrouter  deepseek/deepseek-v4-flash (registry explicitly warns against
#                                           this model — reasoning tokens eat
#                                           max_tokens and cost more)
#   mammouth    gpt-4.1-mini               (already listed above as a FALLBACK,
#                                           not as the verified primary)
#   melious     gpt-oss-20b                (registry primary is the
#                                           captain-chosen minimax-428b-m3)
#   local       liquid/lfm2.5-1.2b         (depends on what is downloaded
#                                           locally — machine-specific)
#
# To reinstate one, set <PROVIDER>_TEST_MODEL in the environment, or promote it
# to `primary` above and update the accompanying rationale.
#
# Verified live on 19.08.2026: the melious primary 'minimax-428b-m3' was no longer
# offered by the gateway, so the resolver fell back on every run. The retired
# override ('gpt-oss-20b') was closer to reality than the entry that called itself
# the chosen default — a reminder that a primary nobody re-checks goes stale
# silently. Replaced with 'nemotron-3-nano-30b-a3b' (captain's choice), verified
# against the live 73-model catalog together with both fallbacks.

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
