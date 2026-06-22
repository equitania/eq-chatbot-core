"""Unit tests for CLI API-key resolution (resolve_api_key).

These tests exercise the real env-var resolution logic — no API calls are
mocked. monkeypatch.setenv sets actual environment variables and we assert the
genuine precedence behavior.
"""

import pytest

from eq_chatbot_core.cli import PROVIDER_API_KEY_ENV, resolve_api_key

# Env vars that resolve_api_key may read; cleared before each test for isolation.
_ALL_KEY_ENVS = list(PROVIDER_API_KEY_ENV.values()) + ["LLM_API_KEY"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove any ambient key env vars so tests are deterministic."""
    for name in _ALL_KEY_ENVS:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.unit
class TestResolveApiKey:
    """Precedence: --api-key > <PROVIDER>_API_KEY > LLM_API_KEY > None."""

    def test_explicit_flag_wins_over_everything(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "from-provider-env")
        monkeypatch.setenv("LLM_API_KEY", "from-generic-env")
        assert resolve_api_key("openai", "from-flag") == "from-flag"

    def test_provider_specific_env_used_when_no_flag(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-xyz")
        assert resolve_api_key("openrouter", None) == "sk-or-xyz"

    def test_provider_specific_env_wins_over_generic(self, monkeypatch):
        monkeypatch.setenv("MELIOUS_API_KEY", "sk-mel-specific")
        monkeypatch.setenv("LLM_API_KEY", "sk-generic")
        assert resolve_api_key("melious", None) == "sk-mel-specific"

    def test_generic_fallback_when_no_provider_specific(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-generic")
        assert resolve_api_key("openai", None) == "sk-generic"

    def test_returns_none_when_nothing_set(self):
        assert resolve_api_key("openai", None) is None

    def test_cross_provider_env_does_not_leak(self, monkeypatch):
        """OPENROUTER_API_KEY must not satisfy provider='openai'."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-xyz")
        assert resolve_api_key("openai", None) is None

    def test_provider_name_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        assert resolve_api_key("OpenAI", None) == "sk-openai"

    def test_unknown_provider_falls_back_to_generic(self, monkeypatch):
        """A provider without a specific mapping (e.g. local) still gets LLM_API_KEY."""
        monkeypatch.setenv("LLM_API_KEY", "sk-generic")
        assert resolve_api_key("lm_studio", None) == "sk-generic"

    def test_none_provider_uses_generic(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-generic")
        assert resolve_api_key(None, None) == "sk-generic"
