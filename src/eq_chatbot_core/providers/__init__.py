"""
LLM Provider adapters for OpenAI, Anthropic, and LangDock.

Usage:
    from eq_chatbot_core.providers import get_provider

    provider = get_provider("openai", api_key="sk-...")
    response = provider.chat_completion(messages=[...])
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eq_chatbot_core.providers.base import BaseLLMProvider


def get_provider(
    provider_name: str,
    api_key: str,
    base_url: str | None = None,
    **kwargs,
) -> "BaseLLMProvider":
    """
    Factory function to get the appropriate LLM provider.

    Args:
        provider_name: One of "openai", "anthropic", "langdock"
        api_key: API key for the provider
        base_url: Optional custom base URL (for LangDock or Azure)
        **kwargs: Additional provider-specific arguments

    Returns:
        An instance of the requested provider

    Raises:
        ValueError: If provider_name is not recognized
    """
    from eq_chatbot_core.providers.openai_provider import OpenAIProvider
    from eq_chatbot_core.providers.anthropic_provider import AnthropicProvider
    from eq_chatbot_core.providers.langdock_provider import LangDockProvider

    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "langdock": LangDockProvider,
    }

    provider_class = providers.get(provider_name.lower())
    if provider_class is None:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Available: {', '.join(providers.keys())}"
        )

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
]
