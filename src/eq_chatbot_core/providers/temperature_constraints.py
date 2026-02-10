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
# Key: model ID or prefix for longest-prefix matching.
MODEL_TEMPERATURE_CONSTRAINTS: dict[str, dict[str, Any]] = {
    # Reasoning models: temperature fixed at 1.0 (not configurable)
    "o1": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o1-mini": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o1-preview": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o3": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o3-mini": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    "o4-mini": {"min": 1.0, "max": 1.0, "supports_temperature": False},
    # New OpenAI models: min temperature = 1.0
    "gpt-5.2-chat": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    "gpt-5.1-chat": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    "gpt-5-mini": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    "gpt-5-nano": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    "gpt-5-chat": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    "gpt-4.1": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    "gpt-4.1-mini": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    "gpt-4.1-nano": {"min": 1.0, "max": 2.0, "supports_temperature": True},
    # Legacy OpenAI: 0.0-2.0
    "gpt-4o": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-4o-mini": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "gpt-4-turbo": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # Anthropic: 0.0-1.0 (prefix match covers all Claude variants)
    "claude": {"min": 0.0, "max": 1.0, "supports_temperature": True},
    # Google Gemini: 0.0-2.0
    "gemini": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    # Mistral: 0.0-1.0
    "mistral": {"min": 0.0, "max": 1.0, "supports_temperature": True},
    # DeepSeek
    "deepseek-chat": {"min": 0.0, "max": 2.0, "supports_temperature": True},
    "deepseek-reasoner": {"min": 1.0, "max": 1.0, "supports_temperature": False},
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

    Uses exact match first, then longest-prefix match against
    MODEL_TEMPERATURE_CONSTRAINTS, falling back to DEFAULT_TEMP_CONSTRAINTS.

    Args:
        model: Model ID (without provider prefix)

    Returns:
        Dict with keys: min, max, supports_temperature
    """
    # Exact match
    if model in MODEL_TEMPERATURE_CONSTRAINTS:
        return MODEL_TEMPERATURE_CONSTRAINTS[model]

    # Longest-prefix match
    best_match_len = 0
    best_match: dict[str, Any] | None = None
    for key, constraints in MODEL_TEMPERATURE_CONSTRAINTS.items():
        if model.startswith(key) and len(key) > best_match_len:
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

    min_temp = constraints["min"]
    max_temp = constraints["max"]

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
