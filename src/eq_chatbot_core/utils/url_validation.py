"""
URL validation for SSRF protection.

Shared between the MCP SSE client (strict mode — blocks private networks) and
the local LLM provider (LAN mode — private/loopback ranges are legitimate for
on-prem model servers, but cloud-metadata and non-HTTP targets stay blocked).
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

_LOCALHOST_NAMES = ("localhost", "127.0.0.1", "::1")

# RFC 6052 well-known prefix used by DNS64 resolvers to synthesize AAAA records
# for IPv4-only hosts. Network-specific prefixes are not detectable from here.
_NAT64_WELL_KNOWN_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def _effective_address(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Return the address that actually determines where a connection lands.

    IPv4-mapped (``::ffff:0:0/96``) and DNS64-synthesized NAT64 addresses
    (``64:ff9b::/96``) are IPv6 wrappers around an IPv4 target. Both prefixes sit
    inside ``::/8``, which Python flags as ``is_reserved`` — so classifying the
    wrapper itself would reject every IPv4-only endpoint on a NAT64 network,
    public API hosts included.

    Classifying the embedded IPv4 instead keeps the guard honest in both
    directions: ``64:ff9b::a9fe:a9fe`` unwraps to 169.254.169.254 and stays
    blocked as the cloud-metadata endpoint it is.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip in _NAT64_WELL_KNOWN_PREFIX:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip


def validate_url(url: str, *, allow_private_ranges: bool = False) -> frozenset[str]:
    """Validate a URL for SSRF protection and return its currently-resolved IPs.

    The returned IP set can be pinned by the caller and re-checked on each
    subsequent request to mitigate DNS rebinding. In LAN mode
    (``allow_private_ranges=True``) an empty frozenset is returned when the
    hostname cannot be resolved at validation time (callers may treat this as
    "no pinning available"). In strict mode an unresolvable hostname is rejected,
    because allowing it would disable the rebinding protection.

    Args:
        url: URL to validate.
        allow_private_ranges: When False (default, strict / cloud-facing), any
            private, reserved, loopback, or link-local target is rejected unless
            the hostname is an explicit localhost name. When True (LAN mode for
            local LLM servers), private and loopback ranges are permitted, but
            link-local (e.g. the 169.254.169.254 cloud-metadata endpoint),
            reserved, multicast, and unspecified addresses remain blocked.

    Returns:
        Frozenset of resolved IP address strings (may be empty if unresolvable).

    Raises:
        ValueError: If the scheme is not http/https, the hostname is missing, or
            the URL resolves to a disallowed address.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed. Use http or https.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must contain a valid hostname")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        # Strict / cloud-facing mode: an unresolvable hostname disables IP
        # pinning, which would otherwise re-open the DNS-rebinding hole the
        # pinning is meant to close. Refuse it rather than silently allowing.
        if not allow_private_ranges:
            raise ValueError(f"URL hostname '{hostname}' could not be resolved; refusing in strict mode.") from e
        # LAN mode: a local model server may legitimately be unresolvable from
        # here (e.g. a hostname only known to the on-prem resolver). Allow it,
        # but signal that no rebinding pin is available for this URL.
        _logger.warning(
            "URL hostname '%s' could not be resolved; allowing without IP pinning (LAN mode).",
            hostname,
        )
        return frozenset()

    is_localhost_name = hostname in _LOCALHOST_NAMES
    resolved_ips: set[str] = set()

    for addr_info in addr_infos:
        ip_str = str(addr_info[4][0])
        # Classify the embedded IPv4 for NAT64/IPv4-mapped forms, but keep pinning
        # the address as resolved — the connection may still take the IPv6 route.
        ip = _effective_address(ipaddress.ip_address(ip_str))
        shown = ip_str if str(ip) == ip_str else f"{ip_str} (embeds {ip})"

        if allow_private_ranges:
            # LAN mode: loopback and private ranges are legitimate for local model
            # servers; still block link-local (cloud-metadata 169.254.x), multicast,
            # unspecified, and non-loopback reserved targets.
            if ip.is_loopback:
                pass  # 127.0.0.1 / ::1 — explicitly allowed
            elif ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
                raise ValueError(f"URL resolves to disallowed IP {shown} (cloud-metadata / reserved range).")
        else:
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                # Allow localhost explicitly for local development.
                if is_localhost_name:
                    resolved_ips.add(ip_str)
                    continue
                raise ValueError(
                    f"URL resolves to private/reserved IP {shown}. "
                    "Internal network access is not allowed for security reasons."
                )
        resolved_ips.add(ip_str)

    return frozenset(resolved_ips)
