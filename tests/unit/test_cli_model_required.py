"""CLI: the model comes from --model or the config file; otherwise a clear message, no traceback."""

import json

import pytest
from click.testing import CliRunner

from eq_chatbot_core.cli import main
from eq_chatbot_core.utils import config as _config
from tests.wire_server import Reply, chat_body

pytestmark = pytest.mark.unit


def _use_config(tmp_path, monkeypatch, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("EQ_CHATBOT_CONFIG", str(path))
    _config.reset_cache()


@pytest.mark.parametrize(
    "args",
    [
        ["test-provider", "-p", "openai", "-k", "sk-test"],
        ["image", "-p", "openai", "-k", "sk-test", "--prompt", "a cat"],
    ],
    ids=["test-provider", "image"],
)
def test_missing_model_is_explained_without_traceback(args):
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 1
    assert "--model" in result.output and "[providers.openai]" in result.output
    assert "Traceback" not in result.output and isinstance(result.exception, SystemExit)


def test_chat_missing_model_is_a_json_error():
    payload = json.dumps({"messages": [{"role": "user", "content": "x"}]})
    result = CliRunner().invoke(main, ["chat", "-p", "openai", "-k", "sk-test"], input=payload)
    assert result.exit_code == 1
    error_line = next(line for line in result.output.splitlines() if line.startswith("{"))
    assert "--model" in json.loads(error_line)["error"]


def test_listing_assets_missing_model(tmp_path):
    recipe = tmp_path / "recipe.json"
    recipe.write_text(
        json.dumps(
            {
                "schema": "eq-listing-assets/1",
                "defaults": {"provider": "openai"},
                "assets": [{"id": "a", "out": "a.png", "prompt": "p"}],
            }
        ),
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["listing-assets", "--recipe", str(recipe), "--api-key", "sk-test"])
    assert result.exit_code == 1
    assert "--model" in result.output and "Traceback" not in result.output


def test_model_from_config_file_is_used(wire_server, tmp_path, monkeypatch):
    _use_config(
        tmp_path, monkeypatch, f'[providers.mammouth]\nmodel = "cfg-model"\nbase_url = "{wire_server.base_url}"\n'
    )
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    result = CliRunner().invoke(main, ["test-provider", "-p", "mammouth", "-k", "mm-test"])
    assert result.exit_code == 0, result.output
    assert wire_server.requests[0].json["model"] == "cfg-model"


def test_flag_beats_config_file(wire_server, tmp_path, monkeypatch):
    _use_config(
        tmp_path, monkeypatch, f'[providers.mammouth]\nmodel = "cfg-model"\nbase_url = "{wire_server.base_url}"\n'
    )
    wire_server.expect("POST", "/v1/chat/completions", Reply(body=chat_body("hallo")))
    result = CliRunner().invoke(main, ["test-provider", "-p", "mammouth", "-k", "mm-test", "-m", "flag-model"])
    assert result.exit_code == 0, result.output
    assert wire_server.requests[0].json["model"] == "flag-model"


def test_listing_assets_dry_run_needs_no_model(tmp_path):
    """A dry run makes no API call, so it must not demand a model."""
    recipe = tmp_path / "recipe.json"
    recipe.write_text(
        json.dumps(
            {
                "schema": "eq-listing-assets/1",
                "defaults": {"provider": "openai"},
                "assets": [{"id": "a", "out": "a.png", "prompt": "p"}],
            }
        ),
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["listing-assets", "--recipe", str(recipe), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "1 asset(s) would be generated." in result.output
