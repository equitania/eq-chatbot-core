"""
Unit tests for shared temperature constraints module.

Tests cover constraint lookup, clamping logic, prefix matching,
and provider prefix stripping.
"""

import pytest

from eq_chatbot_core.providers.temperature_constraints import (
    DEFAULT_TEMP_CONSTRAINTS,
    clamp_temperature,
    get_temperature_constraints,
    strip_provider_prefix,
)

# =============================================================================
# get_temperature_constraints Tests
# =============================================================================


@pytest.mark.unit
class TestGetTemperatureConstraints:
    """Test temperature constraint lookup."""

    def test_exact_match_gpt41(self):
        """Test exact match for GPT-4.1 returns min=0.0."""
        constraints = get_temperature_constraints("gpt-4.1")
        assert constraints["min"] == 0.0
        assert constraints["max"] == 2.0
        assert constraints["supports_temperature"] is True

    def test_exact_match_reasoning_model(self):
        """Test exact match for o3 returns no temperature support."""
        constraints = get_temperature_constraints("o3")
        assert constraints["supports_temperature"] is False
        assert constraints["min"] == 1.0
        assert constraints["max"] == 1.0

    def test_exact_match_legacy_openai(self):
        """Test exact match for gpt-4o returns 0.0-2.0 range."""
        constraints = get_temperature_constraints("gpt-4o")
        assert constraints["min"] == 0.0
        assert constraints["max"] == 2.0
        assert constraints["supports_temperature"] is True

    def test_prefix_match_claude(self):
        """Test prefix match for Claude variants → max=1.0."""
        constraints = get_temperature_constraints("claude-sonnet-4-5-20250929")
        assert constraints["max"] == 1.0
        assert constraints["min"] == 0.0
        assert constraints["supports_temperature"] is True

    def test_prefix_match_claude_opus(self):
        """Test prefix match for Claude Opus → max=1.0."""
        constraints = get_temperature_constraints("claude-opus-4-5-20251101")
        assert constraints["max"] == 1.0

    def test_prefix_match_gemini(self):
        """Test prefix match for Gemini variants → max=2.0."""
        constraints = get_temperature_constraints("gemini-2.5-pro-latest")
        assert constraints["max"] == 2.0
        assert constraints["min"] == 0.0
        assert constraints["supports_temperature"] is True

    def test_prefix_match_mistral(self):
        """Test prefix match for Mistral variants → max=1.0."""
        constraints = get_temperature_constraints("mistral-large-2407")
        assert constraints["max"] == 1.0

    def test_longest_prefix_match(self):
        """Test longest prefix wins: gpt-4.1-mini over gpt-4.1."""
        constraints = get_temperature_constraints("gpt-4.1-mini")
        assert constraints["min"] == 0.0
        assert constraints["max"] == 2.0

    def test_default_fallback_unknown_model(self):
        """Test unknown model returns DEFAULT_TEMP_CONSTRAINTS."""
        constraints = get_temperature_constraints("totally-unknown-model-xyz")
        assert constraints == DEFAULT_TEMP_CONSTRAINTS
        assert constraints["min"] == 0.0
        assert constraints["max"] == 2.0
        assert constraints["supports_temperature"] is True

    def test_deepseek_reasoner(self):
        """Test DeepSeek Reasoner has no temperature support."""
        constraints = get_temperature_constraints("deepseek-reasoner")
        assert constraints["supports_temperature"] is False

    def test_deepseek_chat(self):
        """Test DeepSeek Chat has 0.0-2.0 range."""
        constraints = get_temperature_constraints("deepseek-chat")
        assert constraints["min"] == 0.0
        assert constraints["max"] == 2.0
        assert constraints["supports_temperature"] is True


# =============================================================================
# clamp_temperature Tests
# =============================================================================


@pytest.mark.unit
class TestClampTemperature:
    """Test temperature clamping logic."""

    def test_clamp_passthrough_gpt41(self):
        """Test temperature within range for GPT-4.1 passes through (min=0.0)."""
        assert clamp_temperature("gpt-4.1", 0.5) == 0.5

    def test_clamp_passthrough_gpt5(self):
        """Test temperature within range for GPT-5 passes through (min=0.0)."""
        assert clamp_temperature("gpt-5.2-chat", 0.3) == 0.3

    def test_clamp_above_max_claude(self):
        """Test temperature above max for Claude → clamped to 1.0."""
        assert clamp_temperature("claude-sonnet-4-5-20250929", 1.5) == 1.0

    def test_clamp_above_max_mistral(self):
        """Test temperature above max for Mistral → clamped to 1.0."""
        assert clamp_temperature("mistral-large-latest", 1.5) == 1.0

    def test_reasoning_model_returns_none(self):
        """Test reasoning models return None (temperature not supported)."""
        assert clamp_temperature("o1", 0.7) is None
        assert clamp_temperature("o3", 0.5) is None
        assert clamp_temperature("o4-mini", 0.3) is None

    def test_in_range_passthrough(self):
        """Test temperature within range passes through unchanged."""
        assert clamp_temperature("gpt-4o", 0.7) == 0.7
        assert clamp_temperature("gpt-4o", 0.0) == 0.0
        assert clamp_temperature("gpt-4o", 2.0) == 2.0

    def test_exact_min_boundary(self):
        """Test temperature exactly at min boundary passes through."""
        assert clamp_temperature("gpt-4.1", 0.0) == 0.0

    def test_exact_max_boundary(self):
        """Test temperature exactly at max boundary passes through."""
        assert clamp_temperature("gpt-4.1", 2.0) == 2.0
        assert clamp_temperature("claude-sonnet-4-5-20250929", 1.0) == 1.0

    def test_unknown_model_wide_range(self):
        """Test unknown model allows 0.0-2.0 range."""
        assert clamp_temperature("some-unknown-model", 0.0) == 0.0
        assert clamp_temperature("some-unknown-model", 1.5) == 1.5
        assert clamp_temperature("some-unknown-model", 2.0) == 2.0

    def test_deepseek_reasoner_returns_none(self):
        """Test DeepSeek Reasoner returns None."""
        assert clamp_temperature("deepseek-reasoner", 0.7) is None


# =============================================================================
# strip_provider_prefix Tests
# =============================================================================


@pytest.mark.unit
class TestStripProviderPrefix:
    """Test provider prefix stripping for OpenRouter model IDs."""

    def test_strip_openai_prefix(self):
        """Test stripping openai/ prefix."""
        assert strip_provider_prefix("openai/gpt-4.1") == "gpt-4.1"

    def test_strip_anthropic_prefix(self):
        """Test stripping anthropic/ prefix."""
        assert strip_provider_prefix("anthropic/claude-sonnet-4-5-20250929") == "claude-sonnet-4-5-20250929"

    def test_strip_google_prefix(self):
        """Test stripping google/ prefix."""
        assert strip_provider_prefix("google/gemini-2.5-pro") == "gemini-2.5-pro"

    def test_no_prefix_unchanged(self):
        """Test model ID without prefix returns unchanged."""
        assert strip_provider_prefix("gpt-4o") == "gpt-4o"

    def test_strip_meta_prefix(self):
        """Test stripping meta-llama/ prefix."""
        assert strip_provider_prefix("meta-llama/llama-3.1-70b-instruct") == "llama-3.1-70b-instruct"

    def test_strip_only_first_slash(self):
        """Test only the first slash is used for splitting."""
        assert strip_provider_prefix("provider/model/variant") == "model/variant"


# =============================================================================
# Integration: clamp + strip for OpenRouter
# =============================================================================


@pytest.mark.unit
class TestClampWithPrefixStrip:
    """Test clamping combined with prefix stripping (OpenRouter workflow)."""

    def test_openrouter_gpt41_passthrough(self):
        """Test OpenRouter GPT-4.1 passes through after prefix strip (min=0.0)."""
        bare = strip_provider_prefix("openai/gpt-4.1")
        assert clamp_temperature(bare, 0.5) == 0.5

    def test_openrouter_claude_clamped(self):
        """Test OpenRouter Claude gets max-clamped after prefix strip."""
        bare = strip_provider_prefix("anthropic/claude-sonnet-4-5-20250929")
        assert clamp_temperature(bare, 1.5) == 1.0

    def test_openrouter_o3_returns_none(self):
        """Test OpenRouter o3 reasoning model returns None."""
        bare = strip_provider_prefix("openai/o3")
        assert clamp_temperature(bare, 0.7) is None

    def test_openrouter_unknown_passthrough(self):
        """Test OpenRouter unknown model passes through."""
        bare = strip_provider_prefix("meta-llama/llama-3.1-70b-instruct")
        assert clamp_temperature(bare, 0.7) == 0.7
