"""
LLM Provider adapters for OpenAI, Anthropic, LangDock, OpenRouter, Mammouth, Privatemode, and local servers.

Supports cloud providers (OpenAI, Anthropic, LangDock, OpenRouter, Mammouth, IONOS, Melious, Privatemode, LiteLLM)
and local LLM servers (LM Studio, Ollama) that expose OpenAI-compatible APIs.

Usage:
    from eq_chatbot_core.providers import get_provider

    # Cloud providers
    provider = get_provider("openai", api_key="sk-...")
    response = provider.chat_completion(messages=[...])

    # OpenRouter (400+ models)
    provider = get_provider("openrouter", api_key="sk-or-...")
    response = provider.chat_completion(messages=[...], model="openai/gpt-4o")

    # Mammouth AI (30+ models)
    provider = get_provider("mammouth", api_key="mm-...")
    response = provider.chat_completion(messages=[...], model="gpt-4o")

    response = provider.chat_completion(messages=[...], model="gpt-4o")

    response = provider.chat_completion(messages=[...], model="gemini-2.5-flash")

    # Local providers (LM Studio or Ollama)
    provider = get_provider("local", base_url="http://localhost:1234/v1")
    response = provider.chat_completion(messages=[...])

    # LiteLLM / any OpenAI-compatible gateway (base_url is REQUIRED, no default)
    provider = get_provider("litellm", api_key="...", base_url="https://api.ccsio.ai/v1")
    response = provider.chat_completion(messages=[...], model="qwen3.6-35b-a3b")

    # IONOS AI Model Hub (EU-hosted, OpenAI-compatible; base_url has a default)
    provider = get_provider("ionos", api_key="...")
    response = provider.chat_completion(messages=[...], model="meta-llama/Llama-3.3-70B-Instruct")

    # Melious.ai (sovereign EU-hosted, OpenAI-compatible; base_url has a default)
    provider = get_provider("melious", api_key="sk-mel-...")
    response = provider.chat_completion(messages=[...], model="minimax-428b-m3")

    # Privatemode (end-to-end encrypted, via the locally-run attesting proxy).
    # The proxy usually holds the API key, so none is passed here.
    provider = get_provider("privatemode")  # defaults to http://localhost:8080/v1
    response = provider.chat_completion(messages=[...], model="kimi-latest")
"""

from typing import TYPE_CHECKING, Any

CLOUD_PROVIDERS: list[str] = [
    "openai",
    "anthropic",
    "langdock",
    "openrouter",
    "mammouth",
    "litellm",
    "ionos",
    "melious",
    "privatemode",
]
LOCAL_PROVIDERS: list[str] = ["local", "lm_studio", "lmstudio", "ollama"]

if TYPE_CHECKING:
    from eq_chatbot_core.providers.base import BaseLLMProvider


def get_provider(
    provider_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> "BaseLLMProvider":
    """
    Factory function to get the appropriate LLM provider.

    Args:
        provider_name: One of "openai", "anthropic", "langdock", "openrouter",
                       "mammouth", "litellm", "ionos", "melious", "privatemode", "local",
                       "lm_studio", "lmstudio", "ollama"
        api_key: API key for the provider (optional for local providers)
        base_url: Optional custom base URL. Required for local providers,
                  optional for cloud providers. For convenience aliases:
                  - "lm_studio"/"lmstudio": defaults to http://localhost:1234/v1
                  - "ollama": defaults to http://localhost:11434/v1
        **kwargs: Additional provider-specific arguments

    Returns:
        An instance of the requested provider

    Raises:
        ValueError: If provider_name is not recognized

    Examples:
        # OpenAI cloud
        provider = get_provider("openai", api_key="sk-...")

        # OpenRouter (400+ models)
        provider = get_provider("openrouter", api_key="sk-or-...")

        # Mammouth AI (30+ models)
        provider = get_provider("mammouth", api_key="mm-...")


        # Local LM Studio
        provider = get_provider("lm_studio")
        provider = get_provider("local", base_url="http://localhost:1234/v1")

        # Local Ollama
        provider = get_provider("ollama")
        provider = get_provider("local", base_url="http://localhost:11434/v1")
    """
    from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
    from eq_chatbot_core.providers.ionos_provider import IonosProvider
    from eq_chatbot_core.providers.langdock_provider import LangDockProvider
    from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider
    from eq_chatbot_core.providers.local_provider import LocalLLMProvider
    from eq_chatbot_core.providers.mammouth_provider import MammouthProvider
    from eq_chatbot_core.providers.melious_provider import MeliousProvider
    from eq_chatbot_core.providers.openai_provider import OpenAIProvider
    from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
    from eq_chatbot_core.providers.privatemode_provider import PrivatemodeProvider

    # Provider class mapping
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "langdock": LangDockProvider,
        "openrouter": OpenRouterProvider,
        "mammouth": MammouthProvider,
        "local": LocalLLMProvider,
        "litellm": LiteLLMProvider,
        "ionos": IonosProvider,
        "melious": MeliousProvider,
        "privatemode": PrivatemodeProvider,
    }

    # Convenience aliases for local providers with default URLs
    local_aliases = {
        "lm_studio": LocalLLMProvider.LM_STUDIO_URL,
        "lmstudio": LocalLLMProvider.LM_STUDIO_URL,
        "ollama": LocalLLMProvider.OLLAMA_URL,
    }

    provider_name_lower = provider_name.lower()

    # Handle local provider aliases
    provider_class: (
        type[OpenAIProvider]
        | type[AnthropicProvider]
        | type[LangDockProvider]
        | type[OpenRouterProvider]
        | type[MammouthProvider]
        | type[LocalLLMProvider]
        | type[LiteLLMProvider]
        | type[IonosProvider]
        | type[MeliousProvider]
        | type[PrivatemodeProvider]
        | None
    ) = None

    if provider_name_lower in local_aliases:
        if base_url is None:
            base_url = local_aliases[provider_name_lower]
        provider_class = LocalLLMProvider
    else:
        provider_class = providers.get(provider_name_lower)  # type: ignore[assignment]

    if provider_class is None:
        available = list(providers.keys()) + list(local_aliases.keys())
        raise ValueError(f"Unknown provider: {provider_name}. Available: {', '.join(sorted(set(available)))}")

    # Local providers don't require an API key. Privatemode usually doesn't
    # either — its proxy holds the key — and substitutes its own placeholder, so
    # an empty string is passed through untouched here.
    if provider_class is LocalLLMProvider:
        api_key = api_key or "not-used"

    # api_key is guaranteed to be str at this point for non-local providers
    return provider_class(api_key=api_key or "", base_url=base_url, **kwargs)


# Exports for public API - after get_provider to avoid circular imports
from eq_chatbot_core.providers.base import (  # noqa: E402
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    ImageResult,
    LLMResponse,
    ModelInfo,
    OverloadedError,
    ProviderError,
    RateLimitError,
    StreamChunk,
    ToolDefinition,
)
from eq_chatbot_core.providers.ionos_provider import IonosProvider  # noqa: E402
from eq_chatbot_core.providers.litellm_provider import LiteLLMProvider  # noqa: E402
from eq_chatbot_core.providers.local_provider import LocalLLMProvider  # noqa: E402
from eq_chatbot_core.providers.mammouth_provider import MammouthProvider  # noqa: E402
from eq_chatbot_core.providers.melious_provider import MeliousProvider  # noqa: E402
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider  # noqa: E402
from eq_chatbot_core.providers.privatemode_provider import PrivatemodeProvider  # noqa: E402

__all__ = [
    "get_provider",
    "BaseLLMProvider",
    "LLMResponse",
    "ImageResult",
    "StreamChunk",
    "ModelInfo",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ContextLengthError",
    "OverloadedError",
    "LocalLLMProvider",
    "LiteLLMProvider",
    "IonosProvider",
    "MeliousProvider",
    "PrivatemodeProvider",
    "MammouthProvider",
    "OpenRouterProvider",
    "ToolDefinition",
    "CLOUD_PROVIDERS",
    "LOCAL_PROVIDERS",
]
