"""
OpenRouter provider implementation.

OpenRouter provides access to 400+ AI models through a unified API,
including OpenAI, Anthropic, Google, Meta, Mistral, and many more.
"""

import logging
from typing import Any

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.base import ImageResult, ModelNotSpecifiedError, ProviderError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider

_logger = logging.getLogger(__name__)


class OpenRouterProvider(OpenAICompatibleProvider):
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
    PROVIDER_NAME = "openrouter"
    _validate_default_url = False

    # Image generation is supported via chat/completions with image modality.
    supports_image_generation: bool = True

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        site_url: str | None = None,
        site_name: str | None = None,
        model: str | None = None,
        image_model: str | None = None,
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
            model: Chat model used when a call passes none
            image_model: Image model used when ``generate_image`` gets none
        """
        self.site_url = site_url
        self.site_name = site_name
        self.image_model = image_model or None
        super().__init__(api_key, base_url, timeout, max_retries, model)

    def _default_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers

    def list_models(self) -> list[dict[str, Any]]:
        """List models with the metadata OpenRouter reports; seeds parameter learning.

        A model whose ``supported_parameters`` omit ``temperature`` is seeded as
        "temperature unsupported". A learned rejection always wins over the list:
        ``supports_temperature`` is then ``False`` whatever the list claims.
        Values OpenRouter does not report are ``None``.
        """
        try:
            data = self.client.get("/models", cast_to=object)
        except Exception as e:
            raise self._handle_error(e) from e

        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ProviderError("OpenRouter model listing returned an unusable response", provider=self.provider_name)

        models = []
        for model_data in data["data"]:
            model_id = model_data.get("id", "")
            constraints = self._get_model_constraints(model_data)
            if constraints["supports_temperature"] is False:
                param_learning.seed_temperature_support(self._effective_base_url, model_id, False)
            if param_learning.temperature_support(self._effective_base_url, model_id) is False:
                constraints["supports_temperature"] = False
            models.append(
                {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "description": model_data.get("description", ""),
                    "context_length": model_data.get("context_length"),
                    "provider": self.provider_name,
                    "created": model_data.get("created"),
                    **constraints,
                }
            )
        models.sort(key=lambda m: m["id"])
        return models

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
            model: Image model; falls back to the constructor's ``image_model``.
            size: Not controllable via OpenRouter; stored in ImageResult.size as-is.
            **kwargs: Additional provider-specific parameters

        Returns:
            ImageResult with PNG bytes and metadata

        Raises:
            ProviderError: If no image is returned or on HTTP/API errors
        """
        import base64

        model = model or self.image_model
        if not model:
            raise ModelNotSpecifiedError(self.provider_name, what="image model", constructor_argument="image_model")

        try:
            payload: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["image", "text"],
            }
            payload.update(kwargs)

            data = self.client.post("/chat/completions", body=payload, cast_to=object)

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

        except ProviderError:
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _get_model_constraints(self, model_data: dict[str, Any]) -> dict[str, Any]:
        """Metadata from OpenRouter's model entry; ``None`` where it says nothing.

        OpenRouter may send these fields as JSON null rather than omitting them,
        so ``or`` treats null and absent alike.
        """
        supported = model_data.get("supported_parameters") or None
        defaults = model_data.get("default_parameters") or {}
        input_modalities = model_data.get("input_modalities") or None
        output_modalities = model_data.get("output_modalities") or None
        max_output = (model_data.get("top_provider") or {}).get("max_completion_tokens") or model_data.get("max_tokens")
        return {
            "supports_temperature": ("temperature" in supported) if supported else None,
            "default_temperature": defaults.get("temperature"),
            "min_temperature": defaults.get("min_temperature"),
            "max_temperature": defaults.get("max_temperature"),
            "supports_reasoning": ("reasoning" in supported) if supported else None,
            "supports_vision": ("image" in input_modalities) if input_modalities else None,
            "supports_tools": ("tools" in supported or "tool_choice" in supported) if supported else None,
            "supports_streaming": True,  # OpenRouter streams every model (provider-level)
            "max_output_tokens": max_output or None,
            "default_max_tokens": None,
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
        }
