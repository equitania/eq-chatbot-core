"""
Local LLM provider implementation for LM Studio and Ollama.

Supports local LLM servers that expose OpenAI-compatible APIs:
- LM Studio: http://localhost:1234/v1
- Ollama: http://localhost:11434/v1

Both servers implement the OpenAI Chat Completions API format,
making them interchangeable via the base_url parameter.
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
    ToolDefinition,
    normalize_tools,
)
from eq_chatbot_core.providers.stream_accumulator import ToolCallAccumulator
from eq_chatbot_core.utils.secret_scrub import scrub_secrets

logger = logging.getLogger(__name__)


class LocalLLMProvider(BaseLLMProvider):
    """
    Unified provider for local LLM servers (LM Studio, Ollama).

    Both LM Studio and Ollama expose OpenAI-compatible APIs, so this
    provider works with either by setting the appropriate base_url:

    - LM Studio: http://localhost:1234/v1 (default)
    - Ollama: http://localhost:11434/v1

    Example:
        # LM Studio
        provider = LocalLLMProvider(
            api_key="not-used",
            base_url="http://localhost:1234/v1"
        )

        # Ollama
        provider = LocalLLMProvider(
            api_key="not-used",
            base_url="http://localhost:11434/v1"
        )
    """

    # Default URLs for common local LLM servers
    LM_STUDIO_URL = "http://localhost:1234/v1"
    OLLAMA_URL = "http://localhost:11434/v1"

    # Default timeout is higher for local servers (model loading can be slow)
    DEFAULT_TIMEOUT = 120.0

    def __init__(
        self,
        api_key: str = "not-used",
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 2,
    ):
        """
        Initialize the local LLM provider.

        Args:
            api_key: API key (usually not required for local servers, defaults to "not-used")
            base_url: Server URL (defaults to LM Studio URL)
            timeout: Request timeout in seconds (defaults to 120s for model loading)
            max_retries: Number of retries on transient failures
        """
        # Initialize client attribute BEFORE validation so __del__ works even if
        # construction fails on an invalid base_url.
        self._client: httpx.Client | None = None

        effective_base_url = base_url or self.LM_STUDIO_URL
        # SSRF guard: local servers legitimately live on localhost/LAN, so private
        # ranges are allowed — but reject non-HTTP schemes and cloud-metadata /
        # link-local targets (e.g. 169.254.169.254) that a hostile base_url could aim at.
        # Imported lazily to avoid a providers<->utils<->services import cycle.
        from eq_chatbot_core.utils.url_validation import validate_url

        validate_url(effective_base_url, allow_private_ranges=True)

        super().__init__(
            api_key=api_key,
            base_url=effective_base_url,
            timeout=timeout or self.DEFAULT_TIMEOUT,
            max_retries=max_retries,
        )

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def default_model(self) -> str:
        return "local-model"

    @property
    def client(self) -> httpx.Client:
        """Lazy initialization of httpx client."""
        if self._client is None:
            # Pin the validated addresses for the lifetime of the client: the
            # constructor's validate_url() only covers the resolution at that
            # moment, so without this an attacker-supplied hostname could
            # re-resolve to an internal target before the socket is opened.
            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            # __init__ always passes `base_url or LM_STUDIO_URL` to super(), so
            # this is never None despite the base attribute's wider type.
            base_url = self.base_url or self.LM_STUDIO_URL
            self._client = httpx.Client(
                base_url=base_url,
                transport=build_pinned_transport_for_url(base_url, allow_private_ranges=True),
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _get_server_type(self) -> str:
        """Detect server type based on base_url."""
        if self.base_url and "11434" in self.base_url:
            return "ollama"
        return "lm_studio"

    @staticmethod
    def _extract_error_message(data: Any) -> str | None:
        """Extract an error message from a local-server response body.

        LM Studio / Ollama may return HTTP 200 while signalling failures via an
        ``error`` field in the JSON body (chat) or SSE event (stream), e.g. when
        the prompt exceeds the model's context length. Returns the message string
        or ``None`` when no error is present.
        """
        if not isinstance(data, dict):
            return None
        err = data.get("error")
        if not err:
            return None
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)

    def _error_from_message(self, message: str) -> ProviderError:
        """Build the right exception type for a server-side error message."""
        lowered = message.lower()
        if "context" in lowered or "token" in lowered:
            return ContextLengthError(
                message=f"Context length exceeded: {message}",
                provider=self.provider_name,
            )
        return ProviderError(message=message, provider=self.provider_name)

    def _handle_error(self, error: Exception, response: httpx.Response | None = None) -> ProviderError:
        """Convert HTTP errors to provider-specific exceptions."""
        status_code = response.status_code if response else None

        if status_code == 401:
            return AuthenticationError(
                message="Authentication failed (local server may require API key)",
                provider=self.provider_name,
                status_code=status_code,
            )
        elif status_code == 429:
            retry_after = None
            if response and "retry-after" in response.headers:
                try:
                    retry_after = int(response.headers["retry-after"])
                except ValueError:
                    pass
            return RateLimitError(
                message="Rate limit exceeded on local server",
                provider=self.provider_name,
                status_code=status_code,
                retry_after=retry_after,
            )
        elif status_code == 400:
            error_msg = str(error)
            if "context" in error_msg.lower() or "token" in error_msg.lower():
                return ContextLengthError(
                    message=f"Context length exceeded: {error_msg}",
                    provider=self.provider_name,
                    status_code=status_code,
                )

        # Generic provider error
        return ProviderError(
            message=str(error),
            provider=self.provider_name,
            status_code=status_code,
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
        """
        Send a chat completion request to the local LLM server.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (local servers typically have one model loaded)
            temperature: Sampling temperature (may not be supported by all models)
            max_tokens: Maximum tokens to generate
            tools: Tool definitions (not supported by most local models)
            **kwargs: Additional parameters passed to the API

        Returns:
            LLMResponse with the generated content

        Raises:
            ProviderError: On API errors or connection failures
        """
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)
        model = model or self.default_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Tools are generally not supported by local models, but pass through if provided
        if tools:
            payload["tools"] = tools

        payload.update(kwargs)

        try:
            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            # Local servers (LM Studio/Ollama) may return HTTP 200 with an
            # ``error`` object in the body (e.g. prompt exceeds context length).
            # Surface it instead of crashing on the missing ``choices`` key.
            error_msg = self._extract_error_message(data)
            if error_msg:
                raise self._error_from_message(error_msg)

            choice = data["choices"][0]
            message = choice.get("message", {})

            # Extract usage if available (some local servers don't provide this)
            usage = data.get("usage", {})

            # Handle tool calls if present
            tool_calls = []
            if message.get("tool_calls"):
                tool_calls = message["tool_calls"]

            return LLMResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason"),
                tool_calls=tool_calls,
                raw_response=data,
            )

        except httpx.ConnectError as e:
            raise ProviderError(
                message=f"Cannot connect to local LLM server at {scrub_secrets(self.base_url or self.LM_STUDIO_URL)}. "
                f"Ensure the server is running. Error: {scrub_secrets(str(e))}",
                provider=self.provider_name,
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderError(
                message=f"Request timed out after {self.timeout}s. "
                f"Local model may be loading or server is slow. Error: {scrub_secrets(str(e))}",
                provider=self.provider_name,
            ) from e
        except ProviderError:
            # Already a typed provider error (e.g. server-side error body) — pass through.
            raise
        except httpx.HTTPStatusError as e:
            raise self._handle_error(e, e.response) from e
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
        """
        Stream a chat completion response from the local LLM server.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Tool definitions (not supported by most local models)
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content deltas

        Raises:
            ProviderError: On API errors or connection failures
        """
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)
        model = model or self.default_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = tools

        payload.update(kwargs)

        try:
            with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                accumulated_content = ""
                accumulated_tokens = 0
                # Accumulate streamed tool-call fragments by index so the final
                # chunk can expose complete tool_calls (mirrors openai_provider).
                # Without this, stream.py (which reads chunk.tool_calls) never sees
                # any tool call and the IHA tool loop never runs for local models.
                tool_calls_acc = ToolCallAccumulator()

                for line in response.iter_lines():
                    if not line:
                        continue

                    # SSE format: "data: {...}"
                    if line.startswith("data: "):
                        data_str = line[6:]

                        # Handle stream end marker
                        if data_str.strip() == "[DONE]":
                            # Yield final chunk (include any accumulated tool calls)
                            complete_tool_calls = tool_calls_acc.result()
                            yield StreamChunk(
                                content="",
                                is_final=True,
                                finish_reason="tool_calls" if complete_tool_calls else "stop",
                                tool_calls=complete_tool_calls,
                                output_tokens=accumulated_tokens,
                            )
                            break

                        try:
                            data = json.loads(data_str)
                            # LM Studio/Ollama signal failures (e.g. prompt exceeds
                            # context length) via an ``error`` field in the SSE body
                            # while the HTTP status stays 200. Surface it instead of
                            # silently yielding empty content (which looks like a
                            # blank chat reply to the user).
                            error_msg = self._extract_error_message(data)
                            if error_msg:
                                raise self._error_from_message(error_msg)
                            choice = data.get("choices", [{}])[0]
                            delta = choice.get("delta", {})

                            content = delta.get("content", "")
                            finish_reason = choice.get("finish_reason")

                            if content:
                                accumulated_content += content
                                accumulated_tokens += 1  # Approximate token count

                            # Handle tool call deltas (OpenAI-compatible chunked format):
                            # each delta carries partial {index, id, function:{name, arguments}}.
                            tool_call_delta = None
                            if delta.get("tool_calls"):
                                tool_call_delta = delta["tool_calls"]
                                tool_calls_acc.add(delta["tool_calls"])

                            is_final = finish_reason is not None

                            # On the final chunk, expose the fully accumulated tool calls.
                            complete_tool_calls = tool_calls_acc.result() if is_final else None

                            yield StreamChunk(
                                content=content,
                                is_final=is_final,
                                finish_reason=finish_reason,
                                tool_call_delta=tool_call_delta,
                                tool_calls=complete_tool_calls,
                                output_tokens=accumulated_tokens if is_final else 0,
                            )

                            if is_final:
                                break

                        except json.JSONDecodeError:
                            # Skip malformed JSON lines
                            continue

        except httpx.ConnectError as e:
            raise ProviderError(
                message=f"Cannot connect to local LLM server at {scrub_secrets(self.base_url or self.LM_STUDIO_URL)}. "
                f"Ensure the server is running. Error: {scrub_secrets(str(e))}",
                provider=self.provider_name,
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderError(
                message=f"Stream timed out after {self.timeout}s. Error: {scrub_secrets(str(e))}",
                provider=self.provider_name,
            ) from e
        except ProviderError:
            # Already a typed provider error (e.g. server-side error body) — pass through.
            raise
        except httpx.HTTPStatusError as e:
            raise self._handle_error(e, e.response) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models from the local LLM server.

        Note: Local servers may have limited model metadata.
        LM Studio typically has one model loaded at a time.
        Ollama can list all downloaded models.

        Returns:
            List of model dicts with 'id' and 'name' keys
        """
        try:
            response = self.client.get("/models")
            response.raise_for_status()
            data = response.json()

            models = []
            for model_data in data.get("data", []):
                model_id = model_data.get("id", "unknown")
                models.append(
                    {
                        "id": model_id,
                        "name": model_id,
                        "provider": self.provider_name,
                        "context_length": model_data.get("context_length"),
                        "supports_streaming": True,
                        "supports_tools": False,  # Most local models don't support tools
                        "supports_vision": False,  # Most local models don't support vision
                        "owned_by": model_data.get("owned_by", "local"),
                        "created": model_data.get("created"),
                    }
                )

            return models

        except httpx.ConnectError as e:
            raise ProviderError(
                message=f"Cannot connect to local LLM server at {scrub_secrets(self.base_url or self.LM_STUDIO_URL)}. "
                f"Ensure the server is running. Error: {scrub_secrets(str(e))}",
                provider=self.provider_name,
            ) from e
        except ProviderError:
            # Already a typed provider error (e.g. server-side error body) — pass through.
            raise
        except httpx.HTTPStatusError as e:
            raise self._handle_error(e, e.response) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def is_server_available(self) -> bool:
        """
        Check if the local LLM server is available.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            response = self.client.get("/models")
            return response.status_code == 200
        except (httpx.HTTPError, ConnectionError, OSError, TimeoutError) as e:
            logger.debug("Local server health check failed: %s", e)
            return False

    def __del__(self) -> None:
        """Clean up httpx client on deletion."""
        if self._client is not None:
            self._client.close()
