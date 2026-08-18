"""ToolDefinition must actually reach the providers as wire-format dicts.

BaseLLMProvider advertises `list[ToolDefinition] | list[dict] | None` for
chat_completion/stream_completion, but the chat providers passed `tools`
straight into their request payload — so a ToolDefinition reached the JSON
serializer as a dataclass and failed there. mypy's override errors were pointing
at that gap.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from eq_chatbot_core.providers.base import ToolDefinition, normalize_tools

pytestmark = pytest.mark.unit


def _tool(**overrides):
    kwargs = {
        "name": "get_weather",
        "description": "Look up the weather",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
    }
    kwargs.update(overrides)
    return ToolDefinition(**kwargs)


class TestToChatTool:
    def test_uses_the_nested_chat_completions_shape(self):
        """Chat Completions nests under "function"; the Realtime API does not."""
        assert _tool().to_chat_tool() == {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Look up the weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }

    def test_strict_is_emitted_only_when_set(self):
        assert "strict" not in _tool().to_chat_tool()["function"]
        assert _tool(strict=True).to_chat_tool()["function"]["strict"] is True

    def test_result_is_json_serializable(self):
        """The whole point: a dataclass here used to blow up in the serializer."""
        json.dumps(_tool().to_chat_tool())


class TestNormalizeTools:
    def test_none_and_empty_become_none(self):
        assert normalize_tools(None) is None
        assert normalize_tools([]) is None

    def test_dicts_pass_through_as_copies(self):
        original = {"type": "function", "function": {"name": "f"}}

        result = normalize_tools([original])

        assert result == [original]
        assert result[0] is not original, "must not alias the caller's dict"

    def test_tool_definitions_are_converted(self):
        result = normalize_tools([_tool()])

        assert result[0]["function"]["name"] == "get_weather"

    def test_mixed_lists_are_handled(self):
        result = normalize_tools([_tool(), {"type": "function", "function": {"name": "raw"}}])

        assert [t["function"]["name"] for t in result] == ["get_weather", "raw"]

    def test_output_is_always_json_serializable(self):
        json.dumps(normalize_tools([_tool(), {"type": "function", "function": {"name": "raw"}}]))


class TestProvidersAcceptToolDefinition:
    """End-to-end: a ToolDefinition must arrive at the SDK as a plain dict."""

    def test_openai_provider_sends_dicts(self):
        mock_openai = MagicMock()
        mock_client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "ok"
        response.choices[0].message.tool_calls = None
        response.choices[0].finish_reason = "stop"
        response.usage.prompt_tokens = 1
        response.usage.completion_tokens = 1
        response.model = "gpt-4o"
        mock_client.chat.completions.create.return_value = response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai}):
            from eq_chatbot_core.providers.openai_provider import OpenAIProvider

            provider = OpenAIProvider(api_key="sk-test")
            provider._client = mock_client
            provider.chat_completion([{"role": "user", "content": "hi"}], tools=[_tool()])

        sent = mock_client.chat.completions.create.call_args[1]["tools"]
        assert sent == [_tool().to_chat_tool()]
        json.dumps(sent)

    def test_anthropic_converter_receives_dicts(self):
        """Anthropic translates from the OpenAI dict shape, so normalization must precede it."""
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider(api_key="sk-ant-test")
            converted = provider._convert_tools_to_anthropic(normalize_tools([_tool()]))

        assert converted[0]["name"] == "get_weather"
        json.dumps(converted)
