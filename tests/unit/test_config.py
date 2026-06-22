"""Unit tests for the user config file (utils/config.py) and its CLI wiring.

Real file-based tests — no API calls. Config is written to a tmp file and
EQ_CHATBOT_CONFIG points the loader at it; the autouse isolation fixture in
conftest keeps the host's real config out of the way.
"""

import stat
from pathlib import Path

import pytest
from click.testing import CliRunner

from eq_chatbot_core import cli
from eq_chatbot_core.cli import main, resolve_api_key, resolve_base_url, resolve_model, resolve_provider
from eq_chatbot_core.utils import config as cfg
from eq_chatbot_core.utils.config import ConfigError


@pytest.fixture
def write_config(monkeypatch, tmp_path):
    """Return a function that writes TOML to a tmp config file and activates it."""

    def _write(content: str, *, mode: int = 0o600) -> Path:
        path = tmp_path / "config.toml"
        path.write_text(content, encoding="utf-8")
        path.chmod(mode)
        monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(path))
        cfg.reset_cache()
        return path

    return _write


@pytest.mark.unit
class TestConfigPath:
    def test_explicit_override_wins(self, monkeypatch, tmp_path):
        target = tmp_path / "custom.toml"
        monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(target))
        assert cfg.config_path() == target

    def test_xdg_config_home(self, monkeypatch, tmp_path):
        monkeypatch.delenv("EQ_CHATBOT_CONFIG", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert cfg.config_path() == tmp_path / "eq-chatbot" / "config.toml"

    def test_default_home(self, monkeypatch):
        monkeypatch.delenv("EQ_CHATBOT_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert cfg.config_path() == Path.home() / ".config" / "eq-chatbot" / "config.toml"


@pytest.mark.unit
class TestLoadConfig:
    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(tmp_path / "does-not-exist.toml"))
        cfg.reset_cache()
        assert cfg.load_config() == {}

    def test_malformed_toml_raises(self, write_config):
        write_config("this is = = not valid [[[\n")
        with pytest.raises(ConfigError):
            cfg.load_config()

    def test_permission_warning_when_world_readable(self, write_config, capsys):
        write_config('[providers.openai]\napi_key = "sk-x"\n', mode=0o644)
        cfg.load_config()
        captured = capsys.readouterr()
        assert "readable by others" in captured.err

    def test_no_warning_when_locked_down(self, write_config, capsys):
        write_config('[providers.openai]\napi_key = "sk-x"\n', mode=0o600)
        cfg.load_config()
        captured = capsys.readouterr()
        assert "readable by others" not in captured.err


@pytest.mark.unit
class TestAccessors:
    def test_provider_fields(self, write_config):
        write_config(
            '[providers.openrouter]\napi_key = "sk-or-cfg"\nbase_url = "https://example/v1"\nmodel = "some/model"\n'
        )
        assert cfg.config_api_key("openrouter") == "sk-or-cfg"
        assert cfg.config_base_url("openrouter") == "https://example/v1"
        assert cfg.config_model("openrouter") == "some/model"

    def test_provider_name_case_insensitive(self, write_config):
        write_config('[providers.openai]\napi_key = "sk-cfg"\n')
        assert cfg.config_api_key("OpenAI") == "sk-cfg"

    def test_unknown_provider_returns_none(self, write_config):
        write_config('[providers.openai]\napi_key = "sk-cfg"\n')
        assert cfg.config_api_key("anthropic") is None

    def test_none_provider_returns_none(self, write_config):
        write_config('[providers.openai]\napi_key = "sk-cfg"\n')
        assert cfg.config_api_key(None) is None

    def test_default_provider(self, write_config):
        write_config('default_provider = "melious"\n')
        assert cfg.config_default_provider() == "melious"

    def test_chat_defaults(self, write_config):
        write_config("[defaults]\ntemperature = 0.2\nmax_tokens = 1234\n")
        assert cfg.config_temperature() == 0.2
        assert cfg.config_max_tokens() == 1234

    def test_chat_defaults_absent(self, write_config):
        write_config('[providers.openai]\napi_key = "sk"\n')
        assert cfg.config_temperature() is None
        assert cfg.config_max_tokens() is None

    def test_bool_is_not_accepted_as_number(self, write_config):
        write_config("[defaults]\nmax_tokens = true\n")
        assert cfg.config_max_tokens() is None


@pytest.mark.unit
class TestResolverPrecedence:
    def test_api_key_flag_beats_all(self, write_config, monkeypatch):
        write_config('[providers.openai]\napi_key = "from-config"\n')
        monkeypatch.setenv("OPENAI_API_KEY", "from-env")
        assert resolve_api_key("openai", "from-flag") == "from-flag"

    def test_api_key_env_beats_config(self, write_config, monkeypatch):
        write_config('[providers.openai]\napi_key = "from-config"\n')
        monkeypatch.setenv("OPENAI_API_KEY", "from-env")
        assert resolve_api_key("openai", None) == "from-env"

    def test_api_key_generic_env_beats_config(self, write_config, monkeypatch):
        write_config('[providers.openai]\napi_key = "from-config"\n')
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("LLM_API_KEY", "from-generic")
        assert resolve_api_key("openai", None) == "from-generic"

    def test_api_key_config_used_when_no_flag_or_env(self, write_config, monkeypatch):
        write_config('[providers.openai]\napi_key = "from-config"\n')
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        assert resolve_api_key("openai", None) == "from-config"

    def test_base_url_flag_beats_config(self, write_config):
        write_config('[providers.openai]\nbase_url = "https://config/v1"\n')
        assert resolve_base_url("openai", "https://flag/v1") == "https://flag/v1"

    def test_base_url_from_config(self, write_config):
        write_config('[providers.openai]\nbase_url = "https://config/v1"\n')
        assert resolve_base_url("openai", None) == "https://config/v1"

    def test_model_from_config(self, write_config):
        write_config('[providers.openai]\nmodel = "gpt-cfg"\n')
        assert resolve_model("openai", None) == "gpt-cfg"

    def test_provider_from_config_default(self, write_config):
        write_config('default_provider = "ionos"\n')
        assert resolve_provider(None) == "ionos"

    def test_provider_flag_beats_config(self, write_config):
        write_config('default_provider = "ionos"\n')
        assert resolve_provider("openai") == "openai"


@pytest.mark.unit
class TestWriteTemplate:
    def test_creates_file_0600(self, monkeypatch, tmp_path):
        target = tmp_path / "sub" / "config.toml"
        monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(target))
        written = cfg.write_template()
        assert written == target
        assert target.exists()
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        # Template is valid TOML and parseable
        cfg.reset_cache()
        assert isinstance(cfg.load_config(), dict)

    def test_refuses_overwrite_without_force(self, write_config):
        path = write_config('default_provider = "openai"\n')
        with pytest.raises(ConfigError):
            cfg.write_template(path, force=False)

    def test_force_overwrites(self, write_config):
        path = write_config('default_provider = "openai"\n')
        cfg.write_template(path, force=True)
        assert "eq-chatbot configuration file" in path.read_text(encoding="utf-8")


@pytest.mark.unit
class TestRedact:
    def test_masks_long_value(self):
        assert cfg.redact("sk-1234567890") == "…7890"

    def test_short_value_fully_masked(self):
        assert cfg.redact("abcd") == "****"


@pytest.mark.unit
class TestConfigCLI:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_config_path_command(self, runner, monkeypatch, tmp_path):
        target = tmp_path / "config.toml"
        monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(target))
        result = runner.invoke(main, ["config", "path"])
        assert result.exit_code == 0
        assert str(target) in result.output

    def test_config_init_then_show(self, runner, monkeypatch, tmp_path):
        target = tmp_path / "config.toml"
        monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(target))
        cfg.reset_cache()
        init = runner.invoke(main, ["config", "init"])
        assert init.exit_code == 0
        assert target.exists()
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        show = runner.invoke(main, ["config", "show"])
        assert show.exit_code == 0
        assert str(target) in show.output

    def test_config_init_refuses_overwrite(self, runner, monkeypatch, tmp_path):
        target = tmp_path / "config.toml"
        target.write_text('default_provider = "openai"\n', encoding="utf-8")
        monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(target))
        result = runner.invoke(main, ["config", "init"])
        assert result.exit_code != 0

    def test_config_show_masks_keys(self, runner, write_config):
        write_config('[providers.openrouter]\napi_key = "sk-or-supersecret"\n')
        result = runner.invoke(main, ["config", "show"])
        assert result.exit_code == 0
        assert "sk-or-supersecret" not in result.output
        assert "…cret" in result.output


@pytest.mark.unit
class TestConfigIntegration:
    """The config key flows through to a command without -k or env vars."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_test_provider_uses_config_key(self, runner, write_config, monkeypatch):
        from unittest.mock import MagicMock, patch

        write_config('default_provider = "openrouter"\n[providers.openrouter]\napi_key = "sk-or-from-config"\n')
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)

        with patch("eq_chatbot_core.providers.get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "ok"
            mock_response.input_tokens = 1
            mock_response.output_tokens = 1
            mock_response.model = "x"
            mock_provider.chat_completion.return_value = mock_response
            mock_get.return_value = mock_provider

            # No -p and no -k: provider and key both come from the config file.
            result = runner.invoke(main, ["test-provider"])

        assert result.exit_code == 0, result.output
        assert mock_get.call_args.kwargs.get("api_key") == "sk-or-from-config"
        assert mock_get.call_args.args[0] == "openrouter"


def test_module_exposes_cli_resolvers():
    """Guard against accidental rename of the public resolvers used by cli."""
    assert callable(cli.resolve_api_key)
    assert callable(cli.resolve_base_url)
    assert callable(cli.resolve_model)
    assert callable(cli.resolve_provider)
