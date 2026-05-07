"""Bearer-token authentication middleware for the eq-chatbot server.

Threat model: the sidecar runs on 127.0.0.1 with an ephemeral port. The auth
token is a random per-session secret known only to the spawning parent
process; this guards against other local processes (e.g. browsers, IDE
extensions, malicious user-space tools) that scan localhost for open ports.

The token is compared in constant time via :func:`hmac.compare_digest`. The
``/health`` endpoint is exempt so external watchdogs can probe without the
token (and so a leaked token isn't required just to know the server is up).
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

# Endpoints that bypass auth — keep tight. /docs and /openapi.json reveal API
# shape but no secrets, so they're allowed for local debugging convenience.
_OPEN_PATHS: frozenset[str] = frozenset({"/health", "/openapi.json", "/docs", "/redoc"})


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Validates ``Authorization: Bearer <token>`` on every non-open request."""

    def __init__(self, app, expected_token: str) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        if not expected_token:
            raise ValueError("expected_token must be a non-empty string")
        self._expected: bytes = expected_token.encode("utf-8")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in _OPEN_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        provided = header[7:].strip().encode("utf-8")
        if not hmac.compare_digest(provided, self._expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
