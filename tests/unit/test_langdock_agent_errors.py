"""Unit tests for the LangDock Agent API error translation.

The Agent API answers three very different situations with the same HTTP 400,
so the raw upstream body is useless to an end user. Verified live against
api.langdock.com on 23.08.2026: an agent whose model is set to "Auto" answers
400 "No valid model in the request, and no default model set for this
workspace", and a top-level `model` in the payload does NOT override it.
"""

import pytest

from eq_chatbot_core.providers.langdock_provider import _agent_error_message

AUTO_MODEL_BODY = (
    '{"message":"INVALID REQUEST: No valid model in the request, and no default model set for this workspace."}'
)


@pytest.mark.unit
class TestAgentErrorMessage:
    def test_auto_model_points_at_the_agent_model_setting(self):
        msg = _agent_error_message(400, AUTO_MODEL_BODY)

        assert "Auto" in msg
        assert "festes Modell" in msg
        # The upstream text must survive for diagnosis.
        assert "No valid model in the request" in msg

    def test_auto_model_matching_is_case_insensitive(self):
        msg = _agent_error_message(400, AUTO_MODEL_BODY.upper())

        assert "festes Modell" in msg

    def test_default_model_wording_alone_is_enough(self):
        msg = _agent_error_message(400, '{"message":"no default model set for this workspace"}')

        assert "festes Modell" in msg

    def test_other_400_points_at_agent_id_and_sharing(self):
        msg = _agent_error_message(400, '{"message":"Agent not found"}')

        assert "festes Modell" not in msg
        assert "geteilt" in msg
        assert "Agent not found" in msg

    def test_401_points_at_the_api_key(self):
        msg = _agent_error_message(401, '{"message":"The provided API key is invalid."}')

        assert "API-Key" in msg
        assert "festes Modell" not in msg

    def test_unmapped_status_keeps_the_upstream_body(self):
        msg = _agent_error_message(500, '{"message":"Internal server error"}')

        assert "500" in msg
        assert "Internal server error" in msg

    def test_empty_body_does_not_crash(self):
        msg = _agent_error_message(400, "")

        assert "400" in msg
