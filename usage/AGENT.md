<!--
  Capability Card — generated/maintained via the `cli-capability-card` skill.
  Audience: an LLM/agent that wants to USE this tool. Keep it dense and current.
  Regenerate the command table with scripts/introspect_cli.py after CLI changes.
-->
# eq-chatbot — Agent Capability Card

> Unified command-line gateway to many LLM providers (OpenAI, Anthropic, Azure, Vertex, LangDock, OpenRouter, Mammouth, IONOS, Melious, LiteLLM, local LM Studio/Ollama) with single-turn JSON chat, model listing, text-to-image generation, batch listing-asset generation, a localhost HTTP/SSE server, and LangDock agent backup.

- **Invoke:** `eq-chatbot <command> [options]`
- **Install:** `pip install eq-chatbot-core` (server mode: `pip install 'eq-chatbot-core[server]'`; image resizing: `pip install 'eq-chatbot-core[image]'`)
- **Version:** 1.15.0
- **Framework:** Click  ·  **Human docs:** `docs/` (cli.md, providers.md, server-mode.md, langdock-export.md)

## Capabilities at a glance
- Send one-shot prompts to any supported provider and get a parseable JSON reply (`chat`) — ideal for non-Python callers.
- Smoke-test a provider/API key and inspect token usage (`test-provider`).
- Enumerate a provider's models with vision/tool-support metadata (`list-models`, `--json`).
- Generate a single image from a text prompt (`image`) — OpenAI `gpt-image-1` or OpenRouter image models.
- Batch-generate App-Store listing assets (icon/banner/eyecatchers) from a recipe JSON (`listing-assets`).
- Run a localhost-only HTTP/SSE sidecar exposing the gateway to other apps (`serve`) — bearer-auth, streaming.
- Back up LangDock agents (system prompt + config) and knowledge-folder metadata to local files (`langdock-export`).
- Provider-agnostic: switch backends by changing `-p` and the key — no code changes.

## Command reference
Notation: `[ARG]` optional positional · `ARG` required positional · `a|b` choice · `--flag` boolean.

| Command | Purpose | Args / Flags |
|---|---|---|
| `eq-chatbot chat` | Single-turn chat with JSON I/O for programmatic use. | --provider/-p openai\|anthropic\|langdock\|openrouter\|mammouth\|azure\|vertex\|litellm\|ionos\|melious\|local\|lm_studio\|lmstudio\|ollama, --api-key/-k TEXT, --model/-m TEXT, --temperature/-t FLOAT, --max-tokens INTEGER, --base-url/-u TEXT |
| `eq-chatbot image` | Generate an image from a text prompt. | --provider/-p openai\|openrouter, --api-key/-k TEXT, --model/-m TEXT, --prompt TEXT, --prompt-file PATH, --size TEXT, --fit TEXT, --output/-o TEXT, --base-url/-u TEXT |
| `eq-chatbot info` | Show package information. | — |
| `eq-chatbot langdock-export` | Back up LangDock agents and knowledge metadata to local files. | --api-key/-k TEXT, --output-dir/-o DIRECTORY, --agent-id TEXT, --discover/--no-discover, --knowledge-folder-id TEXT, --format md\|json\|both |
| `eq-chatbot list-models` | List available models from a provider. | --provider/-p openai\|anthropic\|langdock\|openrouter\|mammouth\|azure\|vertex\|litellm\|ionos\|melious\|local\|lm_studio\|lmstudio\|ollama, --api-key/-k TEXT, --base-url/-u TEXT, --json, --vision-only |
| `eq-chatbot listing-assets` | Generate a batch of images from a recipe JSON file. | --recipe PATH, --provider/-p openai\|openrouter, --model/-m TEXT, --api-key/-k TEXT, --base-url/-u TEXT, --dest DIRECTORY, --only TEXT, --dry-run |
| `eq-chatbot serve` | Run a localhost HTTP/SSE server exposing the LLM provider gateway. | --host TEXT, --port INTEGER, --auth-token TEXT, --auth-token-fd INTEGER, --parent-pid INTEGER, --log-level debug\|info\|warning\|error |
| `eq-chatbot test-provider` | Test connection to an LLM provider. | --provider/-p openai\|anthropic\|langdock\|openrouter\|mammouth\|azure\|vertex\|litellm\|ionos\|melious\|local\|lm_studio\|lmstudio\|ollama, --api-key/-k TEXT, --model/-m TEXT, --message/-msg TEXT, --base-url/-u TEXT |

**Key env vars:** On `chat`/`test-provider`/`list-models`/`image`/`listing-assets` the API key resolves as `--api-key` > `<PROVIDER>_API_KEY` > `LLM_API_KEY`. Provider-specific vars: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`, `OPENROUTER_API_KEY`, `MAMMOUTH_API_KEY`, `AZURE_API_KEY`, `LITELLM_API_KEY`, `IONOS_API_KEY`, `MELIOUS_API_KEY` (a key for one provider never satisfies another). `langdock-export` reads `LANGDOCK_API_KEY`. `serve` reads `EQ_CHATBOT_AUTH_TOKEN`. Local providers (`local`, `lm_studio`, `ollama`) and `vertex` (ADC) need no key.

## Recipes

### Programmatic one-shot completion (parse the JSON result)
```bash
echo '{"messages":[{"role":"user","content":"Summarize: ..."}]}' \
  | eq-chatbot chat -p openai -k "$OPENAI_KEY" -m gpt-4o-mini -t 0.3
```
Reads JSON `{"messages":[{role,content},...]}` from **stdin** (≤1 MB). Writes JSON `{"content","model","input_tokens","output_tokens"}` to **stdout**. On failure: JSON `{"error": ...}` on **stderr** and non-zero exit — branch on exit code, not on parsing stdout.

### Pick a model by capability
```bash
eq-chatbot list-models -p anthropic -k "$KEY" --json --vision-only
```
`--json` emits an array of `{id,name,provider,supports_vision,supports_tools,supports_streaming,context_length}`. Filter for the model id you need, then pass it to `chat -m`.

### Validate a key / provider before a batch job
```bash
eq-chatbot test-provider -p ionos -k "$KEY" -msg "ping"
LLM_API_KEY="$KEY" eq-chatbot test-provider -p openai
```
Human-readable success/usage report; exits non-zero on auth/connection failure. Good as a CI/pre-flight gate.

### Talk to a local model (no key)
```bash
eq-chatbot test-provider -p lm_studio                 # defaults to localhost:1234
eq-chatbot list-models  -p ollama                      # defaults to localhost:11434
eq-chatbot test-provider -p local -u http://host:1234/v1
```
Requires the local server already running. `lm_studio`/`ollama` carry built-in default base URLs; `local` requires `-u`.

### Generate a single image
```bash
eq-chatbot image -p openai -k "$KEY" --prompt "A sunset over the ocean" -o sunset.png
eq-chatbot image -p openai -k "$KEY" --prompt-file prompt.txt --size 1024x1536 --fit 512x512:cover
```
Providers limited to `openai` (`gpt-image-1`) and `openrouter` (e.g. `gemini-2.5-flash-image`). Default output `output.png`. `--fit WxH[:mode]` (cover/contain/stretch) requires the `[image]` extra.

### Batch-generate listing assets from a recipe
```bash
eq-chatbot listing-assets --recipe listing.json --dry-run                 # preview, no API calls
eq-chatbot listing-assets --recipe listing.json -k "$KEY" --only icon,banner --dest ./out
```
Recipe schema `eq-listing-assets/v1`; provider/model come from the recipe `defaults` block or CLI overrides. Each asset's `out` filename is confined to `--dest` (an untrusted absolute/`../` name cannot escape). Use `--dry-run` first to review the asset list.

### Run as a sidecar server for another app
```bash
TOKEN=$(python -c 'import secrets;print(secrets.token_urlsafe(32))')
printf '%s' "$TOKEN" | eq-chatbot serve --port 0 --auth-token-fd 0 --parent-pid $$
# stdout: "LISTENING ON host=127.0.0.1 port=NNNNN"  → scrape the port
```
Needs the `[server]` extra. `--port 0` picks a free port. All endpoints except `GET /health` require `Authorization: Bearer <token>`. `--parent-pid` makes the sidecar self-terminate when the parent dies. Endpoints: `GET /health`, `GET /providers`, `POST /models`, `POST /chat`, `POST /chat/stream` (SSE: `chunk`/`tool_call_delta`/`tool_calls`/`usage`/`done`/`error`).

### Back up LangDock agents (portable .md + .json)
```bash
# Specific agents (standard key, no admin scope needed) — pass the UI URL or raw UUID:
LANGDOCK_API_KEY="$KEY" eq-chatbot langdock-export \
  --agent-id https://app.langdock.com/assistant/<uuid> -o ./langdock-backup

# Discover ALL agents (requires an admin key with USAGE_EXPORT_API scope):
LANGDOCK_API_KEY="$ADMIN_KEY" eq-chatbot langdock-export --discover
```
Writes `agents/<slug>-<id8>.md` (YAML frontmatter + system prompt) and `.json` (raw definition), `knowledge/<folder_id>.json` (metadata only), plus `manifest.json`. `--format md|json|both` (default `both`). Knowledge-folder ids referenced by exported agents are backed up automatically.

## Guardrails & gotchas
- **Key env vars:** chat/test/list/image/listing-assets resolve `--api-key` > `<PROVIDER>_API_KEY` > `LLM_API_KEY`; `langdock-export` uses `LANGDOCK_API_KEY`; `serve` uses `EQ_CHATBOT_AUTH_TOKEN`. Don't cross them.
- **`image`/`listing-assets` providers are limited to `openai|openrouter`** — not the full provider list. `--fit` resizing needs the `[image]` extra (Pillow); generation without resizing does not.
- **`langdock-export --discover` needs admin scope** `USAGE_EXPORT_API` — a normal chat key returns HTTP 403. Without it, supply ids via `--agent-id`. Default is `--discover` ON only when no `--agent-id` is given; otherwise pass `--no-discover` explicitly to skip it.
- **Each LangDock agent must be shared with the API key** — the `AGENT_API` scope is only the capability, not per-agent access. Unshared agents return HTTP 404 "does not have access". Share in the UI: open the agent → Share → add the key (per agent, admin only). So `--discover` may list 58 agents yet back up 0 until they are shared.
- **LangDock document content is NOT downloadable — IDs/metadata only.** Knowledge-folder files give *metadata* + semantic search but no raw download (folder must be shared with the key, `KNOWLEDGE_FOLDER_API` scope); agent *attachments* have no download endpoint at all (404) — only their IDs are captured in the agent `.json`. An agent may show `knowledgeFolderIds: []` while its docs live as attachments. `langdock-export` backs up the agent + system prompt + attachment IDs, not the document bytes.
- **`chat` blocks on stdin** — it always reads a JSON payload from stdin; never invoke it without piping input or it will hang. Payload cap is 1 MB. It is one-shot: no streaming, no loop.
- **`serve` requires `[server]` extra** — missing → a clear ClickException telling you to install it. Token passed via `--auth-token` is visible in `argv`/`ps`; prefer `--auth-token-fd` or `EQ_CHATBOT_AUTH_TOKEN`.
- **`--base-url`/`-u` is SSRF-validated** — non-HTTP schemes and cloud-metadata/link-local targets are rejected; in strict mode an unresolvable host is refused (local providers allow private LAN ranges).
- **Output is not pretty-printed for humans** — `chat` and `--json` are designed to be machine-parsed.
- **Destructive:** none. All commands are read-only or write into an explicit `--output-dir`/`--dest`/`--output`; `langdock-export` and image commands overwrite same-named files in that dir without prompting.

## Machine-readable outputs
- `eq-chatbot chat` → stdout `{"content","model","input_tokens","output_tokens"}`; errors → stderr `{"error": ...}` + non-zero exit.
- `eq-chatbot list-models --json` → `[{"id","name","provider","supports_vision","supports_tools","supports_streaming","context_length"}, ...]`.
- `eq-chatbot serve` → first stdout line `LISTENING ON host=H port=P`; `/chat/stream` is SSE; non-streaming endpoints return JSON.
- `eq-chatbot langdock-export` → on disk: `agents/*.md`, `agents/*.json`, `knowledge/*.json`, `manifest.json` (run summary with counts + per-item errors).
- `eq-chatbot listing-assets` → writes one PNG per asset into `--dest`; `--dry-run` prints the planned asset list without API calls.

## Deeper docs
- `docs/cli.md` — full CLI walkthrough (all subcommands).
- `docs/providers.md` — provider specifics, base URLs, regions, temperature clamping.
- `docs/server-mode.md` — `serve` endpoints, SSE event schema, auth/watchdog details.
- `docs/langdock-export.md` — LangDock backup details, scopes, and limitations.
