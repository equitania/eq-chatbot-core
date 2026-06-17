"""
eq-chatbot CLI - Command line interface for eq_chatbot_core.

Usage:
    eq-chatbot test-provider -p openai -k YOUR_API_KEY
    eq-chatbot list-models -p anthropic -k YOUR_API_KEY
    eq-chatbot serve --port 0 --auth-token-fd 0 --parent-pid 1234
    eq-chatbot info
"""

import json
import os
import sys

import click

from eq_chatbot_core.providers import CLOUD_PROVIDERS, LOCAL_PROVIDERS
from eq_chatbot_core.version import __version__

ALL_PROVIDERS = CLOUD_PROVIDERS + LOCAL_PROVIDERS


@click.group()
@click.version_option(version=__version__, prog_name="eq-chatbot")
def main() -> None:
    """eq-chatbot - LLM Provider Testing & Management CLI.

    A command-line tool for testing LLM provider connections,
    listing available models, and managing chatbot configurations.
    """
    pass


@main.command("test-provider")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(ALL_PROVIDERS, case_sensitive=False),
    required=True,
    help="LLM provider to test (cloud: openai, anthropic, langdock, openrouter, mammouth, azure, vertex, litellm, ionos; local: local, lm_studio, ollama)",
)
@click.option(
    "--api-key",
    "-k",
    envvar="LLM_API_KEY",
    help="API key (or set LLM_API_KEY environment variable). Not required for local providers.",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model to use (uses provider default if not specified)",
)
@click.option(
    "--message",
    "-msg",
    default="Hello! Please respond with a brief greeting.",
    help="Test message to send",
)
@click.option(
    "--base-url",
    "-u",
    default=None,
    help="Custom base URL for the provider. For local providers: LM Studio=localhost:1234, Ollama=localhost:11434",
)
def test_provider(provider: str, api_key: str | None, model: str | None, message: str, base_url: str | None) -> None:
    """Test connection to an LLM provider.

    Sends a test message and displays the response along with token usage.

    Examples:

        # Cloud providers
        eq-chatbot test-provider -p openai -k sk-...

        eq-chatbot test-provider -p anthropic -k sk-ant-... -m claude-3-5-sonnet-20241022

        LLM_API_KEY=sk-... eq-chatbot test-provider -p openai

        # Local providers (no API key needed)
        eq-chatbot test-provider -p lm_studio

        eq-chatbot test-provider -p ollama -m llama3.2:latest

        eq-chatbot test-provider -p local -u http://localhost:1234/v1
    """
    # Check API key requirement (not needed for local providers or Vertex)
    is_local = provider.lower() in LOCAL_PROVIDERS
    is_vertex = provider.lower() == "vertex"
    if not api_key and not is_local and not is_vertex:
        click.echo(
            click.style("Error: ", fg="red")
            + "API key required for cloud providers. Use --api-key or set LLM_API_KEY environment variable.",
            err=True,
        )
        sys.exit(1)

    from eq_chatbot_core.providers import ProviderError, get_provider

    try:
        click.echo(f"Testing {click.style(provider, fg='cyan', bold=True)}...")

        provider_instance = get_provider(provider, api_key=api_key, base_url=base_url)

        if model:
            response = provider_instance.chat_completion(
                messages=[{"role": "user", "content": message}],
                model=model,
            )
        else:
            response = provider_instance.chat_completion(
                messages=[{"role": "user", "content": message}],
            )

        click.echo(click.style("✓ Success!", fg="green", bold=True))
        click.echo()
        click.echo(click.style("Response:", fg="blue"))
        click.echo(f"  {response.content}")
        click.echo()

        if response.input_tokens or response.output_tokens:
            click.echo(click.style("Token Usage:", fg="blue"))
            click.echo(f"  Input:  {response.input_tokens}")
            click.echo(f"  Output: {response.output_tokens}")
            click.echo(f"  Total:  {response.total_tokens}")

        if response.model:
            click.echo()
            click.echo(click.style("Model:", fg="blue") + f" {response.model}")

    except ProviderError as e:
        click.echo(click.style(f"✗ Provider Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command("list-models")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(ALL_PROVIDERS, case_sensitive=False),
    required=True,
    help="LLM provider to query (cloud: openai, anthropic, langdock, openrouter, mammouth, azure, vertex, litellm, ionos; local: local, lm_studio, ollama)",
)
@click.option(
    "--api-key",
    "-k",
    envvar="LLM_API_KEY",
    help="API key (or set LLM_API_KEY environment variable). Not required for local providers.",
)
@click.option(
    "--base-url",
    "-u",
    default=None,
    help="Custom base URL for the provider",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--vision-only",
    is_flag=True,
    help="Show only models with vision support",
)
def list_models(provider: str, api_key: str | None, base_url: str | None, as_json: bool, vision_only: bool) -> None:
    """List available models from a provider.

    Queries the provider's API and displays all available models
    with their capabilities.

    Examples:

        # Cloud providers
        eq-chatbot list-models -p openai -k sk-...

        eq-chatbot list-models -p langdock -k YOUR_KEY --json

        eq-chatbot list-models -p anthropic -k sk-ant-... --vision-only

        # Local providers (no API key needed)
        eq-chatbot list-models -p lm_studio

        eq-chatbot list-models -p ollama

        eq-chatbot list-models -p local -u http://localhost:1234/v1
    """
    # Check API key requirement (not needed for local providers or Vertex)
    is_local = provider.lower() in LOCAL_PROVIDERS
    is_vertex = provider.lower() == "vertex"
    if not api_key and not is_local and not is_vertex:
        click.echo(
            click.style("Error: ", fg="red")
            + "API key required for cloud providers. Use --api-key or set LLM_API_KEY environment variable.",
            err=True,
        )
        sys.exit(1)

    from typing import Any

    from eq_chatbot_core.providers import ModelInfo, ProviderError, get_provider

    def get_model_attr(model: ModelInfo | dict[str, Any], attr: str, default: Any = None) -> Any:
        """Get attribute from ModelInfo or dict."""
        if isinstance(model, ModelInfo):
            return getattr(model, attr, default)
        return model.get(attr, default)

    try:
        provider_instance = get_provider(provider, api_key=api_key, base_url=base_url)
        models = provider_instance.list_models()

        if vision_only:
            models = [m for m in models if get_model_attr(m, "supports_vision", False)]

        if as_json:
            output = [
                {
                    "id": get_model_attr(m, "id"),
                    "name": get_model_attr(m, "name"),
                    "provider": get_model_attr(m, "provider"),
                    "supports_vision": get_model_attr(m, "supports_vision", False),
                    "supports_tools": get_model_attr(m, "supports_tools", False),
                    "supports_streaming": get_model_attr(m, "supports_streaming", True),
                    "context_length": get_model_attr(m, "context_length"),
                }
                for m in models
            ]
            click.echo(json.dumps(output, indent=2))
        else:
            click.echo(f"Available models for {click.style(provider, fg='cyan', bold=True)}:")
            click.echo()

            for m in models:
                model_id = get_model_attr(m, "id")
                has_vision = get_model_attr(m, "supports_vision", False)
                vision_badge = click.style(" [vision]", fg="green") if has_vision else ""
                click.echo(f"  • {model_id}{vision_badge}")

            click.echo()
            click.echo(f"Total: {len(models)} models")

    except ProviderError as e:
        click.echo(click.style(f"✗ Provider Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red"), err=True)
        sys.exit(1)


# Maximum stdin payload size (1 MB)
MAX_INPUT_SIZE = 1_048_576

VALID_ROLES = {"user", "assistant", "system", "tool"}


def _validate_messages(messages: list) -> list[dict]:
    """Validate message structure for chat command."""
    validated = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError(f"Message {i} must be a JSON object, got {type(msg).__name__}")
        if "role" not in msg:
            raise ValueError(f"Message {i} missing required 'role' field")
        if msg["role"] not in VALID_ROLES:
            raise ValueError(
                f"Message {i} has invalid role '{msg['role']}'. Must be one of: {', '.join(sorted(VALID_ROLES))}"
            )
        if "content" not in msg:
            raise ValueError(f"Message {i} missing required 'content' field")
        validated.append(msg)
    return validated


@main.command("chat")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(ALL_PROVIDERS, case_sensitive=False),
    required=True,
    help="LLM provider to use",
)
@click.option(
    "--api-key",
    "-k",
    envvar="LLM_API_KEY",
    help="API key (or set LLM_API_KEY environment variable)",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model to use (uses provider default if not specified)",
)
@click.option(
    "--temperature",
    "-t",
    default=0.7,
    type=float,
    help="Temperature for response generation (default: 0.7)",
)
@click.option(
    "--max-tokens",
    default=4096,
    type=int,
    help="Maximum tokens in response (default: 4096)",
)
@click.option(
    "--base-url",
    "-u",
    default=None,
    help="Custom base URL for the provider",
)
def chat(
    provider: str,
    api_key: str | None,
    model: str | None,
    temperature: float,
    max_tokens: int,
    base_url: str | None,
) -> None:
    """Single-turn chat with JSON I/O for programmatic use.

    Reads JSON from stdin with a 'messages' array and writes a JSON response
    to stdout. Designed for integration with other tools (e.g., sysReporter).

    Input format (stdin):

        {"messages": [{"role": "user", "content": "Hello"}]}

    Output format (stdout):

        {"content": "...", "model": "...", "input_tokens": N, "output_tokens": N}

    Examples:

        echo '{"messages":[{"role":"user","content":"Hello"}]}' | eq-chatbot chat -p openai -k sk-...

        cat request.json | eq-chatbot chat -p anthropic -m claude-3-5-sonnet-20241022

        LLM_API_KEY=sk-... eq-chatbot chat -p openai -m gpt-4o-mini
    """
    # Check API key requirement
    is_local = provider.lower() in LOCAL_PROVIDERS
    is_vertex = provider.lower() == "vertex"
    if not api_key and not is_local and not is_vertex:
        error_response = {"error": "API key required. Use --api-key or set LLM_API_KEY environment variable."}
        click.echo(json.dumps(error_response), err=True)
        sys.exit(1)

    from eq_chatbot_core.providers import ProviderError, get_provider

    try:
        # Read JSON payload from stdin (size-limited)
        raw_input = sys.stdin.read(MAX_INPUT_SIZE + 1)
        if len(raw_input) > MAX_INPUT_SIZE:
            error_response = {"error": f"Input exceeds maximum size of {MAX_INPUT_SIZE} bytes."}
            click.echo(json.dumps(error_response), err=True)
            sys.exit(1)
        if not raw_input.strip():
            error_response = {"error": "No input received on stdin. Expected JSON with 'messages' array."}
            click.echo(json.dumps(error_response), err=True)
            sys.exit(1)

        payload = json.loads(raw_input)
        messages = payload.get("messages", [])

        if not messages:
            error_response = {"error": "No messages found in input. Expected 'messages' array."}
            click.echo(json.dumps(error_response), err=True)
            sys.exit(1)

        # Validate message structure
        messages = _validate_messages(messages)

        # Create provider and send request
        provider_instance = get_provider(provider, api_key=api_key, base_url=base_url)

        kwargs: dict = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if model:
            kwargs["model"] = model

        response = provider_instance.chat_completion(**kwargs)

        # Output JSON response to stdout
        output = {
            "content": response.content,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
        click.echo(json.dumps(output))

    except json.JSONDecodeError as e:
        error_response = {"error": f"Invalid JSON input: {e}"}
        click.echo(json.dumps(error_response), err=True)
        sys.exit(1)
    except ValueError as e:
        error_response = {"error": f"Invalid message format: {e}"}
        click.echo(json.dumps(error_response), err=True)
        sys.exit(1)
    except ProviderError as e:
        error_response = {"error": f"Provider error: {e}"}
        click.echo(json.dumps(error_response), err=True)
        sys.exit(1)
    except Exception as e:
        error_response = {"error": f"Unexpected error: {e}"}
        click.echo(json.dumps(error_response), err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# `serve` — localhost HTTP gateway for cross-language integrations
# ─────────────────────────────────────────────────────────────────────────────
# Read at most this many bytes from --auth-token-fd. Tokens are typically
# 32–64 bytes (secrets.token_urlsafe(32) → 43 chars).
_AUTH_TOKEN_MAX_BYTES = 256
_AUTH_TOKEN_MIN_LEN = 16


def _read_auth_token(
    auth_token: str | None,
    auth_token_fd: int | None,
) -> str:
    """Resolve auth token from --auth-token-fd / --auth-token / env var.

    Precedence (most secure first):
      1. --auth-token-fd N → read up to 256 bytes from FD N, then close it.
         Recommended: parent process pipes the token in via stdin (fd 0) so
         it never appears in argv (visible via `ps`) or env (visible via
         /proc/<pid>/environ).
      2. --auth-token <token> → token in argv. INSECURE; visible via `ps`.
         Only for local debugging.
      3. EQ_CHATBOT_AUTH_TOKEN env var → fallback for ad-hoc use.

    Returns the stripped token string. Raises click.ClickException on
    missing/short/unreadable token.
    """
    if auth_token_fd is not None:
        try:
            token_bytes = os.read(auth_token_fd, _AUTH_TOKEN_MAX_BYTES)
        except OSError as exc:
            raise click.ClickException(f"Failed to read auth token from fd {auth_token_fd}: {exc}") from exc
        finally:
            try:
                os.close(auth_token_fd)
            except OSError:
                pass  # FD may already be closed
        token = token_bytes.decode("utf-8", errors="strict").strip()
    elif auth_token:
        token = auth_token.strip()
    else:
        token = os.environ.get("EQ_CHATBOT_AUTH_TOKEN", "").strip()

    if not token:
        raise click.ClickException(
            "Missing auth token. Provide via --auth-token-fd <fd> (recommended), "
            "--auth-token <token>, or EQ_CHATBOT_AUTH_TOKEN env var."
        )
    if len(token) < _AUTH_TOKEN_MIN_LEN:
        raise click.ClickException(
            f"Auth token too short (min {_AUTH_TOKEN_MIN_LEN} chars). Generate via secrets.token_urlsafe(32)."
        )
    return token


@main.command("serve")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Bind host. Default 127.0.0.1 keeps the server localhost-only.",
)
@click.option(
    "--port",
    default=0,
    show_default=True,
    type=int,
    help="Bind port. 0 picks an ephemeral port (recommended); the bound port "
    "is printed to stdout as 'LISTENING ON host=H port=P' for the parent process.",
)
@click.option(
    "--auth-token",
    default=None,
    help="Bearer token (INSECURE — visible in argv). Prefer --auth-token-fd.",
)
@click.option(
    "--auth-token-fd",
    default=None,
    type=int,
    help="Read bearer token from this file descriptor (recommended). "
    "Parent pipes the token in via stdin: `eq-chatbot serve --auth-token-fd 0`.",
)
@click.option(
    "--parent-pid",
    default=None,
    type=int,
    help="Parent process PID. Sidecar polls this every 5s and exits when "
    "the parent disappears (prevents zombie sidecars on parent crash).",
)
@click.option(
    "--log-level",
    default="warning",
    show_default=True,
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
)
def serve(
    host: str,
    port: int,
    auth_token: str | None,
    auth_token_fd: int | None,
    parent_pid: int | None,
    log_level: str,
) -> None:
    """Run a localhost HTTP/SSE server exposing the LLM provider gateway.

    Designed to be spawned by external apps as a sidecar (e.g. fr-designer
    Avalonia desktop app spawning a frozen sidecar binary). All endpoints
    except /health require Authorization: Bearer <token>.

    Example:

        # Generate token in parent, pipe it via stdin, scrape stdout for port:
        token = secrets.token_urlsafe(32)
        proc = Popen(['eq-chatbot', 'serve', '--auth-token-fd', '0',
                      '--parent-pid', str(os.getpid())],
                     stdin=PIPE, stdout=PIPE, text=True)
        proc.stdin.write(token); proc.stdin.close()
        line = proc.stdout.readline()  # "LISTENING ON host=127.0.0.1 port=54123"
    """
    try:
        from eq_chatbot_core.server import create_app, run_server
    except ImportError as exc:
        raise click.ClickException(
            "Server mode requires the [server] optional extras. "
            "Install with: pip install 'eq-chatbot-core[server]'\n  "
            f"(import error: {exc})"
        ) from exc

    token = _read_auth_token(auth_token, auth_token_fd)
    app = create_app(auth_token=token)
    run_server(
        app,
        host=host,
        port=port,
        parent_pid=parent_pid,
        log_level=log_level.lower(),
    )


@main.command("langdock-export")
@click.option(
    "--api-key",
    "-k",
    envvar="LANGDOCK_API_KEY",
    required=True,
    help="LangDock API key (or set LANGDOCK_API_KEY environment variable).",
)
@click.option(
    "--output-dir",
    "-o",
    default="./langdock-backup",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Directory to write the backup into.",
)
@click.option(
    "--agent-id",
    "agent_ids",
    multiple=True,
    help="Agent id or UI URL to back up. Repeatable. If omitted, --discover is used.",
)
@click.option(
    "--discover/--no-discover",
    default=None,
    help="Discover all agent ids via the usage export API "
    "(needs an admin key with the USAGE_EXPORT_API scope). "
    "Defaults to on when no --agent-id is given.",
)
@click.option(
    "--knowledge-folder-id",
    "knowledge_folder_ids",
    multiple=True,
    help="Knowledge folder id to back up file metadata for. Repeatable. "
    "Folder ids referenced by exported agents are added automatically.",
)
@click.option(
    "--format",
    "fmt",
    default="both",
    show_default=True,
    type=click.Choice(["md", "json", "both"], case_sensitive=False),
    help="Output format for agent definitions.",
)
def langdock_export(
    api_key: str,
    output_dir: str,
    agent_ids: tuple[str, ...],
    discover: bool | None,
    knowledge_folder_ids: tuple[str, ...],
    fmt: str,
) -> None:
    """Back up LangDock agents and knowledge metadata to local files.

    Agent definitions (including their system prompt) are saved as portable
    Markdown and raw JSON so they stay usable when LangDock is unavailable.

    Note: knowledge-folder *content* cannot be downloaded via the API — only
    file metadata is backed up.

    Examples:

        # Back up specific agents (no admin key required):
        eq-chatbot langdock-export --agent-id https://app.langdock.com/assistant/<uuid>

        # Discover and back up all agents (needs USAGE_EXPORT_API admin key):
        LANGDOCK_API_KEY=... eq-chatbot langdock-export --discover
    """
    from eq_chatbot_core.providers.base import ProviderError
    from eq_chatbot_core.providers.langdock_provider import (
        LangDockExportManager,
        LangDockKnowledgeManager,
    )
    from eq_chatbot_core.services.langdock_export import LangDockBackupExporter

    # Default: discover when the user gave no explicit agent ids.
    if discover is None:
        discover = len(agent_ids) == 0

    if not agent_ids and not discover and not knowledge_folder_ids:
        raise click.ClickException(
            "Nothing to do. Provide --agent-id, enable --discover, or pass --knowledge-folder-id."
        )

    export_manager = LangDockExportManager(api_key=api_key)
    knowledge_manager = LangDockKnowledgeManager(api_key=api_key)
    exporter = LangDockBackupExporter(export_manager, knowledge_manager)

    resolved_ids: list[str] = list(agent_ids)
    if discover:
        click.echo("Discovering agents via usage export API ...")
        try:
            discovered = exporter.discover_agents()
            resolved_ids.extend(d["id"] for d in discovered)
            click.echo(f"  Discovered {len(discovered)} agent(s).")
        except ProviderError as exc:
            if getattr(exc, "status_code", None) in (401, 403):
                click.echo(
                    click.style(
                        "  Discovery failed (key lacks USAGE_EXPORT_API scope). "
                        "Pass agent ids manually with --agent-id instead.",
                        fg="yellow",
                    )
                )
            else:
                click.echo(click.style(f"  Discovery failed: {exc}", fg="yellow"))

    # Deduplicate while preserving order.
    unique_ids = list(dict.fromkeys(resolved_ids))

    summary: dict[str, object] = {}
    if unique_ids:
        click.echo(f"Backing up {len(unique_ids)} agent(s) ...")
        agent_summary = exporter.backup_agents(unique_ids, output_dir, fmt=fmt.lower())
        summary["agents"] = agent_summary
        click.echo(f"  Agents: {agent_summary['agents_ok']} ok, {agent_summary['agents_failed']} failed.")
        for err in agent_summary["errors"]:
            click.echo(click.style(f"    ! {err['agent_id']}: {err['error']}", fg="yellow"))

    # Knowledge folders: explicit ids + ids referenced by exported agents.
    agents_summary = summary.get("agents")
    referenced = agents_summary.get("knowledge_folder_ids", []) if isinstance(agents_summary, dict) else []
    folder_ids: list[str] = list(knowledge_folder_ids) + list(referenced)
    unique_folders = list(dict.fromkeys(folder_ids))

    if unique_folders:
        click.echo(f"Backing up metadata for {len(unique_folders)} knowledge folder(s) ...")
        knowledge_summary = exporter.backup_knowledge_metadata(unique_folders, output_dir)
        summary["knowledge"] = knowledge_summary
        click.echo(
            f"  Knowledge: {knowledge_summary['folders_ok']} ok, "
            f"{knowledge_summary['folders_failed']} failed (metadata only)."
        )
        for err in knowledge_summary["errors"]:
            click.echo(click.style(f"    ! {err['folder_id']}: {err['error']}", fg="yellow"))

    manifest_path = exporter.write_manifest(output_dir, summary)
    click.echo(click.style(f"Backup written to {output_dir}", fg="green"))
    click.echo(f"Manifest: {manifest_path}")


@main.command("info")
def info() -> None:
    """Show package information.

    Displays version, supported providers, and available features.
    """
    click.echo(click.style("eq-chatbot-core", fg="cyan", bold=True) + f" v{__version__}")
    click.echo()
    click.echo("Core library for LLM chatbot integration with multi-provider support.")
    click.echo()

    click.echo(click.style("Supported Providers:", fg="blue"))
    click.echo("  Cloud:")
    click.echo("    • openai     - GPT-4, GPT-4o, GPT-4.1, o1, o3, o4 series")
    click.echo("    • anthropic  - Claude 3, Claude 3.5, Claude 4")
    click.echo("    • langdock   - Multi-provider gateway (EU/US regions)")
    click.echo("    • openrouter - 400+ models via unified gateway")
    click.echo("    • mammouth   - 30+ AI models via unified API")
    click.echo("    • azure      - Azure AI Foundry (GPT, Claude, Mistral, Llama, DeepSeek)")
    click.echo("    • vertex     - Google Vertex AI (Gemini 2.5 Flash/Pro)")
    click.echo("    • litellm    - LiteLLM / any OpenAI-compatible gateway (base_url required)")
    click.echo("    • ionos      - IONOS AI Model Hub (EU-hosted, OpenAI-compatible)")
    click.echo("  Local:")
    click.echo("    • lm_studio - LM Studio (localhost:1234)")
    click.echo("    • ollama    - Ollama (localhost:11434)")
    click.echo("    • local     - Generic OpenAI-compatible API")
    click.echo()

    click.echo(click.style("Features:", fg="blue"))
    click.echo("  • Multi-provider LLM integration with unified API")
    click.echo("  • Fernet encryption for API key storage")
    click.echo("  • Prompt injection protection")
    click.echo("  • RAG pipeline (chunking, embedding, retrieval)")
    click.echo("  • MCP client (HTTP/SSE and stdio transports)")
    click.echo("  • Cost calculation service")
    click.echo("  • File upload validation")
    click.echo("  • LangDock agent/knowledge backup (langdock-export)")
    click.echo()

    click.echo(click.style("Installation:", fg="blue"))
    click.echo("  pip install eq-chatbot-core")
    click.echo("  pip install eq-chatbot-core[pdf]      # PDF support")
    click.echo("  pip install eq-chatbot-core[security] # File validation")
    click.echo()

    click.echo(click.style("Author:", fg="blue") + " Equitania Software GmbH")
    click.echo(click.style("License:", fg="blue") + " MIT")
    click.echo(click.style("Homepage:", fg="blue") + " https://www.ownerp.com")


if __name__ == "__main__":
    main()
