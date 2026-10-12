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
class ImageResult:
    """Result from an image generation request."""

    data: bytes
    """Raw image bytes."""

    model: str
    """The model used for generation."""

    provider: str
    """Provider name (openai, openrouter, etc.)."""

    size: str | None = None
    """Image dimensions (e.g. '1024x1024'), if known."""

    mime: str = "image/png"
    """MIME type of the image data."""


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

    def to_chat_tool(self) -> dict[str, Any]:
        """Render this definition in OpenAI Chat Completions wire format.

        Note this is the *nested* shape (``{"type": "function", "function": {...}}``),
        which differs from the flat shape the Realtime API expects — the realtime
        providers do their own conversion for that reason.
        """
        function: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
        if self.strict:
            function["strict"] = True
        return {"type": "function", "function": function}


def normalize_tools(
    tools: "list[ToolDefinition] | list[dict[str, Any]] | None",
) -> list[dict[str, Any]] | None:
    """Normalize a tool list to OpenAI Chat Completions dicts.

    The base class advertises that ``chat_completion``/``stream_completion``
    accept :class:`ToolDefinition` instances, but the chat providers pass
    ``tools`` straight into their request payload — so a ToolDefinition used to
    reach the JSON serializer as a dataclass and fail there. Every chat provider
    normalizes through this at its entry point, which also keeps the
    provider-specific converters (Anthropic's ``input_schema`` form, Vertex's
    function declarations) working unchanged, since they already translate from
    the OpenAI dict shape.

    Args:
        tools: Tool definitions, dicts already in OpenAI format, or None.

    Returns:
        A list of OpenAI-format dicts, or None when there is nothing to send.
    """
    if not tools:
        return None
    return [tool.to_chat_tool() if isinstance(tool, ToolDefinition) else dict(tool) for tool in tools]


# --- check_model -----------------------------------------------------------------

CHECK_STATES = ("ok", "refused", "error", "skipped")


@dataclass
class ModelCheck:
    """What ``check_model`` found out about one model on one endpoint.

    Each step is ``"ok"`` (the provider accepted the request), ``"refused"`` (it
    rejected the request even after the adjustments it allows were tried),
    ``"error"`` (no verdict: authentication, rate limit, network) or ``"skipped"``.
    """

    model: str
    text: str = "skipped"
    """A plain streamed answer, sent the way a chat sends it."""

    tools: str = "skipped"
    """The same with one function tool."""

    vision: str = "skipped"
    """The same with a small image."""

    web_search: str = "skipped"
    """The same with the provider's built-in web search switched on; ``"skipped"``
    where the provider has none (``supports_native_web_search``)."""

    adjustments: list[str] = field(default_factory=list)
    """Request adjustments this model needs (``param_learning.LEARNABLE`` names).
    Persist them and hand them back with ``seed_adjustments`` after a restart."""

    limits: dict[str, int] = field(default_factory=dict)
    """Token limits the provider named (``max_output_tokens``, ``context_length``)."""

    messages: dict[str, str] = field(default_factory=dict)
    """The provider's message per step that was not ``"ok"`` (secrets scrubbed)."""

    @property
    def ok(self) -> bool:
        """The model answers at all."""
        return self.text == "ok"


# Output limit of a check request: enough for a reasoning model to finish a
# one-word answer, small enough that a check costs next to nothing.
CHECK_MAX_TOKENS = 256
CHECK_SYSTEM = "This is an automated capability check. Answer in one word."
CHECK_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Returns the current time in a time zone.",
        "parameters": {
            "type": "object",
            "properties": {"timezone": {"type": "string", "description": "IANA time zone, e.g. Europe/Berlin"}},
        },
    },
}


def check_image_png() -> str:
    """A 32x32 grey PNG, base64 — small, but not below the minimum size vision models accept."""
    import base64
    import struct
    import zlib

    width = height = 32
    rows = b"".join(b"\x00" + b"\x80\x80\x80" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii")


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
        model: str | None = None,
    ):
        """
        Initialize the provider.

        Args:
            api_key: API key for authentication
            base_url: Optional custom base URL
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            model: Model used when a call passes none. There is no built-in
                default: without it, every call must pass ``model=``.
        """
        self._api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._model = model or None

    @property
    def api_key(self) -> str:
        """API key used for authentication.

        Exposed read-only and stored as a non-public attribute to discourage
        accidental mutation and to keep it out of naive attribute dumps.
        """
        return self._api_key

    def _learning_scope(self, endpoint: str) -> str:
        """Key under which ``param_learning`` remembers rejections: endpoint plus API-key fingerprint."""
        from eq_chatbot_core.providers import param_learning  # local: providers/__init__ imports this module

        return param_learning.scope(endpoint, getattr(self, "_api_key", None))

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'anthropic')."""
        ...

    @property
    def default_model(self) -> str | None:
        """The model set on this instance (constructor ``model=``), or ``None``."""
        return getattr(self, "_model", None)

    def resolve_model(self, model: str | None = None) -> str:
        """Return the model for one call: ``model`` if given, else the instance's.

        Raises:
            ModelNotSpecifiedError: If neither names a model.
        """
        resolved = model or self.default_model
        if not resolved:
            raise ModelNotSpecifiedError(self.provider_name)
        return resolved

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
            model: Model to use; falls back to the constructor's ``model``.
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
            model: Model to use; falls back to the constructor's ``model``.
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

    # Class-level flag — subclasses override to True when they support image generation.
    supports_image_generation: bool = False

    def generate_image(
        self,
        prompt: str,
        *,
        model: str | None = None,
        size: str = "1024x1024",
        **kwargs: Any,
    ) -> "ImageResult":
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the image to generate
            model: Image model to use; falls back to the constructor's ``image_model``.
            size: Image dimensions (e.g. '1024x1024')
            **kwargs: Additional provider-specific parameters

        Returns:
            ImageResult with image bytes and metadata

        Raises:
            ProviderError: If the provider does not support image generation or on API error
        """
        raise ProviderError(
            f"{self.provider_name} does not support image generation",
            provider=self.provider_name,
        )

    # Output limit sent by probe_output_limit(): above every model's real limit, so
    # the provider rejects the request and names the limit instead of generating.
    PROBE_MAX_TOKENS: int = 10_000_000

    def _limit_scope(self) -> str | None:
        """The ``param_learning`` scope that holds this provider's learned limits.

        ``None`` for providers that learn nothing at runtime.
        """
        return None

    def learned_limits(self, model: str | None = None) -> dict[str, int]:
        """Limits a rejection stated for ``model`` on this endpoint and API key.

        Keys are ``max_output_tokens`` and ``context_length``; a key is present
        only when the provider named the number (in a rejection or a probe). The
        memory lives in this process only — persist the values to keep them.
        """
        scope = self._limit_scope()
        if scope is None:
            return {}
        from eq_chatbot_core.providers import param_learning  # local: providers/__init__ imports this module

        return param_learning.learned_limits(scope, self.resolve_model(model))

    def probe_output_limit(self, model: str | None = None) -> int | None:
        """The model's output limit, asked from the provider without generating text.

        Providers that support it send one request with an output limit far above
        any real one (``PROBE_MAX_TOKENS``); the provider rejects it and names the
        limit, which costs nothing and is remembered like a learned limit. Returns
        ``None`` when the provider accepts the request (it is closed at once) or
        rejects it without naming a number. A limit learned earlier is returned
        without a request. The base implementation sends nothing.

        Raises:
            ProviderError: On errors other than the rejection (authentication,
                rate limit, network).
        """
        return self.learned_limits(model).get("max_output_tokens")

    def _probe_outcome(self, model: str, error: Exception) -> int | None:
        """Result of a probe request that raised ``error``: the stated limit, ``None``, or a raise."""
        limit = self.learned_limits(model).get("max_output_tokens")
        if limit:
            return limit
        status = getattr(error, "status_code", None)
        # A rejection without a number: HTTP 400/422, or an error event inside the
        # stream (no status, but a body — unlike a connection error).
        if status in (400, 422) or (status is None and getattr(error, "body", None) is not None):
            return None
        handle_error = getattr(self, "_handle_error", None)
        if isinstance(error, ProviderError) or handle_error is None:
            raise error
        raise handle_error(error) from error

    # --- learned adjustments ------------------------------------------------------

    def learned_adjustments(self, model: str | None = None) -> list[str]:
        """Request adjustments learned for ``model`` on this endpoint and API key.

        Names from ``param_learning.LEARNABLE``. The memory lives in this process
        only — persist the list (``check_model`` returns it) and restore it with
        ``seed_adjustments``.
        """
        scope = self._limit_scope()
        if scope is None:
            return []
        from eq_chatbot_core.providers import param_learning  # local: providers/__init__ imports this module

        return param_learning.learned_adjustments(scope, self.resolve_model(model))

    def seed_adjustments(self, model: str, adjustments: "list[str] | tuple[str, ...]") -> None:
        """Restore adjustments persisted from an earlier ``check_model`` or ``learned_adjustments``."""
        scope = self._limit_scope()
        if scope is None or not adjustments:
            return
        from eq_chatbot_core.providers import param_learning  # local: providers/__init__ imports this module

        param_learning.seed_adjustments(scope, model, adjustments)

    # --- check_model ----------------------------------------------------------------

    def check_model(
        self,
        model: str | None = None,
        *,
        temperature: float | None = 0.7,
        max_tokens: int | None = None,
        tools: bool = True,
        vision: bool = True,
        web_search: bool = True,
        probe_limit: bool = True,
        **kwargs: Any,
    ) -> ModelCheck:
        """Find out what ``model`` accepts, with a few small requests, before a chat needs it.

        Steps, each a streamed request shaped like a chat turn (system and user
        message, the caller's ``temperature`` and extra ``kwargs``, an output limit
        of at most ``CHECK_MAX_TOKENS``): plain text, then with one function tool
        (``tools``), then with a small image (``vision``), then with the
        provider's built-in web search switched on (``web_search``, only where
        ``supports_native_web_search``; the model is not asked to search, so it
        costs no search). These are only tried once plain text works. Finally the output limit is asked for
        (``probe_limit``, see ``probe_output_limit``).

        A rejection the library does not recognise is explored: the request is
        tried once more unchanged, then with each adjustment the error suggests
        (see ``param_learning.exploring``). What works is remembered and returned
        in ``ModelCheck.adjustments``. Adjustments learned earlier are forgotten
        first, so a model the provider has changed is noticed.

        Cost: the plain step and each accepted step generate at most a few
        hundred tokens; refused requests are not generated at all.

        Never raises for a provider's answer; a missing model raises
        ``ModelNotSpecifiedError``.
        """
        model = self.resolve_model(model)
        from eq_chatbot_core.providers import param_learning  # local: providers/__init__ imports this module

        scope = self._limit_scope()
        if scope is not None:
            param_learning.forget_adjustments(scope, model)
        result = ModelCheck(model=model)
        limit = min(max_tokens or CHECK_MAX_TOKENS, CHECK_MAX_TOKENS)
        system = {"role": "system", "content": CHECK_SYSTEM}

        def step(name: str, user_content: Any, step_tools: list[dict[str, Any]] | None, **extra: Any) -> str:
            messages = [system, {"role": "user", "content": user_content}]
            state, message = self._check_step(model, messages, temperature, limit, step_tools, {**kwargs, **extra})
            setattr(result, name, state)
            if message:
                result.messages[name] = message
            return state

        if step("text", "Reply with OK.", None) == "ok":
            if tools:
                step("tools", "What time is it in Berlin? Use the tool if you can.", [CHECK_TOOL])
            if vision:
                image = self._check_image_part(check_image_png())
                step("vision", [{"type": "text", "text": "Which colour is this image?"}, image], None)
            if web_search and self.supports_native_web_search():
                step("web_search", "Reply with OK.", None, web_search=True)
            if probe_limit:
                try:
                    self.probe_output_limit(model)
                except Exception as error:  # noqa: BLE001 - the limit simply stays unknown
                    result.messages["limit"] = self._check_message(error)
        if scope is not None:
            result.adjustments = param_learning.learned_adjustments(scope, model)
            result.limits = param_learning.learned_limits(scope, model)
        return result

    def _check_step(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        kwargs: dict[str, Any],
    ) -> tuple[str, str]:
        """One check request, streamed to the end; ``(state, provider message)``."""
        from eq_chatbot_core.providers import param_learning  # local: providers/__init__ imports this module

        call_kwargs = dict(kwargs)
        if temperature is not None:
            call_kwargs["temperature"] = temperature
        with param_learning.exploring():
            try:
                for _chunk in self.stream_completion(
                    messages, model=model, max_tokens=max_tokens, tools=tools, **call_kwargs
                ):
                    pass
            except Exception as error:  # noqa: BLE001 - the verdict is the result
                state = "refused" if param_learning.is_rejection(error) else "error"
                return state, self._check_message(error)
        return "ok", ""

    @staticmethod
    def _check_message(error: BaseException) -> str:
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        return scrub_secrets(str(error))[:500]

    def supports_native_web_search(self) -> bool:
        """Whether this provider offers a built-in web search (``web_search=True``).

        The search runs at the provider, which also bills it. Whether a given
        model and account may use it is found out by ``check_model``.
        Providers without one ignore ``web_search``.
        """
        return False

    def _check_image_part(self, png_base64: str) -> dict[str, Any]:
        """The image of the vision step, in the message format this provider expects."""
        return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_base64}"}}

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


class ModelNotSpecifiedError(ProviderError):
    """Raised when a call needs a model and neither the call nor the provider names one.

    The library ships no default model: model IDs change faster than releases.
    """

    def __init__(
        self,
        provider: str,
        *,
        what: str = "model",
        argument: str = "model",
        constructor_argument: str = "model",
        hint: str | None = None,
    ):
        instruction = hint or (
            f'Pass {argument}="..." to this call, or {constructor_argument}="..." when creating the provider: '
            f'get_provider("{provider}", ..., {constructor_argument}="...").'
        )
        super().__init__(f'No {what} specified for provider "{provider}". {instruction}', provider)
        self.what = what


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


__all__ = [
    "LLMResponse",
    "ImageResult",
    "StreamChunk",
    "ToolDefinition",
    "ModelInfo",
    "ModelCheck",
    "BaseLLMProvider",
    "ProviderError",
    "ModelNotSpecifiedError",
    "RateLimitError",
    "AuthenticationError",
    "ContextLengthError",
    "OverloadedError",
]
