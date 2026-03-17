"""
eq-chatbot CLI - Command line interface for eq_chatbot_core.

Usage:
    eq-chatbot test-provider -p openai -k YOUR_API_KEY
    eq-chatbot list-models -p anthropic -k YOUR_API_KEY
    eq-chatbot info
"""

import json
import sys

import click

from eq_chatbot_core.version import __version__


@click.group()
@click.version_option(version=__version__, prog_name="eq-chatbot")
def main() -> None:
    """eq-chatbot - LLM Provider Testing & Management CLI.

    A command-line tool for testing LLM provider connections,
    listing available models, and managing chatbot configurations.
    """
    pass


# Available providers for CLI choices
CLOUD_PROVIDERS = ["openai", "anthropic", "langdock", "openrouter", "mammouth", "azure", "vertex"]
LOCAL_PROVIDERS = ["local", "lm_studio", "ollama"]
ALL_PROVIDERS = CLOUD_PROVIDERS + LOCAL_PROVIDERS


@main.command("test-provider")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(ALL_PROVIDERS, case_sensitive=False),
    required=True,
    help="LLM provider to test (cloud: openai, anthropic, langdock, openrouter, mammouth, azure; local: local, lm_studio, ollama)",
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
    help="LLM provider to query (cloud: openai, anthropic, langdock, openrouter, mammouth, azure; local: local, lm_studio, ollama)",
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
