"""
Privatemode provider implementation (Edgeless Systems).

Privatemode is an end-to-end encrypted GenAI service built on confidential
computing: prompts and responses are encrypted on the client side and only
decrypted inside a hardware-isolated Confidential Computing Environment (CCE) on
the server. Neither the service provider (Edgeless Systems) nor the
infrastructure provider (Scaleway, EU) can read the data. Vetted as EU/GDPR
compliant.

Architecture — READ THIS BEFORE CHANGING ANYTHING HERE
------------------------------------------------------
Unlike every other provider in this package, Privatemode has **no public HTTPS
API to talk to directly**. The encryption and the remote attestation of the
server side are performed by a *local proxy* that the operator runs themselves::

    docker run -p 8080:8080 \\
        ghcr.io/edgelesssys/privatemode/privatemode-proxy:latest \\
        --apiKey <your-api-key>

This provider therefore speaks plain OpenAI Chat Completions to that proxy —
by default ``http://localhost:8080/v1`` — and the proxy does the confidential
part. Two consequences follow, and both are enforced below:

1. ``ALLOW_PRIVATE_RANGES`` must be ``True``. The endpoint is *supposed* to be
   loopback; the SSRF guard would otherwise reject the only correct
   configuration. Cloud-metadata and link-local targets stay blocked regardless.

2. **The end-to-end guarantee is only as good as the hop to the proxy.** Plain
   HTTP to a public address would put prompts on the wire in cleartext while the
   caller believes they are encrypted — the exact failure this product exists to
   prevent. Such a configuration is rejected at construction (see
   :meth:`_assert_confidentiality_boundary`); loopback and cluster-internal
   deployments, which the vendor documents, are allowed.

API key handling
----------------
The proxy normally holds the key (``--apiKey``) and authenticates upstream on the
client's behalf, so ``api_key`` is **optional** here. The OpenAI SDK insists on a
non-empty value, so a placeholder is substituted — this mirrors the vendor's own
Python example. When the proxy is started *without* ``--apiKey`` it forwards the
caller's ``Authorization`` header instead; pass the real key in that case.

Models (see https://docs.privatemode.ai/models/overview/)
---------------------------------------------------------
Model ids change over time and are discovered live via ``GET /v1/models``; no
static catalog is bundled on purpose. At the time of writing the chat models are
``kimi-latest`` / ``kimi-k2.6`` (256k context, vision) and ``gpt-oss-120b``
(128k, text only); all chat models support streaming, tool calling and
structured outputs.

Reference endpoints (OpenAI-compatible, served by the proxy):
- POST /v1/chat/completions   (chat + streaming)
- GET  /v1/models
- POST /v1/embeddings         (``qwen3-embedding-4b``)
- POST /v1/audio/transcriptions (``whisper-large-v3``, ``voxtral-mini-3b``)
"""

import ipaddress
import logging
import socket
from typing import Any, ClassVar
from urllib.parse import urlparse

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider

_logger = logging.getLogger(__name__)

# Hostnames that are loopback by definition and need no DNS round-trip.
_LOOPBACK_NAMES = ("localhost", "127.0.0.1", "::1")


class PrivatemodeProvider(OpenAICompatibleProvider):
    """
    Provider for the Privatemode API via its local, attesting proxy.

    Supports chat completion, streaming, tool calls and model listing through the
    OpenAI-compatible endpoints the proxy exposes. Prompt caching
    (``cache_salt``) and model-specific template flags (``chat_template_kwargs``)
    are accepted as ordinary keyword arguments and routed into the SDK's
    ``extra_body`` for you.
    """

    PROVIDER_NAME = "privatemode"
    # The proxy runs on the caller's own machine by default and terminates the
    # confidential channel; this is a local address by design, not a fallback.
    DEFAULT_BASE_URL = "http://localhost:8080/v1"
    # Soft default — `-latest` tracks the current Kimi release, which the vendor
    # recommends because concrete model ids are retired over time.
    DEFAULT_MODEL = "kimi-latest"
    # The endpoint is loopback (or cluster-internal) by design.
    ALLOW_PRIVATE_RANGES = True

    # Request extras the vendor documents as `extra_body` fields rather than
    # top-level parameters; passing them at top level makes the SDK reject them.
    EXTRA_BODY_KEYS: ClassVar[frozenset[str]] = frozenset({"cache_salt", "chat_template_kwargs"})

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
        *,
        allow_insecure_transport: bool = False,
    ):
        """
        Initialize the provider.

        Args:
            api_key: Optional. Only needed when the proxy was started *without*
                ``--apiKey`` and forwards the caller's ``Authorization`` header.
                When the proxy holds the key, leave this unset.
            base_url: Endpoint of the Privatemode proxy. Defaults to
                ``http://localhost:8080/v1``.
            timeout: Request timeout in seconds.
            max_retries: Number of retries on transient failures.
            model: Default model id for this instance (overridable per call).
            allow_insecure_transport: Escape hatch that permits plain HTTP to a
                *public* address. Off by default because it silently voids the
                end-to-end encryption guarantee; set it only when an external
                mechanism (VPN, service mesh, IPsec) protects that hop.

        Raises:
            ValueError: If ``base_url`` fails URL validation, or if it would
                carry prompts in cleartext to a public address without
                ``allow_insecure_transport``.
        """
        effective_base_url = base_url or self.DEFAULT_BASE_URL
        # Checked before super(), so an unsafe endpoint never reaches the client.
        self._assert_confidentiality_boundary(effective_base_url, allow_insecure_transport)

        # The proxy authenticates upstream on our behalf in the common setup, but
        # the OpenAI SDK rejects an empty key — substitute the placeholder the
        # vendor's own example uses.
        super().__init__(
            api_key=api_key or "placeholder",
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            model=model,
        )

    @staticmethod
    def _assert_confidentiality_boundary(base_url: str, allow_insecure_transport: bool) -> None:
        """Reject configurations that would void the end-to-end encryption.

        The proxy is what encrypts; the hop *to* the proxy is ordinary traffic.
        That hop is acceptable when it is HTTPS, or when it never leaves the host
        or the private network. It is not acceptable in cleartext across the
        public internet — that is precisely the exposure Privatemode is bought to
        eliminate, and it would fail silently.

        Args:
            base_url: The endpoint the client will be pointed at.
            allow_insecure_transport: Deliberate override for cleartext to a
                public address.

        Raises:
            ValueError: On cleartext HTTP to a public address without the
                override.
        """
        parsed = urlparse(base_url)
        # TLS to the proxy: the hop is protected regardless of where it lives.
        if parsed.scheme == "https":
            return

        hostname = parsed.hostname
        if not hostname:
            # Malformed URLs are the SSRF guard's job; it runs right after us and
            # produces a better message than we could here.
            return

        # Short-circuit the common case so the default endpoint costs no lookup.
        if hostname in _LOOPBACK_NAMES:
            return

        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            # Unresolvable here does not mean unresolvable at request time (a
            # cluster-internal name is a normal deployment). Warn and defer the
            # decision to the SSRF guard rather than guessing.
            _logger.warning(
                "Privatemode proxy host '%s' could not be resolved; cannot verify that the "
                "connection to the proxy stays on a trusted network.",
                hostname,
            )
            return

        public_addresses = []
        for info in addr_infos:
            try:
                ip = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if ip.is_global:
                public_addresses.append(str(ip))

        if not public_addresses:
            # Private / cluster-internal over HTTP: the vendor documents this for
            # the Helm deployment. Legitimate, but the hop is still cleartext.
            _logger.info(
                "Privatemode proxy at '%s' is reached over plain HTTP on a private network. "
                "Traffic between this client and the proxy is unencrypted; the end-to-end "
                "guarantee covers only the proxy-to-CCE leg.",
                hostname,
            )
            return

        if allow_insecure_transport:
            _logger.warning(
                "Privatemode proxy at '%s' resolves to a PUBLIC address over plain HTTP (%s). "
                "Prompts and responses leave this host unencrypted; the end-to-end encryption "
                "guarantee does NOT hold. Permitted only because allow_insecure_transport=True.",
                hostname,
                ", ".join(public_addresses),
            )
            return

        raise ValueError(
            f"Refusing to use base_url '{base_url}': it resolves to the public address "
            f"{public_addresses[0]} over plain HTTP, which would send prompts and responses "
            "in cleartext and void Privatemode's end-to-end encryption. Run the proxy locally "
            "(http://localhost:8080/v1), reach it over HTTPS, or keep it on a private network. "
            "See https://docs.privatemode.ai/api/proxy-configuration/#setting-up-tls — if that "
            "hop is protected by other means, pass allow_insecure_transport=True."
        )

    def _build_params(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Assemble the request payload, routing vendor extras into ``extra_body``.

        ``cache_salt`` (prompt-cache isolation) and ``chat_template_kwargs`` (e.g.
        ``{"thinking": false}`` to skip Kimi's reasoning pass) are documented as
        body fields, not SDK parameters. Accepting them as plain keyword
        arguments keeps call sites free of ``extra_body`` plumbing.
        """
        extras = {key: kwargs.pop(key) for key in list(kwargs) if key in self.EXTRA_BODY_KEYS}
        params = super()._build_params(messages, model, temperature, max_tokens, tools, **kwargs)
        if extras:
            # Merge instead of overwrite: a caller may pass extra_body directly.
            extra_body = dict(params.get("extra_body") or {})
            extra_body.update(extras)
            params["extra_body"] = extra_body
        return params


# Module-level aliases kept for consistency with the other provider modules.
DEFAULT_BASE_URL = PrivatemodeProvider.DEFAULT_BASE_URL
DEFAULT_MODEL = PrivatemodeProvider.DEFAULT_MODEL
