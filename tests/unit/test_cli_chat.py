"""Unit tests for the chat CLI command."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from eq_chatbot_core.cli import main


@pytest.mark.unit
class TestChatCommand:
    """Tests for the eq-chatbot chat command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def valid_input(self):
        return json.dumps({"messages": [{"role": "user", "content": "Hello"}]})

    @pytest.fixture
    def mock_response(self):
        resp = MagicMock()
        resp.content = "Hello back!"
        resp.model = "gpt-4o-mini"
        resp.input_tokens = 5
        resp.output_tokens = 3
        return resp

    def test_successful_chat(self, runner, valid_input, mock_response):
        """Successful single-turn chat returns JSON on stdout."""
        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.chat_completion.return_value = mock_response
            mock_get.return_value = mock_provider

            result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=valid_input)

            assert result.exit_code == 0
            output = json.loads(result.output.strip())
            assert output["content"] == "Hello back!"
            assert output["model"] == "gpt-4o-mini"
            assert output["input_tokens"] == 5
            assert output["output_tokens"] == 3

    def test_custom_model_and_temperature(self, runner, valid_input, mock_response):
        """Custom model and temperature are forwarded to provider."""
        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.chat_completion.return_value = mock_response
            mock_get.return_value = mock_provider

            result = runner.invoke(
                main,
                ["chat", "-p", "openai", "-k", "sk-test", "-m", "gpt-4o", "-t", "0.3", "--max-tokens", "100"],
                input=valid_input,
            )

            assert result.exit_code == 0
            call_kwargs = mock_provider.chat_completion.call_args
            assert call_kwargs.kwargs.get("model") or call_kwargs[1].get("model") == "gpt-4o"

    def test_missing_api_key(self, runner, valid_input, monkeypatch):
        """Cloud provider without API key returns JSON error."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        result = runner.invoke(main, ["chat", "-p", "openai"], input=valid_input)

        assert result.exit_code != 0
        # Error output goes to stderr via click.echo(err=True)
        # CliRunner mixes stderr into output unless mix_stderr=False
        assert "API key required" in result.output or "API key required" in (result.stderr or "")

    def test_local_provider_no_key(self, runner, valid_input, mock_response):
        """Local provider works without API key."""
        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.chat_completion.return_value = mock_response
            mock_get.return_value = mock_provider

            result = runner.invoke(main, ["chat", "-p", "lm_studio"], input=valid_input)

            assert result.exit_code == 0

    def test_empty_stdin(self, runner):
        """Empty stdin returns JSON error."""
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input="")

        assert result.exit_code != 0
        assert "No input received" in result.output

    def test_invalid_json(self, runner):
        """Invalid JSON returns JSON error."""
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input="not json")

        assert result.exit_code != 0
        assert "Invalid JSON input" in result.output

    def test_missing_messages(self, runner):
        """JSON without messages array returns error."""
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input='{"data": "hello"}')

        assert result.exit_code != 0
        assert "No messages found" in result.output

    def test_empty_messages(self, runner):
        """Empty messages array returns error."""
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input='{"messages": []}')

        assert result.exit_code != 0
        assert "No messages found" in result.output

    def test_invalid_message_role(self, runner):
        """Message with invalid role returns validation error."""
        payload = json.dumps({"messages": [{"role": "hacker", "content": "Hello"}]})
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)

        assert result.exit_code != 0
        assert "invalid role" in result.output

    def test_invalid_message_no_content(self, runner):
        """Message without content field returns validation error."""
        payload = json.dumps({"messages": [{"role": "user"}]})
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)

        assert result.exit_code != 0
        assert "missing required 'content' field" in result.output

    def test_invalid_message_no_role(self, runner):
        """Message without role field returns validation error."""
        payload = json.dumps({"messages": [{"content": "Hello"}]})
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)

        assert result.exit_code != 0
        assert "missing required 'role' field" in result.output

    def test_message_not_dict(self, runner):
        """Non-dict message returns validation error."""
        payload = json.dumps({"messages": ["just a string"]})
        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)

        assert result.exit_code != 0
        assert "must be a JSON object" in result.output

    def test_provider_error(self, runner, valid_input):
        """ProviderError returns JSON error."""
        from eq_chatbot_core.providers.base import ProviderError

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.chat_completion.side_effect = ProviderError("Model not found", provider="openai")
            mock_get.return_value = mock_provider

            result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=valid_input)

            assert result.exit_code != 0
            assert "Provider error" in result.output

    def test_input_size_limit(self, runner):
        """Input exceeding MAX_INPUT_SIZE returns error."""
        from eq_chatbot_core.cli import MAX_INPUT_SIZE

        # Create oversized payload
        huge_content = "x" * (MAX_INPUT_SIZE + 100)
        payload = json.dumps({"messages": [{"role": "user", "content": huge_content}]})

        result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)

        assert result.exit_code != 0
        assert "exceeds maximum size" in result.output

    def test_multi_message_conversation(self, runner, mock_response):
        """Multi-message conversation is passed correctly."""
        payload = json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello!"},
                    {"role": "user", "content": "How are you?"},
                ]
            }
        )

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.chat_completion.return_value = mock_response
            mock_get.return_value = mock_provider

            result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)

            assert result.exit_code == 0
            call_kwargs = mock_provider.chat_completion.call_args
            msgs = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
            assert len(msgs) == 4

    def test_tool_role_accepted(self, runner, mock_response):
        """Tool role messages are accepted by validation."""
        payload = json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "What's the weather?"},
                    {"role": "tool", "content": '{"temp": 20}'},
                ]
            }
        )

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.chat_completion.return_value = mock_response
            mock_get.return_value = mock_provider

            result = runner.invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)

            assert result.exit_code == 0
