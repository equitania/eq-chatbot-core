"""
Unit tests for shared temperature constraints module: provider prefix stripping.

The provider-level clamp is tested in test_no_name_lists_wire.py.
"""

import pytest

from eq_chatbot_core.providers.temperature_constraints import (
    strip_provider_prefix,
)


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
