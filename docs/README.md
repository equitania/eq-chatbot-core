# Documentation Index — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

Topic-specific guides for `eq-chatbot-core`. Start with the [project README](../README.md) for installation and a one-minute quick start.

| Topic | Documentation |
|-------|---------------|
| Multi-provider integration (OpenAI, Anthropic, LangDock, OpenRouter, Mammouth, IONOS, Melious, Privatemode, local) | [providers.md](providers.md#english) |
| Reasoning / thinking modes (four mechanisms, traces, capability catalog) | [reasoning.md](reasoning.md#english) |
| CLI commands (`info`, `test-provider`, `list-models`, `chat`, `serve`) | [cli.md](cli.md#english) |
| HTTP/SSE server mode (sidecar pattern, bearer auth, watchdog) | [server-mode.md](server-mode.md#english) |
| Security (encryption, prompt-injection detection, rate limit, file validation) | [security.md](security.md#english) |
| MCP client (HTTP/SSE + stdio, DNS pinning, env whitelist) | [mcp.md](mcp.md#english) |
| RAG pipeline (chunking, embedding, Qdrant retrieval, context management) | [rag.md](rag.md#english) |
| Testing (pytest markers, integration setup, cost-aware patterns) | [testing.md](testing.md) |

### Conventions

- Each document is bilingual (English first, German second), separated by a `---` rule and an anchored toggle at the top.
- Code blocks use `python` / `bash` fences and assume the reader has run `uv pip install -e .` (plus any extras listed in the doc).
- Cross-references use relative links — they work both on GitHub render and in IDE preview.

---

[← Back to project README](../README.md#english)

---

## Deutsch

Topic-spezifische Anleitungen für `eq-chatbot-core`. Beginne mit dem [Projekt-README](../README.md) für Installation und einen Ein-Minuten-Quickstart.

| Thema | Dokumentation |
|-------|---------------|
| Multi-Provider-Integration (OpenAI, Anthropic, LangDock, OpenRouter, Mammouth, IONOS, Melious, Privatemode, lokal) | [providers.md](providers.md#deutsch) |
| Reasoning-/Thinking-Modi (vier Mechanismen, Traces, Capability-Katalog) | [reasoning.md](reasoning.md#deutsch) |
| CLI-Befehle (`info`, `test-provider`, `list-models`, `chat`, `serve`) | [cli.md](cli.md#deutsch) |
| HTTP/SSE-Server-Mode (Sidecar-Pattern, Bearer-Auth, Watchdog) | [server-mode.md](server-mode.md#deutsch) |
| Security (Verschlüsselung, Prompt-Injection-Erkennung, Rate-Limit, File-Validation) | [security.md](security.md#deutsch) |
| MCP-Client (HTTP/SSE + stdio, DNS-Pinning, Env-Whitelist) | [mcp.md](mcp.md#deutsch) |
| RAG-Pipeline (Chunking, Embedding, Qdrant-Retrieval, Context-Management) | [rag.md](rag.md#deutsch) |
| Testing (pytest-Marker, Integration-Setup, Cost-Aware-Patterns) | [testing.md](testing.md) |

### Konventionen

- Jedes Dokument ist bilingual (Englisch zuerst, Deutsch danach), getrennt durch eine `---`-Linie und einen Anchor-Toggle oben.
- Code-Blöcke nutzen `python`-/`bash`-Fences und gehen davon aus, dass der Leser `uv pip install -e .` (plus die im Dokument genannten Extras) ausgeführt hat.
- Cross-References verwenden relative Links — funktionieren auf GitHub-Render und im IDE-Preview.

---

[← Zurück zum Projekt-README](../README.md#deutsch)
