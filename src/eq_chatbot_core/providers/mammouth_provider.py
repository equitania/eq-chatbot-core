"""
Mammouth AI provider implementation.

Mammouth AI (https://mammouth.ai) provides access to 30+ AI models through a
unified OpenAI-compatible API, including OpenAI, Anthropic, Google, Mistral,
xAI, DeepSeek, Meta, and more. The wire protocol is handled by
OpenAICompatibleProvider; only the model listing is Mammouth-specific.
"""

import logging
from typing import Any

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature as _shared_clamp_temperature,
)
from eq_chatbot_core.providers.temperature_constraints import (
    get_temperature_constraints as _shared_get_temperature_constraints,
)

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

    # Reasoning models that don't support temperature parameter
    REASONING_MODEL_PREFIXES = ("o1", "o3", "o4")

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
        model_list = data if isinstance(data, list) else data.get("data", data.get("models", []))

        models = []
        for model_data in model_list:
            model_id = model_data.get("id", model_data.get("model", ""))
            if not model_id:
                continue
            temp_constraints = self._get_temperature_constraints(model_id)
            models.append(
                {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "provider": self.provider_name,
                    "context_length": model_data.get("max_input_tokens"),
                    "max_output_tokens": model_data.get("max_output_tokens"),
                    "supports_temperature": temp_constraints["supports_temperature"],
                    "min_temperature": temp_constraints["min"],
                    "max_temperature": temp_constraints["max"],
                    "supports_reasoning": self._is_reasoning_model(model_id),
                    "supports_streaming": True,
                }
            )

        models.sort(key=lambda m: m["id"])
        return models
