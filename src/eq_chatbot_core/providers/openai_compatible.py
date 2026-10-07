"""
Shared implementation for providers speaking the OpenAI Chat Completions API.

Several gateways (IONOS AI Model Hub, Melious.ai, LiteLLM/vLLM proxies) expose an
endpoint that is wire-compatible with OpenAI and are therefore driven by the same
``openai`` SDK code. Before this base class existed, each provider carried a
byte-identical copy of ``chat_completion`` / ``stream_completion`` /
``list_models`` / ``_handle_error`` — which meant every hardening fix had to be
applied N times and was, in practice, applied inconsistently.

Subclasses configure behaviour through class attributes and normally only need to
declare those; override a method solely where the gateway genuinely differs.

Example:
    class MyGatewayProvider(OpenAICompatibleProvider):
        PROVIDER_NAME = "mygateway"
        DEFAULT_BASE_URL = "https://api.example.com/v1"
        DEFAULT_MODEL = "some-model"
"""

import logging
from collections.abc import Iterator
from typing import Any, ClassVar, TypeVar

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    OverloadedError,
    ProviderError,
    RateLimitError,
    StreamChunk,
    ToolDefinition,
    normalize_tools,
)
from eq_chatbot_core.providers.stream_accumulator import ToolCallAccumulator
from eq_chatbot_core.providers.temperature_constraints import clamp_temperature
from eq_chatbot_core.utils.secret_scrub import scrub_secrets

_logger = logging.getLogger(__name__)

_Self = TypeVar("_Self", bound="OpenAICompatibleProvider")


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Base class for OpenAI-wire-compatible providers driven by the ``openai`` SDK.

    Class attributes:
        PROVIDER_NAME: Value returned by :attr:`provider_name`.
        DEFAULT_BASE_URL: Endpoint used when the caller passes no ``base_url``.
            Set to ``None`` for gateways that have no meaningful default and must
            receive an explicit endpoint (e.g. a self-hosted LiteLLM proxy).
        DEFAULT_MODEL: Soft default model id, overridable per call or via the
            ``model`` constructor argument.
        ALLOW_PRIVATE_RANGES: Passed to the SSRF guard. ``False`` for fixed public
            cloud endpoints; ``True`` for gateways that may legitimately live on a
            LAN. Cloud-metadata and link-local targets stay blocked either way.
        MISSING_BASE_URL_MESSAGE: Error text raised when ``DEFAULT_BASE_URL`` is
            ``None`` and the caller supplied no ``base_url``.
        _validate_default_url: Validate ``DEFAULT_BASE_URL`` at construction too.
            ``False`` for providers that never did a DNS lookup for their
            built-in default; the pinned transport validates it on first use.

    Extension hooks (override only where the gateway genuinely differs):
        ``_token_param``, ``_default_headers``, ``_client_kwargs``,
        ``_error_from_message``.
    """

    PROVIDER_NAME: ClassVar[str] = ""
    DEFAULT_BASE_URL: ClassVar[str | None] = None
    DEFAULT_MODEL: ClassVar[str] = ""
    ALLOW_PRIVATE_RANGES: ClassVar[bool] = False
    # Ask for token usage in streams. Off for servers that reject the option.
    STREAM_INCLUDE_USAGE: ClassVar[bool] = True
    MISSING_BASE_URL_MESSAGE: ClassVar[str] = (
        "This provider requires an explicit base_url; there is no default endpoint."
    )
    # Validate DEFAULT_BASE_URL at construction too. True keeps the behaviour of
    # the providers that already inherit this class; providers that never did a
    # DNS lookup for their built-in default set it False.
    _validate_default_url: ClassVar[bool] = True

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
            api_key: API key sent as ``Authorization: Bearer <api_key>``.
            base_url: OpenAI-compatible endpoint. Falls back to
                ``DEFAULT_BASE_URL``; required when that is ``None``.
            timeout: Request timeout in seconds.
            max_retries: Number of retries on transient failures.
            model: Default model id for this instance (overridable per call).
                Falls back to ``DEFAULT_MODEL`` when not given.

        Raises:
            ValueError: If ``base_url`` is missing/empty with no default
                available, or if it fails URL validation.
        """
        # Initialize the client attribute BEFORE validation so close()/__del__
        # stay safe if the SSRF guard below raises.
        self._client: Any = None  # Lazy initialization

        effective_base_url = base_url or self.DEFAULT_BASE_URL
        if not effective_base_url or not effective_base_url.strip():
            raise ValueError(self.MISSING_BASE_URL_MESSAGE)

        # SSRF guard: a caller-supplied base_url is validated now. A built-in
        # default costs no DNS round-trip until the client is created — the
        # pinned transport validates it then. Imported lazily (import cycle).
        if base_url or self._validate_default_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(effective_base_url, allow_private_ranges=self.ALLOW_PRIVATE_RANGES)

        super().__init__(api_key, effective_base_url, timeout, max_retries)
        # Keep the validated URL under a non-optional type: the base attribute
        # is `str | None`, but construction fails above when it would be empty.
        self._effective_base_url: str = effective_base_url
        self._model = model

    @property
    def provider_name(self) -> str:
        return self.PROVIDER_NAME

    @property
    def default_model(self) -> str:
        return self._model or self.DEFAULT_MODEL

    @property
    def client(self) -> Any:
        """Lazy initialization of the OpenAI-compatible client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Install with: pip install openai") from e

            # Route the SDK through an httpx client whose transport re-checks DNS
            # on every connect. Without it the constructor's validate_url() only
            # covers one point in time and an attacker-controlled hostname can
            # re-resolve to an internal address before the socket opens.
            import httpx2

            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self._sdk_max_retries(),
                default_headers=self._default_headers() or None,
                http_client=httpx2.Client(
                    transport=build_pinned_transport_for_url(
                        self._effective_base_url,
                        allow_private_ranges=self.ALLOW_PRIVATE_RANGES,
                    ),
                    timeout=self.timeout,
                ),
                **self._client_kwargs(),
            )
        return self._client

    def _sdk_max_retries(self) -> int:
        """Retry count handed to the OpenAI SDK (it retries 429/5xx, timeouts and connection errors)."""
        return self.max_retries

    def _default_headers(self) -> dict[str, str]:
        """Extra HTTP headers for every request (e.g. OpenRouter attribution)."""
        return {}

    def _client_kwargs(self) -> dict[str, Any]:
        """Extra keyword arguments for the ``openai.OpenAI`` constructor."""
        return {}

    def _token_param(self, model: str) -> str:
        """Initial guess for the output-limit parameter name.

        Runtime learning (``param_learning``) corrects a wrong guess; this only
        saves the first failed request where a provider already knows better.
        """
        return "max_tokens"

    def _build_params(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Assemble the request payload shared by chat and streaming calls."""
        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # Clamp temperature per model constraints (skip for reasoning models)
        clamped = clamp_temperature(model, temperature)
        if clamped is not None:
            params["temperature"] = clamped

        if max_tokens:
            params[self._token_param(model)] = max_tokens

        if tools:
            params["tools"] = tools

        params.update(kwargs)
        return params

    def _create(self, params: dict[str, Any]) -> Any:
        """``chat.completions.create`` that learns unsupported parameters.

        A 400 naming ``temperature`` or ``max_tokens`` as unsupported is retried
        with that parameter adjusted — at most once per parameter — and the fact
        is remembered for this endpoint and model (see ``param_learning``). For
        streaming the rejection arrives before the first chunk, so no output is
        ever duplicated.
        """
        model = params["model"]
        param_learning.apply(self._effective_base_url, model, params)
        adjusted: set[str] = set()
        while True:
            try:
                return self.client.chat.completions.create(**params)
            except Exception as error:
                parameter = param_learning.rejected_parameter(error)
                if parameter is None or parameter in adjusted or not param_learning.adjust(params, parameter):
                    raise
                adjusted.add(parameter)
                param_learning.mark_unsupported(self._effective_base_url, model, parameter)
                _logger.info(
                    "%s: model %s rejected '%s'; retrying adjusted and remembering it for this endpoint",
                    self.provider_name,
                    model,
                    parameter,
                )

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request to the gateway."""
        model = model or self.default_model
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        try:
            params = self._build_params(messages, model, temperature, max_tokens, tools, **kwargs)

            response = self._create(params)

            # getattr: the SDK builds response models without validation, so a body
            # lacking `choices` yields an object without that attribute at all.
            if not getattr(response, "choices", None):
                # Local servers (LM Studio, Ollama) answer 200 with an `error`
                # body instead of choices, e.g. on context overflow.
                error = (getattr(response, "model_extra", None) or {}).get("error")
                if error:
                    message = error.get("message") if isinstance(error, dict) else None
                    if message is None:
                        message = str(error)
                    message = scrub_secrets(str(message))
                    body_dict = error if isinstance(error, dict) else {}
                    if _is_context_overflow(body_dict, message):
                        raise ContextLengthError(message, self.provider_name)
                    raise self._error_from_message(message)
                raise ProviderError(message="Response contained no choices", provider=self.provider_name)

            choice = response.choices[0]
            tool_calls = []

            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            # Note: reasoning models may also return a non-standard
            # `reasoning_content` field. It is preserved in raw_response below but
            # intentionally NOT merged into `content` (the answer != the thinking).
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

        except ProviderError:
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion response from the gateway."""
        model = model or self.default_model
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        try:
            params = self._build_params(messages, model, temperature, max_tokens, tools, **kwargs)
            params["stream"] = True
            if self.STREAM_INCLUDE_USAGE:
                params["stream_options"] = {"include_usage": True}

            stream = self._create(params)

            final_input_tokens = 0
            final_output_tokens = 0
            finish_reason: str | None = None
            tool_calls_acc = ToolCallAccumulator()

            # Content / tool deltas are streamed as they arrive (never marked
            # final). The authoritative final chunk is emitted AFTER the loop so
            # that trailing usage-only frames are always reflected — some gateways
            # send `finish_reason` and the usage totals in SEPARATE chunks, with
            # usage arriving last.
            for chunk in stream:
                if hasattr(chunk, "usage") and chunk.usage:
                    final_input_tokens = chunk.usage.prompt_tokens or 0
                    final_output_tokens = chunk.usage.completion_tokens or 0

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if choice.finish_reason is not None:
                    finish_reason = choice.finish_reason

                # Only the answer content is streamed as `content`; the optional
                # non-standard `reasoning_content` delta is not folded in.
                content = delta.content or ""

                tool_call_delta = None
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        tool_call_delta = {
                            "index": tc.index,
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name if tc.function else None,
                                "arguments": tc.function.arguments if tc.function else None,
                            },
                        }
                    tool_calls_acc.add(delta.tool_calls)

                if content or tool_call_delta is not None:
                    yield StreamChunk(
                        content=content,
                        is_final=False,
                        finish_reason=None,
                        tool_call_delta=tool_call_delta,
                    )

            complete_tool_calls = tool_calls_acc.result()

            yield StreamChunk(
                content="",
                is_final=True,
                finish_reason=finish_reason,
                tool_calls=complete_tool_calls,
                input_tokens=final_input_tokens,
                output_tokens=final_output_tokens,
            )

        except ProviderError:
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List models advertised by the gateway.

        Returns all models from the OpenAI-compatible ``/v1/models`` endpoint
        without provider-specific name filtering.
        """
        try:
            models = self.client.models.list()

            result = []
            for model in models.data:
                result.append(
                    {
                        "id": model.id,
                        "name": model.id,
                        "created": getattr(model, "created", None),
                        "owned_by": getattr(model, "owned_by", None),
                        "provider": self.provider_name,
                    }
                )

            result.sort(key=lambda m: m["id"])
            return result

        except Exception as e:
            raise self._handle_error(e) from e

    def _error_from_message(self, message: str) -> ProviderError:
        """Typed error for a provider message that carries no HTTP status."""
        return ProviderError(message=message, provider=self.provider_name)

    def _handle_error(self, error: Exception) -> ProviderError:
        """Map an SDK exception to the ProviderError hierarchy by HTTP status.

        Substring matching is a fallback for errors without a status only; the
        bare word "token" is deliberately not a criterion ("max_tokens is not
        supported" is not a context-length problem).
        """
        if isinstance(error, ProviderError):
            return error
        import openai

        message = scrub_secrets(str(error))
        provider = self.provider_name
        raw_body = getattr(error, "body", None)
        body: dict[str, Any] = raw_body if isinstance(raw_body, dict) else {}

        if isinstance(error, openai.APIStatusError):
            status = error.status_code
            if status == 429:
                return RateLimitError(message, provider, status_code=429, retry_after=_retry_after(error.response))
            if status in (401, 403):
                return AuthenticationError(message, provider, status_code=status)
            if status in (503, 529):
                return OverloadedError(message, provider, status_code=status)
            if status == 400 and _is_context_overflow(body, message):
                return ContextLengthError(message, provider, status_code=400)
            return ProviderError(message, provider, status_code=status)

        if isinstance(error, openai.APIError):  # error event inside a stream: no status
            if _is_context_overflow(body, message):
                return ContextLengthError(message, provider)
            return self._error_from_message(message)

        lowered = message.lower()
        if "rate limit" in lowered:
            return RateLimitError(message, provider)
        if "context length" in lowered:
            return ContextLengthError(message, provider)
        return ProviderError(message, provider)

    def close(self) -> None:
        """Close the underlying HTTP client, if initialized."""
        if getattr(self, "_client", None) is not None:
            self._client.close()
            self._client = None

    def __del__(self) -> None:
        try:
            self.close()
        except (OSError, RuntimeError):
            pass  # interpreter shutdown

    def __enter__(self: _Self) -> _Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _retry_after(response: Any) -> int | None:
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _is_context_overflow(body: dict[str, Any], message: str) -> bool:
    """OpenAI's code, or the phrasing gateways use when they relay without a code."""
    if body.get("code") == "context_length_exceeded":
        return True
    lowered = message.lower()
    return "context length" in lowered or "context_length" in lowered or "maximum context" in lowered
