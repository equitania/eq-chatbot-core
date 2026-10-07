"""
OpenAI provider implementation.
"""

from typing import Any

from eq_chatbot_core.providers.base import ImageResult, ModelNotSpecifiedError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from eq_chatbot_core.providers.temperature_constraints import get_temperature_constraints


class OpenAIProvider(OpenAICompatibleProvider):
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
    PROVIDER_NAME = "openai"
    _validate_default_url = False

    # Image generation is supported via the /images/generations endpoint.
    supports_image_generation: bool = True

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
        model: str | None = None,
        image_model: str | None = None,
    ):
        self.organization = organization
        self.image_model = image_model or None
        super().__init__(api_key, base_url, timeout, max_retries, model)

    def _client_kwargs(self) -> dict[str, Any]:
        return {"organization": self.organization} if self.organization else {}

    def _token_param(self, model: str) -> str:
        return "max_completion_tokens" if self._uses_new_token_api(model) else "max_tokens"

    def _uses_new_token_api(self, model: str) -> bool:
        """Check if model uses max_completion_tokens instead of max_tokens."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.NEW_API_MODELS)

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
            model: Image model; falls back to the constructor's ``image_model``.
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

        model = model or self.image_model
        if not model:
            raise ModelNotSpecifiedError(self.provider_name, what="image model", constructor_argument="image_model")

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
