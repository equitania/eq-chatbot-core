"""Unit tests for the SSRF URL validator, focused on IPv6 transition addresses.

DNS64/NAT64 networks synthesize AAAA records inside the RFC 6052 well-known
prefix ``64:ff9b::/96`` for IPv4-only hosts. Those addresses must be classified
by the IPv4 address they embed, not by the synthesized IPv6 form.
"""

import socket
from unittest.mock import patch

import pytest

from eq_chatbot_core.utils.url_validation import validate_url


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
