"""
LLM cost calculation service.
"""

from typing import TypedDict


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
    """
    # Try exact match
    pricing = PRICING.get(model)

    # Try longest-prefix match if no exact match
    if pricing is None:
        best_match_len = 0
        for key, p in PRICING.items():
            if model.startswith(key) and len(key) > best_match_len:
                pricing = p
                best_match_len = len(key)

    # Use default if still not found
    if pricing is None:
        pricing = DEFAULT_PRICING

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
    pricing = PRICING.get(model)

    if pricing is None:
        best_match_len = 0
        best_match: ModelPricing | None = None
        for key, p in PRICING.items():
            if model.startswith(key) and len(key) > best_match_len:
                best_match = p
                best_match_len = len(key)
        if best_match is not None:
            return best_match

    return pricing or DEFAULT_PRICING
