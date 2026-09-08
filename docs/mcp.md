# MCP Client — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

The `eq_chatbot_core.mcp` package provides a client for the [Model Context Protocol](https://modelcontextprotocol.io) with three transports:

- `StreamableHTTPMCPClient` — Streamable HTTP (spec 2025-03-26 and later): one POST endpoint such as `https://host/mcp`. This is what every current server SDK offers for remote operation — use it unless the server only speaks the old SSE protocol.
- `MCPClient` — HTTP/SSE (spec 2024-11-05): the legacy remote transport with a `/sse` endpoint and a server-announced POST URL
- `StdioMCPClient` — stdio: spawns a local subprocess and speaks JSON-RPC over its stdin/stdout

All transports expose the same surface — `list_tools()`, `call_tool()`, `get_tool_schema()`, `close()` — and ship hardened against DNS rebinding, SSRF, and environment leakage to subprocesses.

### Quick start

```python
from eq_chatbot_core.mcp import get_mcp_client

# Streamable HTTP transport (current remote transport)
client = get_mcp_client(
    transport="http",
    url="https://mcp.example.com/mcp",
    api_key="bearer-token",
)
tools = client.list_tools()
result = client.call_tool("search", {"query": "python tutorials"})
client.close()

# Same, but the server lives on the intranet (LAN mode — see "Security model")
client = get_mcp_client(
    transport="http",
    url="http://mcp-host:5100/mcp",
    api_key="bearer-token",
    allow_private_ranges=True,
)

# Legacy HTTP/SSE transport
client = get_mcp_client(
    transport="sse",
    url="https://mcp.example.com/sse",
    api_key="bearer-token",
)

# stdio transport
client = get_mcp_client(
    transport="stdio",
    command="npx",
    args=["@modelcontextprotocol/server-filesystem", "/path/to/dir"],
    env={"FOO": "bar"},
)
tools = client.list_tools()
client.close()
```

### `StreamableHTTPMCPClient` (Streamable HTTP)

Connects to MCP servers exposing the Streamable HTTP transport — the .NET, TypeScript and Python server SDKs all offer it. The flow is:

1. Every JSON-RPC message is an HTTP `POST` to the one endpoint, with `Authorization: Bearer <api_key>` and `Accept: application/json, text/event-stream`
2. The server answers with a JSON body or with an SSE stream that carries the response; the client reads either
3. A stateful server assigns `Mcp-Session-Id` on `initialize`; the client replays it on every request and re-initialises once when the server reports the session as gone (HTTP 404). Stateless servers assign nothing and need nothing.
4. After the version negotiation the client sends `MCP-Protocol-Version` on every request

```python
from eq_chatbot_core.mcp import StreamableHTTPMCPClient

client = StreamableHTTPMCPClient(url="https://mcp.example.com/mcp", api_key="...")
client.connect()
schema = client.get_tool_schema("search")
result = client.call_tool("search", {"query": "..."})
client.close()
```

`list_tools()` follows `nextCursor` pagination. A tool that reports `isError: true` comes back as `MCPToolResult(success=False, error=<the tool's text>)` — the model can read the reason instead of guessing.

### `MCPClient` (HTTP/SSE)

Connects to MCP servers exposing the legacy SSE transport. The flow is:

1. Client sends `GET /sse` with `Authorization: Bearer <api_key>`
2. Server emits an `endpoint` event containing the POST URL for outgoing JSON-RPC
3. Client posts JSON-RPC requests to that URL; responses arrive via the SSE stream

```python
from eq_chatbot_core.mcp import MCPClient

client = MCPClient(url="https://mcp.example.com/sse", api_key="...")
client.connect()
schema = client.get_tool_schema("search")
result = client.call_tool("search", {"query": "..."})
client.close()
```

### `StdioMCPClient` (subprocess)

Spawns an MCP server as a child process. The command is **whitelisted** — only entries in `ALLOWED_STDIO_COMMANDS` may be spawned, defending against arbitrary-binary execution if the command name comes from untrusted config.

```python
from eq_chatbot_core.mcp import StdioMCPClient, ALLOWED_STDIO_COMMANDS

print(ALLOWED_STDIO_COMMANDS)  # e.g. ["npx", "uvx", "node", "python", ...]

client = StdioMCPClient(command="npx", args=["@modelcontextprotocol/server-everything"])
tools = client.list_tools()
client.close()
```

### Security model

#### LAN mode for intranet servers (both HTTP transports)

By default the client validates the server URL in strict mode: private, loopback and link-local addresses are rejected, and so is a hostname that does not resolve — that is the right setting when the URL comes from a cloud-facing configuration. An MCP server on the company intranet (`http://mcp-host:5100/mcp`, `http://10.0.0.5/...`) needs `allow_private_ranges=True`: private and loopback targets become reachable, and a hostname only the on-prem resolver knows is accepted without an IP pin. Link-local (the `169.254.169.254` cloud-metadata endpoint), reserved and multicast addresses stay blocked in LAN mode too, and the SSE `endpoint` event is judged by the same rule.

#### DNS rebinding protection (HTTP transports)

Added in v1.6.0. `_validate_url()` resolves the hostname during URL validation and returns the IP set. The HTTP transport (`httpx2.HTTPTransport`) re-resolves on every request and raises `httpx2.ConnectError("DNS rebinding detected")` if the resolution diverges from the pinned set.

The SSE listener client and the request client share the same `_pinned_ips` map; endpoint redirects sent by the server in the `endpoint` event are also pinned. Mitigates the TOCTOU window between URL validation and the actual TCP connect.

> **Note**: A small TOCTOU window remains between DNS resolution and the actual connect. For complete protection in production deployments, combine this with network-level egress filtering.

#### SSRF protection on SSE `endpoint` events (v1.5.1)

The POST URL announced by the MCP server in the `endpoint` event is validated:

- Private/reserved IPs (RFC 1918, loopback, link-local, multicast) are rejected
- Non-`http`/`https` schemes (e.g. `file:///`, `ftp://`, `gopher://`) are rejected
- Non-`/`-relative paths are rejected

This prevents a hostile MCP server from redirecting outgoing traffic to internal services after SSE setup.

#### Environment whitelist (stdio transport)

`StdioMCPClient.start()` does **not** forward `os.environ` to the spawned subprocess. Only this minimal whitelist is passed through:

```
PATH, HOME, LANG, LC_ALL, TZ, TMPDIR, USER, LOGNAME, SHELL,
SystemRoot / SYSTEMROOT (Windows)
```

Plus any keys explicitly supplied via the `env=` argument.

`PYTHONPATH` was on the whitelist before v1.6.0; it was removed because `PYTHONPATH` inheritance allowed module injection that overrode stdlib imports inside the subprocess, defeating the command whitelist. Callers needing a custom Python path must now pass it explicitly via `env={"PYTHONPATH": "..."}`.

### Public API surface

```python
from eq_chatbot_core.mcp import (
    StreamableHTTPMCPClient,  # Streamable HTTP transport (current)
    MCPClient,             # legacy HTTP/SSE transport
    StdioMCPClient,        # subprocess transport
    MCPToolResult,         # dataclass for tool-call results
    ALLOWED_STDIO_COMMANDS,  # subprocess whitelist
    get_mcp_client,        # factory: dispatches to the right transport
)
```

### See also

- [Security](security.md#english) — encryption, injection detection, rate limiting, file validation
- [Providers](providers.md#english) — provider abstraction (independent of MCP)

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

Das Paket `eq_chatbot_core.mcp` stellt einen Client für das [Model Context Protocol](https://modelcontextprotocol.io) mit drei Transports bereit:

- `StreamableHTTPMCPClient` — Streamable HTTP (Spec ab 2025-03-26): ein einziger POST-Endpunkt wie `https://host/mcp`. Das bieten alle aktuellen Server-SDKs für den Fernbetrieb — die erste Wahl, sofern der Server nicht nur das alte SSE-Protokoll spricht.
- `MCPClient` — HTTP/SSE (Spec 2024-11-05): der ältere Remote-Transport mit `/sse`-Endpunkt und vom Server gemeldeter POST-URL
- `StdioMCPClient` — stdio: spawnt einen lokalen Subprozess und spricht JSON-RPC über dessen stdin/stdout

Alle Transports exponieren dieselbe Oberfläche — `list_tools()`, `call_tool()`, `get_tool_schema()`, `close()` — und sind gehärtet gegen DNS-Rebinding, SSRF und Environment-Leakage zum Subprozess.

### Quick Start

```python
from eq_chatbot_core.mcp import get_mcp_client

# Streamable-HTTP-Transport (aktueller Remote-Transport)
client = get_mcp_client(
    transport="http",
    url="https://mcp.example.com/mcp",
    api_key="bearer-token",
)
tools = client.list_tools()
result = client.call_tool("search", {"query": "Python-Tutorials"})
client.close()

# Dasselbe für einen Server im Intranet (LAN-Modus — siehe „Sicherheitsmodell")
client = get_mcp_client(
    transport="http",
    url="http://mcp-host:5100/mcp",
    api_key="bearer-token",
    allow_private_ranges=True,
)

# Älterer HTTP/SSE-Transport
client = get_mcp_client(
    transport="sse",
    url="https://mcp.example.com/sse",
    api_key="bearer-token",
)

# stdio-Transport
client = get_mcp_client(
    transport="stdio",
    command="npx",
    args=["@modelcontextprotocol/server-filesystem", "/pfad/zum/dir"],
    env={"FOO": "bar"},
)
tools = client.list_tools()
client.close()
```

### `StreamableHTTPMCPClient` (Streamable HTTP)

Verbindet sich mit MCP-Servern, die den Streamable-HTTP-Transport exponieren — die Server-SDKs für .NET, TypeScript und Python bieten ihn alle. Der Ablauf:

1. Jede JSON-RPC-Nachricht ist ein HTTP-`POST` an den einen Endpunkt, mit `Authorization: Bearer <api_key>` und `Accept: application/json, text/event-stream`
2. Der Server antwortet mit einem JSON-Body oder mit einem SSE-Stream, der die Antwort trägt; der Client liest beides
3. Ein zustandsbehafteter Server vergibt beim `initialize` eine `Mcp-Session-Id`; der Client sendet sie bei jeder Anfrage mit und initialisiert einmal neu, wenn der Server die Sitzung als abgelaufen meldet (HTTP 404). Zustandslose Server vergeben nichts und brauchen nichts.
4. Nach der Versionsaushandlung sendet der Client `MCP-Protocol-Version` bei jeder Anfrage

```python
from eq_chatbot_core.mcp import StreamableHTTPMCPClient

client = StreamableHTTPMCPClient(url="https://mcp.example.com/mcp", api_key="...")
client.connect()
schema = client.get_tool_schema("search")
result = client.call_tool("search", {"query": "..."})
client.close()
```

`list_tools()` folgt der `nextCursor`-Blätterung. Ein Werkzeug, das `isError: true` meldet, kommt als `MCPToolResult(success=False, error=<Text des Werkzeugs>)` zurück — das Modell liest den Grund, statt zu raten.

### `MCPClient` (HTTP/SSE)

Verbindet sich mit MCP-Servern, die den älteren SSE-Transport exponieren. Der Ablauf:

1. Client sendet `GET /sse` mit `Authorization: Bearer <api_key>`
2. Server emittiert ein `endpoint`-Event mit der POST-URL für ausgehende JSON-RPC
3. Client postet JSON-RPC-Requests an diese URL; Responses kommen über den SSE-Stream

```python
from eq_chatbot_core.mcp import MCPClient

client = MCPClient(url="https://mcp.example.com/sse", api_key="...")
client.connect()
schema = client.get_tool_schema("search")
result = client.call_tool("search", {"query": "..."})
client.close()
```

### `StdioMCPClient` (Subprozess)

Spawnt einen MCP-Server als Child-Prozess. Das Command ist **whitelisted** — nur Einträge in `ALLOWED_STDIO_COMMANDS` dürfen gespawnt werden, schützt vor Arbitrary-Binary-Execution wenn der Command-Name aus unsicherer Config kommt.

```python
from eq_chatbot_core.mcp import StdioMCPClient, ALLOWED_STDIO_COMMANDS

print(ALLOWED_STDIO_COMMANDS)  # z.B. ["npx", "uvx", "node", "python", ...]

client = StdioMCPClient(command="npx", args=["@modelcontextprotocol/server-everything"])
tools = client.list_tools()
client.close()
```

### Sicherheitsmodell

#### LAN-Modus für Server im Intranet (beide HTTP-Transports)

Standardmäßig prüft der Client die Server-URL im strikten Modus: private, Loopback- und Link-Local-Adressen werden abgewiesen, ebenso ein Hostname, der sich nicht auflösen lässt — die richtige Einstellung, wenn die URL aus einer nach außen gerichteten Konfiguration stammt. Ein MCP-Server im Firmen-Intranet (`http://mcp-host:5100/mcp`, `http://10.0.0.5/...`) braucht `allow_private_ranges=True`: private und Loopback-Ziele werden erreichbar, und ein Hostname, den nur der interne Resolver kennt, wird ohne IP-Pin akzeptiert. Link-Local (der Cloud-Metadaten-Endpunkt `169.254.169.254`), reservierte und Multicast-Adressen bleiben auch im LAN-Modus gesperrt; das SSE-`endpoint`-Event wird nach derselben Regel beurteilt.

#### DNS-Rebinding-Schutz (HTTP-Transports)

Hinzugefügt in v1.6.0. `_validate_url()` resolvt den Hostname während der URL-Validierung und liefert das IP-Set zurück. Der HTTP-Transport (`httpx2.HTTPTransport`) resolvt bei jedem Request neu und wirft `httpx2.ConnectError("DNS rebinding detected")` wenn die Auflösung vom gepinnten Set abweicht.

SSE-Listener-Client und Request-Client teilen dieselbe `_pinned_ips`-Map; Endpoint-Redirects, die der Server im `endpoint`-Event sendet, werden ebenfalls gepinnt. Reduziert das TOCTOU-Fenster zwischen URL-Validierung und tatsächlichem TCP-Connect.

> **Hinweis**: Ein kleines TOCTOU-Fenster bleibt zwischen DNS-Auflösung und Connect. Für vollständigen Schutz in Production zusätzlich Netzwerk-Level-Egress-Filtering einsetzen.

#### SSRF-Schutz auf SSE-`endpoint`-Events (v1.5.1)

Die POST-URL, die der MCP-Server im `endpoint`-Event ankündigt, wird validiert:

- Private/reservierte IPs (RFC 1918, Loopback, Link-Local, Multicast) werden abgelehnt
- Nicht-`http`/`https`-Schemes (z.B. `file:///`, `ftp://`, `gopher://`) werden abgelehnt
- Nicht-`/`-relative Pfade werden abgelehnt

Verhindert dass ein feindlicher MCP-Server ausgehenden Traffic nach SSE-Setup auf interne Dienste umleitet.

#### Environment-Whitelist (stdio-Transport)

`StdioMCPClient.start()` reicht `os.environ` **nicht** an den gespawnten Subprozess weiter. Nur diese minimale Whitelist:

```
PATH, HOME, LANG, LC_ALL, TZ, TMPDIR, USER, LOGNAME, SHELL,
SystemRoot / SYSTEMROOT (Windows)
```

Plus alle Keys, die explizit über `env=` übergeben werden.

`PYTHONPATH` war vor v1.6.0 auf der Whitelist; es wurde entfernt, weil `PYTHONPATH`-Inheritance Modul-Injection erlaubte, die stdlib-Imports im Subprozess überschreiben konnte und damit die Command-Whitelist umging. Callers, die einen eigenen Python-Pfad brauchen, müssen ihn explizit über `env={"PYTHONPATH": "..."}` übergeben.

### Öffentliche API-Oberfläche

```python
from eq_chatbot_core.mcp import (
    StreamableHTTPMCPClient,  # Streamable-HTTP-Transport (aktuell)
    MCPClient,             # älterer HTTP/SSE-Transport
    StdioMCPClient,        # Subprozess-Transport
    MCPToolResult,         # Dataclass für Tool-Call-Resultate
    ALLOWED_STDIO_COMMANDS,  # Subprozess-Whitelist
    get_mcp_client,        # Factory: dispatcht zum richtigen Transport
)
```

### Siehe auch

- [Security](security.md#deutsch) — Verschlüsselung, Injection-Erkennung, Rate-Limiting, File-Validation
- [Provider](providers.md#deutsch) — Provider-Abstraktion (unabhängig von MCP)

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
