"""
Azure AI Foundry provider implementation.

Uses the azure-ai-inference SDK with ChatCompletionsClient for lightweight,
stable access to Azure AI models (GPT, Claude, Mistral, etc.) via API key auth.
"""

import logging
from collections.abc import Iterator
from typing import Any

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    OverloadedError,
    ProviderError,
    RateLimitError,
    StreamChunk,
)
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature as _shared_clamp_temperature,
)
from eq_chatbot_core.providers.temperature_constraints import (
    get_temperature_constraints as _shared_get_temperature_constraints,
)

_logger = logging.getLogger(__name__)

# Graceful import for azure-ai-inference SDK
_azure_available = True
try:
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import (
        AssistantMessage,
        ChatCompletionsToolDefinition,
        FunctionDefinition,
        SystemMessage,
        ToolMessage,
        UserMessage,
    )
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
except ImportError:
    _azure_available = False
    # Placeholders for type hints when SDK not installed
    ChatCompletionsClient = None  # type: ignore[assignment, misc]
    AzureKeyCredential = None  # type: ignore[assignment, misc]
    ClientAuthenticationError = None  # type: ignore[assignment, misc]
    HttpResponseError = None  # type: ignore[assignment, misc]


class AzureProvider(BaseLLMProvider):
    """
    Azure AI Foundry provider using azure-ai-inference SDK.

    Supports models deployed on Azure AI (GPT-4o, GPT-4.1, O1, O3, O4,
    Claude, Mistral, etc.) via AzureKeyCredential authentication.

    Requires 'azure' extra: pip install eq-chatbot-core[azure]
    """

    # Reasoning models that don't support temperature parameter
    REASONING_MODEL_PREFIXES = ("o1", "o3", "o4")

    # Static model catalog for list_models() (Azure has no list endpoint)
    KNOWN_MODELS = [
        {"id": "gpt-4o", "name": "GPT-4o", "context_length": 128000, "max_output_tokens": 16384},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000, "max_output_tokens": 16384},
        {"id": "gpt-4.1", "name": "GPT-4.1", "context_length": 1048576, "max_output_tokens": 32768},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "context_length": 1048576, "max_output_tokens": 32768},
        {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano", "context_length": 1048576, "max_output_tokens": 32768},
        {"id": "o1", "name": "O1", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "o3", "name": "O3", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "o3-mini", "name": "O3 Mini", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "o4-mini", "name": "O4 Mini", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5", "context_length": 200000, "max_output_tokens": 8192},
        {"id": "mistral-large", "name": "Mistral Large", "context_length": 128000, "max_output_tokens": 8192},
    ]

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        """
        Initialize the Azure AI provider.

        Args:
            api_key: Azure API key for AzureKeyCredential auth
            base_url: REQUIRED - Azure endpoint URL (e.g. https://your-resource.services.ai.azure.com/)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures

        Raises:
            ImportError: If azure-ai-inference is not installed
            ValueError: If base_url is not provided
        """
        if not _azure_available:
            raise ImportError(
                "Azure AI SDK not installed. Install with: pip install eq-chatbot-core[azure] "
                "or: pip install azure-ai-inference azure-core"
            )

        if not base_url:
            raise ValueError(
                "base_url is required for Azure provider. Example: https://your-resource.services.ai.azure.com/"
            )

        super().__init__(api_key, base_url, timeout, max_retries)
        self._client: ChatCompletionsClient | None = None

    @property
    def provider_name(self) -> str:
        return "azure"

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    @property
    def client(self) -> "ChatCompletionsClient":
        """Lazy initialization of Azure ChatCompletionsClient."""
        if self._client is None:
            self._client = ChatCompletionsClient(
                endpoint=self.base_url,
                credential=AzureKeyCredential(self.api_key),
            )
        return self._client

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (O1, O3, O4)."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.REASONING_MODEL_PREFIXES)

    def _get_temperature_constraints(self, model: str) -> dict[str, Any]:
        """Get temperature constraints for a specific model. Delegates to shared module."""
        return _shared_get_temperature_constraints(model)

    def _clamp_temperature(self, model: str, temperature: float) -> float | None:
        """Clamp temperature to valid range for the model. Delegates to shared module."""
        return _shared_clamp_temperature(model, temperature)

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list:
        """Convert dict messages to Azure SDK message types."""
        azure_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                azure_messages.append(SystemMessage(content=content))
            elif role == "user":
                azure_messages.append(UserMessage(content=content))
            elif role == "assistant":
                azure_messages.append(AssistantMessage(content=content))
            elif role == "tool":
                azure_messages.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=msg.get("tool_call_id", ""),
                    )
                )
            else:
                # Fallback: treat unknown roles as user messages
                _logger.warning("Unknown message role '%s', treating as user message", role)
                azure_messages.append(UserMessage(content=content))

        return azure_messages

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list:
        """Convert dict tool definitions to Azure SDK tool types."""
        azure_tools = []
        for tool in tools:
            func = tool.get("function", {})
            azure_tools.append(
                ChatCompletionsToolDefinition(
                    function=FunctionDefinition(
                        name=func.get("name", ""),
                        description=func.get("description", ""),
                        parameters=func.get("parameters", {}),
                    )
                )
            )
        return azure_tools

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to Azure AI."""
        model = model or self.default_model

        try:
            azure_messages = self._convert_messages(messages)

            params: dict[str, Any] = {
                "messages": azure_messages,
                "model": model,
            }

            # Clamp temperature per model constraints
            clamped_temp = self._clamp_temperature(model, temperature)
            if clamped_temp is not None:
                params["temperature"] = clamped_temp

            if max_tokens:
                params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = self._convert_tools(tools)

            response = self.client.complete(**params)

            choice = response.choices[0]
            message = choice.message

            # Parse tool calls if present
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                    )

            usage = response.usage

            return LLMResponse(
                content=message.content or "",
                model=response.model or model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
            )

        except ClientAuthenticationError as e:
            raise AuthenticationError(
                message=str(e),
                provider=self.provider_name,
                status_code=401,
            ) from e
        except HttpResponseError as e:
            raise self._handle_http_error(e) from e
        except (AuthenticationError, RateLimitError, ContextLengthError, OverloadedError, ProviderError):
            raise
        except Exception as e:
            raise ProviderError(
                message=str(e),
                provider=self.provider_name,
            ) from e

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion response from Azure AI."""
        model = model or self.default_model

        try:
            azure_messages = self._convert_messages(messages)

            params: dict[str, Any] = {
                "messages": azure_messages,
                "model": model,
                "stream": True,
            }

            # Clamp temperature per model constraints
            clamped_temp = self._clamp_temperature(model, temperature)
            if clamped_temp is not None:
                params["temperature"] = clamped_temp

            if max_tokens:
                params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = self._convert_tools(tools)

            response = self.client.complete(**params)

            # Accumulate tool calls from deltas
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            for chunk in response:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                content = delta.content or "" if delta else ""
                is_final = choice.finish_reason is not None

                # Handle tool call deltas
                tool_call_delta = None
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.get("index", 0) if isinstance(tc, dict) else getattr(tc, "index", 0)
                        func = tc.get("function", {}) if isinstance(tc, dict) else tc.function

                        func_name = func.get("name", "") if isinstance(func, dict) else getattr(func, "name", "") or ""
                        func_args = (
                            func.get("arguments", "")
                            if isinstance(func, dict)
                            else getattr(func, "arguments", "") or ""
                        )
                        tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "") or ""

                        tool_call_delta = {
                            "index": idx,
                            "id": tc_id,
                            "function": {
                                "name": func_name,
                                "arguments": func_args,
                            },
                        }

                        # Accumulate tool call data
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            }

                        if tc_id:
                            accumulated_tool_calls[idx]["id"] = tc_id
                        if func_name:
                            accumulated_tool_calls[idx]["function"]["name"] += func_name
                        if func_args:
                            accumulated_tool_calls[idx]["function"]["arguments"] += func_args

                # On final chunk, include accumulated tool calls
                complete_tool_calls = None
                if is_final and accumulated_tool_calls:
                    complete_tool_calls = [accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())]

                # Extract usage if available
                usage = getattr(chunk, "usage", None)
                input_tokens = usage.prompt_tokens if usage and is_final else 0
                output_tokens = usage.completion_tokens if usage and is_final else 0

                yield StreamChunk(
                    content=content,
                    is_final=is_final,
                    finish_reason=choice.finish_reason,
                    tool_call_delta=tool_call_delta,
                    tool_calls=complete_tool_calls,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

        except ClientAuthenticationError as e:
            raise AuthenticationError(
                message=str(e),
                provider=self.provider_name,
                status_code=401,
            ) from e
        except HttpResponseError as e:
            raise self._handle_http_error(e) from e
        except (AuthenticationError, RateLimitError, ContextLengthError, OverloadedError, ProviderError):
            raise
        except Exception as e:
            raise ProviderError(
                message=str(e),
                provider=self.provider_name,
            ) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List known Azure AI models.

        Azure doesn't provide a model listing API, so this returns a static
        catalog of commonly available models with temperature constraints.

        Returns:
            List of model dicts with 'id', 'name', constraints, and metadata.
        """
        models = []
        for model_data in self.KNOWN_MODELS:
            model_id = model_data["id"]
            temp_constraints = self._get_temperature_constraints(model_id)
            is_reasoning = self._is_reasoning_model(model_id)

            models.append(
                {
                    "id": model_id,
                    "name": model_data["name"],
                    "provider": self.provider_name,
                    "context_length": model_data.get("context_length"),
                    "max_output_tokens": model_data.get("max_output_tokens"),
                    "supports_temperature": temp_constraints["supports_temperature"],
                    "min_temperature": temp_constraints["min"],
                    "max_temperature": temp_constraints["max"],
                    "supports_reasoning": is_reasoning,
                    "supports_streaming": True,
                }
            )

        models.sort(key=lambda m: m["id"])
        return models

    def _handle_http_error(self, error: "HttpResponseError") -> ProviderError:
        """Convert Azure HTTP errors to ProviderError types."""
        status = error.status_code or 500
        message = str(error.message) if error.message else str(error)

        if status == 429:
            return RateLimitError(
                message=message,
                provider=self.provider_name,
                status_code=429,
            )

        if status in (401, 403):
            return AuthenticationError(
                message=message,
                provider=self.provider_name,
                status_code=status,
            )

        if status in (503, 529):
            return OverloadedError(
                message=message,
                provider=self.provider_name,
                status_code=status,
            )

        if status == 400 and "context" in message.lower():
            return ContextLengthError(
                message=message,
                provider=self.provider_name,
            )

        return ProviderError(
            message=message,
            provider=self.provider_name,
            status_code=status,
        )

    def close(self) -> None:
        """Close the Azure client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "AzureProvider":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except AttributeError:
            pass
