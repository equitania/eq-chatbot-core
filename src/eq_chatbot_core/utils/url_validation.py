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
        ip = ipaddress.ip_address(ip_str)

        if allow_private_ranges:
            # LAN mode: loopback and private ranges are legitimate for local model
            # servers; still block link-local (cloud-metadata 169.254.x), multicast,
            # unspecified, and non-loopback reserved targets.
            if ip.is_loopback:
                pass  # 127.0.0.1 / ::1 — explicitly allowed
            elif ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
                raise ValueError(f"URL resolves to disallowed IP {ip} (cloud-metadata / reserved range).")
        else:
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                # Allow localhost explicitly for local development.
                if is_localhost_name:
                    resolved_ips.add(ip_str)
                    continue
                raise ValueError(
                    f"URL resolves to private/reserved IP {ip}. "
                    "Internal network access is not allowed for security reasons."
                )
        resolved_ips.add(ip_str)

    return frozenset(resolved_ips)
