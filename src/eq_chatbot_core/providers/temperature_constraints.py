"""Provider-level temperature rules.

Only rules that hold for every model of a provider live here: the 0–2 range of
the OpenAI wire protocol and Anthropic's 0–1 range. Whether a particular model
accepts ``temperature`` at all is learned at runtime (``param_learning``),
never looked up by name.
"""

import logging
from typing import Any

_logger = logging.getLogger(__name__)

ANTHROPIC_MAX_TEMPERATURE = 1.0


def strip_provider_prefix(model: str) -> str:
    """
    Strip provider prefix from model ID (e.g. OpenRouter format).

    Examples:
        "vendor/your-model-id" -> "your-model-id"
        "your-model-id" -> "your-model-id"  (no prefix, unchanged)
    """
    if "/" in model:
        return model.split("/", 1)[1]
    return model


def clamp_temperature(temperature: float, *, maximum: float = 2.0) -> float:
    """Clamp ``temperature`` into ``0.0 … maximum``; logs a warning when it clamps."""
    if temperature < 0.0:
        _logger.warning("Temperature %.2f below 0.00, clamping to 0.00", temperature)
        return 0.0
    if temperature > maximum:
        _logger.warning("Temperature %.2f above maximum %.2f, clamping to %.2f", temperature, maximum, maximum)
        return maximum
    return temperature


def apply_anthropic_temperature(params: dict[str, Any], temperature: float) -> None:
    """Put a temperature clamped to 0–1 where the Anthropic SDK still accepts it.

    anthropic 1.0.0 removed ``temperature``, ``top_p`` and ``top_k`` from
    ``messages.create()`` / ``messages.stream()``: passing one raises
    ``TypeError``. The value travels in ``extra_body`` instead, as the SDK's
    migration guide prescribes. A model that no longer takes a temperature
    rejects it; ``anthropic_shared`` learns that and drops it.

    Args:
        params: Request kwargs, mutated in place. An existing ``extra_body`` is
            merged into, never replaced.
        temperature: Requested temperature.
    """
    extra_body = params.setdefault("extra_body", {})
    extra_body["temperature"] = clamp_temperature(temperature, maximum=ANTHROPIC_MAX_TEMPERATURE)
