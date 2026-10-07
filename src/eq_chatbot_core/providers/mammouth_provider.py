"""
Mammouth AI provider implementation.

Mammouth AI (https://mammouth.ai) provides access to 30+ AI models through a
unified OpenAI-compatible API, including OpenAI, Anthropic, Google, Mistral,
xAI, DeepSeek, Meta, and more. The wire protocol is handled by
OpenAICompatibleProvider; only the model listing is Mammouth-specific.
"""

import logging
from typing import Any

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.base import ProviderError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider

_logger = logging.getLogger(__name__)


class MammouthProvider(OpenAICompatibleProvider):
    """
    Mammouth AI API provider for 30+ AI models.

    Model IDs use simple names without provider prefix (e.g. "gpt-4o",
    "claude-sonnet-4-5") unlike OpenRouter which uses "provider/model" format.
    """

    PROVIDER_NAME = "mammouth"
    DEFAULT_BASE_URL = "https://api.mammouth.ai/v1"
    MODELS_URL = "https://api.mammouth.ai/public/models"
    _validate_default_url = False

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
    ):
        """
        Initialize the Mammouth AI provider.

        Args:
            api_key: Mammouth AI API key
            base_url: Optional custom base URL (defaults to Mammouth API)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            model: Model used when a call passes none
        """
        super().__init__(api_key, base_url, timeout, max_retries, model)

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models from Mammouth AI.

        Uses the /public/models endpoint (separate from the v1 base URL), fetched
        through the same pinned client as every other request.
        """
        try:
            data = self.client.get(self.MODELS_URL, cast_to=object)
        except Exception as e:
            raise self._handle_error(e) from e

        # Mammouth returns a list directly or wrapped in "data"/"models"
        model_list = (
            data if isinstance(data, list) else data.get("data", data.get("models")) if isinstance(data, dict) else None
        )
        if not isinstance(model_list, list):
            raise ProviderError("Mammouth model listing returned an unusable response", provider=self.provider_name)

        models = []
        for model_data in model_list:
            model_id = model_data.get("id", model_data.get("model", ""))
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "provider": self.provider_name,
                    "context_length": model_data.get("max_input_tokens"),
                    "max_output_tokens": model_data.get("max_output_tokens"),
                    # Mammouth's list says nothing about temperature or reasoning.
                    "supports_temperature": param_learning.temperature_support(self._effective_base_url, model_id),
                    "min_temperature": None,
                    "max_temperature": None,
                    "supports_reasoning": None,
                    "supports_streaming": True,
                }
            )

        models.sort(key=lambda m: m["id"])
        return models
