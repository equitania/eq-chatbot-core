"""Unit tests for the `eq-chatbot serve` CLI subcommand.

Focuses on auth-token resolution and error paths. The actual server start
(uvicorn binding a socket and entering the asyncio loop) is NOT exercised
here — that's covered by integration tests / manual smoke tests.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from eq_chatbot_core.cli import _read_auth_token, main


@pytest.mark.unit
class TestReadAuthToken:
    """Covers the auth-token precedence: --auth-token-fd > --auth-token > env."""

    def test_fd_takes_precedence_and_closes_fd(self) -> None:
        r, w = os.pipe()
        os.write(w, b"token-from-fd-1234567890")
        os.close(w)
        token = _read_auth_token(auth_token=None, auth_token_fd=r)
        assert token == "token-from-fd-1234567890"
        # FD was closed by the function — reading again raises
        with pytest.raises(OSError):
            os.read(r, 1)

    def test_fd_strips_whitespace_and_newline(self) -> None:
        r, w = os.pipe()
        os.write(w, b"  token-from-fd-with-newline-9999\n")
        os.close(w)
        assert _read_auth_token(None, r) == "token-from-fd-with-newline-9999"

    def test_argv_token_when_no_fd(self) -> None:
        token = _read_auth_token(auth_token="argv-token-1234567890", auth_token_fd=None)
        assert token == "argv-token-1234567890"

    def test_env_var_used_as_fallback(self, monkeypatch) -> None:
        monkeypatch.setenv("EQ_CHATBOT_AUTH_TOKEN", "env-token-1234567890")
        token = _read_auth_token(auth_token=None, auth_token_fd=None)
        assert token == "env-token-1234567890"

    def test_missing_token_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("EQ_CHATBOT_AUTH_TOKEN", raising=False)
        import click

        with pytest.raises(click.ClickException, match="Missing auth token"):
            _read_auth_token(auth_token=None, auth_token_fd=None)

    def test_short_token_raises(self) -> None:
        import click

        with pytest.raises(click.ClickException, match="too short"):
            _read_auth_token(auth_token="short", auth_token_fd=None)


@pytest.mark.unit
class TestServeCommand:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_missing_token_exits_nonzero(self, runner, monkeypatch) -> None:
        monkeypatch.delenv("EQ_CHATBOT_AUTH_TOKEN", raising=False)
        result = runner.invoke(main, ["serve", "--port", "0"])
        assert result.exit_code != 0
        assert "Missing auth token" in result.output

    def test_short_token_exits_nonzero(self, runner) -> None:
        result = runner.invoke(main, ["serve", "--port", "0", "--auth-token", "short"])
        assert result.exit_code != 0
        assert "too short" in result.output

    def test_valid_token_invokes_run_server(self, runner) -> None:
        """Valid token path: cli should reach run_server (which we patch out)."""
        with patch("eq_chatbot_core.server.lifecycle.run_server") as mock_run:
            mock_run.return_value = None
            result = runner.invoke(
                main,
                [
                    "serve",
                    "--port",
                    "0",
                    "--auth-token",
                    "valid-token-with-enough-entropy",
                    "--log-level",
                    "warning",
                ],
            )
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        # run_server got an app + correct kwargs
        kwargs = mock_run.call_args.kwargs
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 0
        assert kwargs["log_level"] == "warning"

    def test_serve_help_lists_options(self, runner) -> None:
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        for opt in ["--auth-token-fd", "--parent-pid", "--host", "--port", "--log-level"]:
            assert opt in result.output
