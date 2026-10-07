"""
OpenAI provider implementation.
"""

from typing import Any

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.base import ImageResult, ModelNotSpecifiedError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider


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

    def list_models(self) -> list[dict[str, Any]]:
        """
        List every model the OpenAI API reports.

        Nothing is filtered by name, so embedding, audio and image models appear
        too. Metadata the API does not report is ``None`` (unknown);
        ``supports_temperature`` is ``False`` once a rejection was learned.
        """
        try:
            models = self.client.models.list()
            result = [
                {
                    "id": model.id,
                    "name": model.id,
                    "created": getattr(model, "created", None),
                    "owned_by": getattr(model, "owned_by", None),
                    "provider": self.provider_name,
                    **param_learning.model_metadata(self._effective_base_url, model.id),
                }
                for model in models.data
            ]
            result.sort(key=lambda m: m["id"])
            return result

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
