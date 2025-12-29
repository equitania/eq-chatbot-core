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
def main():
    """eq-chatbot - LLM Provider Testing & Management CLI.

    A command-line tool for testing LLM provider connections,
    listing available models, and managing chatbot configurations.
    """
    pass


@main.command("test-provider")
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["openai", "anthropic", "langdock"], case_sensitive=False),
    required=True,
    help="LLM provider to test",
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
    "--message",
    "-msg",
    default="Hello! Please respond with a brief greeting.",
    help="Test message to send",
)
@click.option(
    "--base-url",
    "-u",
    default=None,
    help="Custom base URL for the provider",
)
def test_provider(provider: str, api_key: str, model: str, message: str, base_url: str):
    """Test connection to an LLM provider.

    Sends a test message and displays the response along with token usage.

    Examples:

        eq-chatbot test-provider -p openai -k sk-...

        eq-chatbot test-provider -p anthropic -k sk-ant-... -m claude-3-5-sonnet-20241022

        LLM_API_KEY=sk-... eq-chatbot test-provider -p openai
    """
    if not api_key:
        click.echo(
            click.style("Error: ", fg="red")
            + "API key required. Use --api-key or set LLM_API_KEY environment variable.",
            err=True,
        )
        sys.exit(1)

    from eq_chatbot_core.providers import ProviderError, get_provider

    try:
        click.echo(f"Testing {click.style(provider, fg='cyan', bold=True)}...")

        provider_instance = get_provider(provider, api_key=api_key, base_url=base_url)

        kwargs = {}
        if model:
            kwargs["model"] = model

        response = provider_instance.chat_completion(
            messages=[{"role": "user", "content": message}],
            **kwargs,
        )

        click.echo(click.style("✓ Success!", fg="green", bold=True))
        click.echo()
        click.echo(click.style("Response:", fg="blue"))
        click.echo(f"  {response.content}")
        click.echo()

        if response.usage:
            click.echo(click.style("Token Usage:", fg="blue"))
            click.echo(f"  Input:  {response.usage.prompt_tokens}")
            click.echo(f"  Output: {response.usage.completion_tokens}")
            click.echo(f"  Total:  {response.usage.total_tokens}")

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
    type=click.Choice(["openai", "anthropic", "langdock"], case_sensitive=False),
    required=True,
    help="LLM provider to query",
)
@click.option(
    "--api-key",
    "-k",
    envvar="LLM_API_KEY",
    help="API key (or set LLM_API_KEY environment variable)",
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
def list_models(provider: str, api_key: str, as_json: bool, vision_only: bool):
    """List available models from a provider.

    Queries the provider's API and displays all available models
    with their capabilities.

    Examples:

        eq-chatbot list-models -p openai -k sk-...

        eq-chatbot list-models -p langdock -k YOUR_KEY --json

        eq-chatbot list-models -p anthropic -k sk-ant-... --vision-only
    """
    if not api_key:
        click.echo(
            click.style("Error: ", fg="red")
            + "API key required. Use --api-key or set LLM_API_KEY environment variable.",
            err=True,
        )
        sys.exit(1)

    from eq_chatbot_core.providers import ProviderError, get_provider

    try:
        provider_instance = get_provider(provider, api_key=api_key)
        models = provider_instance.list_models()

        if vision_only:
            models = [m for m in models if m.supports_vision]

        if as_json:
            output = [
                {
                    "model_id": m.model_id,
                    "supports_vision": m.supports_vision,
                    "supports_temperature": m.supports_temperature,
                    "max_tokens": m.max_tokens,
                    "context_length": m.context_length,
                }
                for m in models
            ]
            click.echo(json.dumps(output, indent=2))
        else:
            click.echo(
                f"Available models for {click.style(provider, fg='cyan', bold=True)}:"
            )
            click.echo()

            for m in models:
                vision_badge = (
                    click.style(" [vision]", fg="green") if m.supports_vision else ""
                )
                click.echo(f"  • {m.model_id}{vision_badge}")

            click.echo()
            click.echo(f"Total: {len(models)} models")

    except ProviderError as e:
        click.echo(click.style(f"✗ Provider Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red"), err=True)
        sys.exit(1)


@main.command("info")
def info():
    """Show package information.

    Displays version, supported providers, and available features.
    """
    click.echo(click.style("eq-chatbot-core", fg="cyan", bold=True) + f" v{__version__}")
    click.echo()
    click.echo("Core library for LLM chatbot integration with multi-provider support.")
    click.echo()

    click.echo(click.style("Supported Providers:", fg="blue"))
    click.echo("  • openai    - GPT-4, GPT-4o, o1, o3, o4 series")
    click.echo("  • anthropic - Claude 3, Claude 3.5, Claude 4")
    click.echo("  • langdock  - Multi-provider gateway (EU/US regions)")
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
