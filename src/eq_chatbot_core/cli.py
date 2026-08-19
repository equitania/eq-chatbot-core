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
from typing import Any

import click

from eq_chatbot_core.providers import CLOUD_PROVIDERS, LOCAL_PROVIDERS
from eq_chatbot_core.utils.config import (
    config_api_key,
    config_base_url,
    config_default_provider,
    config_max_tokens,
    config_model,
    config_temperature,
)
from eq_chatbot_core.version import __version__

ALL_PROVIDERS = CLOUD_PROVIDERS + LOCAL_PROVIDERS

# Provider -> preferred env variable (in addition to the generic LLM_API_KEY fallback).
# Lets users store one key per provider on the host instead of swapping LLM_API_KEY.
PROVIDER_API_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "langdock": "LANGDOCK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "mammouth": "MAMMOUTH_API_KEY",
    "azure": "AZURE_API_KEY",
    "litellm": "LITELLM_API_KEY",
    "ionos": "IONOS_API_KEY",
    "melious": "MELIOUS_API_KEY",
    "privatemode": "PRIVATEMODE_API_KEY",
}


def resolve_api_key(provider: str | None, explicit_key: str | None) -> str | None:
    """Resolve the API key for a provider.

    Precedence (highest first):
        1. explicit_key (--api-key / -k flag)
        2. <PROVIDER>_API_KEY env var (e.g. OPENROUTER_API_KEY)
        3. LLM_API_KEY env var (generic fallback)
        4. config file ([providers.<name>].api_key)
        5. None (caller decides; local providers and Vertex need no key)
    """
    if explicit_key:
        return explicit_key
    if provider:
        env_name = PROVIDER_API_KEY_ENV.get(provider.lower())
        if env_name and (key := os.environ.get(env_name)):
            return key
    generic = os.environ.get("LLM_API_KEY")
    if generic:
        return generic
    return config_api_key(provider)


def resolve_base_url(provider: str | None, explicit_url: str | None) -> str | None:
    """Resolve the base URL: --base-url flag > config file > None (provider default)."""
    if explicit_url:
        return explicit_url
    return config_base_url(provider)


def resolve_model(provider: str | None, explicit_model: str | None) -> str | None:
    """Resolve the model: --model flag > config file > None (provider default)."""
    if explicit_model:
        return explicit_model
    return config_model(provider)


def resolve_provider(explicit_provider: str | None) -> str | None:
    """Resolve the provider: --provider flag > config default_provider > None."""
    if explicit_provider:
        return explicit_provider
    return config_default_provider()


def resolve_cli_provider(explicit_provider: str | None, allowed: list[str]) -> tuple[str | None, str | None]:
    """Resolve and validate a provider for a CLI command.

    A provider coming from the config file bypasses click.Choice validation, so it
    must be checked against ``allowed`` here.

    Returns ``(provider, None)`` on success or ``(None, error_message)`` on failure.
    """
    resolved = resolve_provider(explicit_provider)
    if not resolved:
        return None, "No provider specified. Use --provider or set default_provider in the config file."
    if resolved.lower() not in {a.lower() for a in allowed}:
        return None, f"Invalid provider '{resolved}'. Valid providers: {', '.join(allowed)}."
    return resolved, None


@click.group()
@click.version_option(version=__version__, prog_name="eq-chatbot")
def main() -> None:
    """eq-chatbot - Multi-provider LLM CLI.

    Test provider connections and list models, run single-turn JSON chat,
    generate images (image / listing-assets), and run a localhost HTTP/SSE
    gateway (serve).
    """
    pass


@main.command("test-provider")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(ALL_PROVIDERS, case_sensitive=False),
    default=None,
    help="LLM provider to test (cloud: openai, anthropic, langdock, openrouter, mammouth, azure, vertex, litellm, ionos, melious, privatemode; local: local, lm_studio, ollama). Falls back to default_provider in the config file.",
)
@click.option(
    "--api-key",
    "-k",
    default=None,
    help="API key. Falls back to <PROVIDER>_API_KEY then LLM_API_KEY env var, then the config file. Not required for local providers.",
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
def test_provider(
    provider: str | None, api_key: str | None, model: str | None, message: str, base_url: str | None
) -> None:
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
    provider, perr = resolve_cli_provider(provider, ALL_PROVIDERS)
    if perr:
        click.echo(click.style("Error: ", fg="red") + perr, err=True)
        sys.exit(1)
    assert provider is not None  # narrowed by perr check

    # Check API key requirement (not needed for local providers or Vertex)
    api_key = resolve_api_key(provider, api_key)
    base_url = resolve_base_url(provider, base_url)
    model = resolve_model(provider, model)
    is_local = provider.lower() in LOCAL_PROVIDERS
    is_vertex = provider.lower() == "vertex"
    if not api_key and not is_local and not is_vertex:
        click.echo(
            click.style("Error: ", fg="red")
            + "API key required for cloud providers. Use --api-key, <PROVIDER>_API_KEY, LLM_API_KEY or the config file.",
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
    default=None,
    help="LLM provider to query (cloud: openai, anthropic, langdock, openrouter, mammouth, azure, vertex, litellm, ionos, melious, privatemode; local: local, lm_studio, ollama). Falls back to default_provider in the config file.",
)
@click.option(
    "--api-key",
    "-k",
    default=None,
    help="API key. Falls back to <PROVIDER>_API_KEY then LLM_API_KEY env var, then the config file. Not required for local providers.",
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
def list_models(
    provider: str | None, api_key: str | None, base_url: str | None, as_json: bool, vision_only: bool
) -> None:
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
    provider, perr = resolve_cli_provider(provider, ALL_PROVIDERS)
    if perr:
        click.echo(click.style("Error: ", fg="red") + perr, err=True)
        sys.exit(1)
    assert provider is not None  # narrowed by perr check

    # Check API key requirement (not needed for local providers or Vertex)
    api_key = resolve_api_key(provider, api_key)
    base_url = resolve_base_url(provider, base_url)
    is_local = provider.lower() in LOCAL_PROVIDERS
    is_vertex = provider.lower() == "vertex"
    if not api_key and not is_local and not is_vertex:
        click.echo(
            click.style("Error: ", fg="red")
            + "API key required for cloud providers. Use --api-key, <PROVIDER>_API_KEY, LLM_API_KEY or the config file.",
            err=True,
        )
        sys.exit(1)

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
            # `list` is invariant, so rebind instead of narrowing the union in place.
            models = [m for m in models if get_model_attr(m, "supports_vision", False)]  # type: ignore[assignment]

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


def _validate_messages(messages: list[Any]) -> list[dict[str, Any]]:
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
    default=None,
    help="LLM provider to use. Falls back to default_provider in the config file.",
)
@click.option(
    "--api-key",
    "-k",
    default=None,
    help="API key. Falls back to <PROVIDER>_API_KEY then LLM_API_KEY env var, then the config file.",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model to use (config file or provider default if not specified)",
)
@click.option(
    "--temperature",
    "-t",
    default=None,
    type=float,
    help="Temperature for response generation (config [defaults].temperature or 0.7)",
)
@click.option(
    "--max-tokens",
    default=None,
    type=int,
    help="Maximum tokens in response (config [defaults].max_tokens or 4096)",
)
@click.option(
    "--base-url",
    "-u",
    default=None,
    help="Custom base URL for the provider",
)
def chat(
    provider: str | None,
    api_key: str | None,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
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
    provider, perr = resolve_cli_provider(provider, ALL_PROVIDERS)
    if perr:
        click.echo(json.dumps({"error": perr}), err=True)
        sys.exit(1)
    assert provider is not None  # narrowed by perr check

    # Check API key requirement
    api_key = resolve_api_key(provider, api_key)
    base_url = resolve_base_url(provider, base_url)
    model = resolve_model(provider, model)
    if temperature is None:
        temperature = config_temperature()
        if temperature is None:
            temperature = 0.7
    if max_tokens is None:
        max_tokens = config_max_tokens()
        if max_tokens is None:
            max_tokens = 4096
    is_local = provider.lower() in LOCAL_PROVIDERS
    is_vertex = provider.lower() == "vertex"
    if not api_key and not is_local and not is_vertex:
        error_response = {
            "error": "API key required. Use --api-key, <PROVIDER>_API_KEY, LLM_API_KEY or the config file."
        }
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

        kwargs: dict[str, Any] = {
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


# Providers that support image generation
IMAGE_PROVIDERS = ["openai", "openrouter"]


@main.command("image")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(IMAGE_PROVIDERS, case_sensitive=False),
    default=None,
    help="LLM provider to use for image generation (openai, openrouter). Falls back to default_provider in the config file.",
)
@click.option(
    "--api-key",
    "-k",
    default=None,
    help="API key. Falls back to <PROVIDER>_API_KEY then LLM_API_KEY env var, then the config file.",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model to use (uses provider default if not specified)",
)
@click.option(
    "--prompt",
    default=None,
    help="Text prompt describing the image to generate",
)
@click.option(
    "--prompt-file",
    default=None,
    type=click.Path(exists=True, readable=True),
    help="Read prompt from a file instead of --prompt",
)
@click.option(
    "--size",
    default="1024x1024",
    show_default=True,
    help="Image dimensions (e.g. 1024x1024, 1024x1536, auto)",
)
@click.option(
    "--fit",
    default=None,
    help="Resize output image: WxH[:mode] where mode is cover/contain/stretch (e.g. '512x512' or '512x512:contain'). Requires [image] extra.",
)
@click.option(
    "--output",
    "-o",
    default="output.png",
    show_default=True,
    help="Output file path for the generated image",
)
@click.option(
    "--base-url",
    "-u",
    default=None,
    help="Custom base URL for the provider",
)
def image(
    provider: str | None,
    api_key: str | None,
    model: str | None,
    prompt: str | None,
    prompt_file: str | None,
    size: str,
    fit: str | None,
    output: str,
    base_url: str | None,
) -> None:
    """Generate an image from a text prompt.

    Saves the generated image to a file (PNG by default).
    Supported providers: openai (gpt-image-1), openrouter (gemini-2.5-flash-image).

    Examples:

        eq-chatbot image -p openai -k sk-... --prompt "A sunset over the ocean"

        eq-chatbot image -p openrouter -k sk-or-... --prompt "A cat in space" -o cat.png

        eq-chatbot image -p openai -k sk-... --prompt-file prompt.txt --fit 512x512:cover
    """
    if not prompt and not prompt_file:
        click.echo(click.style("Error: ", fg="red") + "Provide --prompt or --prompt-file.", err=True)
        sys.exit(1)
    if prompt and prompt_file:
        click.echo(click.style("Error: ", fg="red") + "Use either --prompt or --prompt-file, not both.", err=True)
        sys.exit(1)

    provider, perr = resolve_cli_provider(provider, IMAGE_PROVIDERS)
    if perr:
        click.echo(click.style("Error: ", fg="red") + perr, err=True)
        sys.exit(1)
    assert provider is not None  # narrowed by perr check

    api_key = resolve_api_key(provider, api_key)
    base_url = resolve_base_url(provider, base_url)
    model = resolve_model(provider, model)
    if not api_key:
        click.echo(
            click.style("Error: ", fg="red")
            + "API key required. Use --api-key, <PROVIDER>_API_KEY, LLM_API_KEY or the config file.",
            err=True,
        )
        sys.exit(1)

    if prompt_file:
        import pathlib

        prompt = pathlib.Path(prompt_file).read_text(encoding="utf-8").strip()

    from eq_chatbot_core.providers import ProviderError, get_provider

    try:
        provider_instance = get_provider(provider, api_key=api_key, base_url=base_url)

        click.echo(f"Generating image via {click.style(provider, fg='cyan', bold=True)}...")

        result = provider_instance.generate_image(
            prompt or "",
            model=model,
            size=size,
        )

        image_data = result.data

        # Optional resize via Pillow
        if fit:
            from eq_chatbot_core.utils.image import fit_to, parse_size

            # Parse WxH or WxH:mode
            if ":" in fit:
                size_part, fit_mode = fit.rsplit(":", 1)
            else:
                size_part, fit_mode = fit, "cover"

            fit_w, fit_h = parse_size(size_part)
            image_data = fit_to(image_data, fit_w, fit_h, mode=fit_mode)

        from eq_chatbot_core.utils.image import save_png

        out_path = save_png(image_data, output)
        size_kb = len(image_data) / 1024

        click.echo(click.style("Image saved:", fg="green") + f" {out_path} ({size_kb:.1f} KB)")

    except ProviderError as e:
        click.echo(click.style(f"Provider error: {e}", fg="red"), err=True)
        sys.exit(1)
    except ImportError as e:
        click.echo(click.style(f"Missing dependency: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


def _parse_fit(fit: str | None) -> tuple[int, int, str] | None:
    """Parse fit string 'WxH' or 'WxH:mode' into (width, height, mode).

    Returns None when fit is None or empty.
    """
    if not fit:
        return None
    if ":" in fit:
        size_part, mode = fit.rsplit(":", 1)
    else:
        size_part, mode = fit, "cover"
    from eq_chatbot_core.utils.image import parse_size

    w, h = parse_size(size_part)
    return w, h, mode


def _load_recipe(recipe_path: str) -> dict[str, Any]:
    """Load and validate a recipe JSON file.

    Raises click.ClickException with a clear message on any validation error.
    """
    import json
    from pathlib import Path

    path = Path(recipe_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Cannot read recipe file: {exc}") from exc

    try:
        recipe = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Recipe is not valid JSON: {exc}") from exc

    schema = recipe.get("schema", "")
    if not isinstance(schema, str) or not schema.startswith("eq-listing-assets/"):
        raise click.ClickException(f"Invalid recipe schema '{schema}'. Must start with 'eq-listing-assets/'.")

    assets = recipe.get("assets")
    if not assets:
        raise click.ClickException("Recipe must contain a non-empty 'assets' list.")
    if not isinstance(assets, list):
        raise click.ClickException("'assets' must be a JSON array.")

    for i, asset in enumerate(assets):
        for required_key in ("id", "out", "prompt"):
            if required_key not in asset:
                raise click.ClickException(f"Asset #{i} is missing required field '{required_key}'.")

    value: dict[str, Any] = recipe
    return value


@main.command("listing-assets")
@click.option(
    "--recipe",
    "recipe_file",
    required=True,
    type=click.Path(exists=True, readable=True),
    help="Path to the recipe JSON file (eq-listing-assets/v1 schema).",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(IMAGE_PROVIDERS, case_sensitive=False),
    default=None,
    help="Override provider from recipe defaults (openai, openrouter).",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Override model from recipe defaults.",
)
@click.option(
    "--api-key",
    "-k",
    default=None,
    help="API key. Falls back to <PROVIDER>_API_KEY then LLM_API_KEY env var.",
)
@click.option(
    "--base-url",
    "-u",
    default=None,
    help="Custom base URL for the provider.",
)
@click.option(
    "--dest",
    default=None,
    type=click.Path(file_okay=False),
    help="Destination directory for generated images (default: recipe file directory).",
)
@click.option(
    "--only",
    default=None,
    help="Comma-separated list of asset IDs to generate (filter).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="List what would be generated without making any API calls.",
)
def listing_assets(
    recipe_file: str,
    provider: str | None,
    model: str | None,
    api_key: str | None,
    base_url: str | None,
    dest: str | None,
    only: str | None,
    dry_run: bool,
) -> None:
    """Generate a batch of images from a recipe JSON file.

    The recipe defines a list of assets (icon, banner, eyecatchers, ...) with
    prompts, sizes, and optional fit parameters. Provider and model can be set
    globally via 'defaults' in the recipe or overridden with CLI flags.

    Schema: eq-listing-assets/v1

    A recipe can mix assets that carry rendered TEXT (a banner showing the
    module title) and pure IMAGERY (an app icon). Example recipe
    (eq_chatbot_listing.json):

    \b
    {
      "schema": "eq-listing-assets/v1",
      "module": "eq_chatbot",
      "defaults": {"provider": "openai", "model": "gpt-image-1"},
      "assets": [
        {"id": "banner", "out": "banner.png", "size": "1536x1024",
         "prompt": "Wide App-Store banner, deep-blue gradient, friendly robot
                    mascot, bold headline 'eq_chatbot - AI Assistant for Odoo'"},
        {"id": "icon", "out": "icon.png", "size": "1024x1024",
         "prompt": "Minimal flat app icon, rounded square, speech bubble with a
                    spark, blue and white, no text"}
      ]
    }

    Examples:

    \b
        # Preview what would be generated (no API calls, no key needed)
        eq-chatbot listing-assets --recipe eq_chatbot_listing.json --dry-run

    \b
        # Generate every asset
        eq-chatbot listing-assets --recipe eq_chatbot_listing.json -k sk-...

    \b
        # Only the banner, written into the module's listing folder
        eq-chatbot listing-assets --recipe eq_chatbot_listing.json \\
            --only banner --dest ./eq_chatbot/static/description -k sk-...
    """
    import pathlib

    recipe = _load_recipe(recipe_file)
    defaults = recipe.get("defaults", {})

    # Resolve provider and model: CLI > recipe defaults > config file > hard default
    resolved_provider = provider or defaults.get("provider") or config_default_provider() or "openai"
    resolved_model = model or defaults.get("model") or config_model(resolved_provider) or None

    # Resolve destination directory
    recipe_dir = pathlib.Path(recipe_file).parent
    dest_dir = pathlib.Path(dest) if dest else recipe_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    assets: list[dict[str, Any]] = recipe["assets"]

    # Apply --only filter
    if only:
        filter_ids = {s.strip() for s in only.split(",") if s.strip()}
        assets = [a for a in assets if a["id"] in filter_ids]
        if not assets:
            raise click.ClickException(f"No assets matched the --only filter: {only}")

    if dry_run:
        click.echo(click.style("Dry run — no API calls will be made.", fg="yellow"))
        click.echo()
        for asset in assets:
            size = asset.get("size", "1024x1024")
            fit = asset.get("fit", "")
            fit_info = f"  fit={fit}" if fit else ""
            click.echo(f"  [{asset['id']}]  {asset['out']}  size={size}{fit_info}")
        click.echo()
        click.echo(f"{len(assets)} asset(s) would be generated.")
        return

    api_key = resolve_api_key(resolved_provider, api_key)
    base_url = resolve_base_url(resolved_provider, base_url)
    if not api_key:
        raise click.ClickException(
            "API key required. Use --api-key, <PROVIDER>_API_KEY, LLM_API_KEY or the config file."
        )

    from eq_chatbot_core.providers import get_provider
    from eq_chatbot_core.utils.image import fit_to, parse_size, save_png

    provider_instance = get_provider(resolved_provider, api_key=api_key, base_url=base_url)

    generated: list[str] = []
    failed: list[tuple[str, str]] = []

    for asset in assets:
        asset_id = asset["id"]
        out_name = asset["out"]
        prompt_text = asset["prompt"]
        size = asset.get("size", "1024x1024")
        fit = asset.get("fit")

        try:
            click.echo(f"  Generating [{asset_id}]  {out_name}  ({size}) ...")

            result = provider_instance.generate_image(
                prompt_text,
                model=resolved_model,
                size=size,
            )

            image_data = result.data

            if fit:
                if ":" in fit:
                    size_part, fit_mode = fit.rsplit(":", 1)
                else:
                    size_part, fit_mode = fit, "cover"
                fit_w, fit_h = parse_size(size_part)
                image_data = fit_to(image_data, fit_w, fit_h, mode=fit_mode)

            # out_name comes from the asset spec (untrusted); constrain the write
            # to dest_dir so a "../" or absolute name cannot escape it.
            out_path = dest_dir / out_name
            out_path = save_png(image_data, out_path, base_dir=dest_dir)
            generated.append(str(out_path))
            click.echo(click.style(f"    -> {out_path}", fg="green"))

        except Exception as exc:
            failed.append((asset_id, str(exc)))
            click.echo(
                click.style(f"    ! [{asset_id}] failed: {exc}", fg="red"),
                err=True,
            )

    click.echo()
    click.echo(f"Generated: {len(generated)}/{len(assets)}")
    for p in generated:
        click.echo(f"  {p}")

    if failed:
        click.echo()
        click.echo(click.style("Failed:", fg="red"))
        for asset_id, err_msg in failed:
            click.echo(click.style(f"  [{asset_id}] {err_msg}", fg="red"))
        import sys

        sys.exit(1)


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
    click.echo("    • melious    - Melious.ai (sovereign EU-hosted, OpenAI-compatible)")
    click.echo("    • privatemode - Privatemode.ai, end-to-end encrypted via local proxy (localhost:8080)")
    click.echo("  Local:")
    click.echo("    • lm_studio - LM Studio (localhost:1234)")
    click.echo("    • ollama    - Ollama (localhost:11434)")
    click.echo("    • local     - Generic OpenAI-compatible API")
    click.echo()

    click.echo(click.style("Features:", fg="blue"))
    click.echo("  • Multi-provider LLM integration with unified API")
    click.echo("  • Text-to-image generation (image, listing-assets)")
    click.echo("  • Realtime voice providers (ElevenLabs, OpenAI, Gemini Live)")
    click.echo("  • Localhost HTTP/SSE server mode (serve)")
    click.echo("  • Fernet encryption for API key storage")
    click.echo("  • Prompt injection protection (direct + indirect tool/RAG content)")
    click.echo("  • RAG pipeline (chunking, embedding, retrieval)")
    click.echo("  • MCP client (HTTP/SSE and stdio transports)")
    click.echo("  • Cost calculation service")
    click.echo("  • File upload validation")
    click.echo()

    click.echo(click.style("Installation:", fg="blue"))
    click.echo("  pip install eq-chatbot-core")
    click.echo("  pip install eq-chatbot-core[pdf]      # PDF→image conversion (vision)")
    click.echo("  pip install eq-chatbot-core[security] # MIME-type file validation")
    click.echo("  pip install eq-chatbot-core[image]    # Text-to-image generation")
    click.echo("  pip install eq-chatbot-core[server]   # HTTP/SSE sidecar")
    click.echo("  pip install eq-chatbot-core[realtime] # Realtime voice providers")
    click.echo("  pip install eq-chatbot-core[azure]    # Azure AI Foundry")
    click.echo("  pip install eq-chatbot-core[vertex]   # Google Vertex AI")
    click.echo("  pip install eq-chatbot-core[local]    # Local sentence-transformers")
    click.echo()

    click.echo(click.style("Author:", fg="blue") + " Equitania Software GmbH")
    click.echo(click.style("License:", fg="blue") + " MIT")
    click.echo(click.style("Homepage:", fg="blue") + " https://www.ownerp.com")


@main.group("config")
def config_group() -> None:
    """Manage the user config file (~/.config/eq-chatbot/config.toml).

    Store provider API keys, base URLs, default models and chat defaults so they
    do not have to be passed on every call.
    """
    pass


@config_group.command("init")
@click.option("--force", is_flag=True, help="Overwrite an existing config file.")
def config_init(force: bool) -> None:
    """Write a commented config template (mode 0600) to the config path.

    Examples:

        eq-chatbot config init

        EQ_CHATBOT_CONFIG=./eqbot.toml eq-chatbot config init --force
    """
    from eq_chatbot_core.utils.config import ConfigError, write_template

    try:
        path = write_template(force=force)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(click.style("✓ Config written:", fg="green") + f" {path}")
    click.echo("Edit it to add your provider keys, then run: eq-chatbot config show")


@config_group.command("path")
def config_path_cmd() -> None:
    """Print the resolved config file path (whether or not it exists)."""
    from eq_chatbot_core.utils.config import config_path

    click.echo(str(config_path()))


@config_group.command("show")
def config_show() -> None:
    """Show the config path, permissions and a key-masked view of the contents."""
    from eq_chatbot_core.utils.config import ConfigError, config_path, load_config, redact

    path = config_path()
    click.echo(click.style("Path:", fg="blue") + f" {path}")
    if not path.exists():
        click.echo(click.style("Status:", fg="blue") + " not found (run: eq-chatbot config init)")
        return

    mode = path.stat().st_mode & 0o777
    perm_style = "yellow" if mode & 0o077 else "green"
    click.echo(click.style("Permissions:", fg="blue") + " " + click.style(f"{mode:04o}", fg=perm_style))

    try:
        data = load_config()
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    default_provider = data.get("default_provider")
    if default_provider:
        click.echo(click.style("Default provider:", fg="blue") + f" {default_provider}")

    defaults = data.get("defaults")
    if isinstance(defaults, dict) and defaults:
        click.echo(click.style("Chat defaults:", fg="blue") + f" {defaults}")

    providers = data.get("providers")
    if isinstance(providers, dict) and providers:
        click.echo(click.style("Providers:", fg="blue"))
        for name, section in providers.items():
            if not isinstance(section, dict):
                continue
            parts = []
            if isinstance(section.get("api_key"), str) and section["api_key"]:
                parts.append(f"api_key={redact(section['api_key'])}")
            if isinstance(section.get("model"), str) and section["model"]:
                parts.append(f"model={section['model']}")
            if isinstance(section.get("base_url"), str) and section["base_url"]:
                parts.append(f"base_url={section['base_url']}")
            detail = ", ".join(parts) if parts else "(empty)"
            click.echo(f"  {name}: {detail}")


if __name__ == "__main__":
    main()
