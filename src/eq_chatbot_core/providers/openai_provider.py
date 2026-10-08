"""
OpenAI provider implementation.
"""

from typing import Any

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.base import ImageResult, ModelNotSpecifiedError, ProviderError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    """
    OpenAI API provider: chat completions and image generation.

    Pass the chat model per call or as ``model=``, the image model per call or as
    ``image_model=``; ``list_models()`` returns every id the account can use.
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    PROVIDER_NAME = "openai"
    _validate_default_url = False

    # Image generation is supported via the /images/generations endpoint.
    supports_image_generation: bool = True

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
        """The OpenAI API takes ``max_completion_tokens`` for every current model."""
        return "max_completion_tokens"

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
                    **param_learning.model_metadata(self._learning_scope(self._effective_base_url), model.id),
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
            size: Image dimensions, passed through to the API (valid sizes depend on the model).
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
                "size": size,
            }
            params.update(kwargs)

            resp = self.client.images.generate(**params)
            b64 = resp.data[0].b64_json
            if not b64:
                raise ProviderError(
                    f"Image model {model} returned no base64 image data. "
                    'Pass response_format="b64_json" for models that answer with a URL.',
                    provider=self.provider_name,
                )
            image_bytes = base64.b64decode(b64)

            return ImageResult(
                data=image_bytes,
                model=model,
                provider=self.provider_name,
                size=size,
                mime="image/png",
            )

        except Exception as e:
            raise self._handle_error(e) from e
