"""Unit tests for the SSRF URL validator, focused on IPv6 transition addresses.

DNS64/NAT64 networks synthesize AAAA records inside the RFC 6052 well-known
prefix ``64:ff9b::/96`` for IPv4-only hosts. Those addresses must be classified
by the IPv4 address they embed, not by the synthesized IPv6 form.
"""

import socket
from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.utils.url_validation import (
    build_pinned_transport_for_url,
    build_validating_transport,
    validate_url,
)


def _addrinfo(*ips: str) -> list[tuple]:
    """Build a getaddrinfo-style result set for the given IP strings."""
    infos: list[tuple] = []
    for ip in ips:
        if ":" in ip:
            infos.append((socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, 0, 0, 0)))
        else:
            infos.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)))
    return infos


@pytest.mark.unit
class TestNAT64Synthesis:
    """A DNS64 resolver must not make public IPv4-only endpoints unreachable."""

    def test_dual_result_with_synthesized_ipv6_accepted(self):
        """Real-world DNS64 answer: public A record plus synthesized AAAA."""
        # 64:ff9b::a213:88b8 embeds 162.19.136.184 (public).
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("162.19.136.184", "64:ff9b::a213:88b8")):
            ips = validate_url("https://api.example.com/v1")

        # Both forms stay pinnable: the connection may take either address.
        assert ips == frozenset({"162.19.136.184", "64:ff9b::a213:88b8"})

    def test_synthesized_ipv6_only_accepted(self):
        """IPv6-only clients see nothing but the synthesized address."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::a213:88b8")):
            ips = validate_url("https://api.example.com/v1")

        assert ips == frozenset({"64:ff9b::a213:88b8"})

    def test_synthesized_ipv6_accepted_in_lan_mode(self):
        """LAN mode must not be stricter than strict mode for public targets."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::a213:88b8")):
            ips = validate_url("https://api.example.com/v1", allow_private_ranges=True)

        assert ips == frozenset({"64:ff9b::a213:88b8"})


@pytest.mark.unit
class TestNAT64DoesNotWeakenSSRFProtection:
    """Unwrapping must classify the embedded IPv4, never wave the prefix through."""

    def test_metadata_endpoint_blocked(self):
        """64:ff9b::a9fe:a9fe embeds 169.254.169.254 (cloud metadata)."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::a9fe:a9fe")):
            with pytest.raises(ValueError, match="private/reserved"):
                validate_url("https://metadata.example.com")

    def test_metadata_endpoint_blocked_in_lan_mode(self):
        """Link-local stays blocked even where private ranges are legitimate."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::a9fe:a9fe")):
            with pytest.raises(ValueError, match="disallowed"):
                validate_url("https://metadata.example.com", allow_private_ranges=True)

    def test_private_range_blocked_in_strict_mode(self):
        """64:ff9b::a00:1 embeds 10.0.0.1."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::a00:1")):
            with pytest.raises(ValueError, match="private/reserved"):
                validate_url("https://internal.example.com")

    def test_loopback_blocked_in_strict_mode(self):
        """64:ff9b::7f00:1 embeds 127.0.0.1."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::7f00:1")):
            with pytest.raises(ValueError, match="private/reserved"):
                validate_url("https://sneaky.example.com")

    def test_private_range_allowed_in_lan_mode(self):
        """On-prem model servers behind NAT64 remain reachable in LAN mode."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::a00:1")):
            ips = validate_url("https://llm.internal.example.com", allow_private_ranges=True)

        assert ips == frozenset({"64:ff9b::a00:1"})

    def test_one_bad_address_rejects_the_whole_url(self):
        """A public A record must not launder a disallowed synthesized AAAA."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.34", "64:ff9b::a9fe:a9fe")):
            with pytest.raises(ValueError, match="private/reserved"):
                validate_url("https://rebind.example.com")


@pytest.mark.unit
class TestIPv4MappedAddresses:
    """::ffff:0:0/96 inherits is_reserved from ::/8 and needs the same handling."""

    def test_public_mapped_address_accepted(self):
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("::ffff:93.184.216.34")):
            ips = validate_url("https://api.example.com")

        assert ips == frozenset({"::ffff:93.184.216.34"})

    def test_private_mapped_address_blocked(self):
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("::ffff:10.0.0.1")):
            with pytest.raises(ValueError, match="private/reserved"):
                validate_url("https://internal.example.com")


@pytest.mark.unit
class TestNativeIPv6Unchanged:
    """Ordinary IPv6 classification must be untouched by the unwrapping."""

    def test_global_ipv6_accepted(self):
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("2607:6bc0::10")):
            ips = validate_url("https://api.example.com")

        assert ips == frozenset({"2607:6bc0::10"})

    def test_reserved_ipv6_still_blocked(self):
        """100::/64 (discard-only) is genuinely reserved — not a NAT64 address."""
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("100::1")):
            with pytest.raises(ValueError, match="private/reserved"):
                validate_url("https://blackhole.example.com")

    def test_unique_local_ipv6_blocked_in_strict_mode(self):
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("fd00::1")):
            with pytest.raises(ValueError, match="private/reserved"):
                validate_url("https://internal.example.com")


@pytest.mark.unit
class TestPinnedTransportRebinding:
    """The transport returned by build_pinned_transport_for_url must re-check DNS.

    Validating the URL once in the constructor only covers that moment: a hostname
    can pass validation and then re-resolve to an internal target before the socket
    is opened (DNS rebinding / TOCTOU SSRF).
    """

    def _transport(self, initial_ip: str = "93.184.216.34", **kwargs):
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo(initial_ip)):
            return build_pinned_transport_for_url("https://api.example.com/v1", **kwargs)

    def _request(self):
        import httpx2

        return httpx2.Request("GET", "https://api.example.com/v1/models")

    def test_rebinding_to_cloud_metadata_is_blocked(self):
        import httpx2

        transport = self._transport()
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("169.254.169.254")):
            with pytest.raises(httpx2.ConnectError, match="DNS rebinding blocked"):
                transport.handle_request(self._request())

    def test_rebinding_to_private_range_is_blocked(self):
        import httpx2

        transport = self._transport()
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("10.0.0.5")):
            with pytest.raises(httpx2.ConnectError, match="DNS rebinding blocked"):
                transport.handle_request(self._request())

    def test_rebinding_via_nat64_wrapped_metadata_is_blocked(self):
        """The embedded IPv4 must be classified, not just the outer IPv6 form."""
        import httpx2

        transport = self._transport()
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("64:ff9b::a9fe:a9fe")):
            with pytest.raises(httpx2.ConnectError, match="DNS rebinding blocked"):
                transport.handle_request(self._request())

    def test_rotation_to_another_public_ip_is_allowed(self):
        """CDN-fronted endpoints legitimately rotate; that must not break requests.

        Strict set-pinning would reject this and turn normal IP rotation into hard
        connection failures in long-lived processes.
        """
        transport = self._transport()
        called = {}

        def _fake_super(request):
            called["ok"] = True

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.99")):
            with patch("httpx2.HTTPTransport.handle_request", side_effect=_fake_super):
                transport.handle_request(self._request())

        assert called.get("ok"), "legitimate public-IP rotation must pass the guard"

    def test_unchanged_resolution_is_allowed(self):
        transport = self._transport()
        called = {}

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            with patch("httpx2.HTTPTransport.handle_request", side_effect=lambda r: called.setdefault("ok", True)):
                transport.handle_request(self._request())

        assert called.get("ok")

    def test_lan_mode_allows_private_target_but_still_blocks_metadata(self):
        import httpx2

        transport = self._transport("192.168.1.50", allow_private_ranges=True)

        # A different private address is fine in LAN mode ...
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("192.168.1.51")):
            with patch("httpx2.HTTPTransport.handle_request", side_effect=lambda r: None):
                transport.handle_request(self._request())

        # ... but the cloud-metadata endpoint stays blocked even there.
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("169.254.169.254")):
            with pytest.raises(httpx2.ConnectError, match="DNS rebinding blocked"):
                transport.handle_request(self._request())

    def test_strict_mode_rejects_unresolvable_host_at_request_time(self):
        import httpx2

        transport = self._transport()
        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("nope")):
            with pytest.raises(httpx2.ConnectError, match="DNS resolution failed"):
                transport.handle_request(self._request())


@pytest.mark.unit
class TestValidatingTransport:
    """build_validating_transport checks every host, not just pinned ones.

    Needed wherever the target is not one known endpoint: a URL from an API
    response, a configurable catalog location, or any request that follows
    redirects — a redirect can name a host no pin ever covered.
    """

    def _request(self, url="https://storage.example.com/report.csv"):
        import httpx2

        return httpx2.Request("GET", url)

    def test_public_host_passes(self):
        transport = build_validating_transport()
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            with patch("httpx2.HTTPTransport.handle_request", return_value="passed"):
                assert transport.handle_request(self._request()) == "passed"

    def test_metadata_endpoint_blocked(self):
        import httpx2

        transport = build_validating_transport()
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("169.254.169.254")):
            with pytest.raises(httpx2.ConnectError, match="Blocked request"):
                transport.handle_request(self._request())

    def test_private_range_blocked(self):
        import httpx2

        transport = build_validating_transport()
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("10.1.2.3")):
            with pytest.raises(httpx2.ConnectError, match="Blocked request"):
                transport.handle_request(self._request())

    def test_any_disallowed_address_in_the_set_blocks(self):
        """A host resolving to one public and one internal address must not pass."""
        import httpx2

        transport = build_validating_transport()
        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.34", "127.0.0.1")):
            with pytest.raises(httpx2.ConnectError, match="Blocked request"):
                transport.handle_request(self._request())

    def test_non_http_scheme_blocked(self):
        import httpx2

        transport = build_validating_transport()
        with pytest.raises(httpx2.ConnectError, match="scheme"):
            transport.handle_request(httpx2.Request("GET", "ftp://example.com/x"))

    def test_unresolvable_host_blocked(self):
        import httpx2

        transport = build_validating_transport()
        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror("nope")):
            with pytest.raises(httpx2.ConnectError, match="DNS resolution failed"):
                transport.handle_request(self._request())

    def test_lan_mode_allows_private_but_not_metadata(self):
        import httpx2

        transport = build_validating_transport(allow_private_ranges=True)

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("192.168.1.10")):
            with patch("httpx2.HTTPTransport.handle_request", return_value="passed"):
                assert transport.handle_request(self._request()) == "passed"

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("169.254.169.254")):
            with pytest.raises(httpx2.ConnectError, match="Blocked request"):
                transport.handle_request(self._request())


@pytest.mark.unit
class TestClientLibrarySplit:
    """Two HTTP client libraries are in play, and which one is used matters.

    httpx2 (Pydantic's maintained continuation of httpx) carries this library's
    own requests and the OpenAI SDK, which moved to it in 3.x. The Anthropic SDK
    still declares ``httpx<1`` in every release up to 0.122 and rejects an httpx2
    client, so that one provider stays on httpx. Mixing them up produces a
    transport the SDK will not accept, so the split is asserted rather than
    assumed.
    """

    def test_default_transport_is_built_against_httpx2(self):
        import httpx2

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            transport = build_pinned_transport_for_url("https://api.example.com/v1")

        assert isinstance(transport, httpx2.HTTPTransport)

    def test_transport_can_be_built_against_httpx_for_the_anthropic_sdk(self):
        import httpx

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            transport = build_pinned_transport_for_url("https://api.example.com/v1", http=httpx)

        assert isinstance(transport, httpx.HTTPTransport)

    def test_validating_transport_honours_the_same_choice(self):
        import httpx

        assert isinstance(build_validating_transport(http=httpx), httpx.HTTPTransport)

    def test_guard_still_fires_on_the_httpx_variant(self):
        """The Anthropic island must not be a hole in the SSRF protection."""
        import httpx

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            transport = build_pinned_transport_for_url("https://api.example.com/v1", http=httpx)

        with patch.object(socket, "getaddrinfo", return_value=_addrinfo("169.254.169.254")):
            with pytest.raises(httpx.ConnectError, match="DNS rebinding blocked"):
                transport.handle_request(httpx.Request("GET", "https://api.example.com/v1/models"))

    def test_anthropic_provider_builds_an_httpx_client(self):
        """AnthropicProvider must hand the SDK a client it accepts."""
        import httpx

        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider(api_key="sk-ant-test")
            provider._client = None
            _ = provider.client

        http_client = mock_anthropic.Anthropic.call_args[1]["http_client"]
        assert isinstance(http_client, httpx.Client)
