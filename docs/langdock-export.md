# LangDock Backup / Export — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

Decentralised backup of your LangDock **agents** (including their system prompt) and
**knowledge-folder metadata** to local files — so they stay portable when LangDock is
unavailable, and reusable in other AI tools (e.g. as a Claude Code subagent prompt).

### Quick start

```bash
# Back up specific agents — pass the UI URL or a raw UUID (standard key is enough):
LANGDOCK_API_KEY=ld-... eq-chatbot langdock-export \
  --agent-id https://app.langdock.com/assistant/<uuid> \
  --output-dir ./langdock-backup

# Discover and back up ALL agents (requires an admin key with the USAGE_EXPORT_API scope):
LANGDOCK_API_KEY=ld-admin-... eq-chatbot langdock-export --discover
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--api-key` / `-k` | `LANGDOCK_API_KEY` env | LangDock API key |
| `--output-dir` / `-o` | `./langdock-backup` | Backup root directory |
| `--agent-id` | — | Agent UUID or UI URL (repeatable) |
| `--discover` / `--no-discover` | discover when no `--agent-id` | Auto-discover ids via the usage export API |
| `--knowledge-folder-id` | — | Folder id to back up metadata for (repeatable) |
| `--format` | `both` | `md`, `json`, or `both` |

### Output layout

```
langdock-backup/
├── agents/
│   ├── <slug>-<id8>.md     # YAML frontmatter + system prompt (portable)
│   └── <slug>-<id8>.json   # raw agent definition
├── knowledge/
│   └── <folder_id>.json    # file metadata of the folder
└── manifest.json           # run summary (counts, paths, per-item errors)
```

Knowledge-folder ids referenced by exported agents are backed up automatically.

### API scopes & limits

- **Each agent must be shared with the API key** — the `AGENT_API` scope (the "Agent API"
  permission checkbox) is only the *capability*; it grants **no** per-agent access. In the LangDock
  UI: open the agent → **Share** (top right) → search the API key's name → add it. Repeat per agent
  (no bulk option, admin only). Without this, every retrieval returns HTTP 404 "Agent not found or
  API key does not have access".
- **Single-agent retrieval** (`--agent-id`) uses `GET /agent/v1/get`. Agent ids live in the LangDock
  UI URL when you open an agent (e.g. `…/chat?a=<uuid>`).
- **Discovery** (`--discover`) calls `POST /export/agents` and needs an **admin key with the
  `USAGE_EXPORT_API` scope**. A normal key returns HTTP 403 — the run continues and falls back to a
  hint to pass `--agent-id`.
- **Knowledge content cannot be downloaded** via the API — only file *metadata* is available, and
  only for folders explicitly shared with the key (`KNOWLEDGE_FOLDER_API` scope).

Create / scope API keys at `https://app.langdock.com/settings/workspace/products/api`.

### Programmatic use

```python
from eq_chatbot_core.providers.langdock_provider import (
    LangDockExportManager, LangDockKnowledgeManager,
)
from eq_chatbot_core.services.langdock_export import LangDockBackupExporter

exporter = LangDockBackupExporter(
    LangDockExportManager(api_key="ld-..."),
    LangDockKnowledgeManager(api_key="ld-..."),
)
summary = exporter.backup_agents(["<uuid-or-ui-url>"], "./langdock-backup", fmt="both")
print(summary["agents_ok"], summary["knowledge_folder_ids"])
```

---

[← Back to documentation index](README.md#english)

---

## Deutsch

Dezentrale Sicherung deiner LangDock-**Agenten** (inkl. System-Prompt) und der
**Knowledge-Folder-Metadaten** in lokale Dateien — damit sie bei einem LangDock-Ausfall portabel
bleiben und in anderen KI-Tools weiterverwendbar sind (z.B. als Claude-Code-Subagent-Prompt).

### Schnellstart

```bash
# Bestimmte Agenten sichern — UI-URL oder rohe UUID angeben (Standard-Key genügt):
LANGDOCK_API_KEY=ld-... eq-chatbot langdock-export \
  --agent-id https://app.langdock.com/assistant/<uuid> \
  --output-dir ./langdock-backup

# ALLE Agenten automatisch finden und sichern (Admin-Key mit USAGE_EXPORT_API-Scope nötig):
LANGDOCK_API_KEY=ld-admin-... eq-chatbot langdock-export --discover
```

### Optionen

| Flag | Default | Bedeutung |
|------|---------|-----------|
| `--api-key` / `-k` | `LANGDOCK_API_KEY` env | LangDock-API-Key |
| `--output-dir` / `-o` | `./langdock-backup` | Backup-Wurzelverzeichnis |
| `--agent-id` | — | Agent-UUID oder UI-URL (wiederholbar) |
| `--discover` / `--no-discover` | discover, wenn kein `--agent-id` | IDs automatisch über die Export-API finden |
| `--knowledge-folder-id` | — | Folder-ID, deren Metadaten gesichert werden (wiederholbar) |
| `--format` | `both` | `md`, `json` oder `both` |

### Ausgabe-Layout

```
langdock-backup/
├── agents/
│   ├── <slug>-<id8>.md     # YAML-Frontmatter + System-Prompt (portabel)
│   └── <slug>-<id8>.json   # rohe Agenten-Definition
├── knowledge/
│   └── <folder_id>.json    # Datei-Metadaten des Folders
└── manifest.json           # Lauf-Zusammenfassung (Counts, Pfade, Fehler pro Eintrag)
```

Von exportierten Agenten referenzierte Knowledge-Folder-IDs werden automatisch mitgesichert.

### API-Scopes & Grenzen

- **Jeder Agent muss mit dem API-Key geteilt werden** — der `AGENT_API`-Scope (das Häkchen
  „Agenten API") ist nur die *Capability* und gewährt **keinen** Zugriff auf einzelne Agenten. In
  der LangDock-UI: Agent öffnen → **Share** (oben rechts) → Key-Namen suchen → hinzufügen. Pro Agent
  wiederholen (kein Bulk, nur Admin). Ohne das liefert jeder Abruf HTTP 404 „Agent not found or API
  key does not have access".
- **Einzel-Agent-Abruf** (`--agent-id`) nutzt `GET /agent/v1/get`. Die Agent-ID steht in der
  LangDock-UI-URL, wenn du einen Agenten öffnest (z.B. `…/chat?a=<uuid>`).
- **Discovery** (`--discover`) ruft `POST /export/agents` auf und braucht einen **Admin-Key mit
  `USAGE_EXPORT_API`-Scope**. Ein normaler Key liefert HTTP 403 — der Lauf bricht nicht ab und
  weist auf den manuellen `--agent-id`-Weg hin.
- **Knowledge-Inhalte sind nicht herunterladbar** — nur Datei-*Metadaten*, und nur für Folder, die
  dem Key explizit freigegeben sind (`KNOWLEDGE_FOLDER_API`-Scope).

API-Keys erstellen/scopen unter `https://app.langdock.com/settings/workspace/products/api`.

### Programmatische Nutzung

```python
from eq_chatbot_core.providers.langdock_provider import (
    LangDockExportManager, LangDockKnowledgeManager,
)
from eq_chatbot_core.services.langdock_export import LangDockBackupExporter

exporter = LangDockBackupExporter(
    LangDockExportManager(api_key="ld-..."),
    LangDockKnowledgeManager(api_key="ld-..."),
)
summary = exporter.backup_agents(["<uuid-oder-ui-url>"], "./langdock-backup", fmt="both")
print(summary["agents_ok"], summary["knowledge_folder_ids"])
```

---

[← Zurück zum Dokumentations-Index](README.md#deutsch)
