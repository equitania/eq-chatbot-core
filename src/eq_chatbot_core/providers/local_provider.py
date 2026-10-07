"""
Local LLM provider implementation for LM Studio and Ollama.

Supports local LLM servers that expose OpenAI-compatible APIs:
- LM Studio: http://localhost:1234/v1
- Ollama: http://localhost:11434/v1

Both servers implement the OpenAI Chat Completions API format,
making them interchangeable via the base_url parameter.
"""

import logging
from typing import Any

from eq_chatbot_core.providers.base import AuthenticationError, ContextLengthError, ProviderError
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from eq_chatbot_core.utils.secret_scrub import scrub_secrets

logger = logging.getLogger(__name__)


class LocalLLMProvider(OpenAICompatibleProvider):
    """
    Unified provider for local LLM servers (LM Studio, Ollama).

    Both LM Studio and Ollama expose OpenAI-compatible APIs, so this
    provider works with either by setting the appropriate base_url:

    - LM Studio: http://localhost:1234/v1 (default)
    - Ollama: http://localhost:11434/v1

    Example:
        # LM Studio
        provider = LocalLLMProvider(
            api_key="not-used",
            base_url="http://localhost:1234/v1"
        )

        # Ollama
        provider = LocalLLMProvider(
            api_key="not-used",
            base_url="http://localhost:11434/v1"
        )
    """

    PROVIDER_NAME = "local"
    ALLOW_PRIVATE_RANGES = True
    STREAM_INCLUDE_USAGE = False

    # Default URLs for common local LLM servers
    LM_STUDIO_URL = "http://localhost:1234/v1"
    OLLAMA_URL = "http://localhost:11434/v1"
    DEFAULT_BASE_URL = LM_STUDIO_URL

    # Default timeout is higher for local servers (model loading can be slow)
    DEFAULT_TIMEOUT = 120.0

    def __init__(
        self,
        api_key: str = "not-used",
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 2,
        model: str | None = None,
    ):
        """
        Initialize the local LLM provider.

        Args:
            api_key: API key (usually not required for local servers, defaults to "not-used")
            base_url: Server URL (defaults to LM Studio URL)
            timeout: Request timeout in seconds (defaults to 120s for model loading)
            max_retries: Number of retries on transient failures
            model: Model used when a call passes none (the id the server lists)
        """
        # Always validated (LAN mode): local servers are reachable without DNS
        # surprises, and the old provider validated the default too.
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.LM_STUDIO_URL,
            timeout=timeout or self.DEFAULT_TIMEOUT,
            max_retries=max_retries,
            model=model,
        )

    def _get_server_type(self) -> str:
        """Detect server type based on base_url."""
        if self.base_url and "11434" in self.base_url:
            return "ollama"
        return "lm_studio"

    @staticmethod
    def _extract_error_message(data: Any) -> str | None:
        """Extract an error message from a local-server response body (kept for callers)."""
        if not isinstance(data, dict):
            return None
        err = data.get("error")
        if not err:
            return None
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)

    def _sdk_max_retries(self) -> int:
        """Never let the SDK retry: the pre-3.4 LocalLLMProvider accepted max_retries but never
        retried, and a timed-out local generation must not be re-sent."""
        return 0

    def _error_from_message(self, message: str) -> ProviderError:
        """LM Studio/Ollama signal context overflow in the body, without a status."""
        lowered = message.lower()
        if "context" in lowered or "token" in lowered:
            return ContextLengthError(message=f"Context length exceeded: {message}", provider=self.provider_name)
        return ProviderError(message=message, provider=self.provider_name)

    def _handle_error(self, error: Exception) -> ProviderError:
        import openai

        where = scrub_secrets(self.base_url or self.LM_STUDIO_URL)
        if isinstance(error, openai.APITimeoutError):
            return ProviderError(
                message=f"Request timed out after {self.timeout}s. Error: {scrub_secrets(str(error))}",
                provider=self.provider_name,
            )
        if isinstance(error, openai.APIConnectionError):
            return ProviderError(
                message=f"Cannot connect to local LLM server at {where}. "
                f"Ensure the server is running. Error: {scrub_secrets(str(error))}",
                provider=self.provider_name,
            )
        if isinstance(error, openai.APIStatusError) and error.status_code == 401:
            return AuthenticationError(
                message="Authentication failed (local server may require API key)",
                provider=self.provider_name,
                status_code=401,
            )
        return super()._handle_error(error)

    def list_models(self) -> list[dict[str, Any]]:
        """List models from the local server (limited metadata)."""
        try:
            data = self.client.get("/models", cast_to=object)
        except Exception as e:
            raise self._handle_error(e) from e

        models = []
        for model_data in data.get("data", []) if isinstance(data, dict) else []:
            model_id = model_data.get("id", "unknown")
            models.append(
                {
                    "id": model_id,
                    "name": model_id,
                    "provider": self.provider_name,
                    "context_length": model_data.get("context_length"),
                    "supports_streaming": True,
                    "supports_tools": None,
                    "supports_vision": None,
                    "owned_by": model_data.get("owned_by", "local"),
                    "created": model_data.get("created"),
                }
            )
        return models

    def is_server_available(self) -> bool:
        """Check if the local LLM server is reachable (no retries)."""
        try:
            self.client.with_options(max_retries=0).get("/models", cast_to=object)
            return True
        except Exception as e:
            logger.debug("Local server health check failed: %s", scrub_secrets(str(e)))
            return False
