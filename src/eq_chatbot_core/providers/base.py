"""
Base classes and types for LLM providers.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    """The generated text content."""

    model: str
    """The model used for generation."""

    input_tokens: int = 0
    """Number of input tokens used."""

    output_tokens: int = 0
    """Number of output tokens generated."""

    finish_reason: str | None = None
    """Why the generation stopped (stop, length, tool_calls, etc.)."""

    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    """Tool calls requested by the model."""

    raw_response: dict[str, Any] | None = None
    """The raw response from the provider (for debugging)."""

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""

    content: str
    """The text content of this chunk."""

    is_final: bool = False
    """Whether this is the final chunk."""

    finish_reason: str | None = None
    """Why the stream ended (only set on final chunk)."""

    tool_call_delta: dict[str, Any] | None = None
    """Partial tool call data (for streaming tool calls)."""

    tool_calls: list[dict[str, Any]] | None = None
    """Complete tool calls (accumulated from deltas, set on final chunk)."""

    input_tokens: int = 0
    """Number of input tokens (only set on final chunk with usage data)."""

    output_tokens: int = 0
    """Number of output tokens (only set on final chunk with usage data)."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Typed tool/function definition shared by chat and realtime providers.

    Parameters must use flat JSON Schema (no $ref, $defs, allOf, anyOf, oneOf).
    Both OpenAI and Gemini strip or reject JSON Schema references (PITFALL-12).
    """

    name: str
    description: str
    parameters: dict[str, Any]  # Flat JSON Schema dict
    strict: bool = False


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers must implement chat_completion and stream_completion.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        """
        Initialize the provider.

        Args:
            api_key: API key for authentication
            base_url: Optional custom base URL
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'anthropic')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider."""
        ...

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            tools: Optional tool definitions for function calling
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with the generated content and metadata

        Raises:
            ProviderError: On API errors
            TimeoutError: On request timeout
        """
        ...

    @abstractmethod
    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """
        Stream a chat completion response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to provider's default)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            tools: Optional tool definitions for function calling
            **kwargs: Additional provider-specific parameters

        Yields:
            StreamChunk objects with content deltas

        Raises:
            ProviderError: On API errors
            TimeoutError: On request timeout
        """
        ...

    @abstractmethod
    def list_models(self) -> list["ModelInfo"] | list[dict[str, Any]]:
        """
        List available models from the provider.

        Returns:
            List of ModelInfo objects or dicts with model metadata.
            Note: Future versions will standardize on list[ModelInfo].

        Raises:
            ProviderError: On API errors
            AuthenticationError: On invalid API key
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider_name})"


@dataclass
class ModelInfo:
    """Information about an available model."""

    id: str
    """The model ID used for API calls."""

    name: str
    """Human-readable name."""

    provider: str
    """Provider name (openai, anthropic, etc.)."""

    context_length: int | None = None
    """Maximum context length in tokens."""

    supports_streaming: bool = True
    """Whether the model supports streaming."""

    supports_tools: bool = True
    """Whether the model supports function calling."""

    supports_vision: bool = False
    """Whether the model supports image inputs."""


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after


class RateLimitError(ProviderError):
    """Raised when the provider's rate limit is exceeded."""

    pass


class AuthenticationError(ProviderError):
    """Raised when API authentication fails."""

    pass


class ContextLengthError(ProviderError):
    """Raised when the context length is exceeded."""

    pass


class OverloadedError(ProviderError):
    """Raised when the provider's servers are overloaded (transient, retryable)."""

    pass
