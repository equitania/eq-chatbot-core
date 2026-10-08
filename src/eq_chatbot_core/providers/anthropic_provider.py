"""
Anthropic provider implementation.
"""

import json
import logging
import time
from collections.abc import Iterator
from contextlib import ExitStack
from typing import Any

from eq_chatbot_core.providers.anthropic_shared import create_message, list_anthropic_models, open_message_stream
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
from eq_chatbot_core.providers.temperature_constraints import apply_anthropic_temperature

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Messages API provider.

    Pass the model per call or as ``model=`` to the constructor; ``list_models()``
    returns the ids the account can use.
    """

    DEFAULT_BASE_URL = "https://api.anthropic.com"

    # Retry configuration for transient errors (overloaded)
    OVERLOAD_MAX_RETRIES = 3
    OVERLOAD_BASE_DELAY = 2.0  # Initial delay in seconds
    OVERLOAD_MAX_DELAY = 30.0  # Maximum delay in seconds

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
    ):
        # Initialize the client attribute BEFORE validation so close()/__del__
        # stay safe if the SSRF guard below raises.
        self._client: Any = None

        # SSRF guard: only a caller-supplied base_url is validated — the fixed
        # public default needs no DNS round-trip. Private ranges are rejected
        # because Anthropic is a public cloud endpoint. Imported lazily to avoid
        # an import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        super().__init__(api_key, base_url, timeout, max_retries, model)

    def _should_retry_error(self, error: Exception) -> bool:
        """Check if an error is retryable (overloaded, temporary failures)."""
        error_str = str(error).lower()
        return "overloaded" in error_str or "529" in error_str

    def _get_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        import random

        delay: float = min(self.OVERLOAD_BASE_DELAY * (2**attempt), self.OVERLOAD_MAX_DELAY)
        # Add jitter (±25%)
        jitter: float = delay * 0.25 * (2 * random.random() - 1)
        return delay + jitter

    def _endpoint(self) -> str:
        """Endpoint key for parameter learning."""
        return self.base_url or self.DEFAULT_BASE_URL

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def client(self) -> Any:
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise ImportError("Anthropic package not installed. Install with: pip install anthropic") from e

            # Route the SDK through an httpx client whose transport re-checks DNS
            # on every connect. Without it the constructor's validate_url() only
            # covers one point in time and an attacker-controlled hostname can
            # re-resolve to an internal address before the socket opens.
            import httpx2

            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            effective_url = self.base_url or self.DEFAULT_BASE_URL
            self._client = Anthropic(
                api_key=self.api_key,
                base_url=effective_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                http_client=httpx2.Client(
                    transport=build_pinned_transport_for_url(effective_url),
                    timeout=self.timeout,
                ),
            )
        return self._client

    def _extract_system_prompt(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | list[dict[str, Any]] | None, list[dict[str, Any]]]:
        """
        Extract system prompt from messages.

        Anthropic requires system prompt as a separate parameter. Two output
        shapes are supported, picked automatically:

        * Plain string (legacy path): used when no system message carries a
          ``cache_control`` hint. Cheapest path, preserves the original
          single-string behaviour for callers that don't opt in to caching.
        * List of content blocks (prompt-caching path): used when ANY system
          message carries a ``cache_control`` value. Each system message
          contributes a ``{"type": "text", "text": ..., "cache_control": ...}``
          block; messages without a hint emit a plain text block. Anthropic
          caches all prefix blocks up to and including the last one tagged
          ``cache_control`` (5 min TTL for ``ephemeral``).
        """
        text_parts: list[tuple[str, dict[str, Any] | None]] = []
        filtered_messages: list[dict[str, Any]] = []
        any_cache_control = False

        for msg in messages:
            if msg.get("role") != "system":
                filtered_messages.append(msg)
                continue

            cc = msg.get("cache_control")
            if cc is not None:
                any_cache_control = True

            # Normalise content: callers may already pass a list of content
            # blocks (e.g. when constructing the prompt programmatically) —
            # in that case, harvest the text payloads and concat them.
            content = msg.get("content", "")
            if isinstance(content, list):
                text = "\n\n".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                text = str(content)
            text_parts.append((text, cc))

        if not text_parts:
            return None, filtered_messages

        if not any_cache_control:
            # Legacy fast path — plain string.
            return "\n\n".join(t for t, _ in text_parts), filtered_messages

        # Prompt-caching path — emit content blocks.
        blocks: list[dict[str, Any]] = []
        for text, cc in text_parts:
            block: dict[str, Any] = {"type": "text", "text": text}
            if cc is not None:
                block["cache_control"] = cc
            blocks.append(block)
        return blocks, filtered_messages

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert OpenAI-style messages to Anthropic format.

        Key conversions:
        - assistant messages with tool_calls -> content with tool_use blocks
        - tool messages -> user messages with tool_result content blocks
        """
        converted = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "assistant" and msg.get("tool_calls"):
                # Convert assistant message with tool_calls to Anthropic format
                content_blocks = []

                # Add text content if present
                if content:
                    content_blocks.append({"type": "text", "text": content})

                # Add tool_use blocks for each tool call
                for tool_call in msg.get("tool_calls", []):
                    func = tool_call.get("function", {})
                    arguments = func.get("arguments", "{}")

                    # Parse arguments - could be string or dict
                    if isinstance(arguments, str):
                        try:
                            parsed_args = json.loads(arguments)
                        except json.JSONDecodeError:
                            parsed_args = {"raw": arguments}
                    else:
                        parsed_args = arguments

                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tool_call.get("id", ""),
                            "name": func.get("name", ""),
                            "input": parsed_args,
                        }
                    )

                converted.append(
                    {
                        "role": "assistant",
                        "content": content_blocks,
                    }
                )

            elif role == "tool":
                # Convert tool message to user message with tool_result block
                tool_call_id = msg.get("tool_call_id", "")

                # Handle content that might be JSON or plain text
                result_content = content
                if isinstance(content, dict):
                    result_content = json.dumps(content)

                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": result_content,
                            }
                        ],
                    }
                )

            else:
                # Pass through user/assistant messages as-is
                converted.append(msg)

        return converted

    def _convert_tools_to_anthropic(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Convert OpenAI-style tools to Anthropic format."""
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append(
                    {
                        "name": func.get("name"),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )

        return anthropic_tools if anthropic_tools else None

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request to Anthropic with retry on overload."""
        model = self.resolve_model(model)
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        system_prompt, filtered_messages = self._extract_system_prompt(messages)
        # Convert OpenAI-style tool messages to Anthropic format
        filtered_messages = self._convert_messages(filtered_messages)
        anthropic_tools = self._convert_tools_to_anthropic(tools)

        params: dict[str, Any] = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": max_tokens or 4096,
        }

        apply_anthropic_temperature(params, temperature)

        if system_prompt:
            params["system"] = system_prompt

        if anthropic_tools:
            params["tools"] = anthropic_tools

        params.update(kwargs)

        last_error: Exception | None = None

        for attempt in range(self.OVERLOAD_MAX_RETRIES + 1):
            try:
                response = create_message(
                    self.client,
                    params,
                    base_url=self._learning_scope(self._endpoint()),
                    provider=self.provider_name,
                    logger=logger,
                )

                # Extract text content
                content = ""
                tool_calls = []

                for block in response.content:
                    if block.type == "text":
                        content += block.text
                    elif block.type == "tool_use":
                        # Serialize tool input as JSON string for downstream compatibility
                        arguments = json.dumps(block.input) if isinstance(block.input, dict) else str(block.input)
                        tool_calls.append(
                            {
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": arguments,
                                },
                            }
                        )

                return LLMResponse(
                    content=content,
                    model=response.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    finish_reason=response.stop_reason,
                    tool_calls=tool_calls,
                    raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
                )

            except Exception as e:
                last_error = e
                if self._should_retry_error(e) and attempt < self.OVERLOAD_MAX_RETRIES:
                    delay = self._get_retry_delay(attempt)
                    logger.warning(
                        f"Anthropic API overloaded, retry {attempt + 1}/{self.OVERLOAD_MAX_RETRIES} in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue
                # Non-retryable error or max retries reached
                raise self._handle_error(e) from e

        # Should not reach here, but just in case
        if last_error:
            raise self._handle_error(last_error) from last_error
        raise ProviderError(message="Unexpected error in chat_completion", provider=self.provider_name)

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion response from Anthropic with retry on overload."""
        model = self.resolve_model(model)
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        system_prompt, filtered_messages = self._extract_system_prompt(messages)
        # Convert OpenAI-style tool messages to Anthropic format
        filtered_messages = self._convert_messages(filtered_messages)
        anthropic_tools = self._convert_tools_to_anthropic(tools)

        params: dict[str, Any] = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": max_tokens or 4096,
        }

        apply_anthropic_temperature(params, temperature)

        if system_prompt:
            params["system"] = system_prompt

        if anthropic_tools:
            params["tools"] = anthropic_tools

        params.update(kwargs)

        last_error: Exception | None = None

        for attempt in range(self.OVERLOAD_MAX_RETRIES + 1):
            try:
                # Track usage for final chunk
                final_input_tokens = 0
                final_output_tokens = 0

                # Accumulate tool calls from stream events
                # Key: content block index, Value: tool call data
                accumulated_tool_calls: dict[int, dict[str, Any]] = {}
                current_block_index = 0

                with ExitStack() as stack:
                    stream = open_message_stream(
                        stack,
                        self.client,
                        params,
                        base_url=self._learning_scope(self._endpoint()),
                        provider=self.provider_name,
                        logger=logger,
                    )
                    for event in stream:
                        # Capture input tokens from message_start event
                        if event.type == "message_start":
                            if hasattr(event, "message") and hasattr(event.message, "usage"):
                                final_input_tokens = event.message.usage.input_tokens or 0

                        # Capture output tokens from message_delta event
                        elif event.type == "message_delta":
                            if hasattr(event, "usage"):
                                final_output_tokens = event.usage.output_tokens or 0

                        # Track content block index
                        elif event.type == "content_block_start":
                            current_block_index = getattr(event, "index", 0)
                            # Check if this is a tool_use block
                            if hasattr(event, "content_block"):
                                block = event.content_block
                                if hasattr(block, "type") and block.type == "tool_use":
                                    # Initialize tool call accumulator
                                    accumulated_tool_calls[current_block_index] = {
                                        "id": getattr(block, "id", ""),
                                        "type": "function",
                                        "function": {
                                            "name": getattr(block, "name", ""),
                                            "arguments": "",
                                        },
                                    }
                                    # Emit tool_call_delta for the start
                                    yield StreamChunk(
                                        content="",
                                        is_final=False,
                                        tool_call_delta={
                                            "index": current_block_index,
                                            "id": getattr(block, "id", ""),
                                            "function": {
                                                "name": getattr(block, "name", ""),
                                                "arguments": None,
                                            },
                                        },
                                    )

                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text"):
                                yield StreamChunk(
                                    content=delta.text,
                                    is_final=False,
                                )
                            # Handle tool input JSON deltas
                            elif hasattr(delta, "type") and delta.type == "input_json_delta":
                                partial_json = getattr(delta, "partial_json", "")
                                if current_block_index in accumulated_tool_calls:
                                    # Accumulate the JSON arguments
                                    accumulated_tool_calls[current_block_index]["function"]["arguments"] += partial_json
                                    # Emit tool_call_delta
                                    yield StreamChunk(
                                        content="",
                                        is_final=False,
                                        tool_call_delta={
                                            "index": current_block_index,
                                            "id": None,
                                            "function": {
                                                "name": None,
                                                "arguments": partial_json,
                                            },
                                        },
                                    )

                        elif event.type == "message_stop":
                            # Build complete tool calls list
                            complete_tool_calls = None
                            if accumulated_tool_calls:
                                complete_tool_calls = [
                                    accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())
                                ]

                            yield StreamChunk(
                                content="",
                                is_final=True,
                                finish_reason="end_turn",
                                tool_calls=complete_tool_calls,
                                input_tokens=final_input_tokens,
                                output_tokens=final_output_tokens,
                            )

                # Success - exit retry loop
                return

            except Exception as e:
                last_error = e
                if self._should_retry_error(e) and attempt < self.OVERLOAD_MAX_RETRIES:
                    delay = self._get_retry_delay(attempt)
                    logger.warning(
                        f"Anthropic API overloaded, retry {attempt + 1}/{self.OVERLOAD_MAX_RETRIES} in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue
                # Non-retryable error or max retries reached
                raise self._handle_error(e) from e

        # Should not reach here, but just in case
        if last_error:
            raise self._handle_error(last_error) from last_error

    def list_models(self) -> list[dict[str, Any]]:
        """
        List the models the Anthropic Models API reports, with the limits and
        capabilities it reports; everything else is ``None`` (unknown).

        ``supports_temperature`` is ``False`` once a rejection was learned.
        """
        try:
            return list_anthropic_models(self.client, self._learning_scope(self._endpoint()), self.provider_name)

        except Exception as e:
            raise self._handle_error(e) from e

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert Anthropic exceptions to ProviderError types (secrets scrubbed)."""
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        message = scrub_secrets(str(error))
        error_str = message.lower()

        # Check for overloaded error (transient, retryable)
        if "overloaded" in error_str or "529" in error_str:
            return OverloadedError(
                message=message,
                provider=self.provider_name,
                status_code=529,
                retry_after=5,  # Suggest 5 second wait
            )

        if "rate limit" in error_str or "429" in error_str:
            return RateLimitError(
                message=message,
                provider=self.provider_name,
                status_code=429,
            )

        if "authentication" in error_str or "401" in error_str:
            return AuthenticationError(
                message=message,
                provider=self.provider_name,
                status_code=401,
            )

        if "context" in error_str or "token" in error_str:
            return ContextLengthError(
                message=message,
                provider=self.provider_name,
            )

        return ProviderError(
            message=message,
            provider=self.provider_name,
        )
