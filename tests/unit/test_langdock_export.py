"""Unit tests for the LangDock backup/export tooling.

Covers the HTTP manager (LangDockExportManager), the orchestrator
(LangDockBackupExporter), and the CLI command (langdock-export).

Pattern: unittest.mock + patch("...langdock_provider.httpx") + CliRunner.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from eq_chatbot_core.cli import main
from eq_chatbot_core.providers.base import AuthenticationError, ProviderError
from eq_chatbot_core.providers.langdock_provider import LangDockExportManager
from eq_chatbot_core.services.langdock_export import (
    LangDockBackupExporter,
    extract_agent_id,
    slugify,
)

_HTTPX = "eq_chatbot_core.providers.langdock_provider.httpx"

SAMPLE_AGENT = {
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Weather Agent",
    "description": "Helps with weather",
    "instruction": "You are a helpful weather assistant.",
    "model": "gpt-5.1",
    "temperature": 0.5,
    "capabilities": {"webSearch": True, "imageGeneration": False},
    "conversationStarters": ["What's the weather?"],
    "knowledgeFolderIds": ["folder-abc"],
}


# --------------------------------------------------------------------- helpers
@pytest.mark.unit
class TestHelpers:
    def test_extract_agent_id_from_uuid(self):
        uid = "11111111-2222-3333-4444-555555555555"
        assert extract_agent_id(uid) == uid

    def test_extract_agent_id_from_ui_url(self):
        url = "https://app.langdock.com/assistant/11111111-2222-3333-4444-555555555555"
        assert extract_agent_id(url) == "11111111-2222-3333-4444-555555555555"

    def test_extract_agent_id_from_url_with_query(self):
        url = "https://app.langdock.com/agent/my-agent-slug?tab=settings"
        assert extract_agent_id(url) == "my-agent-slug"

    def test_extract_agent_id_passthrough(self):
        assert extract_agent_id("  raw-id  ") == "raw-id"

    def test_slugify(self):
        assert slugify("Weather Agent!") == "weather-agent"
        assert slugify("") == "agent"
        assert slugify("", fallback="x") == "x"


# ----------------------------------------------------------------- markdown fmt
@pytest.mark.unit
class TestAgentMarkdown:
    def _exporter(self):
        return LangDockBackupExporter(MagicMock())

    def test_markdown_contains_system_prompt(self):
        md = self._exporter().agent_to_markdown(SAMPLE_AGENT)
        assert "## System Prompt" in md
        assert "You are a helpful weather assistant." in md

    def test_markdown_frontmatter(self):
        md = self._exporter().agent_to_markdown(SAMPLE_AGENT)
        assert md.startswith("---")
        assert "name: Weather Agent" in md
        assert "model: gpt-5.1" in md
        # only enabled capabilities are listed
        assert "capabilities: [webSearch]" in md
        assert "knowledge_folder_ids: [folder-abc]" in md

    def test_markdown_handles_missing_knowledge_folders(self):
        agent = {k: v for k, v in SAMPLE_AGENT.items() if k != "knowledgeFolderIds"}
        md = self._exporter().agent_to_markdown(agent)
        assert "knowledge_folder_ids" not in md
        assert "You are a helpful weather assistant." in md

    def test_markdown_handles_minimal_agent(self):
        md = self._exporter().agent_to_markdown({"id": "abc", "instruction": ""})
        assert "# abc" in md
        assert "## System Prompt" in md


# ------------------------------------------------------------------- discovery
@pytest.mark.unit
class TestDiscovery:
    def test_parse_agents_csv(self):
        csv_text = (
            "assistant_id,assistant_name,unique_users\n"
            "id-1,Agent One,5\n"
            "id-2,Agent Two,3\n"
            "id-1,Agent One,5\n"  # duplicate row
        )
        rows = LangDockBackupExporter._parse_agents_csv(csv_text)
        ids = {r["id"]: r["name"] for r in rows}
        assert ids == {"id-1": "Agent One", "id-2": "Agent Two"}

    def test_discover_agents_flow(self):
        export = MagicMock()
        export.export_report.return_value = {"downloadUrl": "https://signed/csv"}
        export.download_signed_csv.return_value = "assistant_id,assistant_name\nid-9,Nine\n"
        exporter = LangDockBackupExporter(export)

        result = exporter.discover_agents()

        assert result == [{"id": "id-9", "name": "Nine"}]
        export.export_report.assert_called_once()
        export.download_signed_csv.assert_called_once_with("https://signed/csv")

    def test_discover_agents_without_download_url(self):
        export = MagicMock()
        export.export_report.return_value = {}
        with pytest.raises(ProviderError, match="downloadUrl"):
            LangDockBackupExporter(export).discover_agents()


# ----------------------------------------------------------------- HTTP manager
@pytest.mark.unit
class TestExportManager:
    def test_get_agent_unwraps_envelope(self):
        with patch(_HTTPX) as mock_httpx:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"agent": SAMPLE_AGENT}
            client = MagicMock()
            client.get.return_value = resp
            mock_httpx.Client.return_value = client

            mgr = LangDockExportManager(api_key="test-key")
            agent = mgr.get_agent(SAMPLE_AGENT["id"])

            assert agent["name"] == "Weather Agent"
            client.get.assert_called_once_with("/agent/v1/get", params={"agentId": SAMPLE_AGENT["id"]})

    def test_get_agent_without_envelope(self):
        with patch(_HTTPX) as mock_httpx:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = SAMPLE_AGENT
            client = MagicMock()
            client.get.return_value = resp
            mock_httpx.Client.return_value = client

            agent = LangDockExportManager(api_key="k").get_agent("x")
            assert agent["model"] == "gpt-5.1"

    def test_get_agent_401_raises_auth_error(self):
        with patch(_HTTPX) as mock_httpx:
            resp = MagicMock()
            resp.status_code = 401
            resp.text = "Bearer secret-token-here invalid"
            client = MagicMock()
            client.get.return_value = resp
            mock_httpx.Client.return_value = client

            mgr = LangDockExportManager(api_key="k")
            with pytest.raises(AuthenticationError) as exc_info:
                mgr.get_agent("x")
            # token must be scrubbed out of the surfaced message
            assert "secret-token-here" not in str(exc_info.value)

    def test_export_report_rejects_unknown_report(self):
        mgr = LangDockExportManager(api_key="k")
        with pytest.raises(ProviderError, match="Unknown export report"):
            mgr.export_report("nope", "from", "to")

    def test_export_report_unwraps_data(self):
        with patch(_HTTPX) as mock_httpx:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"success": True, "data": {"downloadUrl": "u"}}
            client = MagicMock()
            client.post.return_value = resp
            mock_httpx.Client.return_value = client

            data = LangDockExportManager(api_key="k").export_report(
                "agents", "2024-01-01T00:00:00.000Z", "2024-01-31T23:59:59.999Z"
            )
            assert data == {"downloadUrl": "u"}

    def test_download_signed_csv_uses_bare_get(self):
        with patch(_HTTPX) as mock_httpx:
            resp = MagicMock()
            resp.status_code = 200
            resp.text = "assistant_id\nid-1\n"
            mock_httpx.get.return_value = resp

            text = LangDockExportManager(api_key="k").download_signed_csv("https://s/u")
            assert "id-1" in text
            # bare get → no auth client involved
            mock_httpx.get.assert_called_once()


# ------------------------------------------------------------------- backup I/O
@pytest.mark.unit
class TestBackupAgents:
    def test_backup_writes_md_and_json(self, tmp_path):
        export = MagicMock()
        export.get_agent.return_value = dict(SAMPLE_AGENT)
        exporter = LangDockBackupExporter(export)

        summary = exporter.backup_agents([SAMPLE_AGENT["id"]], tmp_path, fmt="both")

        assert summary["agents_ok"] == 1
        assert summary["agents_failed"] == 0
        agents_dir = tmp_path / "agents"
        md_files = list(agents_dir.glob("*.md"))
        json_files = list(agents_dir.glob("*.json"))
        assert len(md_files) == 1 and len(json_files) == 1
        assert "weather-agent" in md_files[0].name
        # collected knowledge folder ids surface for the knowledge step
        assert summary["knowledge_folder_ids"] == ["folder-abc"]
        # json is the raw definition
        raw = json.loads(json_files[0].read_text())
        assert raw["instruction"] == SAMPLE_AGENT["instruction"]

    def test_backup_json_only(self, tmp_path):
        export = MagicMock()
        export.get_agent.return_value = dict(SAMPLE_AGENT)
        exporter = LangDockBackupExporter(export)
        exporter.backup_agents([SAMPLE_AGENT["id"]], tmp_path, fmt="json")
        agents_dir = tmp_path / "agents"
        assert not list(agents_dir.glob("*.md"))
        assert list(agents_dir.glob("*.json"))

    def test_single_failure_does_not_abort(self, tmp_path):
        export = MagicMock()
        export.get_agent.side_effect = [
            ProviderError("boom", provider="langdock"),
            dict(SAMPLE_AGENT),
        ]
        exporter = LangDockBackupExporter(export)

        summary = exporter.backup_agents(["bad-id", SAMPLE_AGENT["id"]], tmp_path)

        assert summary["agents_ok"] == 1
        assert summary["agents_failed"] == 1
        assert summary["errors"][0]["agent_id"] == "bad-id"

    def test_backup_knowledge_metadata(self, tmp_path):
        knowledge = MagicMock()
        knowledge.list_files.return_value = [{"id": "f1", "name": "doc.pdf"}]
        exporter = LangDockBackupExporter(MagicMock(), knowledge)

        summary = exporter.backup_knowledge_metadata(["folder-abc"], tmp_path)

        assert summary["folders_ok"] == 1
        path = tmp_path / "knowledge" / "folder-abc.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["file_count"] == 1

    def test_backup_knowledge_requires_manager(self, tmp_path):
        exporter = LangDockBackupExporter(MagicMock(), None)
        with pytest.raises(ProviderError, match="knowledge manager"):
            exporter.backup_knowledge_metadata(["x"], tmp_path)


# ------------------------------------------------------------------------- CLI
@pytest.mark.unit
class TestCLI:
    def test_requires_something_to_do(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["langdock-export", "-k", "test", "--no-discover"],
        )
        assert result.exit_code != 0
        assert "Nothing to do" in result.output

    def test_agent_id_path(self, tmp_path):
        runner = CliRunner()
        with (
            patch("eq_chatbot_core.providers.langdock_provider.LangDockExportManager") as mock_export_cls,
            patch("eq_chatbot_core.providers.langdock_provider.LangDockKnowledgeManager") as mock_kn_cls,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_agent.return_value = dict(SAMPLE_AGENT)
            mock_export_cls.return_value = mock_mgr
            mock_kn_cls.return_value.list_files.return_value = []

            result = runner.invoke(
                main,
                [
                    "langdock-export",
                    "-k",
                    "test",
                    "--agent-id",
                    SAMPLE_AGENT["id"],
                    "--no-discover",
                    "-o",
                    str(tmp_path),
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "1 ok" in result.output
        assert (tmp_path / "manifest.json").exists()

    def test_discovery_auth_failure_is_graceful(self, tmp_path):
        runner = CliRunner()
        with (
            patch("eq_chatbot_core.providers.langdock_provider.LangDockExportManager") as mock_export_cls,
            patch("eq_chatbot_core.providers.langdock_provider.LangDockKnowledgeManager"),
        ):
            mock_mgr = MagicMock()
            mock_mgr.export_report.side_effect = AuthenticationError("forbidden", provider="langdock", status_code=403)
            mock_export_cls.return_value = mock_mgr

            result = runner.invoke(
                main,
                ["langdock-export", "-k", "test", "--discover", "-o", str(tmp_path)],
            )

        # Discovery fails softly; run still completes and writes a manifest.
        assert result.exit_code == 0, result.output
        assert "USAGE_EXPORT_API" in result.output

    def test_access_denied_prints_sharing_hint(self, tmp_path):
        runner = CliRunner()
        with (
            patch("eq_chatbot_core.providers.langdock_provider.LangDockExportManager") as mock_export_cls,
            patch("eq_chatbot_core.providers.langdock_provider.LangDockKnowledgeManager"),
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_agent.side_effect = ProviderError(
                "LangDock request failed (404): does not have access to this agent",
                provider="langdock",
                status_code=404,
            )
            mock_export_cls.return_value = mock_mgr

            ids = []
            for n in range(5):
                ids += ["--agent-id", f"0000000{n}-0000-0000-0000-000000000000"]
            result = runner.invoke(
                main,
                ["langdock-export", "-k", "test", "--no-discover", "-o", str(tmp_path), *ids],
            )

        assert result.exit_code == 0, result.output
        # All 5 fail; errors are collapsed and the sharing hint is shown.
        assert "0 ok, 5 failed" in result.output
        assert "and 2 more error(s)" in result.output
        assert "must be shared with this API key" in result.output
