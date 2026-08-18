"""
URL validation for SSRF protection.

Shared between the MCP SSE client (strict mode — blocks private networks) and
the local LLM provider (LAN mode — private/loopback ranges are legitimate for
on-prem model servers, but cloud-metadata and non-HTTP targets stay blocked).

Validation alone only covers the resolution at construction time. Anything that
issues requests later must additionally pin the resolved addresses via
:func:`build_pinned_transport_for_url`, otherwise an attacker-controlled
hostname can pass validation and re-resolve to an internal address before the
socket is opened (DNS rebinding / TOCTOU SSRF).
"""

import ipaddress
import logging
import socket
import threading
from typing import Any
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


def _assert_ip_allowed(ip_str: str, *, allow_private_ranges: bool, is_localhost_name: bool) -> None:
    """Raise ValueError if a resolved address is not an allowed connect target.

    Shared by :func:`validate_url` (construction time) and the revalidating
    transport (request time) so both apply exactly the same policy.

    Args:
        ip_str: Resolved address, as returned by ``socket.getaddrinfo``.
        allow_private_ranges: LAN mode — permit loopback/private targets.
        is_localhost_name: Whether the hostname itself is an explicit localhost
            name, which is allowed to resolve into loopback even in strict mode.

    Raises:
        ValueError: If the address is a disallowed target.
    """
    # Classify the embedded IPv4 for NAT64/IPv4-mapped forms, but keep pinning
    # the address as resolved — the connection may still take the IPv6 route.
    ip = _effective_address(ipaddress.ip_address(ip_str))
    shown = ip_str if str(ip) == ip_str else f"{ip_str} (embeds {ip})"

    if allow_private_ranges:
        # LAN mode: loopback and private ranges are legitimate for local model
        # servers; still block link-local (cloud-metadata 169.254.x), multicast,
        # unspecified, and non-loopback reserved targets.
        if ip.is_loopback:
            return  # 127.0.0.1 / ::1 — explicitly allowed
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise ValueError(f"URL resolves to disallowed IP {shown} (cloud-metadata / reserved range).")
        return

    if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
        # Allow localhost explicitly for local development.
        if is_localhost_name:
            return
        raise ValueError(
            f"URL resolves to private/reserved IP {shown}. Internal network access is not allowed for security reasons."
        )


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
        _assert_ip_allowed(
            ip_str,
            allow_private_ranges=allow_private_ranges,
            is_localhost_name=is_localhost_name,
        )
        resolved_ips.add(ip_str)

    return frozenset(resolved_ips)


def _http_lib(http: Any = None) -> Any:
    """Return the HTTP client library a transport should be built against.

    Two libraries are unavoidably in play: httpx2 is Pydantic's maintained
    continuation of httpx and carries this library's own requests plus the
    OpenAI SDK, while the Anthropic SDK still declares ``httpx<1`` in every
    release up to 0.122 and rejects an httpx2 client. Rather than duplicate the
    guard for each, the transports below are built against whichever module the
    caller passes.

    Args:
        http: The ``httpx`` or ``httpx2`` module. Defaults to httpx2.

    Returns:
        The module to build the transport against.

    Raises:
        ImportError: If the default library is not installed.
    """
    if http is not None:
        return http
    try:
        import httpx2
    except ImportError as e:  # pragma: no cover - httpx2 is a core dependency
        raise ImportError("httpx2 package not installed. Install with: pip install httpx2") from e
    return httpx2


def build_pinned_transport(pinned_ips: dict[str, frozenset[str]], lock: threading.Lock, *, http: Any = None) -> Any:
    """Build an httpx HTTPTransport that re-checks DNS resolution against pinned IPs.

    Mitigates DNS rebinding attacks: at validation time the URL's hostname is
    resolved to a set of allowed IPs; at request time the transport re-resolves
    and rejects the connection if the resolution diverges from that set.

    Note: A small TOCTOU window remains between this check and httpx's actual
    socket connect call. For complete protection, deploy network-level egress
    filtering against private/reserved IP ranges.

    Args:
        pinned_ips: Shared mapping of hostname -> frozenset of allowed IPs.
                    The caller may keep updating it as new endpoints are
                    validated; the transport reads it under ``lock``.
        lock: Lock guarding concurrent updates to ``pinned_ips``.

    Returns:
        Subclass of httpx.HTTPTransport.

    Raises:
        ImportError: If httpx is not installed.
    """
    httpx = _http_lib(http)

    class _PinnedHostTransport(httpx.HTTPTransport):  # type: ignore[misc,name-defined]
        def handle_request(self, request: Any) -> Any:
            host = request.url.host
            with lock:
                pinned = pinned_ips.get(host)
            if pinned:
                try:
                    infos = socket.getaddrinfo(host, None)
                except socket.gaierror as e:
                    raise httpx.ConnectError(f"DNS resolution failed for {host}: {e}") from e
                current = frozenset(str(info[4][0]) for info in infos)
                rogue = current - pinned
                if rogue:
                    raise httpx.ConnectError(
                        f"DNS rebinding detected: {host} now resolves to {sorted(rogue)}, "
                        f"expected subset of pinned set {sorted(pinned)}."
                    )
            return super().handle_request(request)

    return _PinnedHostTransport()


def build_pinned_transport_for_url(url: str, *, allow_private_ranges: bool = False, http: Any = None) -> Any:
    """Validate ``url`` and return an httpx transport that re-checks every connect.

    Convenience wrapper for the common single-endpoint case: callers that talk to
    exactly one host (every LLM provider) get validation and rebinding protection
    in one call, instead of validating once and then connecting unpinned.

    Unlike :func:`build_pinned_transport`, a divergence from the pinned set is not
    rejected outright — the new addresses are re-run through the same SSRF policy
    and only blocked if they are private/reserved/metadata targets. That keeps the
    security property (never connect to an internal address) while tolerating the
    legitimate IP rotation of CDN-fronted provider endpoints, which strict pinning
    would eventually turn into hard connection failures in long-lived processes.

    Args:
        url: Base URL to validate and pin.
        allow_private_ranges: Permit private/loopback targets (on-prem servers).

    Returns:
        Subclass of httpx.HTTPTransport, seeded with the IPs ``url`` resolved to.

    Raises:
        ValueError: If ``url`` fails SSRF validation.
        ImportError: If httpx is not installed.
    """
    httpx = _http_lib(http)

    resolved = validate_url(url, allow_private_ranges=allow_private_ranges)
    hostname = urlparse(url).hostname
    allowed: dict[str, frozenset[str]] = {hostname: resolved} if hostname else {}
    lock = threading.Lock()

    class _RevalidatingHostTransport(httpx.HTTPTransport):  # type: ignore[misc,name-defined]
        def handle_request(self, request: Any) -> Any:
            host = request.url.host
            with lock:
                pinned = allowed.get(host)
            if pinned is None:
                return super().handle_request(request)

            try:
                infos = socket.getaddrinfo(host, None)
            except socket.gaierror as e:
                if allow_private_ranges:
                    # LAN mode mirrors validate_url: a local hostname may only be
                    # resolvable further down the path (proxy, on-prem resolver).
                    _logger.warning("Could not re-resolve '%s' for rebinding check; proceeding (LAN mode).", host)
                    return super().handle_request(request)
                raise httpx.ConnectError(f"DNS resolution failed for {host}: {e}") from e

            current = frozenset(str(info[4][0]) for info in infos)
            unseen = current - pinned
            if unseen:
                is_localhost_name = host in _LOCALHOST_NAMES
                for ip_str in sorted(unseen):
                    try:
                        _assert_ip_allowed(
                            ip_str,
                            allow_private_ranges=allow_private_ranges,
                            is_localhost_name=is_localhost_name,
                        )
                    except ValueError as e:
                        raise httpx.ConnectError(f"DNS rebinding blocked for {host}: {e}") from e
                with lock:
                    allowed[host] = allowed.get(host, frozenset()) | unseen

            return super().handle_request(request)

    return _RevalidatingHostTransport()


def build_validating_transport(*, allow_private_ranges: bool = False, http: Any = None) -> Any:
    """Build an httpx transport that SSRF-checks *every* host it connects to.

    Use this instead of :func:`build_pinned_transport_for_url` when the target is
    not a single known endpoint — a URL taken from an API response, a
    configurable catalog location, or any request made with
    ``follow_redirects=True``. Pinning only guards hosts it already knows, so a
    redirect to a fresh hostname would sail past it; this transport re-applies
    the full policy to whatever host each hop actually names.

    Args:
        allow_private_ranges: Permit private/loopback targets (on-prem servers).

    Returns:
        Subclass of httpx.HTTPTransport.

    Raises:
        ImportError: If httpx is not installed.
    """
    httpx = _http_lib(http)

    class _ValidatingHostTransport(httpx.HTTPTransport):  # type: ignore[misc,name-defined]
        def handle_request(self, request: Any) -> Any:
            if request.url.scheme not in ("http", "https"):
                raise httpx.ConnectError(f"Blocked request: scheme '{request.url.scheme}' is not allowed.")

            host = request.url.host
            if not host:
                raise httpx.ConnectError("Blocked request: URL has no hostname.")

            try:
                infos = socket.getaddrinfo(host, None)
            except socket.gaierror as e:
                raise httpx.ConnectError(f"DNS resolution failed for {host}: {e}") from e

            is_localhost_name = host in _LOCALHOST_NAMES
            for info in infos:
                try:
                    _assert_ip_allowed(
                        str(info[4][0]),
                        allow_private_ranges=allow_private_ranges,
                        is_localhost_name=is_localhost_name,
                    )
                except ValueError as e:
                    raise httpx.ConnectError(f"Blocked request to {host}: {e}") from e

            return super().handle_request(request)

    return _ValidatingHostTransport()
