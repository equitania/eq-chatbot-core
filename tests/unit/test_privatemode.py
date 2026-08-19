"""
Unit tests for the Privatemode.ai provider (end-to-end encrypted via local proxy).

All tests use mocked responses — no real API calls and no running proxy. The
provider is built on the openai SDK, so the openai module is mocked at import
time.

The focus of this module is the part that is unique to Privatemode: the
confidentiality boundary check that refuses configurations which would carry
prompts in cleartext across the public internet, and the routing of the
vendor's ``extra_body`` fields.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# The openai SDK is imported lazily inside the provider's `client` property, so
# it only has to be mocked while a test runs — see the autouse fixture below.
# Deliberately NOT installed at import time: several sibling test modules do that
# and rely on being the last importer, so an extra one silently breaks them.
mock_openai_module = MagicMock()

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
)
from eq_chatbot_core.providers.privatemode_provider import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    PrivatemodeProvider,
)

PROVIDER_MODULE = "eq_chatbot_core.providers.privatemode_provider"


def _addrinfo(*addresses):
    """Build a getaddrinfo() return value carrying the given IP addresses."""
    return [(2, 1, 6, "", (addr, 0)) for addr in addresses]


def _assert_pinned_http_client(call_kwargs):
    """The SDK client must be routed through the DNS-rebinding-aware transport."""
    http_client = call_kwargs["http_client"]
    transport = http_client._transport
    assert type(transport).__name__ == "_RevalidatingHostTransport", (
        f"expected pinned transport, got {type(transport).__name__}"
    )


@pytest.fixture
def mock_chat_response():
    """Mock chat completion response."""
    response = MagicMock()
    response.model = "kimi-latest"
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Vertraulich verarbeitet."
    response.choices[0].message.tool_calls = None
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 9
    response.usage.completion_tokens = 4
    response.model_dump.return_value = {"model": "kimi-latest"}
    return response


@pytest.fixture
def mock_stream_chunks():
    """Mock streaming chunk generator (usage arrives in the final chunk)."""

    def generate():
        for content in ["Ver", "trau", "lich"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = content
            chunk.choices[0].delta.tool_calls = None
            chunk.choices[0].finish_reason = None
            chunk.usage = None
            yield chunk

        final = MagicMock()
        final.choices = [MagicMock()]
        final.choices[0].delta.content = ""
        final.choices[0].delta.tool_calls = None
        final.choices[0].finish_reason = "stop"
        final.usage = MagicMock()
        final.usage.prompt_tokens = 5
        final.usage.completion_tokens = 3
        yield final

    return generate


@pytest.fixture
def mock_models_list():
    """Mock /v1/models response as served by the proxy."""
    models = MagicMock()
    models.data = [
        MagicMock(id="kimi-latest", created=1700000000, owned_by="moonshot"),
        MagicMock(id="gpt-oss-120b", created=1700000000, owned_by="openai"),
    ]
    return models


@pytest.fixture(autouse=True)
def _use_privatemode_openai_mock():
    """Install our openai mock for each test, then restore the prior entry.

    Other provider test modules also replace sys.modules["openai"] at import
    time, so the live entry depends on import order.
    """
    saved = sys.modules.get("openai")
    sys.modules["openai"] = mock_openai_module
    try:
        yield
    finally:
        if saved is not None:
            sys.modules["openai"] = saved
        else:
            sys.modules.pop("openai", None)


def _make_provider_with_client(mock_client) -> PrivatemodeProvider:
    """Build a provider whose openai client is the given mock."""
    mock_openai_module.OpenAI = MagicMock(return_value=mock_client)
    provider = PrivatemodeProvider()
    provider._client = None  # force lazy re-creation through the mocked OpenAI()
    return provider


# =============================================================================
# Initialization
# =============================================================================


@pytest.mark.unit
class TestPrivatemodeProviderInit:
    def test_basic_init_defaults_to_local_proxy(self):
        provider = PrivatemodeProvider()
        assert provider.base_url == DEFAULT_BASE_URL
        assert provider.timeout == 60.0
        assert provider.max_retries == 2

    def test_api_key_optional_uses_placeholder(self):
        # The proxy normally holds the key; the SDK still needs a non-empty one.
        provider = PrivatemodeProvider()
        assert provider.api_key == "placeholder"

    def test_api_key_passed_through_when_given(self):
        provider = PrivatemodeProvider(api_key="pm-secret")
        assert provider.api_key == "pm-secret"

    def test_private_range_allowed(self):
        # Cluster-internal deployments are documented by the vendor.
        provider = PrivatemodeProvider(base_url="http://10.1.2.3:8080/v1")
        assert provider.base_url == "http://10.1.2.3:8080/v1"

    def test_ssrf_metadata_still_blocked(self):
        # ALLOW_PRIVATE_RANGES must not open up cloud-metadata endpoints.
        with pytest.raises(ValueError):
            PrivatemodeProvider(base_url="http://169.254.169.254/v1")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(ValueError):
            PrivatemodeProvider(base_url="file:///etc/passwd")

    def test_lazy_client(self):
        provider = PrivatemodeProvider()
        assert provider._client is None

    def test_client_created_with_default_base_url(self):
        mock_openai_class = MagicMock()
        mock_openai_module.OpenAI = mock_openai_class

        provider = PrivatemodeProvider()
        provider._client = None
        _ = provider.client

        kwargs = mock_openai_class.call_args.kwargs
        _assert_pinned_http_client(kwargs)
        assert {k: v for k, v in kwargs.items() if k != "http_client"} == {
            "api_key": "placeholder",
            "base_url": DEFAULT_BASE_URL,
            "timeout": 60.0,
            "max_retries": 2,
        }


@pytest.mark.unit
class TestPrivatemodeProviderProperties:
    def test_provider_name(self):
        assert PrivatemodeProvider().provider_name == "privatemode"

    def test_default_model_fallback(self):
        assert PrivatemodeProvider().default_model == DEFAULT_MODEL

    def test_default_model_override(self):
        assert PrivatemodeProvider(model="gpt-oss-120b").default_model == "gpt-oss-120b"


# =============================================================================
# Confidentiality boundary — the part that is unique to this provider
# =============================================================================


@pytest.mark.unit
class TestConfidentialityBoundary:
    def test_loopback_needs_no_dns_lookup(self):
        # The default endpoint must not cost the boundary check a resolution.
        # (The SSRF guard that runs afterwards does its own lookup — this
        # asserts the short-circuit inside the boundary check itself.)
        with patch(f"{PROVIDER_MODULE}.socket.getaddrinfo") as resolver:
            PrivatemodeProvider._assert_confidentiality_boundary(DEFAULT_BASE_URL, False)
        resolver.assert_not_called()

    def test_public_host_over_plain_http_is_refused(self):
        with patch(f"{PROVIDER_MODULE}.socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            with pytest.raises(ValueError) as exc:
                PrivatemodeProvider(base_url="http://proxy.example.com:8080/v1")

        message = str(exc.value)
        assert "93.184.216.34" in message
        assert "end-to-end encryption" in message
        assert "allow_insecure_transport=True" in message

    def test_public_host_over_plain_http_allowed_with_override(self, caplog):
        with patch(f"{PROVIDER_MODULE}.socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            with caplog.at_level("WARNING", logger=PROVIDER_MODULE):
                provider = PrivatemodeProvider(
                    base_url="http://proxy.example.com:8080/v1",
                    allow_insecure_transport=True,
                )

        assert provider.base_url == "http://proxy.example.com:8080/v1"
        assert "does NOT hold" in caplog.text

    def test_https_is_allowed_without_lookup(self):
        # TLS protects the hop, so the boundary check needs no resolution at all.
        with patch(f"{PROVIDER_MODULE}.socket.getaddrinfo") as resolver:
            PrivatemodeProvider._assert_confidentiality_boundary("https://proxy.example.com/v1", False)
        resolver.assert_not_called()

    def test_private_host_over_plain_http_is_allowed_and_noted(self, caplog):
        with patch(f"{PROVIDER_MODULE}.socket.getaddrinfo", return_value=_addrinfo("10.1.2.3")):
            with caplog.at_level("INFO", logger=PROVIDER_MODULE):
                provider = PrivatemodeProvider(base_url="http://privatemode-proxy.svc.local:8080/v1")

        assert provider.base_url == "http://privatemode-proxy.svc.local:8080/v1"
        assert "private network" in caplog.text

    def test_mixed_resolution_with_any_public_address_is_refused(self):
        # A host resolving to both a private and a public address is unsafe.
        resolved = _addrinfo("10.1.2.3", "93.184.216.34")
        with patch(f"{PROVIDER_MODULE}.socket.getaddrinfo", return_value=resolved):
            with pytest.raises(ValueError):
                PrivatemodeProvider(base_url="http://proxy.example.com:8080/v1")

    def test_unresolvable_host_warns_and_defers(self, caplog):
        # A cluster-internal name may not resolve from where the client is
        # constructed. The boundary check warns instead of guessing; the SSRF
        # guard runs in LAN mode here and lets it through without IP pinning.
        import socket as _socket

        with patch(f"{PROVIDER_MODULE}.socket.getaddrinfo", side_effect=_socket.gaierror("nope")):
            with caplog.at_level("WARNING", logger=PROVIDER_MODULE):
                provider = PrivatemodeProvider(base_url="http://does-not-exist.invalid:8080/v1")

        assert provider.base_url == "http://does-not-exist.invalid:8080/v1"
        assert "could not be resolved" in caplog.text


# =============================================================================
# extra_body routing
# =============================================================================


@pytest.mark.unit
class TestExtraBodyRouting:
    def test_cache_salt_is_routed_into_extra_body(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            cache_salt="tenant-42",
        )

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["extra_body"] == {"cache_salt": "tenant-42"}
        assert "cache_salt" not in kwargs

    def test_chat_template_kwargs_is_routed_into_extra_body(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            chat_template_kwargs={"thinking": False},
        )

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["extra_body"] == {"chat_template_kwargs": {"thinking": False}}

    def test_explicit_extra_body_is_merged_not_replaced(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            extra_body={"custom": 1},
            cache_salt="tenant-42",
        )

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["extra_body"] == {"custom": 1, "cache_salt": "tenant-42"}

    def test_no_extra_body_when_nothing_requested(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "extra_body" not in kwargs


# =============================================================================
# Chat / streaming / models — inherited behaviour, verified once
# =============================================================================


@pytest.mark.unit
class TestPrivatemodeChatCompletion:
    def test_basic_completion(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        response = provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert response.content == "Vertraulich verarbeitet."
        assert response.model == "kimi-latest"
        assert response.input_tokens == 9
        assert response.output_tokens == 4
        assert response.finish_reason == "stop"

    def test_default_model_is_used(self, mock_chat_response):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_chat_response
        provider = _make_provider_with_client(mock_client)

        provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

        assert mock_client.chat.completions.create.call_args.kwargs["model"] == DEFAULT_MODEL


@pytest.mark.unit
class TestPrivatemodeStreaming:
    def test_stream_yields_content_and_final_usage(self, mock_stream_chunks):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_stream_chunks()
        provider = _make_provider_with_client(mock_client)

        chunks = list(provider.stream_completion(messages=[{"role": "user", "content": "Hi"}]))

        assert "".join(c.content or "" for c in chunks) == "Vertraulich"
        assert chunks[-1].is_final is True


@pytest.mark.unit
class TestPrivatemodeListModels:
    def test_list_models(self, mock_models_list):
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_models_list
        provider = _make_provider_with_client(mock_client)

        models = provider.list_models()

        assert {m["id"] for m in models} == {"kimi-latest", "gpt-oss-120b"}


@pytest.mark.unit
class TestPrivatemodeErrorHandling:
    def _raise(self, mock_client, exc):
        mock_client.chat.completions.create.side_effect = exc
        provider = _make_provider_with_client(mock_client)
        return provider

    def test_auth_error_mapped(self):
        provider = self._raise(MagicMock(), Exception("401 Unauthorized"))
        with pytest.raises(AuthenticationError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_rate_limit_mapped(self):
        provider = self._raise(MagicMock(), Exception("429 rate limit exceeded"))
        with pytest.raises(RateLimitError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_generic_error_mapped(self):
        provider = self._raise(MagicMock(), Exception("boom"))
        with pytest.raises(ProviderError):
            provider.chat_completion(messages=[{"role": "user", "content": "Hi"}])
