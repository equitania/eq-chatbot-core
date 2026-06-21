"""
LLM cost calculation service.
"""

import logging
from typing import TypedDict

from eq_chatbot_core.providers.temperature_constraints import strip_provider_prefix

_logger = logging.getLogger(__name__)

# Lazily-built singleton over the bundled pricing snapshot. Used only as a
# gap-filler for models absent from the curated ``PRICING`` table below, so the
# curated (intentionally overriding) values always win.
_CATALOG = None
_CATALOG_LOADED = False


def _get_catalog():
    """Return the bundled :class:`PricingCatalog` (snapshot), or ``None``."""
    global _CATALOG, _CATALOG_LOADED
    if not _CATALOG_LOADED:
        _CATALOG_LOADED = True
        try:
            from eq_chatbot_core.services.pricing_catalog import PricingCatalog

            _CATALOG = PricingCatalog.from_snapshot()
        except Exception as e:  # missing snapshot / parse error -> static only
            _logger.warning("Pricing catalog unavailable, using static table only: %s", e)
            _CATALOG = None
    return _CATALOG


class ModelPricing(TypedDict):
    """Pricing structure for a model."""

    input: float  # USD per 1K input tokens
    output: float  # USD per 1K output tokens


# Pricing table (USD per 1K tokens)
# Last updated: February 2025
PRICING: dict[str, ModelPricing] = {
    # OpenAI - GPT series
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4": {"input": 0.03, "output": 0.06},
    # OpenAI - o-series reasoning models
    "o1": {"input": 0.015, "output": 0.06},
    "o1-mini": {"input": 0.003, "output": 0.012},
    "o1-preview": {"input": 0.015, "output": 0.06},
    "o3": {"input": 0.01, "output": 0.04},
    "o3-mini": {"input": 0.0011, "output": 0.0044},
    # Anthropic - Claude 4.x / 3.5 series
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5": {"input": 0.001, "output": 0.005},
    "claude-opus-4": {"input": 0.015, "output": 0.075},
    "claude-3-5-sonnet-latest": {"input": 0.003, "output": 0.015},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-5-haiku-latest": {"input": 0.001, "output": 0.005},
    "claude-3-opus-latest": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    # Mammouth AI models (pricing per 1K tokens, converted from per-million rates)
    "gpt-5.2-chat": {"input": 0.00175, "output": 0.014},
    "gpt-5.1-chat": {"input": 0.00125, "output": 0.01},
    "gpt-5-mini": {"input": 0.00025, "output": 0.002},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},
    # Google Gemini (via Vertex AI / Mammouth)
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.01},
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "gemini-2.0-flash-lite": {"input": 0.000075, "output": 0.0003},
    "mistral-large-latest": {"input": 0.002, "output": 0.006},
    "deepseek-chat": {"input": 0.00027, "output": 0.0011},
    "deepseek-reasoner": {"input": 0.00055, "output": 0.0022},
    # IONOS AI Model Hub (EU-hosted). Source: IONOS published rates in EUR per 1M
    # tokens, converted to USD per 1K tokens at EUR->USD ~1.08 (June 2026). IONOS
    # bills per token and rates can be contract-specific — verify before relying
    # on exact cost figures. Keys are provider-prefix-stripped (meta-llama/X -> X)
    # to match get_model_pricing()'s strip_provider_prefix() lookup.
    "Llama-3.3-70B-Instruct": {"input": 0.000702, "output": 0.000702},
    "Meta-Llama-3.1-8B-Instruct": {"input": 0.000162, "output": 0.000162},
    "Mistral-Small-24B-Instruct": {"input": 0.000108, "output": 0.000324},
    "Mistral-Nemo-Instruct-2407": {"input": 0.000162, "output": 0.000162},
    # Melious.ai (sovereign EU-hosted). Source: melious.ai/pricing in EUR per 1M
    # tokens, converted to USD per 1K tokens at EUR->USD ~1.08 (June 2026). Keys
    # are the live API model ids (verified against GET /v1/models). Image (flux-*)
    # and audio (whisper-*) models are billed per image / per minute, not per
    # token, so they are intentionally absent from this per-token table.
    # -- Chat / reasoning --
    "deepseek-r1-0528": {"input": 0.000702, "output": 0.002808},
    "deepseek-v3-0324": {"input": 0.000324, "output": 0.001026},
    "deepseek-v3.1": {"input": 0.000216, "output": 0.000864},
    "deepseek-v3.2": {"input": 0.000324, "output": 0.00054},
    "deepseek-v4-flash": {"input": 0.000162, "output": 0.000324},
    "deepseek-v4-pro": {"input": 0.001782, "output": 0.003564},
    "gemma-3-27b-it": {"input": 0.00027, "output": 0.00054},
    "gemma-4-26b-a4b": {"input": 0.00027, "output": 0.00054},
    "gemma-4-31b": {"input": 0.000108, "output": 0.000324},
    "gpt-oss-120b": {"input": 0.0000432, "output": 0.000216},
    "gpt-oss-20b": {"input": 0.0000324, "output": 0.0001404},
    "hermes-4-405b": {"input": 0.001026, "output": 0.003078},
    "hermes-4-70b": {"input": 0.0001296, "output": 0.000432},
    "holo2-30b-a3b": {"input": 0.000324, "output": 0.000756},
    "intellect-3": {"input": 0.000216, "output": 0.001134},
    "kimi-k2.5": {"input": 0.00054, "output": 0.002808},
    "kimi-k2.6": {"input": 0.000756, "output": 0.00378},
    "kimi-k2.7-code": {"input": 0.00135, "output": 0.0054},
    "llama-3.1-405b-instruct": {"input": 0.00189, "output": 0.00189},
    "llama-3.1-8b-instruct": {"input": 0.000108, "output": 0.000108},
    "llama-3.3-70b-instruct": {"input": 0.000108, "output": 0.000324},
    "minimax-m2": {"input": 0.00027, "output": 0.00108},
    "minimax-m2.1": {"input": 0.000324, "output": 0.002592},
    "minimax-m2.5": {"input": 0.000216, "output": 0.00108},
    "minimax-m2.7": {"input": 0.000648, "output": 0.002592},
    "minimax-428b-m3": {"input": 0.000432, "output": 0.00216},  # == "MiniMax M3" (default)
    "devstral-2-123b-instruct-2512": {"input": 0.000432, "output": 0.00216},
    "mistral-medium-3.5-128b": {"input": 0.00162, "output": 0.0054},
    "mistral-small-3.2-24b-instruct": {"input": 0.000108, "output": 0.000324},
    "mistral-small-4-119b-instruct": {"input": 0.000162, "output": 0.000648},
    "nemotron-3-nano-30b-a3b": {"input": 0.0000648, "output": 0.0002592},
    "nemotron-3-super-120b-a12b": {"input": 0.000324, "output": 0.000972},
    "pixtral-12b-2409": {"input": 0.000216, "output": 0.000216},
    "qwen2.5-vl-72b-instruct": {"input": 0.00027, "output": 0.00081},
    "qwen3-235b-a22b-instruct": {"input": 0.0000756, "output": 0.000486},
    "qwen3-30b-a3b-instruct": {"input": 0.000108, "output": 0.000324},
    "qwen3-32b": {"input": 0.0000864, "output": 0.0002592},
    "qwen3-coder-30b-a3b-instruct": {"input": 0.0000648, "output": 0.0002592},
    "qwen3-coder-next": {"input": 0.0001836, "output": 0.000972},
    "qwen3-next-80b-a3b-thinking": {"input": 0.000162, "output": 0.001296},
    "qwen3-vl-235b-a22b-instruct": {"input": 0.000216, "output": 0.001944},
    "qwen3.5-122b-a10b": {"input": 0.000108, "output": 0.000324},
    "qwen3.5-397b-a17b": {"input": 0.000648, "output": 0.003888},
    "qwen3.5-9b": {"input": 0.0000756, "output": 0.000216},
    "qwen3.6-27b": {"input": 0.000216, "output": 0.001296},
    "qwen3.6-35b-a3b": {"input": 0.00027, "output": 0.00162},
    "voxtral-small-24b-2507": {"input": 0.000162, "output": 0.000378},
    "glm-4.6": {"input": 0.000432, "output": 0.001782},
    "glm-4.7": {"input": 0.000594, "output": 0.002376},
    "glm-5": {"input": 0.001026, "output": 0.003186},
    "glm-5.1": {"input": 0.001404, "output": 0.004374},
    "glm-5.2": {"input": 0.00162, "output": 0.00486},
    # -- Content safety --
    "qwen3guard-gen-0.6b": {"input": 0.0000324, "output": 0.000108},
    "qwen3guard-gen-8b": {"input": 0.000054, "output": 0.000216},
    # -- Embeddings (output billed at 0) --
    "bge-large-en-v1.5": {"input": 0.0000216, "output": 0.0},
    "bge-m3": {"input": 0.0000108, "output": 0.0},
    "bge-multilingual-gemma2": {"input": 0.0000108, "output": 0.0},
    "qwen3-embedding-8b": {"input": 0.0000108, "output": 0.0},
    "paraphrase-multilingual-mpnet": {"input": 0.0000108, "output": 0.0},
    "multilingual-e5-large": {"input": 0.0000324, "output": 0.0},
    "multilingual-e5-large-instruct": {"input": 0.0000324, "output": 0.0},
    # Embeddings
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0.0},
}

# Default pricing for unknown models
DEFAULT_PRICING: ModelPricing = {"input": 0.01, "output": 0.03}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
) -> float:
    """
    Calculate cost in USD for API usage.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD (6 decimal places)

    Raises:
        ValueError: If token counts are negative.
    """
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError(f"Token counts must be non-negative (got input={input_tokens}, output={output_tokens}).")

    pricing = get_model_pricing(model)
    cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]

    return round(cost, 6)


def estimate_monthly_cost(
    model: str,
    requests_per_day: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
) -> float:
    """
    Estimate monthly cost for a usage pattern.

    Args:
        model: Model name
        requests_per_day: Average requests per day
        avg_input_tokens: Average input tokens per request
        avg_output_tokens: Average output tokens per request

    Returns:
        Estimated monthly cost in USD
    """
    cost_per_request = calculate_cost(model, avg_input_tokens, avg_output_tokens)
    daily_cost = cost_per_request * requests_per_day
    monthly_cost = daily_cost * 30

    return round(monthly_cost, 2)


def get_model_pricing(model: str) -> ModelPricing:
    """
    Get pricing for a model.

    Args:
        model: Model name

    Returns:
        ModelPricing dict with input/output rates
    """
    lookup = strip_provider_prefix(model)
    pricing = PRICING.get(lookup)

    if pricing is None:
        best_match_len = 0
        best_match: ModelPricing | None = None
        for key, p in PRICING.items():
            if lookup.startswith(key) and len(key) > best_match_len:
                best_match = p
                best_match_len = len(key)
        if best_match is not None:
            return best_match

    if pricing is not None:
        return pricing

    # Fall back to the broader bundled catalog before the generic default, so
    # models absent from the curated table still get a real estimate.
    catalog = _get_catalog()
    if catalog is not None:
        hit = catalog.lookup(model)
        if hit is not None:
            return {"input": hit["input"], "output": hit["output"]}

    return DEFAULT_PRICING
