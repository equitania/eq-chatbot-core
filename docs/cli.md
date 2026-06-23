# CLI Reference — eq-chatbot-core

> **Language / Sprache**: [DE](#deutsch) | [EN](#english)

---

## English

### Overview

`eq-chatbot-core` ships a Click-based CLI named `eq-chatbot`. Five subcommands cover provider testing, model discovery, programmatic chat I/O, the HTTP/SSE sidecar, and package introspection.

```bash
eq-chatbot --help
```

### Subcommands

#### `eq-chatbot info`

Print the package version, installed extras, and Python version. Useful for bug reports.

```bash
eq-chatbot info
```

#### `eq-chatbot test-provider`

Smoke-test a provider connection by sending a single chat completion. Exits non-zero on auth or transport errors.

```bash
eq-chatbot test-provider -p openai -k $OPENAI_API_KEY
eq-chatbot test-provider -p anthropic -k sk-ant-... -m claude-3-5-sonnet-20241022
eq-chatbot test-provider -p local --base-url http://localhost:1234/v1
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Provider name (`openai`, `anthropic`, `azure`, `vertex`, `langdock`, `openrouter`, `mammouth`, `local`, `lm_studio`, `ollama`) |
| `-k`, `--api-key` | API key (cloud providers only) |
| `-m`, `--model` | Model id (defaults to provider's `default_model`) |
| `--message` | Custom test prompt (default: a short greeting) |
| `--base-url` | Custom endpoint (Azure, local OpenAI-compatible) |

#### `eq-chatbot list-models`

List models available from a provider. Output is human-readable by default; pass `--json` for machine consumption.

```bash
eq-chatbot list-models -p openai -k YOUR_KEY
eq-chatbot list-models -p langdock -k YOUR_KEY --vision-only
eq-chatbot list-models -p anthropic -k YOUR_KEY --json
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Provider name |
| `-k`, `--api-key` | API key |
| `--base-url` | Custom endpoint |
| `--json` | Output as JSON array of model objects |
| `--vision-only` | Filter to vision-capable models |

#### `eq-chatbot chat`

Single-turn chat with JSON I/O — designed for integration with tools that don't speak Python (Rust, Go, Bash). Reads a JSON envelope from stdin, writes the result to stdout, errors as JSON to stderr with non-zero exit.

```bash
echo '{"messages":[{"role":"user","content":"Hello"}]}' | \
    eq-chatbot chat -p openai -k YOUR_KEY

# Output: {"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}
```

**Input schema** (stdin):

```json
{
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Question here"}
  ]
}
```

Stdin is capped at **1 MB** to avoid runaway memory usage.

**Output schema** (stdout):

```json
{
  "content": "model response text",
  "model": "gpt-4o-mini",
  "input_tokens": 42,
  "output_tokens": 17
}
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Provider name |
| `-k`, `--api-key` | API key (or set `LLM_API_KEY` env) |
| `-m`, `--model` | Model id |
| `-t`, `--temperature` | Sampling temperature (clamped per provider rules) |
| `--max-tokens` | Output token cap |
| `--base-url` | Custom endpoint |

This subcommand was added in v1.5.0 and is used by external tools like the sysReporter Rust CLI.

#### `eq-chatbot image`

Generate a single image from a text prompt and save it to a file (added in v1.14.0). Supported providers: `openai` (`gpt-image-1`) and `openrouter` (e.g. `gemini-2.5-flash-image`).

```bash
# Prompt inline, default model, write to output.png
eq-chatbot image -p openai -k sk-... --prompt "A sunset over the ocean"

# OpenRouter, explicit output file
eq-chatbot image -p openrouter -k sk-or-... --prompt "A cat in space" -o cat.png

# Prompt from a file, resize the result (requires the [image] extra)
eq-chatbot image -p openai -k sk-... --prompt-file prompt.txt --fit 512x512:cover
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | `openai` or `openrouter` (**required**) |
| `-k`, `--api-key` | API key (or set `LLM_API_KEY` env) |
| `-m`, `--model` | Model id (provider default if omitted) |
| `--prompt` | Text prompt describing the image |
| `--prompt-file` | Read the prompt from a file instead of `--prompt` |
| `--size` | Dimensions, e.g. `1024x1024`, `1024x1536`, `auto` (default `1024x1024`) |
| `--fit` | Resize output: `WxH[:mode]`, mode = `cover`/`contain`/`stretch` (needs `[image]` extra) |
| `-o`, `--output` | Output file path (default `output.png`) |
| `-u`, `--base-url` | Custom endpoint |

#### `eq-chatbot listing-assets`

Batch-generate images from a recipe JSON file (schema `eq-listing-assets/v1`) — built for App-Store listing assets (icon, banner, eyecatchers). Provider/model come from the recipe's `defaults` block or are overridden by CLI flags. A recipe can mix assets that carry rendered **text** (a banner showing the module title) and pure **imagery** (an app icon):

```json
{
  "schema": "eq-listing-assets/v1",
  "module": "eq_chatbot",
  "defaults": {"provider": "openai", "model": "gpt-image-1"},
  "assets": [
    {"id": "banner", "out": "banner.png", "size": "1536x1024",
     "prompt": "Wide App-Store banner, deep-blue gradient, friendly robot mascot, bold headline 'eq_chatbot - AI Assistant for Odoo'"},
    {"id": "icon", "out": "icon.png", "size": "1024x1024",
     "prompt": "Minimal flat app icon, rounded square, speech bubble with a spark, blue and white, no text"}
  ]
}
```

```bash
# Preview what would be generated, no API calls
eq-chatbot listing-assets --recipe eq_chatbot_listing.json --dry-run

# Generate every asset in the recipe
eq-chatbot listing-assets --recipe eq_chatbot_listing.json -k sk-...

# Only the banner, written into the module's listing folder
eq-chatbot listing-assets --recipe eq_chatbot_listing.json --only banner --dest ./eq_chatbot/static/description -k sk-...
```

| Flag | Purpose |
|------|---------|
| `--recipe` | Path to the recipe JSON (`eq-listing-assets/v1` schema) (**required**) |
| `-p`, `--provider` | Override provider from recipe defaults (`openai`/`openrouter`) |
| `-m`, `--model` | Override model from recipe defaults |
| `-k`, `--api-key` | API key (or set `LLM_API_KEY` env) |
| `-u`, `--base-url` | Custom endpoint |
| `--dest` | Destination directory (default: recipe file directory) |
| `--only` | Comma-separated asset IDs to generate (filter) |
| `--dry-run` | List what would be generated without making API calls |

Each asset's `out` filename is written confined to `--dest` (an untrusted absolute/`../` name cannot escape).

#### `eq-chatbot serve`

Start the local HTTP/SSE sidecar. See [server-mode.md](server-mode.md) for the full reference.

```bash
echo "$TOKEN" | eq-chatbot serve --port 0 --auth-token-fd 0 --parent-pid $$
```

#### `eq-chatbot langdock-export`

Back up LangDock agents (system prompt + config) and knowledge-folder metadata to portable `.md`/`.json` files (added in v1.11.0). See [langdock-export.md](langdock-export.md#english) for the full reference.

```bash
eq-chatbot langdock-export -k ld-... --agent-id AGENT_ID -o ./langdock-backup
```

The API key may also be set via the `LANGDOCK_API_KEY` env var.

### Environment variables

The API key for `chat`, `test-provider`, `list-models`, `image`, and `listing-assets`
is resolved in this order (highest priority first):

1. `-k` / `--api-key` flag
2. `<PROVIDER>_API_KEY` — provider-specific variable (e.g. `OPENROUTER_API_KEY`)
3. `LLM_API_KEY` — generic fallback
4. the [config file](#configuration-file) (`[providers.<name>].api_key`)

This lets you store one key per provider on the host and never pass `-k` again:

```fish
# ~/.config/fish/config.fish
set -gx OPENAI_API_KEY     sk-...
set -gx OPENROUTER_API_KEY sk-or-...
set -gx MELIOUS_API_KEY    sk-mel-...
```

Provider-specific variables: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`,
`OPENROUTER_API_KEY`, `MAMMOUTH_API_KEY`, `AZURE_API_KEY`, `LITELLM_API_KEY`,
`IONOS_API_KEY`, `MELIOUS_API_KEY`. A key set for one provider never satisfies another.

| Variable | Purpose | Used by |
|----------|---------|---------|
| `<PROVIDER>_API_KEY` | Per-provider key (e.g. `OPENAI_API_KEY`); checked before `LLM_API_KEY` | `chat`, `test-provider`, `list-models`, `image`, `listing-assets` |
| `LLM_API_KEY` | Generic fallback API key when no flag or provider-specific var is set | `chat`, `test-provider`, `list-models`, `image`, `listing-assets` |
| `LANGDOCK_API_KEY` | Fallback API key when `-k`/`--api-key` is not given | `langdock-export` |
| `EQ_CHATBOT_AUTH_TOKEN` | Fallback bearer token when no `--auth-token*` flag is given | `serve` |
| `EQ_CHATBOT_CONFIG` | Override the config file path (default: `~/.config/eq-chatbot/config.toml`) | all |

### Configuration file

Instead of (or in addition to) environment variables you can store keys, base URLs,
default models, a default provider and chat defaults in a TOML file. Default path:
`~/.config/eq-chatbot/config.toml` (honours `$XDG_CONFIG_HOME`; override with
`$EQ_CHATBOT_CONFIG`).

```bash
eq-chatbot config init     # write a commented template (mode 0600)
eq-chatbot config show     # show path, permissions and a key-masked view
eq-chatbot config path     # print the resolved config path
```

Example `config.toml`:

```toml
default_provider = "melious"     # used when --provider is omitted

[defaults]                       # used by `chat` when the flags are omitted
temperature = 0.7
max_tokens  = 4096

[providers.openrouter]
api_key  = "sk-or-..."
model    = "openai/gpt-4o"       # optional
# base_url = "https://openrouter.ai/api/v1"   # optional
```

Resolution (highest priority first):

| Value | Order |
|-------|-------|
| api_key | `--api-key` > `<PROVIDER>_API_KEY` env > `LLM_API_KEY` env > config |
| base_url | `--base-url` > config > provider default |
| model | `--model` > config > provider default |
| provider | `--provider` > config `default_provider` |
| temperature / max_tokens | flag > config `[defaults]` > built-in (0.7 / 4096) |

The file holds keys in **plain text** — keep it private (`chmod 600`). eq-chatbot warns
if the file is readable by others.

### See also

- [Providers](providers.md#english) — provider names accepted by `-p`
- [Server mode](server-mode.md#english) — full reference for `eq-chatbot serve`

---

[← Back to README](../README.md#english) · [docs index →](README.md#english)

---

## Deutsch

### Überblick

`eq-chatbot-core` liefert ein Click-basiertes CLI namens `eq-chatbot`. Fünf Subcommands decken Provider-Tests, Modell-Discovery, programmatische Chat-I/O, den HTTP/SSE-Sidecar und Paket-Introspektion ab.

```bash
eq-chatbot --help
```

### Subcommands

#### `eq-chatbot info`

Gibt Paket-Version, installierte Extras und Python-Version aus. Nützlich für Bug-Reports.

```bash
eq-chatbot info
```

#### `eq-chatbot test-provider`

Smoke-Test einer Provider-Verbindung über eine einzelne Chat-Completion. Exit-Code != 0 bei Auth-/Transport-Fehlern.

```bash
eq-chatbot test-provider -p openai -k $OPENAI_API_KEY
eq-chatbot test-provider -p anthropic -k sk-ant-... -m claude-3-5-sonnet-20241022
eq-chatbot test-provider -p local --base-url http://localhost:1234/v1
```

| Flag | Zweck |
|------|-------|
| `-p`, `--provider` | Provider-Name (`openai`, `anthropic`, `azure`, `vertex`, `langdock`, `openrouter`, `mammouth`, `local`, `lm_studio`, `ollama`) |
| `-k`, `--api-key` | API-Key (nur Cloud-Provider) |
| `-m`, `--model` | Modell-ID (Default: `default_model` des Providers) |
| `--message` | Eigener Test-Prompt (Default: kurzer Gruß) |
| `--base-url` | Eigener Endpoint (Azure, lokale OpenAI-kompatible) |

#### `eq-chatbot list-models`

Listet verfügbare Modelle eines Providers. Default human-readable; `--json` für maschinelle Verarbeitung.

```bash
eq-chatbot list-models -p openai -k YOUR_KEY
eq-chatbot list-models -p langdock -k YOUR_KEY --vision-only
eq-chatbot list-models -p anthropic -k YOUR_KEY --json
```

| Flag | Zweck |
|------|-------|
| `-p`, `--provider` | Provider-Name |
| `-k`, `--api-key` | API-Key |
| `--base-url` | Eigener Endpoint |
| `--json` | Ausgabe als JSON-Array von Modell-Objekten |
| `--vision-only` | Auf vision-fähige Modelle filtern |

#### `eq-chatbot chat`

Single-Turn-Chat mit JSON-I/O — für Integration mit Tools, die kein Python sprechen (Rust, Go, Bash). Liest JSON-Envelope von stdin, schreibt Ergebnis nach stdout, Fehler als JSON nach stderr mit non-zero Exit.

```bash
echo '{"messages":[{"role":"user","content":"Hallo"}]}' | \
    eq-chatbot chat -p openai -k YOUR_KEY

# Ausgabe: {"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}
```

**Input-Schema** (stdin):

```json
{
  "messages": [
    {"role": "system", "content": "Du bist hilfreich."},
    {"role": "user", "content": "Frage hier"}
  ]
}
```

Stdin ist auf **1 MB** begrenzt um Runaway-Memory zu vermeiden.

**Output-Schema** (stdout):

```json
{
  "content": "Modell-Antwort",
  "model": "gpt-4o-mini",
  "input_tokens": 42,
  "output_tokens": 17
}
```

| Flag | Zweck |
|------|-------|
| `-p`, `--provider` | Provider-Name |
| `-k`, `--api-key` | API-Key (oder `LLM_API_KEY`-Env) |
| `-m`, `--model` | Modell-ID |
| `-t`, `--temperature` | Sampling-Temperatur (per Provider-Regel geclampt) |
| `--max-tokens` | Output-Token-Cap |
| `--base-url` | Eigener Endpoint |

Dieser Subcommand wurde in v1.5.0 hinzugefügt und wird z.B. vom sysReporter-Rust-CLI verwendet.

#### `eq-chatbot image`

Generiert ein einzelnes Bild aus einem Text-Prompt und speichert es in eine Datei (hinzugefügt in v1.14.0). Unterstützte Provider: `openai` (`gpt-image-1`) und `openrouter` (z.B. `gemini-2.5-flash-image`).

```bash
# Prompt inline, Default-Modell, Ausgabe nach output.png
eq-chatbot image -p openai -k sk-... --prompt "Ein Sonnenuntergang über dem Meer"

# OpenRouter, explizite Ausgabedatei
eq-chatbot image -p openrouter -k sk-or-... --prompt "Eine Katze im Weltall" -o cat.png

# Prompt aus Datei, Ergebnis skalieren (benötigt das [image]-Extra)
eq-chatbot image -p openai -k sk-... --prompt-file prompt.txt --fit 512x512:cover
```

| Flag | Zweck |
|------|-------|
| `-p`, `--provider` | `openai` oder `openrouter` (**erforderlich**) |
| `-k`, `--api-key` | API-Key (oder `LLM_API_KEY`-Env) |
| `-m`, `--model` | Modell-ID (Provider-Default wenn weggelassen) |
| `--prompt` | Text-Prompt zur Bildbeschreibung |
| `--prompt-file` | Prompt aus Datei lesen statt `--prompt` |
| `--size` | Abmessungen, z.B. `1024x1024`, `1024x1536`, `auto` (Default `1024x1024`) |
| `--fit` | Ausgabe skalieren: `WxH[:mode]`, mode = `cover`/`contain`/`stretch` (benötigt `[image]`-Extra) |
| `-o`, `--output` | Ausgabe-Dateipfad (Default `output.png`) |
| `-u`, `--base-url` | Eigener Endpoint |

#### `eq-chatbot listing-assets`

Generiert mehrere Bilder im Batch aus einer Recipe-JSON-Datei (Schema `eq-listing-assets/v1`) — gebaut für App-Store-Listing-Assets (Icon, Banner, Eyecatcher). Provider/Modell kommen aus dem `defaults`-Block der Recipe oder werden per CLI-Flags überschrieben. Eine Recipe kann Assets mit gerendertem **Text** (ein Banner mit dem Modultitel) und reine **Bild**-Assets (ein App-Icon) kombinieren:

```json
{
  "schema": "eq-listing-assets/v1",
  "module": "eq_chatbot",
  "defaults": {"provider": "openai", "model": "gpt-image-1"},
  "assets": [
    {"id": "banner", "out": "banner.png", "size": "1536x1024",
     "prompt": "Wide App-Store banner, deep-blue gradient, friendly robot mascot, bold headline 'eq_chatbot - AI Assistant for Odoo'"},
    {"id": "icon", "out": "icon.png", "size": "1024x1024",
     "prompt": "Minimal flat app icon, rounded square, speech bubble with a spark, blue and white, no text"}
  ]
}
```

```bash
# Vorschau ohne API-Calls
eq-chatbot listing-assets --recipe eq_chatbot_listing.json --dry-run

# Alle Assets der Recipe generieren
eq-chatbot listing-assets --recipe eq_chatbot_listing.json -k sk-...

# Nur den Banner, direkt in den Listing-Ordner des Moduls
eq-chatbot listing-assets --recipe eq_chatbot_listing.json --only banner --dest ./eq_chatbot/static/description -k sk-...
```

| Flag | Zweck |
|------|-------|
| `--recipe` | Pfad zur Recipe-JSON (`eq-listing-assets/v1`-Schema) (**erforderlich**) |
| `-p`, `--provider` | Provider aus Recipe-Defaults überschreiben (`openai`/`openrouter`) |
| `-m`, `--model` | Modell aus Recipe-Defaults überschreiben |
| `-k`, `--api-key` | API-Key (oder `LLM_API_KEY`-Env) |
| `-u`, `--base-url` | Eigener Endpoint |
| `--dest` | Zielverzeichnis für die generierten Bilder (Default: Recipe-Verzeichnis) |
| `--only` | Komma-getrennte Asset-IDs (Filter) |
| `--dry-run` | Auflisten was generiert würde, ohne API-Calls |

Der `out`-Dateiname jedes Assets wird auf `--dest` beschränkt geschrieben (ein nicht vertrauenswürdiger absoluter/`../`-Name kann nicht ausbrechen).

#### `eq-chatbot serve`

Startet den lokalen HTTP/SSE-Sidecar. Vollständige Referenz: [server-mode.md](server-mode.md).

```bash
echo "$TOKEN" | eq-chatbot serve --port 0 --auth-token-fd 0 --parent-pid $$
```

#### `eq-chatbot langdock-export`

Sichert LangDock-Agenten (System-Prompt + Konfig) und Knowledge-Folder-Metadaten als portable `.md`/`.json`-Dateien (hinzugefügt in v1.11.0). Vollständige Referenz: [langdock-export.md](langdock-export.md#deutsch).

```bash
eq-chatbot langdock-export -k ld-... --agent-id AGENT_ID -o ./langdock-backup
```

Der API-Key kann auch über die `LANGDOCK_API_KEY`-Env gesetzt werden.

### Umgebungsvariablen

Der API-Key für `chat`, `test-provider`, `list-models`, `image` und `listing-assets`
wird in dieser Reihenfolge aufgelöst (höchste Priorität zuerst):

1. `-k` / `--api-key`-Flag
2. `<PROVIDER>_API_KEY` — provider-spezifische Variable (z.B. `OPENROUTER_API_KEY`)
3. `LLM_API_KEY` — generischer Fallback
4. die [Konfigurationsdatei](#konfigurationsdatei) (`[providers.<name>].api_key`)

So lässt sich pro Provider ein Key auf dem Host hinterlegen, ohne je wieder `-k` zu übergeben:

```fish
# ~/.config/fish/config.fish
set -gx OPENAI_API_KEY     sk-...
set -gx OPENROUTER_API_KEY sk-or-...
set -gx MELIOUS_API_KEY    sk-mel-...
```

Provider-spezifische Variablen: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGDOCK_API_KEY`,
`OPENROUTER_API_KEY`, `MAMMOUTH_API_KEY`, `AZURE_API_KEY`, `LITELLM_API_KEY`,
`IONOS_API_KEY`, `MELIOUS_API_KEY`. Ein Key für einen Provider erfüllt nie einen anderen.

| Variable | Zweck | Genutzt von |
|----------|-------|-------------|
| `<PROVIDER>_API_KEY` | Key pro Provider (z.B. `OPENAI_API_KEY`); vor `LLM_API_KEY` geprüft | `chat`, `test-provider`, `list-models`, `image`, `listing-assets` |
| `LLM_API_KEY` | Generischer Fallback-API-Key wenn weder Flag noch provider-spezifische Variable gesetzt | `chat`, `test-provider`, `list-models`, `image`, `listing-assets` |
| `LANGDOCK_API_KEY` | Fallback-API-Key wenn `-k`/`--api-key` fehlt | `langdock-export` |
| `EQ_CHATBOT_AUTH_TOKEN` | Fallback-Bearer-Token wenn kein `--auth-token*`-Flag | `serve` |
| `EQ_CHATBOT_CONFIG` | Überschreibt den Config-Pfad (Default: `~/.config/eq-chatbot/config.toml`) | alle |

### Konfigurationsdatei

Statt (oder zusätzlich zu) Umgebungsvariablen lassen sich Keys, base_urls,
Default-Modelle, ein Default-Provider und Chat-Defaults in einer TOML-Datei ablegen.
Default-Pfad: `~/.config/eq-chatbot/config.toml` (beachtet `$XDG_CONFIG_HOME`;
übersteuerbar via `$EQ_CHATBOT_CONFIG`).

```bash
eq-chatbot config init     # kommentiertes Template schreiben (Rechte 0600)
eq-chatbot config show     # Pfad, Rechte und key-maskierte Ansicht
eq-chatbot config path     # aufgelösten Config-Pfad ausgeben
```

Beispiel `config.toml`:

```toml
default_provider = "melious"     # greift wenn --provider fehlt

[defaults]                       # genutzt von `chat` wenn die Flags fehlen
temperature = 0.7
max_tokens  = 4096

[providers.openrouter]
api_key  = "sk-or-..."
model    = "openai/gpt-4o"       # optional
# base_url = "https://openrouter.ai/api/v1"   # optional
```

Auflösung (höchste Priorität zuerst):

| Wert | Reihenfolge |
|------|-------------|
| api_key | `--api-key` > `<PROVIDER>_API_KEY` env > `LLM_API_KEY` env > Config |
| base_url | `--base-url` > Config > Provider-Default |
| model | `--model` > Config > Provider-Default |
| provider | `--provider` > Config `default_provider` |
| temperature / max_tokens | Flag > Config `[defaults]` > eingebaut (0.7 / 4096) |

Die Datei enthält Keys im **Klartext** — privat halten (`chmod 600`). eq-chatbot warnt,
wenn die Datei für andere lesbar ist.

### Siehe auch

- [Provider](providers.md#deutsch) — Provider-Namen für `-p`
- [Server-Mode](server-mode.md#deutsch) — vollständige Referenz für `eq-chatbot serve`

---

[← Zurück zum README](../README.md#deutsch) · [Doku-Index →](README.md#deutsch)
