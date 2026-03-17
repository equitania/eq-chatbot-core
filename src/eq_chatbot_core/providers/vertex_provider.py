"""
Google Vertex AI provider implementation.

Uses the google-genai SDK with vertexai=True mode for access to
Gemini models via Google Cloud Application Default Credentials (ADC).

Authentication: gcloud auth application-default login (local dev)
or GOOGLE_APPLICATION_CREDENTIALS env var (service account).
"""

import json
import logging
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

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

# Graceful import for google-genai SDK
_google_available = True
try:
    from google import genai
    from google.genai import types
except ImportError:
    _google_available = False
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


class VertexProvider(BaseLLMProvider):
    """
    Google Vertex AI provider using the google-genai SDK.

    Supports Gemini models (2.0, 2.5) via Google Cloud Vertex AI
    with Application Default Credentials (ADC) authentication.

    Requires 'vertex' extra: pip install eq-chatbot-core[vertex]
    """

    # Static model catalog for list_models() with EU availability.
    KNOWN_MODELS = [
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "context_length": 1048576,
            "max_output_tokens": 65536,
            "supports_vision": True,
            "supports_tools": True,
        },
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "context_length": 1048576,
            "max_output_tokens": 65536,
            "supports_vision": True,
            "supports_tools": True,
        },
        {
            "id": "gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "context_length": 1048576,
            "max_output_tokens": 8192,
            "supports_vision": True,
            "supports_tools": True,
        },
        {
            "id": "gemini-2.0-flash-lite",
            "name": "Gemini 2.0 Flash Lite",
            "context_length": 1048576,
            "max_output_tokens": 8192,
            "supports_vision": True,
            "supports_tools": True,
        },
    ]

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        **kwargs: Any,
    ):
        """
        Initialize the Vertex AI provider.

        Args:
            api_key: Not used (Vertex uses ADC). Accepted for interface compatibility.
            base_url: Not used. Accepted for interface compatibility.
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            **kwargs: Must include 'project' (GCP project ID).
                      Optional: 'location' (default: europe-west1)

        Raises:
            ImportError: If google-genai is not installed
            ValueError: If project is not provided
        """
        if not _google_available:
            raise ImportError(
                "Google Gen AI SDK not installed. Install with: pip install eq-chatbot-core[vertex] "
                "or: pip install google-genai"
            )

        self._project = kwargs.pop("project", None)
        self._location = kwargs.pop("location", "europe-west1")

        if not self._project:
            raise ValueError(
                "project is required for Vertex provider. Example: get_provider('vertex', project='my-gcp-project')"
            )

        super().__init__(api_key or "not-used", base_url, timeout, max_retries)
        self._client: Any | None = None

    @property
    def provider_name(self) -> str:
        return "vertex"

    @property
    def default_model(self) -> str:
        return "gemini-2.5-flash"

    @property
    def client(self) -> Any:
        """Lazy initialization of google-genai Client in Vertex AI mode."""
        if self._client is None:
            self._client = genai.Client(
                vertexai=True,
                project=self._project,
                location=self._location,
            )
        return self._client

    def _get_temperature_constraints(self, model: str) -> dict[str, Any]:
        """Get temperature constraints for a specific model. Delegates to shared module."""
        return _shared_get_temperature_constraints(model)

    def _clamp_temperature(self, model: str, temperature: float) -> float | None:
        """Clamp temperature to valid range for the model. Delegates to shared module."""
        return _shared_clamp_temperature(model, temperature)

    def _convert_messages(self, messages: list[dict[str, Any]]) -> tuple[str | None, list[Any]]:
        """
        Convert OpenAI-style messages to google-genai format.

        Extracts system messages into a separate system_instruction string.
        Maps 'assistant' role to 'model' role for google-genai.

        Returns:
            Tuple of (system_instruction, contents)
        """
        system_parts = []
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=content)],
                    )
                )
            elif role == "tool":
                # Tool response: wrap as function response
                tool_call_id = msg.get("tool_call_id", "")
                tool_name = msg.get("name", tool_call_id)
                try:
                    result_data = json.loads(content) if content else {}
                except (json.JSONDecodeError, TypeError):
                    result_data = {"result": content}

                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=tool_name,
                                response=result_data,
                            )
                        ],
                    )
                )
            else:
                # user or unknown role
                if role != "user":
                    _logger.warning("Unknown message role '%s', treating as user message", role)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=content)],
                    )
                )

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[Any]:
        """Convert OpenAI-style tool definitions to google-genai format."""
        declarations = []
        for tool in tools:
            func = tool.get("function", {})
            params = func.get("parameters", {})

            declarations.append(
                types.FunctionDeclaration(
                    name=func.get("name", ""),
                    description=func.get("description", ""),
                    parameters=params if params else None,
                )
            )
        return [types.Tool(function_declarations=declarations)]

    def _parse_tool_calls(self, parts: list[Any]) -> list[dict[str, Any]]:
        """Parse google-genai function call parts into OpenAI-style tool calls."""
        tool_calls = []
        for part in parts:
            fn_call = getattr(part, "function_call", None)
            if fn_call:
                args = dict(fn_call.args) if fn_call.args else {}
                tool_calls.append(
                    {
                        "id": f"call_{uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": fn_call.name,
                            "arguments": json.dumps(args),
                        },
                    }
                )
        return tool_calls

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to Vertex AI."""
        model = model or self.default_model

        try:
            system_instruction, contents = self._convert_messages(messages)

            config_params: dict[str, Any] = {}

            # Clamp temperature per model constraints
            clamped_temp = self._clamp_temperature(model, temperature)
            if clamped_temp is not None:
                config_params["temperature"] = clamped_temp

            if max_tokens:
                config_params["max_output_tokens"] = max_tokens

            if tools:
                config_params["tools"] = self._convert_tools(tools)

            if system_instruction:
                config_params["system_instruction"] = system_instruction

            config = types.GenerateContentConfig(**config_params)

            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            # Extract content and tool calls from response
            content = ""
            tool_calls: list[dict[str, Any]] = []

            if response.candidates:
                candidate = response.candidates[0]
                parts = candidate.content.parts if candidate.content else []

                text_parts = []
                for part in parts:
                    if hasattr(part, "text") and part.text:
                        text_parts.append(part.text)

                content = "".join(text_parts)
                tool_calls = self._parse_tool_calls(parts)

            # Extract token usage
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

            # Determine finish reason
            finish_reason = None
            if response.candidates:
                raw_reason = getattr(response.candidates[0], "finish_reason", None)
                if raw_reason:
                    reason_str = str(raw_reason).lower()
                    if "stop" in reason_str:
                        finish_reason = "stop"
                    elif "length" in reason_str or "max_tokens" in reason_str:
                        finish_reason = "length"
                    elif "tool" in reason_str or "function" in reason_str:
                        finish_reason = "tool_calls"
                    else:
                        finish_reason = reason_str

            return LLMResponse(
                content=content,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
                tool_calls=tool_calls,
            )

        except Exception as e:
            raise self._handle_error(e) from e

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion response from Vertex AI."""
        model = model or self.default_model

        try:
            system_instruction, contents = self._convert_messages(messages)

            config_params: dict[str, Any] = {}

            clamped_temp = self._clamp_temperature(model, temperature)
            if clamped_temp is not None:
                config_params["temperature"] = clamped_temp

            if max_tokens:
                config_params["max_output_tokens"] = max_tokens

            if tools:
                config_params["tools"] = self._convert_tools(tools)

            if system_instruction:
                config_params["system_instruction"] = system_instruction

            config = types.GenerateContentConfig(**config_params)

            response_stream = self.client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )

            accumulated_tool_calls: list[dict[str, Any]] = []

            for chunk in response_stream:
                content = ""
                tool_call_delta = None

                # Determine if this chunk has a finish_reason (signals end of stream)
                is_final = False
                finish_reason = None

                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    parts = candidate.content.parts if candidate.content else []

                    for part in parts:
                        if hasattr(part, "text") and part.text:
                            content += part.text

                        fn_call = getattr(part, "function_call", None)
                        if fn_call:
                            args = dict(fn_call.args) if fn_call.args else {}
                            tc = {
                                "id": f"call_{uuid4().hex[:8]}",
                                "type": "function",
                                "function": {
                                    "name": fn_call.name,
                                    "arguments": json.dumps(args),
                                },
                            }
                            accumulated_tool_calls.append(tc)
                            tool_call_delta = {
                                "index": len(accumulated_tool_calls) - 1,
                                "id": tc["id"],
                                "function": tc["function"],
                            }

                    # Check finish_reason to determine finality
                    raw_reason = getattr(candidate, "finish_reason", None)
                    if raw_reason:
                        is_final = True
                        reason_str = str(raw_reason).lower()
                        if "stop" in reason_str:
                            finish_reason = "stop"
                        elif "length" in reason_str:
                            finish_reason = "length"
                        elif "tool" in reason_str or "function" in reason_str:
                            finish_reason = "tool_calls"
                        else:
                            finish_reason = reason_str

                # Token usage on final chunk
                usage = getattr(chunk, "usage_metadata", None)
                input_tokens = getattr(usage, "prompt_token_count", 0) if usage and is_final else 0
                output_tokens = getattr(usage, "candidates_token_count", 0) if usage and is_final else 0

                yield StreamChunk(
                    content=content,
                    is_final=is_final,
                    finish_reason=finish_reason,
                    tool_call_delta=tool_call_delta,
                    tool_calls=accumulated_tool_calls if is_final and accumulated_tool_calls else None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List known Vertex AI Gemini models.

        Returns a static catalog of commonly available Gemini models
        with temperature constraints and capabilities metadata.
        """
        models = []
        for model_data in self.KNOWN_MODELS:
            model_id = model_data["id"]
            temp_constraints = self._get_temperature_constraints(model_id)

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
                    "supports_vision": model_data.get("supports_vision", False),
                    "supports_tools": model_data.get("supports_tools", False),
                    "supports_streaming": True,
                }
            )

        models.sort(key=lambda m: m["id"])
        return models

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert google-genai errors to ProviderError types."""
        # Re-raise if already a ProviderError
        if isinstance(error, ProviderError):
            return error

        message = str(error)
        status_code = getattr(error, "code", None) or getattr(error, "status_code", None)

        # Try to extract HTTP status from error
        if status_code is None:
            error_str = message.lower()
            if "429" in error_str:
                status_code = 429
            elif "401" in error_str or "403" in error_str or "unauthenticated" in error_str:
                status_code = 401
            elif "503" in error_str or "unavailable" in error_str:
                status_code = 503

        if status_code == 429 or "resource exhausted" in message.lower():
            return RateLimitError(
                message=message,
                provider=self.provider_name,
                status_code=429,
            )

        if status_code in (401, 403) or "permission" in message.lower() or "unauthenticated" in message.lower():
            return AuthenticationError(
                message=message,
                provider=self.provider_name,
                status_code=status_code or 401,
            )

        if status_code in (503, 529) or "overloaded" in message.lower():
            return OverloadedError(
                message=message,
                provider=self.provider_name,
                status_code=status_code or 503,
            )

        msg_lower = message.lower()
        if ("context" in msg_lower and ("length" in msg_lower or "exceeded" in msg_lower or "window" in msg_lower)) or (
            "token" in msg_lower and "limit" in msg_lower
        ):
            return ContextLengthError(
                message=message,
                provider=self.provider_name,
            )

        return ProviderError(
            message=message,
            provider=self.provider_name,
            status_code=status_code,
        )

    def close(self) -> None:
        """Close the Vertex AI client."""
        self._client = None

    def __enter__(self) -> "VertexProvider":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except AttributeError:
            pass
