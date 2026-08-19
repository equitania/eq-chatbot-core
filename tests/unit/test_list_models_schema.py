"""Pin what ``list_models()`` reports per provider — especially what it does NOT.

Why this exists
---------------
Consumers build UI and routing decisions on the dicts ``list_models()`` returns.
A missing key is indistinguishable from "unknown" at the call site, and a
consumer that fills the gap with a default silently invents a capability.

That is not hypothetical. Melious, IONOS, LiteLLM and Privatemode all inherit
``OpenAICompatibleProvider.list_models()``, which reports no ``supports_tools``
at all. The Odoo integration defaulted the missing key to True, sent tool
schemas to a model that cannot call tools, and every chat on that model died
with a raw provider error. No test caught it: the live suites had working API
keys for seven providers, but not a single assertion about this field.

These tests need no credentials and run in CI. They do not demand that every
provider report every key — they make the current gaps *explicit*, so widening
one is a deliberate act that updates this file, and closing one is visible.
"""

from __future__ import annotations

import pytest

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider

# Keys the Odoo integration reads off a list_models() entry. `id` and `name`
# are load-bearing (a model cannot be selected without them); the rest are
# enrichment that consumers must treat as optional.
REQUIRED_KEYS = {"id", "name"}
CAPABILITY_KEYS = {"supports_tools", "supports_vision", "supports_reasoning", "context_length"}

# Providers reaching the network through the shared OpenAI-compatible listing.
# The endpoint is a plain /v1/models list that carries no capability metadata,
# so none of these can report tool support. Consumers MUST NOT read a missing
# key as "yes" — see eq_chatbot 19.0.1.21.0, which recovers at runtime instead.
OPENAI_COMPATIBLE_PROVIDERS = ("litellm", "ionos", "melious", "privatemode")


def test_openai_compatible_providers_share_one_listing():
    """All four inherit the listing — none may quietly grow its own."""
    from eq_chatbot_core.providers.ionos_provider import IonosProvider
    from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
    from eq_chatbot_core.providers.melious_provider import MeliousProvider
    from eq_chatbot_core.providers.privatemode_provider import PrivatemodeProvider

    for cls in (LiteLLMProvider, IonosProvider, MeliousProvider, PrivatemodeProvider):
        assert "list_models" not in vars(cls), (
            f"{cls.__name__} now overrides list_models(). If it reports capability "
            f"metadata, move it out of OPENAI_COMPATIBLE_PROVIDERS and pin the new "
            f"keys — consumers key their defaults off this list."
        )
        assert issubclass(cls, OpenAICompatibleProvider)


@pytest.mark.parametrize("provider_name", OPENAI_COMPATIBLE_PROVIDERS)
def test_openai_compatible_listing_reports_no_capabilities(provider_name, monkeypatch):
    """Document the gap: these entries carry identity only, never capabilities.

    A consumer seeing no ``supports_tools`` must treat it as unknown. This test
    fails the day the upstream listing grows capability data — at which point
    the consumers' fallbacks should be revisited, not left in place.
    """
    from eq_chatbot_core.providers import get_provider

    class _FakeModel:
        id = "some-model"
        created = 0
        owned_by = "owner"

    class _FakeModels:
        def list(self):
            class _Page:
                data = [_FakeModel()]

            return _Page()

    # LiteLLM deliberately has no default endpoint and rejects construction
    # without one; the others default to their own (Privatemode: local proxy).
    kwargs = {"base_url": "https://gateway.example/v1"} if provider_name == "litellm" else {}
    provider = get_provider(provider_name=provider_name, api_key="test-key", **kwargs)
    monkeypatch.setattr(type(provider), "client", property(lambda self: type("C", (), {"models": _FakeModels()})()))

    entries = provider.list_models()
    assert entries, "listing must not be empty for a responding endpoint"
    for entry in entries:
        missing = REQUIRED_KEYS - entry.keys()
        assert not missing, f"{provider_name}: listing lost a required key: {missing}"
        reported = CAPABILITY_KEYS & entry.keys()
        assert not reported, (
            f"{provider_name} now reports {sorted(reported)}. That is an improvement — "
            f"update this test and review the consumer-side defaults that exist "
            f"precisely because the data was missing."
        )


def test_capability_reporting_matrix_is_current():
    """Fail when a provider starts or stops reporting supports_tools.

    The matrix is the documented truth about who can be trusted for tool
    capability. Only OpenRouter derives it from real data (supported_params) and
    LocalLLM hardcodes False; everyone else is silent.
    """
    import inspect

    from eq_chatbot_core.providers.local_provider import LocalLLMProvider
    from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

    expected_reporters = {LocalLLMProvider, OpenRouterProvider}

    from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
    from eq_chatbot_core.providers.langdock_provider import LangDockProvider
    from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
    from eq_chatbot_core.providers.openai_provider import OpenAIProvider

    all_classes = {
        LocalLLMProvider,
        OpenRouterProvider,
        AnthropicProvider,
        LangDockProvider,
        MammouthProvider,
        OpenAIProvider,
        OpenAICompatibleProvider,
    }

    # Scan the whole class, not just list_models: OpenRouter assembles the flag in
    # the _get_model_constraints helper that list_models() merges into each entry.
    # Inspecting the method body alone reported OpenRouter as silent — the exact
    # kind of false negative this matrix exists to prevent.
    actual_reporters = set()
    for cls in all_classes:
        if vars(cls).get("list_models") is None:
            continue
        if '"supports_tools"' in inspect.getsource(cls):
            actual_reporters.add(cls)

    assert actual_reporters == expected_reporters, (
        "Tool-capability reporting changed.\n"
        f"  now reporting: {sorted(c.__name__ for c in actual_reporters)}\n"
        f"  expected:      {sorted(c.__name__ for c in expected_reporters)}\n"
        "Update this matrix AND the consumers that compensate for the gap "
        "(eq_chatbot stream.py runtime probe, capability catalog)."
    )
