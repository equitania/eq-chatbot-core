"""
Integration tests for OpenAI, Anthropic, and LangDock providers.

These tests require valid API keys in ~/.config/eq-chatbot/config.toml:
- OPENAI_API_KEY for OpenAI tests
- ANTHROPIC_API_KEY for Anthropic tests
- LANGDOCK_API_KEY for LangDock tests

Run with: pytest -m integration tests/integration/test_openai_live.py

Live tests run by default; export SKIP_LIVE_TESTS=true to skip them.
"""

import pytest

from eq_chatbot_core.providers import get_provider

# =============================================================================
# OpenAI Integration Tests
# =============================================================================


@pytest.mark.integration
class TestOpenAILive:
    """Live integration tests for OpenAI provider."""

    @pytest.fixture
    def provider(self, openai_api_key):
        """Create OpenAI provider (skips if no API key)."""
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY not set")
        return get_provider("openai", api_key=openai_api_key)

    def test_simple_completion(self, provider, test_config, openai_resolved_model):
        """Test simple chat completion with the resolved cheapest model."""
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=openai_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model
        assert response.input_tokens > 0
        assert response.output_tokens > 0

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_list_models(self, provider):
        """Test listing available models."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # Should include common models
        # list_models() returns ModelInfo dataclass or dict depending on provider
        if hasattr(models[0], "model_id"):
            model_ids = [m.model_id for m in models]
        else:
            model_ids = [m.get("model_id", m.get("id", "")) for m in models]
        # gpt-4o-mini should be available
        assert any("gpt" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:5]}")

    def test_streaming_completion(self, provider, test_config, openai_resolved_model):
        """Test streaming chat completion."""
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=openai_resolved_model,
                max_tokens=test_config.get("max_tokens", 20),
            )
        )

        assert len(chunks) > 0

        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        print(f"\n  Streamed: {full_content[:100]}")

    def test_system_message(self, provider, test_config, openai_resolved_model):
        """Test completion with system message."""
        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "You only respond with the word 'ACKNOWLEDGED'."},
                {"role": "user", "content": "Hello!"},
            ],
            model=openai_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "acknowledged" in response.content.lower()

    def test_json_mode(self, provider, test_config, openai_resolved_model):
        """Test JSON response format."""
        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "Respond only with valid JSON."},
                {"role": "user", "content": "Give me a JSON object with key 'status' and value 'ok'."},
            ],
            model=openai_resolved_model,
            max_tokens=test_config.get("max_tokens", 30),
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        assert response.content
        # Should be valid JSON
        import json

        try:
            data = json.loads(response.content)
            assert "status" in data
        except json.JSONDecodeError:
            pytest.fail(f"Response is not valid JSON: {response.content}")


# =============================================================================
# Anthropic Integration Tests
# =============================================================================


@pytest.mark.integration
class TestAnthropicLive:
    """Live integration tests for Anthropic provider."""

    @pytest.fixture
    def provider(self, anthropic_api_key):
        """Create Anthropic provider (skips if no API key)."""
        if not anthropic_api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")
        return get_provider("anthropic", api_key=anthropic_api_key)

    def test_simple_completion(self, provider, test_config, anthropic_resolved_model):
        """Test simple chat completion with the resolved cheapest model."""
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=anthropic_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model
        assert response.input_tokens > 0
        assert response.output_tokens > 0

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_list_models(self, provider):
        """Test listing available models."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # list_models() returns ModelInfo dataclass or dict depending on provider
        if hasattr(models[0], "model_id"):
            model_ids = [m.model_id for m in models]
        else:
            model_ids = [m.get("model_id", m.get("id", "")) for m in models]
        # Should include Claude models
        assert any("claude" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:5]}")

    def test_streaming_completion(self, provider, test_config, anthropic_resolved_model):
        """Test streaming chat completion."""
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=anthropic_resolved_model,
                max_tokens=test_config.get("max_tokens", 20),
            )
        )

        assert len(chunks) > 0

        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        print(f"\n  Streamed: {full_content[:100]}")

    def test_system_message(self, provider, test_config, anthropic_resolved_model):
        """Test completion with system message."""
        response = provider.chat_completion(
            messages=[
                {"role": "user", "content": "What is 2+2?"},
            ],
            model=anthropic_resolved_model,
            max_tokens=test_config.get("max_tokens", 20),
            temperature=0.0,
            system="You only respond with numbers, nothing else.",
        )

        assert response.content
        assert "4" in response.content


# =============================================================================
# LangDock Integration Tests
# =============================================================================


@pytest.mark.integration
class TestLangDockLive:
    """Live integration tests for LangDock provider (OpenAI backend)."""

    @pytest.fixture
    def provider(self, langdock_api_key):
        """Create LangDock provider with OpenAI backend (skips if no API key)."""
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")
        return get_provider("langdock", api_key=langdock_api_key, backend="openai", region="eu")

    def test_simple_completion(self, provider, test_config, langdock_resolved_model):
        """Test simple chat completion via LangDock."""
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=langdock_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model
        assert response.input_tokens > 0
        assert response.output_tokens > 0

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")
        print(f"  Tokens: {response.input_tokens} in / {response.output_tokens} out")

    def test_list_models(self, provider):
        """Test listing available models via LangDock."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # Should include GPT models
        model_ids = [m.get("id", "") for m in models]
        assert any("gpt" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} models")
        print(f"  Sample: {model_ids[:5]}")

    def test_streaming_completion(self, provider, test_config, langdock_resolved_model):
        """Test streaming chat completion via LangDock."""
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1, 2, 3"}],
                model=langdock_resolved_model,
                max_tokens=test_config.get("max_tokens", 20),
            )
        )

        assert len(chunks) > 0

        full_content = "".join(c.content for c in chunks if c.content)
        assert len(full_content) > 0
        print(f"\n  Streamed: {full_content[:100]}")

    def test_system_message(self, provider, test_config, langdock_resolved_model):
        """Test completion with system message via LangDock."""
        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "You only respond with the word 'ACKNOWLEDGED'."},
                {"role": "user", "content": "Hello!"},
            ],
            model=langdock_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "acknowledged" in response.content.lower()

    def test_eu_region(self, langdock_api_key, langdock_resolved_model):
        """Test that EU region is used for GDPR compliance."""
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")

        provider = get_provider(
            "langdock",
            api_key=langdock_api_key,
            backend="openai",
            region="eu",
        )

        # Verify region is set correctly
        assert provider.region == "eu"

        # Make a simple API call to verify it works. The budget is generous on
        # purpose: LangDock's current GPT-5.6 tier reasons before answering and
        # spent all of the previous 5 tokens thinking, returning empty content —
        # which failed this test for a reason that has nothing to do with the
        # region it is meant to check.
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model=langdock_resolved_model,
            max_tokens=512,
        )

        assert response.content


@pytest.mark.integration
class TestLangDockAnthropicBackend:
    """Live integration tests for LangDock with Anthropic backend."""

    @pytest.fixture
    def provider(self, langdock_api_key):
        """Create LangDock provider with Anthropic backend."""
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")
        return get_provider(
            "langdock",
            api_key=langdock_api_key,
            backend="anthropic",
            region="eu",
        )

    def test_anthropic_completion(self, provider, test_config, langdock_anthropic_resolved_model):
        """Test completion via LangDock Anthropic backend.

        Model id is resolved at session start against the live LangDock model
        list (see ``tests/model_registry.py`` -> ``langdock.anthropic``) to
        absorb LangDock's frequent ``claude-*-default`` rotations.
        """
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=langdock_anthropic_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")

    def test_anthropic_list_models(self, provider):
        """Test listing Anthropic models via LangDock."""
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        model_ids = [m.get("id", "") for m in models]
        assert any("claude" in m.lower() for m in model_ids)

        print(f"\n  Found {len(models)} Anthropic models")
        print(f"  Sample: {model_ids[:5]}")


# =============================================================================
# Cost-Effective Testing Pattern
# =============================================================================


@pytest.mark.integration
class TestCostEffectivePatterns:
    """Examples of cost-effective testing patterns."""

    def test_minimal_token_usage(self, openai_api_key, test_config):
        """Demonstrate minimal token usage pattern."""
        if not openai_api_key:
            pytest.skip("OPENAI_API_KEY not set")

        provider = get_provider("openai", api_key=openai_api_key)

        # Use the cheapest model
        model = "gpt-4o-mini"

        # Minimal prompt
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "1"}],  # Minimal input
            model=model,
            max_tokens=1,  # Minimal output
            temperature=0.0,
        )

        # This should cost < $0.0001
        print(f"\n  Tokens used: {response.input_tokens + response.output_tokens}")
        print(f"  Estimated cost: ~${(response.input_tokens * 0.15 + response.output_tokens * 0.60) / 1_000_000:.6f}")


@pytest.mark.integration
class TestLangDockGoogleBackend:
    """Live integration tests for LangDock with the Google backend.

    This backend is not OpenAI-compatible: `_google_chat_completion` posts to
    LangDock's Gemini endpoint with its own payload shape and converts message
    content into Gemini `parts` itself. Nothing the OpenAI-backend tests exercise
    covers that code, which is why it gets its own class.
    """

    @pytest.fixture
    def provider(self, langdock_api_key):
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")
        return get_provider("langdock", api_key=langdock_api_key, backend="google", region="eu")

    def test_google_completion(self, provider, test_config, langdock_google_resolved_model):
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say 'test' only."}],
            model=langdock_google_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "test" in response.content.lower()
        assert response.model

        print(f"\n  Model: {response.model}")
        print(f"  Response: {response.content}")

    def test_google_system_message(self, provider, test_config, langdock_google_resolved_model):
        """Gemini takes instructions separately — the conversion must not drop them."""
        response = provider.chat_completion(
            messages=[
                {"role": "system", "content": "Reply with exactly: ACKNOWLEDGED"},
                {"role": "user", "content": "Hello"},
            ],
            model=langdock_google_resolved_model,
            max_tokens=test_config.get("max_tokens", 10),
            temperature=0.0,
        )

        assert response.content
        assert "acknowledged" in response.content.lower()

    def test_google_streaming(self, provider, test_config, langdock_google_resolved_model):
        chunks = list(
            provider.stream_completion(
                messages=[{"role": "user", "content": "Count: 1 2 3"}],
                model=langdock_google_resolved_model,
                max_tokens=test_config.get("max_tokens", 20),
                temperature=0.0,
            )
        )

        assert chunks
        assert "".join(c.content or "" for c in chunks).strip()
        assert chunks[-1].is_final

    def test_google_list_models(self, provider):
        models = provider.list_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert all("id" in m for m in models)


@pytest.mark.integration
class TestLangDockDefaultsAreLive:
    """Nothing about model choice may quietly go stale.

    list_models() asks LangDock and gets back exactly the models this workspace
    enabled, so discovery is live everywhere. The one unavoidable constant is the
    per-backend default id — and that is precisely what broke on 23.08.2026, when
    the Google default still pointed at the retired gemini-2.5-flash and every
    default-model call answered 400. This test turns that class of failure into a
    red run instead of a production incident.
    """

    @pytest.mark.parametrize("backend", ["openai", "anthropic", "google"])
    def test_backend_defaults_are_actually_available(self, langdock_api_key, backend):
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")

        provider = get_provider("langdock", api_key=langdock_api_key, backend=backend, region="eu")
        available = {m["id"] for m in provider.list_models()}

        assert provider.default_model in available, (
            f"LangDock no longer serves the {backend} default "
            f"{provider.default_model!r} — available: {sorted(available)}"
        )

    def test_listing_reflects_the_workspace_not_a_catalogue(self, langdock_api_key):
        """A model the listing offers must be one the endpoint actually accepts."""
        if not langdock_api_key:
            pytest.skip("LANGDOCK_API_KEY not set")

        provider = get_provider("langdock", api_key=langdock_api_key, backend="google", region="eu")

        for model in provider.list_models():
            response = provider.chat_completion(
                messages=[{"role": "user", "content": "Hi"}],
                model=model["id"],
                max_tokens=512,
            )
            assert response.content, f"listing offers {model['id']} but it returned nothing"


@pytest.mark.integration
class TestProviderDefaultsAreLive:
    """Every provider's default model must be one the provider still serves.

    On 23.08.2026 four of them were not: anthropic pointed at
    claude-sonnet-4-20250514 and melious at minimax-428b-m3, both withdrawn, while
    openai/mammouth/openrouter still named gpt-4o — a generation this workspace no
    longer runs. A default is the id a caller gets when they pass none, so a stale
    one fails the very first call of anyone who did not choose explicitly.
    """

    @pytest.mark.parametrize(
        "provider_name,key_fixture",
        [
            ("openai", "openai_api_key"),
            ("anthropic", "anthropic_api_key"),
            ("openrouter", "openrouter_api_key"),
            ("mammouth", "mammouth_api_key"),
            ("melious", "melious_api_key"),
        ],
    )
    def test_default_model_is_still_served(self, request, provider_name, key_fixture):
        api_key = request.getfixturevalue(key_fixture)
        if not api_key:
            pytest.skip(f"{key_fixture.upper()} not set")

        provider = get_provider(provider_name, api_key=api_key)
        available = {m["id"] for m in provider.list_models()}

        assert provider.default_model in available, (
            f"{provider_name} no longer serves its default {provider.default_model!r}"
        )

    @pytest.mark.parametrize(
        "provider_name,key_fixture",
        [
            ("openai", "openai_api_key"),
            ("anthropic", "anthropic_api_key"),
            ("melious", "melious_api_key"),
        ],
    )
    def test_default_model_actually_answers(self, request, provider_name, key_fixture):
        """Being listed is not enough — the temperature handling must fit too.

        gpt-5.6 refuses the `temperature` parameter outright, so a provider that
        sends it anyway gets HTTP 400 on a model that looks perfectly available.
        """
        api_key = request.getfixturevalue(key_fixture)
        if not api_key:
            pytest.skip(f"{key_fixture.upper()} not set")

        provider = get_provider(provider_name, api_key=api_key)
        response = provider.chat_completion(
            messages=[{"role": "user", "content": "Say OK"}],
            model=provider.default_model,
            temperature=0.7,
            max_tokens=512,
        )

        assert response.content.strip()
