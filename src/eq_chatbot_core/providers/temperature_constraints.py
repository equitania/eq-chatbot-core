"""
Shared temperature constraints for all LLM providers.

Temperature constraints are model-specific, not provider-specific: GPT-4.1 has the
same limits whether accessed through OpenAI, LangDock, OpenRouter, or Mammouth.
This module provides a single source of truth for clamping logic used by all providers.
"""

import logging
from typing import Any

_logger = logging.getLogger(__name__)


# Per-model temperature constraints.
# Key: model ID or prefix (lowercase) for case-insensitive longest-prefix matching.
# get_temperature_constraints() lowercases the input before lookup, so all keys
# here MUST be lowercase. Mixed-case gateway model IDs (DeepSeek-V3, MAI-DS-R1)
# and lowercase OpenRouter IDs (deepseek-v3) both resolve to the same entry.
MODEL_TEMPERATURE_CONSTRAINTS: dict[str, dict[str, Any]] = {
    # Reasoning models: temperature fixed at 1.0 (not configurable)
    "o1": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o1-mini": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o1-preview": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o3": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o3-mini": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o3-pro": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o4-mini": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "codex-mini": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    # GPT-4.1 family: 0.0-2.0 (same as GPT-4o)
    "gpt-4.1": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-4.1-mini": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-4.1-nano": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # GPT-5 family — the support is NOT continuous, so the generic prefix says NO
    # and the generations that do accept the parameter are listed explicitly.
    # Measured against the live API on 23.08.2026: gpt-5 and gpt-5-mini refuse it
    # ("Only the default (1) value is supported"), 5.1 / 5.2 / 5.4 accept it, and
    # 5.5 / 5.6 refuse it again. A single permissive prefix entry meant every call
    # to gpt-5, gpt-5.5 and the whole current gpt-5.6 tier failed with HTTP 400.
    #
    # Failing SAFE means omitting: a model that would have accepted temperature is
    # unaffected by leaving it out, while sending it to one that refuses breaks
    # every call. An untested future generation therefore inherits "no".
    "gpt-5": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "gpt-5.1": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-5.2": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-5.3": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-5.4": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # Legacy OpenAI: 0.0-2.0
    "gpt-4o": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-4o-mini": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-4-turbo": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # Anthropic Claude 5 family and Opus 4.7+: temperature was removed from the
    # API and a request carrying it is rejected with
    # "400 invalid_request_error: `temperature` is deprecated for this model".
    # Listed before the generic "claude" prefix below, which would otherwise
    # match them (longest-prefix wins, so the explicit ids take precedence).
    "claude-fable-5": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "claude-mythos-5": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "claude-mythos-preview": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "claude-opus-5": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "claude-opus-4-8": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "claude-opus-4-7": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "claude-sonnet-5": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    # Anthropic up to Opus 4.6 / Sonnet 4.6: 0.0-1.0
    # (prefix match covers the remaining Claude variants)
    "claude": {"min": 0.0, "max": 1.0, "supports_temperature": True},
    # Google Gemini: 0.0-2.0
    "gemini": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # Mistral: 0.0-1.0 (covers Mistral-Large-3 etc.)
    "mistral": {"min": 0.0, "max": 1.0, "supports_temperature": True},
    # DeepSeek
    "deepseek-chat": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "deepseek-reasoner": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "deepseek-v3": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "deepseek-r1": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    # Microsoft MAI (reasoning)
    "mai-ds-r1": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    # Meta Llama: 0.0-2.0
    "llama": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # xAI Grok: 0.0-2.0
    "grok": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # Cohere: 0.0-1.0
    "cohere": {"min": 0.0, "max": 1.0, "supports_temperature": True},
    # Moonshot Kimi: 0.0-1.0
    "kimi": {"min": 0.0, "max": 1.0, "supports_temperature": True},
}

DEFAULT_TEMP_CONSTRAINTS: dict[str, Any] = {
    "min": 0.0,
    "max": 2.0,
    "supports_temperature": True,
}


def strip_provider_prefix(model: str) -> str:
    """
    Strip provider prefix from model ID (e.g. OpenRouter format).

    Examples:
        "openai/gpt-4.1" -> "gpt-4.1"
        "anthropic/claude-sonnet-4-5-20250929" -> "claude-sonnet-4-5-20250929"
        "gpt-4o" -> "gpt-4o"  (no prefix, unchanged)
    """
    if "/" in model:
        return model.split("/", 1)[1]
    return model


def get_temperature_constraints(model: str) -> dict[str, Any]:
    """
    Get temperature constraints for a specific model.

    Case-insensitive: the model ID is lowercased before lookup. Uses exact match
    first, then longest-prefix match against MODEL_TEMPERATURE_CONSTRAINTS,
    falling back to DEFAULT_TEMP_CONSTRAINTS.

    Args:
        model: Model ID, with or without a provider prefix. Case is ignored.

    Returns:
        Dict with keys: min, max, supports_temperature
    """
    # Strip a provider prefix here rather than trusting every caller to do it.
    # Without this "openai/gpt-5.6-luna" matched no key and fell through to the
    # permissive default — a model that REFUSES temperature silently got it sent.
    # strip_provider_prefix() is idempotent, so a bare id is unaffected.
    lookup = strip_provider_prefix(model).lower()

    # Exact match
    if lookup in MODEL_TEMPERATURE_CONSTRAINTS:
        return MODEL_TEMPERATURE_CONSTRAINTS[lookup]

    # Longest-prefix match
    best_match_len = 0
    best_match: dict[str, Any] | None = None
    for key, constraints in MODEL_TEMPERATURE_CONSTRAINTS.items():
        if lookup.startswith(key) and len(key) > best_match_len:
            best_match = constraints
            best_match_len = len(key)

    return best_match or DEFAULT_TEMP_CONSTRAINTS


def clamp_temperature(model: str, temperature: float) -> float | None:
    """
    Clamp temperature to valid range for the model.

    Returns None if the model doesn't support temperature at all
    (reasoning models like o1, o3, o4). Logs a warning when clamping.

    Args:
        model: Model ID (without provider prefix)
        temperature: Requested temperature value

    Returns:
        Clamped temperature value, or None for reasoning models
    """
    constraints = get_temperature_constraints(model)

    if not constraints["supports_temperature"]:
        return None

    min_temp: float = constraints["min"]
    max_temp: float = constraints["max"]

    if temperature < min_temp:
        _logger.warning(
            "Temperature %.2f below minimum %.2f for model %s, clamping to %.2f",
            temperature,
            min_temp,
            model,
            min_temp,
        )
        return min_temp

    if temperature > max_temp:
        _logger.warning(
            "Temperature %.2f above maximum %.2f for model %s, clamping to %.2f",
            temperature,
            max_temp,
            model,
            max_temp,
        )
        return max_temp

    return temperature


def apply_anthropic_temperature(params: dict[str, Any], model: str, temperature: float) -> bool:
    """Put a clamped temperature where the Anthropic SDK still accepts it.

    anthropic 1.0.0 removed ``temperature``, ``top_p`` and ``top_k`` from
    ``messages.create()`` / ``messages.stream()`` and their beta counterparts:
    passing one raises ``TypeError``, it is not merely deprecated. Current models
    ignore the parameter regardless, but older ones still honour it when it
    travels in ``extra_body`` — which is what the SDK's own migration guide
    prescribes.

    Callers therefore must not write ``params["temperature"]`` themselves. This
    helper folds the clamping rules and the transport decision into one place, so
    the next SDK move is a single edit rather than four.

    Args:
        params: Request kwargs, mutated in place. An existing ``extra_body`` is
            merged into, never replaced.
        model: Model id, used to resolve the clamping constraints.
        temperature: Requested temperature.

    Returns:
        True if a temperature was applied, False for models that take none
        (reasoning models, and every Claude line from Opus 4.7 onwards).
    """
    clamped = clamp_temperature(model, temperature)
    if clamped is None:
        return False

    extra_body = params.setdefault("extra_body", {})
    extra_body["temperature"] = clamped
    return True
