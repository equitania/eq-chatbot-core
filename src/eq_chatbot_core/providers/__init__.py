"""
LLM Provider adapters for OpenAI, Anthropic, LangDock, OpenRouter, and local servers.

Supports cloud providers (OpenAI, Anthropic, LangDock, OpenRouter) and local LLM servers
(LM Studio, Ollama) that expose OpenAI-compatible APIs.

Usage:
    from eq_chatbot_core.providers import get_provider

    # Cloud providers
    provider = get_provider("openai", api_key="sk-...")
    response = provider.chat_completion(messages=[...])

    # OpenRouter (400+ models)
    provider = get_provider("openrouter", api_key="sk-or-...")
    response = provider.chat_completion(messages=[...], model="openai/gpt-4o")

    # Local providers (LM Studio or Ollama)
    provider = get_provider("local", base_url="http://localhost:1234/v1")
    response = provider.chat_completion(messages=[...])
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eq_chatbot_core.providers.base import BaseLLMProvider


def get_provider(
    provider_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs,
) -> "BaseLLMProvider":
    """
    Factory function to get the appropriate LLM provider.

    Args:
        provider_name: One of "openai", "anthropic", "langdock", "openrouter",
                       "local", "lm_studio", "lmstudio", "ollama"
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

        # Local LM Studio
        provider = get_provider("lm_studio")
        provider = get_provider("local", base_url="http://localhost:1234/v1")

        # Local Ollama
        provider = get_provider("ollama")
        provider = get_provider("local", base_url="http://localhost:11434/v1")
    """
    from eq_chatbot_core.providers.openai_provider import OpenAIProvider
    from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
    from eq_chatbot_core.providers.langdock_provider import LangDockProvider
    from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider
    from eq_chatbot_core.providers.local_provider import LocalLLMProvider

    # Provider class mapping
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "langdock": LangDockProvider,
        "openrouter": OpenRouterProvider,
        "local": LocalLLMProvider,
    }

    # Convenience aliases for local providers with default URLs
    local_aliases = {
        "lm_studio": LocalLLMProvider.LM_STUDIO_URL,
        "lmstudio": LocalLLMProvider.LM_STUDIO_URL,
        "ollama": LocalLLMProvider.OLLAMA_URL,
    }

    provider_name_lower = provider_name.lower()

    # Handle local provider aliases
    if provider_name_lower in local_aliases:
        if base_url is None:
            base_url = local_aliases[provider_name_lower]
        provider_class = LocalLLMProvider
    else:
        provider_class = providers.get(provider_name_lower)

    if provider_class is None:
        available = list(providers.keys()) + list(local_aliases.keys())
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Available: {', '.join(sorted(set(available)))}"
        )

    # Local providers don't require API key
    if provider_class == LocalLLMProvider:
        api_key = api_key or "not-used"

    return provider_class(api_key=api_key, base_url=base_url, **kwargs)


from eq_chatbot_core.providers.base import (
    BaseLLMProvider,
    LLMResponse,
    StreamChunk,
    ModelInfo,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ContextLengthError,
)

from eq_chatbot_core.providers.local_provider import LocalLLMProvider
from eq_chatbot_core.providers.openrouter_provider import OpenRouterProvider

__all__ = [
    "get_provider",
    "BaseLLMProvider",
    "LLMResponse",
    "StreamChunk",
    "ModelInfo",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ContextLengthError",
    "LocalLLMProvider",
    "OpenRouterProvider",
]
