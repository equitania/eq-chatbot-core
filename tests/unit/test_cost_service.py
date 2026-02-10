"""
Unit tests for the cost_service module.

Tests calculate_cost(), get_model_pricing(), estimate_monthly_cost(),
and the PRICING dict. Special focus on the longest-prefix-matching fix
that prevents e.g. "o1-mini" from matching "o1" instead of the more
specific "o1-mini" entry.
"""

import pytest

from eq_chatbot_core.services.cost_service import (
    DEFAULT_PRICING,
    PRICING,
    calculate_cost,
    estimate_monthly_cost,
    get_model_pricing,
)

# =============================================================================
# calculate_cost() Tests
# =============================================================================


@pytest.mark.unit
class TestCalculateCost:
    """Test cost calculation with exact, prefix, and longest-prefix matching."""

    def test_exact_match_gpt4o_mini(self):
        """Exact model name 'gpt-4o-mini' uses its specific pricing."""
        cost = calculate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=1000)
        expected = (1000 / 1000) * 0.00015 + (1000 / 1000) * 0.0006
        assert cost == pytest.approx(round(expected, 6))

    def test_prefix_match_gpt4o_dated(self):
        """A dated variant 'gpt-4o-2024-01-15' falls back to 'gpt-4o' pricing."""
        cost = calculate_cost("gpt-4o-2024-01-15", input_tokens=1000, output_tokens=1000)
        gpt4o_pricing = PRICING["gpt-4o"]
        expected = (1000 / 1000) * gpt4o_pricing["input"] + (1000 / 1000) * gpt4o_pricing["output"]
        assert cost == pytest.approx(round(expected, 6))

    def test_longest_prefix_o1_mini_over_o1(self):
        """'o1-mini-2024' must match 'o1-mini' (len=7) NOT 'o1' (len=2)."""
        cost = calculate_cost("o1-mini-2024", input_tokens=1000, output_tokens=1000)
        o1_mini_pricing = PRICING["o1-mini"]
        expected = (1000 / 1000) * o1_mini_pricing["input"] + (1000 / 1000) * o1_mini_pricing["output"]
        assert cost == pytest.approx(round(expected, 6))
        # Verify it did NOT use "o1" pricing
        o1_pricing = PRICING["o1"]
        wrong_cost = (1000 / 1000) * o1_pricing["input"] + (1000 / 1000) * o1_pricing["output"]
        assert cost != pytest.approx(round(wrong_cost, 6))

    def test_longest_prefix_claude_sonnet_dated_v2(self):
        """'claude-3-5-sonnet-20241022-v2' must match 'claude-3-5-sonnet-20241022' NOT 'claude-3-5-sonnet-latest'."""
        cost = calculate_cost("claude-3-5-sonnet-20241022-v2", input_tokens=1000, output_tokens=1000)
        specific_pricing = PRICING["claude-3-5-sonnet-20241022"]
        expected = (1000 / 1000) * specific_pricing["input"] + (1000 / 1000) * specific_pricing["output"]
        assert cost == pytest.approx(round(expected, 6))

    def test_longest_prefix_gpt4o_mini_custom_over_gpt4o(self):
        """'gpt-4o-mini-custom' must match 'gpt-4o-mini' (len=10) NOT 'gpt-4o' (len=6)."""
        cost = calculate_cost("gpt-4o-mini-custom", input_tokens=1000, output_tokens=1000)
        mini_pricing = PRICING["gpt-4o-mini"]
        expected = (1000 / 1000) * mini_pricing["input"] + (1000 / 1000) * mini_pricing["output"]
        assert cost == pytest.approx(round(expected, 6))
        # Verify it did NOT use "gpt-4o" pricing
        gpt4o_pricing = PRICING["gpt-4o"]
        wrong_cost = (1000 / 1000) * gpt4o_pricing["input"] + (1000 / 1000) * gpt4o_pricing["output"]
        assert cost != pytest.approx(round(wrong_cost, 6))

    def test_unknown_model_uses_default_pricing(self):
        """A completely unknown model falls back to DEFAULT_PRICING."""
        cost = calculate_cost("totally-unknown-model-xyz", input_tokens=1000, output_tokens=1000)
        expected = (1000 / 1000) * DEFAULT_PRICING["input"] + (1000 / 1000) * DEFAULT_PRICING["output"]
        assert cost == pytest.approx(round(expected, 6))

    def test_zero_tokens_returns_zero(self):
        """Zero input and output tokens produce zero cost."""
        cost = calculate_cost("gpt-4o", input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_only_input_tokens_defaults_output_to_zero(self):
        """Omitting output_tokens defaults to 0, only input cost counted."""
        cost = calculate_cost("gpt-4o", input_tokens=1000)
        gpt4o_pricing = PRICING["gpt-4o"]
        expected = (1000 / 1000) * gpt4o_pricing["input"]
        assert cost == pytest.approx(round(expected, 6))

    def test_result_rounded_to_six_decimal_places(self):
        """Result is rounded to 6 decimal places."""
        # Use odd token counts to trigger non-trivial rounding
        cost = calculate_cost("gpt-4o", input_tokens=137, output_tokens=89)
        # Verify it has at most 6 decimal places
        cost_str = f"{cost:.10f}"
        # The last 4 digits (positions 7-10 after dot) should be zeros
        decimal_part = cost_str.split(".")[1]
        assert decimal_part[6:] == "0000", f"Cost {cost} has more than 6 decimal places"

    def test_embedding_model_zero_output_cost(self):
        """Embedding model text-embedding-3-small has 0 output cost."""
        cost = calculate_cost("text-embedding-3-small", input_tokens=1000, output_tokens=1000)
        expected = (1000 / 1000) * PRICING["text-embedding-3-small"]["input"]
        # output pricing is 0.0, so output_tokens contribute nothing
        assert cost == pytest.approx(round(expected, 6))


# =============================================================================
# get_model_pricing() Tests
# =============================================================================


@pytest.mark.unit
class TestGetModelPricing:
    """Test pricing lookup with exact and longest-prefix matching."""

    def test_exact_match_returns_correct_pricing(self):
        """Exact model name returns its pricing dict."""
        pricing = get_model_pricing("gpt-4o-mini")
        assert pricing["input"] == pytest.approx(0.00015)
        assert pricing["output"] == pytest.approx(0.0006)

    def test_longest_prefix_match_o1_mini_variant(self):
        """'o1-mini-2024-09' resolves to 'o1-mini' pricing, not 'o1'."""
        pricing = get_model_pricing("o1-mini-2024-09")
        o1_mini = PRICING["o1-mini"]
        assert pricing["input"] == pytest.approx(o1_mini["input"])
        assert pricing["output"] == pytest.approx(o1_mini["output"])
        # Must NOT be "o1" pricing
        o1 = PRICING["o1"]
        assert not (pricing["input"] == pytest.approx(o1["input"]) and pricing["output"] == pytest.approx(o1["output"]))

    def test_unknown_model_returns_default(self):
        """Completely unknown model returns DEFAULT_PRICING."""
        pricing = get_model_pricing("nonexistent-model-42")
        assert pricing["input"] == pytest.approx(DEFAULT_PRICING["input"])
        assert pricing["output"] == pytest.approx(DEFAULT_PRICING["output"])


# =============================================================================
# estimate_monthly_cost() Tests
# =============================================================================


@pytest.mark.unit
class TestEstimateMonthlyCost:
    """Test monthly cost estimation."""

    def test_basic_monthly_calculation(self):
        """Monthly cost = cost_per_request * requests_per_day * 30."""
        monthly = estimate_monthly_cost(
            model="gpt-4o-mini",
            requests_per_day=100,
            avg_input_tokens=500,
            avg_output_tokens=200,
        )
        cost_per_request = calculate_cost("gpt-4o-mini", 500, 200)
        expected = round(cost_per_request * 100 * 30, 2)
        assert monthly == pytest.approx(expected)

    def test_zero_requests_returns_zero(self):
        """Zero requests per day produces zero monthly cost."""
        monthly = estimate_monthly_cost(
            model="gpt-4o",
            requests_per_day=0,
            avg_input_tokens=1000,
            avg_output_tokens=500,
        )
        assert monthly == 0.0

    def test_result_rounded_to_two_decimal_places(self):
        """Monthly estimate is rounded to 2 decimal places."""
        monthly = estimate_monthly_cost(
            model="gpt-4o",
            requests_per_day=37,
            avg_input_tokens=1234,
            avg_output_tokens=567,
        )
        # Verify at most 2 decimal places
        monthly_str = f"{monthly:.6f}"
        decimal_part = monthly_str.split(".")[1]
        assert decimal_part[2:] == "0000", f"Monthly cost {monthly} has more than 2 decimal places"


# =============================================================================
# PRICING Dict Integrity Tests
# =============================================================================


@pytest.mark.unit
class TestPricingDict:
    """Test PRICING dictionary structure and completeness."""

    @pytest.mark.parametrize(
        "model_key",
        [
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4",
            "o1",
            "o1-mini",
            "o3-mini",
            "claude-3-5-sonnet-latest",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-latest",
            "text-embedding-3-small",
            "text-embedding-3-large",
        ],
    )
    def test_key_models_exist_in_pricing(self, model_key: str):
        """Spot-check that key models are present in the PRICING dict."""
        assert model_key in PRICING, f"Expected model '{model_key}' not found in PRICING"

    def test_all_entries_have_input_and_output_keys(self):
        """Every PRICING entry must have 'input' and 'output' keys with numeric values."""
        for model, pricing in PRICING.items():
            assert "input" in pricing, f"Model '{model}' missing 'input' key"
            assert "output" in pricing, f"Model '{model}' missing 'output' key"
            assert isinstance(pricing["input"], (int, float)), f"Model '{model}' input is not numeric"
            assert isinstance(pricing["output"], (int, float)), f"Model '{model}' output is not numeric"
            assert pricing["input"] >= 0, f"Model '{model}' has negative input pricing"
            assert pricing["output"] >= 0, f"Model '{model}' has negative output pricing"
