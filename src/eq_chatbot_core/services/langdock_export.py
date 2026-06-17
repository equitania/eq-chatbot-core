"""
LangDock backup/export orchestration.

Decentralised backup of LangDock agents and knowledge-folder metadata so they
stay portable when LangDock is unavailable. Agent definitions (including their
system prompt / ``instruction``) are written both as portable Markdown and as
raw JSON, ready to reuse in other AI tools (e.g. Claude Code subagents).

API limitations (honest constraints):
  - LangDock exposes NO "list all agents" endpoint. Agent IDs come either from
    the UI URL (manual) or from the ``/export/agents`` usage CSV (needs an admin
    key with the ``USAGE_EXPORT_API`` scope).
  - Knowledge-folder *content* (documents) cannot be downloaded via the API.
    Only file metadata (listing) can be backed up.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import re
from pathlib import Path
from typing import Any

from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.langdock_provider import (
    LangDockExportManager,
    LangDockKnowledgeManager,
)

# UUID v4-ish shape used to pull an agent id out of a UI URL.
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

# Default usage-export window when discovering agent ids (days back from today).
_DISCOVERY_WINDOW_DAYS = 365


def extract_agent_id(value: str) -> str:
    """
    Normalise a user-supplied agent reference to a bare id.

    Accepts a raw UUID or a full LangDock UI URL and returns the embedded id.
    Falls back to the trimmed input when no UUID pattern is found (LangDock ids
    are not guaranteed to be UUIDs forever).

    Args:
        value: Raw UUID, or a UI URL such as
            ``https://app.langdock.com/assistant/<uuid>``

    Returns:
        The extracted agent id.
    """
    value = (value or "").strip()
    match = _UUID_RE.search(value)
    if match:
        return match.group(0)
    if "/" in value:
        # No UUID match — take the last non-empty path segment (strip query).
        segment = value.rstrip("/").split("?")[0].split("/")[-1]
        return segment or value
    return value


def slugify(name: str, fallback: str = "agent") -> str:
    """Make a filesystem-safe slug from an agent name."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or fallback


def _yaml_scalar(value: Any) -> str:
    """Render a value as a single-line YAML scalar (quoted when needed)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or re.search(r"[:#\[\]{}\"'\n]|^[\s>|@`-]", text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        return f'"{escaped}"'
    return text


class LangDockBackupExporter:
    """Orchestrates LangDock agent / knowledge backups to the local filesystem."""

    def __init__(
        self,
        export_manager: LangDockExportManager,
        knowledge_manager: LangDockKnowledgeManager | None = None,
    ):
        """
        Args:
            export_manager: HTTP manager for agent + usage-export endpoints.
            knowledge_manager: Optional manager for knowledge-folder listings.
        """
        self.export = export_manager
        self.knowledge = knowledge_manager

    # ------------------------------------------------------------------ discover
    def discover_agents(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        timezone: str = "UTC",
    ) -> list[dict[str, str]]:
        """
        Discover agent ids via the ``/export/agents`` usage CSV.

        Requires an admin API key with the ``USAGE_EXPORT_API`` scope.

        Returns:
            List of ``{"id": ..., "name": ...}`` dicts (deduplicated, id-keyed).
        """
        if date_from is None or date_to is None:
            today = datetime.datetime.now(datetime.timezone.utc)
            start = today - datetime.timedelta(days=_DISCOVERY_WINDOW_DAYS)
            date_to = date_to or _iso(today)
            date_from = date_from or _iso(start)

        meta = self.export.export_report("agents", date_from, date_to, timezone)
        url = meta.get("downloadUrl")
        if not url:
            raise ProviderError("Usage export returned no downloadUrl", provider="langdock")
        csv_text = self.export.download_signed_csv(url)
        return self._parse_agents_csv(csv_text)

    @staticmethod
    def _parse_agents_csv(csv_text: str) -> list[dict[str, str]]:
        """Pull (id, name) pairs out of an /export/agents CSV."""
        reader = csv.DictReader(io.StringIO(csv_text))
        found: dict[str, str] = {}
        for row in reader:
            agent_id = (row.get("assistant_id") or row.get("agent_id") or "").strip()
            if not agent_id:
                continue
            name = (row.get("assistant_name") or row.get("agent_name") or "").strip()
            found.setdefault(agent_id, name)
        return [{"id": k, "name": v} for k, v in found.items()]

    # -------------------------------------------------------------------- format
    def agent_to_markdown(self, agent: dict[str, Any]) -> str:
        """
        Render an agent definition as portable Markdown.

        YAML frontmatter carries the configuration; the body is the system
        prompt (``instruction``) verbatim, ready to reuse as a prompt elsewhere.
        """
        export_date = datetime.date.today().isoformat()
        instruction = agent.get("instruction") or ""

        front: list[tuple[str, Any]] = [
            ("id", agent.get("id")),
            ("name", agent.get("name")),
            ("description", agent.get("description")),
            ("model", agent.get("model")),
            ("temperature", agent.get("temperature")),
            ("input_type", agent.get("inputType")),
            ("source", "langdock"),
            ("export_date", export_date),
        ]

        lines = ["---"]
        for key, value in front:
            if value is None:
                continue
            lines.append(f"{key}: {_yaml_scalar(value)}")

        capabilities = agent.get("capabilities")
        if isinstance(capabilities, dict) and capabilities:
            enabled = [k for k, v in capabilities.items() if v]
            if enabled:
                lines.append(f"capabilities: [{', '.join(enabled)}]")

        folder_ids = agent.get("knowledgeFolderIds")
        if isinstance(folder_ids, list) and folder_ids:
            joined = ", ".join(_yaml_scalar(f) for f in folder_ids)
            lines.append(f"knowledge_folder_ids: [{joined}]")

        lines.append("---")
        lines.append("")
        lines.append(f"# {agent.get('name') or agent.get('id') or 'Agent'}")
        lines.append("")

        description = agent.get("description")
        if description:
            lines.append(str(description))
            lines.append("")

        lines.append("## System Prompt")
        lines.append("")
        lines.append(instruction)
        lines.append("")

        starters = agent.get("conversationStarters")
        if isinstance(starters, list) and starters:
            lines.append("## Conversation Starters")
            lines.append("")
            for starter in starters:
                lines.append(f"- {starter}")
            lines.append("")

        return "\n".join(lines)

    # -------------------------------------------------------------------- backup
    def backup_agents(
        self,
        agent_ids: list[str],
        output_dir: str | Path,
        fmt: str = "both",
    ) -> dict[str, Any]:
        """
        Back up the given agents to ``<output_dir>/agents/``.

        A failure on a single agent is recorded and does not abort the run.

        Args:
            agent_ids: Agent ids or UI URLs (normalised internally).
            output_dir: Backup root directory.
            fmt: "md", "json", or "both".

        Returns:
            Summary dict with counts, written paths, collected knowledge folder
            ids, and per-agent errors.
        """
        agents_dir = Path(output_dir) / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        errors: list[dict[str, str]] = []
        folder_ids: set[str] = set()
        ok = 0

        for raw in agent_ids:
            agent_id = extract_agent_id(raw)
            try:
                agent = self.export.get_agent(agent_id)
            except ProviderError as exc:
                errors.append({"agent_id": agent_id, "error": str(exc)})
                continue

            agent.setdefault("id", agent_id)
            slug = slugify(str(agent.get("name") or ""), fallback=agent_id[:8] or "agent")
            stem = f"{slug}-{agent_id[:8]}"

            if fmt in ("json", "both"):
                json_path = agents_dir / f"{stem}.json"
                json_path.write_text(json.dumps(agent, indent=2, ensure_ascii=False), encoding="utf-8")
                written.append(str(json_path))
            if fmt in ("md", "both"):
                md_path = agents_dir / f"{stem}.md"
                md_path.write_text(self.agent_to_markdown(agent), encoding="utf-8")
                written.append(str(md_path))

            collected = agent.get("knowledgeFolderIds")
            if isinstance(collected, list):
                folder_ids.update(str(f) for f in collected)
            ok += 1

        return {
            "agents_ok": ok,
            "agents_failed": len(errors),
            "written": written,
            "errors": errors,
            "knowledge_folder_ids": sorted(folder_ids),
        }

    def backup_knowledge_metadata(
        self,
        folder_ids: list[str],
        output_dir: str | Path,
    ) -> dict[str, Any]:
        """
        Back up file metadata for the given knowledge folders.

        Only metadata (file listings) is available — the API offers no
        document-content download.

        Returns:
            Summary dict with counts, written paths, and per-folder errors.
        """
        if self.knowledge is None:
            raise ProviderError("Knowledge backup requires a knowledge manager", provider="langdock")

        knowledge_dir = Path(output_dir) / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        errors: list[dict[str, str]] = []
        ok = 0

        for folder_id in folder_ids:
            try:
                files = self.knowledge.list_files(folder_id)
            except Exception as exc:  # noqa: BLE001 - record, never abort the run
                errors.append({"folder_id": folder_id, "error": str(exc)})
                continue
            path = knowledge_dir / f"{folder_id}.json"
            path.write_text(
                json.dumps(
                    {
                        "folder_id": folder_id,
                        "export_date": datetime.date.today().isoformat(),
                        "file_count": len(files),
                        "files": files,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            written.append(str(path))
            ok += 1

        return {
            "folders_ok": ok,
            "folders_failed": len(errors),
            "written": written,
            "errors": errors,
        }

    def write_manifest(
        self,
        output_dir: str | Path,
        summary: dict[str, Any],
    ) -> str:
        """Write a run summary to ``<output_dir>/manifest.json`` and return its path."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        manifest = {
            "export_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "tool": "eq-chatbot langdock-export",
            **summary,
        }
        path = out / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)


def _iso(dt: datetime.datetime) -> str:
    """Format a datetime as the millisecond ISO 8601 LangDock expects."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
