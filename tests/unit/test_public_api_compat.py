"""The public provider surface must match the snapshot taken before the base-class migration.

A failure here means a consumer (Odoo module, CLI, server mode) may break. Fix the
code, not the snapshot — regenerating it is a reviewed API change.
"""

import json

import pytest

from tests.compat.snapshot import SNAPSHOT_PATH, public_surface

pytestmark = pytest.mark.unit

# `client` changes type (httpx2.Client -> openai.OpenAI) for providers moving off
# hand-written HTTP; it is an implementation detail, documented in the release notes.
_ALLOWED_DRIFT = {"client"}

# Stage 2 (no model IDs in source) changes these on purpose. Each stage-2 task
# adds what it changes; the snapshot task regenerates public_api.json and
# removes this mapping again.
_STAGE2_CHANGES: dict[str, set[str]] = {
    "providers.__all__": {"ModelNotSpecifiedError"},
    "OpenAIProvider": {"__init__", "DEFAULT_IMAGE_MODEL"},
    "OpenRouterProvider": {"__init__", "DEFAULT_IMAGE_MODEL"},
    "MammouthProvider": {"__init__"},
    "LocalLLMProvider": {"__init__"},
    "LangDockProvider": {"__init__"},
    "LangDockAgentManager": {"create_agent"},
    "IonosProvider": {"DEFAULT_MODEL"},
    "MeliousProvider": {"DEFAULT_MODEL"},
    "LiteLLMProvider": {"__init__", "DEFAULT_MODEL", "text_to_speech", "transcribe"},
    "PrivatemodeProvider": {"DEFAULT_MODEL"},
}


def _strip(surface: dict) -> dict:
    return {
        cls: {
            "members": {k: v for k, v in body["members"].items() if k not in _ALLOWED_DRIFT},
            "constants": body["constants"],
        }
        if isinstance(body, dict)
        else body
        for cls, body in surface.items()
    }


def test_public_surface_unchanged():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    actual = public_surface()
    for cls, body in _strip(expected).items():
        allowed = _STAGE2_CHANGES.get(cls, set())
        if not isinstance(body, dict):
            assert (set(actual[cls]) ^ set(body)) <= allowed, cls
            continue
        live = _strip(actual)[cls]
        missing = set(body["members"]) - set(live["members"]) - allowed
        assert not missing, f"{cls} lost public members: {sorted(missing)}"
        changed = {
            k for k in body["members"] if k in live["members"] and live["members"][k] != body["members"][k]
        } - allowed
        assert not changed, f"{cls} changed signatures: {sorted(changed)}"
        lost_or_changed = {k for k, v in body["constants"].items() if live["constants"].get(k) != v} - allowed
        assert not lost_or_changed, f"{cls} constants lost or changed: {sorted(lost_or_changed)}"


def test_wire_server_serves_a_chat_completion(wire_server):
    from openai import OpenAI

    from tests.wire_server import Reply, chat_body

    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    client = OpenAI(api_key="k", base_url=wire_server.base_url, max_retries=0)
    reply = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert reply.choices[0].message.content == "hallo"
    assert wire_server.requests[0].json["model"] == "m"
