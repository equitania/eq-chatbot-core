"""Unit tests for the bearer-token auth middleware."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")  # skip whole module if [server] extras missing

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from eq_chatbot_core.server.auth import BearerTokenMiddleware  # noqa: E402


def _build_app(token: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(BearerTokenMiddleware, expected_token=token)

    @app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.mark.unit
class TestBearerTokenMiddleware:
    def test_health_bypasses_auth(self) -> None:
        client = TestClient(_build_app("supersecret-token-1234567890"))
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_missing_authorization_header_is_401(self) -> None:
        client = TestClient(_build_app("supersecret-token-1234567890"))
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert "Bearer" in resp.headers.get("www-authenticate", "")

    def test_wrong_scheme_is_401(self) -> None:
        client = TestClient(_build_app("supersecret-token-1234567890"))
        resp = client.get("/protected", headers={"Authorization": "Basic foo"})
        assert resp.status_code == 401

    def test_wrong_token_is_401(self) -> None:
        client = TestClient(_build_app("supersecret-token-1234567890"))
        resp = client.get("/protected", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

    def test_correct_token_passes(self) -> None:
        token = "supersecret-token-1234567890"
        client = TestClient(_build_app(token))
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_token_compared_constant_time_against_prefix_match(self) -> None:
        """Ensure ``hmac.compare_digest`` is used — a prefix of the real token must fail."""
        token = "supersecret-token-1234567890"
        client = TestClient(_build_app(token))

        # Provide a prefix; constant-time comparison must reject.
        resp = client.get("/protected", headers={"Authorization": f"Bearer {token[:10]}"})
        assert resp.status_code == 401

    def test_empty_token_in_constructor_raises(self) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        with pytest.raises(ValueError, match="non-empty"):
            BearerTokenMiddleware(app, expected_token="")
