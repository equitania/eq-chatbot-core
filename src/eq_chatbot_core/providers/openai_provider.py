"""
OpenAI provider implementation.
"""

from collections.abc import Iterator
from typing import Any

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    ImageResult,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
    ToolDefinition,
    normalize_tools,
)
from eq_chatbot_core.providers.stream_accumulator import ToolCallAccumulator
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature,
    get_temperature_constraints,
)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API provider for GPT models.

    Supports:
    - GPT-4 Turbo (gpt-4-turbo)
    - GPT-4o (gpt-4o, gpt-4o-mini)
    - GPT-5 series (gpt-5, gpt-5.2)
    - O1/O3 series (o1, o1-mini, o1-preview, o3)
    - Image generation via gpt-image-1 (DALL-E 3 / DALL-E 2 also supported)
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    # Image generation is supported via the /images/generations endpoint.
    supports_image_generation: bool = True

    # Default model for image generation.
    DEFAULT_IMAGE_MODEL = "gpt-image-1"

    # Models that require max_completion_tokens instead of max_tokens
    # All GPT-4o, GPT-5.x, O1, and O3 models use the new API
    NEW_API_MODELS = (
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "gpt-5.1",
        "gpt-5.2",
        "o1",
        "o1-mini",
        "o1-preview",
        "o3",
        "o3-mini",
        "o4",
        "o4-mini",
    )

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        organization: str | None = None,
    ):
        # Initialize the client attribute BEFORE validation so close()/__del__
        # stay safe if the SSRF guard below raises.
        self._client: Any = None  # Lazy initialization

        # SSRF guard: only a caller-supplied base_url is validated — the fixed
        # public default needs no DNS round-trip. Private ranges are rejected
        # because OpenAI is a public cloud endpoint. Imported lazily to avoid an
        # import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        super().__init__(api_key, base_url, timeout, max_retries)
        self.organization = organization

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        # Verified live on 23.08.2026: the previous default had either been
        # retired or belonged to a generation we no longer run. Policy is to
        # default to the current one — see the live test that fails when this
        # id stops being served.
        return "gpt-5.6-luna"

    @property
    def client(self) -> Any:
        """Lazy initialization of OpenAI client."""
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

            effective_url = self.base_url or self.DEFAULT_BASE_URL
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=effective_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                organization=self.organization,
                http_client=httpx2.Client(
                    transport=build_pinned_transport_for_url(effective_url),
                    timeout=self.timeout,
                ),
            )
        return self._client

    def _uses_new_token_api(self, model: str) -> bool:
        """Check if model uses max_completion_tokens instead of max_tokens."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.NEW_API_MODELS)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request to OpenAI."""
        model = model or self.default_model
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            # Clamp temperature per model constraints (skip for reasoning models)
            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

            if max_tokens:
                if self._uses_new_token_api(model):
                    params["max_completion_tokens"] = max_tokens
                else:
                    params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

            # Add any additional kwargs
            params.update(kwargs)

            response = self.client.chat.completions.create(**params)

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

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

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
        """Stream a chat completion response from OpenAI."""
        model = model or self.default_model
        # Accept ToolDefinition instances as the base class promises; the
        # request payload below needs plain OpenAI-format dicts.
        tools = normalize_tools(tools)

        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},  # Request usage in stream
            }

            # Clamp temperature per model constraints (skip for reasoning models)
            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

            if max_tokens:
                if self._uses_new_token_api(model):
                    params["max_completion_tokens"] = max_tokens
                else:
                    params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

            params.update(kwargs)

            stream = self.client.chat.completions.create(**params)

            # Track usage for final chunk
            final_input_tokens = 0
            final_output_tokens = 0

            tool_calls = ToolCallAccumulator()

            for chunk in stream:
                # Check for usage data (sent in final chunk with stream_options)
                if hasattr(chunk, "usage") and chunk.usage:
                    final_input_tokens = chunk.usage.prompt_tokens or 0
                    final_output_tokens = chunk.usage.completion_tokens or 0

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                content = delta.content or ""
                is_final = choice.finish_reason is not None

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
                    tool_calls.add(delta.tool_calls)

                # On the final chunk, expose the fully accumulated tool calls.
                complete_tool_calls = tool_calls.result() if is_final else None

                yield StreamChunk(
                    content=content,
                    is_final=is_final,
                    finish_reason=choice.finish_reason,
                    tool_call_delta=tool_call_delta,
                    tool_calls=complete_tool_calls,
                    input_tokens=final_input_tokens if is_final else 0,
                    output_tokens=final_output_tokens if is_final else 0,
                )

        except Exception as e:
            raise self._handle_error(e) from e

    # Chat model prefixes to filter from models list
    CHAT_MODEL_PREFIXES = (
        "gpt-3.5",
        "gpt-4",
        "gpt-5",
        "o1",
        "o3",
        "o4",
        "chatgpt",
    )

    # Model context lengths (approximate, for common models)
    MODEL_CONTEXT_LENGTHS = {
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "o1": 200000,
        "o1-mini": 128000,
        "o1-preview": 128000,
        "o3": 200000,
        "o3-mini": 200000,
        "o4-mini": 200000,
        "gpt-5": 200000,
    }

    def _get_model_constraints(self, model_id: str) -> dict[str, Any]:
        """Get temperature, token, and capability constraints for a model."""
        model_lower = model_id.lower()

        # Use shared temperature constraints for accurate min/max
        temp_constraints = get_temperature_constraints(model_id)
        is_reasoning = not temp_constraints["supports_temperature"]

        # Check if model supports vision (GPT-4o, GPT-4-turbo, GPT-5, O1, O3, O4)
        vision_prefixes = ("gpt-4o", "gpt-4-turbo", "gpt-5", "o1", "o3", "o4")
        supports_vision = any(model_lower.startswith(prefix) for prefix in vision_prefixes)

        # Get context length
        context_length = None
        for prefix, length in self.MODEL_CONTEXT_LENGTHS.items():
            if model_lower.startswith(prefix):
                context_length = length
                break

        if is_reasoning:
            return {
                "supports_temperature": False,
                "default_temperature": 1.0,
                "min_temperature": 1.0,
                "max_temperature": 1.0,
                "supports_reasoning": True,
                "supports_vision": supports_vision,
                "max_output_tokens": 100000 if "o1" in model_lower else 65536,
                "default_max_tokens": 16384,
                "context_length": context_length or 200000,
            }
        else:
            return {
                "supports_temperature": True,
                "default_temperature": 1.0,
                "min_temperature": temp_constraints["min"],
                "max_temperature": temp_constraints["max"],
                "supports_reasoning": False,
                "supports_vision": supports_vision,
                "max_output_tokens": 16384 if "gpt-4o" in model_lower else 4096,
                "default_max_tokens": 4096,
                "context_length": context_length or 128000,
            }

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available chat models from OpenAI.

        Returns:
            List of model dicts with 'id', 'name', constraints, and metadata.
            Only returns models suitable for chat completion.
        """
        try:
            models = self.client.models.list()

            chat_models = []
            for model in models.data:
                model_id = model.id.lower()

                # Filter for chat-capable models
                if any(model_id.startswith(prefix) for prefix in self.CHAT_MODEL_PREFIXES):
                    constraints = self._get_model_constraints(model.id)
                    chat_models.append(
                        {
                            "id": model.id,
                            "name": model.id,  # OpenAI uses ID as name
                            "created": model.created,
                            "owned_by": model.owned_by,
                            "provider": self.provider_name,
                            **constraints,
                        }
                    )

            # Sort by model ID for consistent ordering
            chat_models.sort(key=lambda m: m["id"])
            return chat_models

        except Exception as e:
            raise self._handle_error(e) from e

    def generate_image(
        self,
        prompt: str,
        *,
        model: str | None = None,
        size: str = "1024x1024",
        **kwargs: Any,
    ) -> ImageResult:
        """
        Generate an image using OpenAI's image generation API.

        Args:
            prompt: Text description of the image to generate
            model: Model to use (defaults to 'gpt-image-1')
            size: Image dimensions. Valid for gpt-image-1: 1024x1024, 1024x1536,
                  1536x1024, auto. DALL-E 3: 1024x1024, 1792x1024, 1024x1792.
                  Unknown sizes are passed through to the API.
            **kwargs: Additional provider-specific parameters

        Returns:
            ImageResult with PNG bytes and metadata

        Raises:
            ProviderError: On API errors (mapped to AuthenticationError, RateLimitError, etc.)
        """
        import base64

        model = model or self.DEFAULT_IMAGE_MODEL

        try:
            params: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "n": 1,
            }

            # gpt-image-1 always returns b64_json implicitly — adding response_format
            # causes a parameter error. Only set it explicitly for dall-e-* models.
            model_lower = model.lower()
            if model_lower.startswith("dall-e"):
                params["response_format"] = "b64_json"

            if size != "1024x1024":
                params["size"] = size
            else:
                params["size"] = size

            params.update(kwargs)

            resp = self.client.images.generate(**params)
            image_bytes = base64.b64decode(resp.data[0].b64_json)

            return ImageResult(
                data=image_bytes,
                model=model,
                provider=self.provider_name,
                size=size,
                mime="image/png",
            )

        except Exception as e:
            raise self._handle_error(e) from e

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert OpenAI exceptions to ProviderError types (secrets scrubbed)."""
        from eq_chatbot_core.utils.secret_scrub import scrub_secrets

        message = scrub_secrets(str(error))
        error_str = message.lower()

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

        if "context length" in error_str or "token" in error_str:
            return ContextLengthError(
                message=message,
                provider=self.provider_name,
            )

        return ProviderError(
            message=message,
            provider=self.provider_name,
        )
