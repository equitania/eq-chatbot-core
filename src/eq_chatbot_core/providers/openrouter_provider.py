"""
OpenRouter provider implementation.

OpenRouter provides access to 400+ AI models through a unified API,
including OpenAI, Anthropic, Google, Meta, Mistral, and many more.
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
    ImageResult,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
)
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature,
    strip_provider_prefix,
)
from eq_chatbot_core.utils.secret_scrub import scrub_secrets

_logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter API provider for 400+ AI models.

    Supports models from multiple providers through a unified API:
    - OpenAI (GPT-4, GPT-4o, O1, O3, O4)
    - Anthropic (Claude 3, Claude 3.5, Claude 4)
    - Google (Gemini Pro, Gemini Ultra)
    - Meta (Llama 3, Llama 4)
    - Mistral (Mistral Large, Mixtral)
    - And many more...

    Model IDs follow the format: provider/model-name
    Examples:
    - openai/gpt-4o
    - anthropic/claude-3.5-sonnet
    - google/gemini-pro-1.5
    - meta-llama/llama-3.1-70b-instruct
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    # Image generation is supported via chat/completions with image modality.
    supports_image_generation: bool = True

    # Default model for image generation via OpenRouter.
    DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image"

    # Reasoning models that don't support temperature
    REASONING_MODEL_PREFIXES = (
        "openai/o1",
        "openai/o3",
        "openai/o4",
    )

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        site_url: str | None = None,
        site_name: str | None = None,
    ):
        """
        Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            base_url: Optional custom base URL (defaults to OpenRouter API)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            site_url: Optional site URL for HTTP-Referer header (for rankings)
            site_name: Optional site name for X-Title header (for display)
        """
        # SSRF guard: only a caller-supplied base_url is validated — the fixed
        # public default needs no DNS round-trip. Imported lazily to avoid an
        # import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, timeout, max_retries)
        self.site_url = site_url
        self.site_name = site_name
        self._client: httpx.Client | None = None

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def default_model(self) -> str:
        return "openai/gpt-4o"

    @property
    def client(self) -> httpx.Client:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            if self.site_url:
                headers["HTTP-Referer"] = self.site_url
            if self.site_name:
                headers["X-Title"] = self.site_name

            # Pin the resolved addresses against DNS rebinding. Done here rather
            # than in __init__ so the fixed public default still costs no DNS
            # round-trip until the client is actually used.
            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            self._client = httpx.Client(
                base_url=self.base_url,
                transport=build_pinned_transport_for_url(self.base_url),
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (O1, O3, O4)."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix.lower()) for prefix in self.REASONING_MODEL_PREFIXES)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request to OpenRouter."""
        model = model or self.default_model

        try:
            # Build request payload (OpenAI-compatible format)
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            # Clamp temperature per model constraints (strip provider/ prefix first)
            bare_model = strip_provider_prefix(model)
            clamped = clamp_temperature(bare_model, temperature)
            if clamped is not None:
                payload["temperature"] = clamped

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools:
                payload["tools"] = tools

            # Add any additional kwargs
            payload.update(kwargs)

            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            message = choice["message"]

            # Parse tool calls if present
            tool_calls = []
            if message.get("tool_calls"):
                tool_calls = [
                    {
                        "id": tc["id"],
                        "type": tc["type"],
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in message["tool_calls"]
                ]

            usage = data.get("usage", {})

            return LLMResponse(
                content=message.get("content") or "",
                model=data.get("model", model),
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason"),
                tool_calls=tool_calls,
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
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
        """Stream a chat completion response from OpenRouter."""
        model = model or self.default_model

        try:
            # Build request payload
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
            }

            # Clamp temperature per model constraints (strip provider/ prefix first)
            bare_model = strip_provider_prefix(model)
            clamped = clamp_temperature(bare_model, temperature)
            if clamped is not None:
                payload["temperature"] = clamped

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if tools:
                payload["tools"] = tools

            payload.update(kwargs)

            # Use streaming request
            with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                # Track usage for final chunk
                final_input_tokens = 0
                final_output_tokens = 0

                # Accumulate tool calls from deltas
                accumulated_tool_calls: dict[int, dict[str, Any]] = {}

                for line in response.iter_lines():
                    if not line:
                        continue

                    # SSE comment / keep-alive lines (OpenRouter sends
                    # ": OPENROUTER PROCESSING" while the upstream model warms up) are
                    # not data — ignore them per the SSE spec instead of failing to
                    # JSON-parse and logging a warning for every ping.
                    if line.startswith(":"):
                        continue

                    # Handle SSE format
                    if line.startswith("data: "):
                        line = line[6:]  # Remove "data: " prefix

                    if line == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(line)
                    except json.JSONDecodeError:
                        _logger.warning(f"Failed to parse SSE chunk: {line[:200]}")
                        continue

                    # Check for usage data
                    if "usage" in chunk_data:
                        usage = chunk_data["usage"]
                        final_input_tokens = usage.get("prompt_tokens", 0)
                        final_output_tokens = usage.get("completion_tokens", 0)

                    if not chunk_data.get("choices"):
                        continue

                    choice = chunk_data["choices"][0]
                    delta = choice.get("delta", {})

                    content = delta.get("content") or ""
                    is_final = choice.get("finish_reason") is not None

                    # Handle tool call deltas
                    tool_call_delta = None
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            func = tc.get("function", {})

                            tool_call_delta = {
                                "index": idx,
                                "id": tc.get("id"),
                                "function": {
                                    "name": func.get("name"),
                                    "arguments": func.get("arguments"),
                                },
                            }

                            # Accumulate tool call data
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.get("id") or "",
                                    "type": "function",
                                    "function": {
                                        "name": "",
                                        "arguments": "",
                                    },
                                }

                            # Update with new data
                            if tc.get("id"):
                                accumulated_tool_calls[idx]["id"] = tc["id"]
                            if func.get("name"):
                                accumulated_tool_calls[idx]["function"]["name"] += func["name"]
                            if func.get("arguments"):
                                accumulated_tool_calls[idx]["function"]["arguments"] += func["arguments"]

                    # On final chunk, include accumulated tool calls
                    complete_tool_calls = None
                    if is_final and accumulated_tool_calls:
                        complete_tool_calls = [
                            accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())
                        ]

                    yield StreamChunk(
                        content=content,
                        is_final=is_final,
                        finish_reason=choice.get("finish_reason"),
                        tool_call_delta=tool_call_delta,
                        tool_calls=complete_tool_calls,
                        input_tokens=final_input_tokens if is_final else 0,
                        output_tokens=final_output_tokens if is_final else 0,
                    )

        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models from OpenRouter.

        Returns:
            List of model dicts with 'id', 'name', constraints, pricing, and metadata.
        """
        try:
            response = self.client.get("/models")
            response.raise_for_status()
            data = response.json()

            models = []
            for model_data in data.get("data", []):
                model_id = model_data.get("id", "")
                constraints = self._get_model_constraints(model_data)
                pricing = self._extract_pricing(model_data)

                models.append(
                    {
                        "id": model_id,
                        "name": model_data.get("name", model_id),
                        "description": model_data.get("description", ""),
                        "context_length": model_data.get("context_length"),
                        "provider": self.provider_name,
                        "created": model_data.get("created"),
                        **constraints,
                        **pricing,
                    }
                )

            # Sort by model ID for consistent ordering
            models.sort(key=lambda m: m["id"])
            return models

        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
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
        Generate an image via OpenRouter's chat/completions endpoint with image modality.

        OpenRouter does not expose a dedicated /images endpoint. Instead, image-capable
        models are invoked via chat/completions with ``"modalities": ["image", "text"]``.
        The image is returned as a data URL in ``choices[0].message.images``.

        Args:
            prompt: Text description of the image to generate
            model: Model to use (defaults to 'google/gemini-2.5-flash-image')
            size: Not controllable via OpenRouter; stored in ImageResult.size as-is.
            **kwargs: Additional provider-specific parameters

        Returns:
            ImageResult with PNG bytes and metadata

        Raises:
            ProviderError: If no image is returned or on HTTP/API errors
        """
        import base64

        model = model or self.DEFAULT_IMAGE_MODEL

        try:
            payload: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["image", "text"],
            }
            payload.update(kwargs)

            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            # Image data is in choices[0].message.images as a list of image_url dicts.
            images = (data.get("choices") or [{}])[0].get("message", {}).get("images") or []
            if not images:
                raise ProviderError(
                    "No image returned by OpenRouter model. Ensure the model supports image output modality.",
                    provider=self.provider_name,
                )

            # Parse data URL: "data:<mime>;base64,<data>"
            image_url_entry = images[0]
            url = image_url_entry.get("image_url", {}).get("url", "")
            if not url.startswith("data:"):
                raise ProviderError(
                    f"Unexpected image URL format from OpenRouter: {url[:80]}",
                    provider=self.provider_name,
                )

            # Extract mime and base64 payload
            # Format: data:<mime>;base64,<b64data>
            meta, _, b64_data = url.partition(",")
            mime = meta.split(";")[0].replace("data:", "") or "image/png"
            image_bytes = base64.b64decode(b64_data)

            return ImageResult(
                data=image_bytes,
                model=model,
                provider=self.provider_name,
                size=None,  # OpenRouter does not expose size control
                mime=mime,
            )

        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except ProviderError:
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _get_model_constraints(self, model_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract temperature, token, and capability constraints from model data.

        OpenRouter provides:
        - supported_parameters: list of parameters the model accepts
        - default_parameters: dict of default values
        - input_modalities: list like ["text", "image"]
        - output_modalities: list like ["text"]
        """
        model_id = model_data.get("id", "").lower()
        # OpenRouter may return these fields explicitly as JSON null (not absent),
        # so a dict.get(key, default) fallback does NOT apply — coerce with `or`.
        supported_params = model_data.get("supported_parameters") or []
        default_params = model_data.get("default_parameters") or {}
        input_modalities = model_data.get("input_modalities") or ["text"]
        output_modalities = model_data.get("output_modalities") or ["text"]

        # Check if it's a reasoning model
        is_reasoning = any(model_id.startswith(prefix.lower()) for prefix in self.REASONING_MODEL_PREFIXES)

        # Determine temperature support
        # Either from supported_parameters or by checking if not a reasoning model
        supports_temperature = "temperature" in supported_params if supported_params else not is_reasoning

        # Get temperature bounds from default_parameters or use defaults
        if is_reasoning:
            min_temp = 1.0
            max_temp = 1.0
            default_temp = 1.0
        else:
            # Try to extract from model data, fallback to standard bounds
            min_temp = default_params.get("min_temperature", 0.0)
            max_temp = default_params.get("max_temperature", 2.0)
            default_temp = default_params.get("temperature", 1.0)

        # Vision support from input modalities
        supports_vision = "image" in input_modalities

        # Tool/function calling support
        supports_tools = "tools" in supported_params or "tool_choice" in supported_params

        # Max output tokens
        max_output = (model_data.get("top_provider") or {}).get("max_completion_tokens")
        if not max_output:
            max_output = model_data.get("max_tokens", 4096)

        return {
            "supports_temperature": supports_temperature,
            "default_temperature": default_temp,
            "min_temperature": min_temp,
            "max_temperature": max_temp,
            "supports_reasoning": is_reasoning,
            "supports_vision": supports_vision,
            "supports_tools": supports_tools,
            "supports_streaming": True,  # OpenRouter supports streaming for all models
            "max_output_tokens": max_output,
            "default_max_tokens": min(max_output, 4096) if max_output else 4096,
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
        }

    def _extract_pricing(self, model_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract pricing information from model data.

        OpenRouter provides pricing in the 'pricing' field:
        - prompt: cost per input token (as string like "0.000001")
        - completion: cost per output token (as string)
        """
        pricing = model_data.get("pricing", {})

        try:
            prompt_price = float(pricing.get("prompt", "0")) if pricing.get("prompt") else None
            completion_price = float(pricing.get("completion", "0")) if pricing.get("completion") else None
            image_price = float(pricing.get("image", "0")) if pricing.get("image") else None
        except (ValueError, TypeError):
            prompt_price = None
            completion_price = None
            image_price = None

        # Normalized per-1k-token keys (USD) so consumers read one consistent
        # field regardless of provider. OpenRouter quotes per single token.
        input_per_1k = round(prompt_price * 1000, 6) if prompt_price is not None else None
        output_per_1k = round(completion_price * 1000, 6) if completion_price is not None else None

        return {
            "input_cost_per_token": prompt_price,
            "output_cost_per_token": completion_price,
            "image_cost_per_token": image_price,
            "input_cost_per_1k": input_per_1k,
            "output_cost_per_1k": output_per_1k,
        }

    def _handle_http_error(self, error: httpx.HTTPStatusError) -> ProviderError:
        """Convert HTTP errors to ProviderError types (secrets scrubbed)."""
        status = error.response.status_code
        try:
            error_data = error.response.json()
            message = error_data.get("error", {}).get("message", str(error))
        except (ValueError, KeyError):
            message = str(error)

        # Gateway error bodies can echo request headers/credentials — mask before
        # the message reaches a logger or an API caller.
        message = scrub_secrets(message)

        if status == 429:
            return RateLimitError(
                message=message,
                provider=self.provider_name,
                status_code=429,
            )

        if status == 401:
            return AuthenticationError(
                message=message,
                provider=self.provider_name,
                status_code=401,
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

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert general exceptions to ProviderError (secrets scrubbed)."""
        return ProviderError(
            message=scrub_secrets(str(error)),
            provider=self.provider_name,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OpenRouterProvider":
        return self

    def __exit__(self, *args) -> None:
        self.close()
