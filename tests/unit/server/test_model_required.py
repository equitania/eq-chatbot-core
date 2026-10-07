"""Server mode: the request's model field (or provider_extra model), else HTTP 400 before any stream."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from eq_chatbot_core.server.app import create_app  # noqa: E402
from tests.wire_server import Reply, chat_body  # noqa: E402

TOKEN = "test-token-with-enough-entropy-aaaaaaaa"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
BODY = {"provider": "openai", "api_key": "sk-test", "messages": [{"role": "user", "content": "x"}]}


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """Same reason as in test_app.py: sse-starlette binds a singleton event to the first loop."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None  # type: ignore[assignment]
    yield
    AppStatus.should_exit_event = None  # type: ignore[assignment]


@pytest.fixture
def client():
    return TestClient(create_app(auth_token=TOKEN))


@pytest.mark.unit
def test_chat_without_model_is_400(client):
    resp = client.post("/chat", json=BODY, headers=AUTH)
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["type"] == "ModelNotSpecifiedError" and detail["provider"] == "openai"
    assert '"model"' in detail["error"]


@pytest.mark.unit
def test_stream_without_model_is_400_before_the_stream(client):
    """Review focus 5: not a 200 event stream that carries an error event."""
    resp = client.post("/chat/stream", json=BODY, headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["detail"]["type"] == "ModelNotSpecifiedError"


@pytest.mark.unit
def test_model_in_provider_extra_counts(client, wire_server):
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    body = {
        **BODY,
        "provider": "mammouth",
        "base_url": wire_server.base_url,
        "provider_extra": {"model": "extra-model"},
    }
    resp = client.post("/chat", json=body, headers=AUTH)
    assert resp.status_code == 200 and resp.json()["content"] == "hallo"
    assert wire_server.requests[0].json["model"] == "extra-model"
