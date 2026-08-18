"""
Azure AI Foundry provider implementation.

Uses the standard ``openai`` SDK against the Azure OpenAI ``/v1`` endpoint.

Migration note (v2.0.0): this provider previously used the ``azure-ai-inference``
beta SDK, which Microsoft deprecated and retires on **26 August 2026**. The
official replacement is the GA OpenAI SDK pointed at
``https://<resource>.openai.azure.com/openai/v1/``. That endpoint speaks plain
OpenAI Chat Completions and serves both Azure OpenAI models and Foundry Models
from other providers (DeepSeek, Llama, Mistral, Cohere, Grok, ...), so the whole
message/tool conversion layer this module used to carry is gone and the wire
handling is inherited from :class:`OpenAICompatibleProvider`.

Consequences for callers:
- ``base_url`` must now be the ``.openai.azure.com/openai/v1/`` form. The old
  ``.services.ai.azure.com/models`` endpoint is detected and rejected with a
  migration hint rather than failing later with an opaque 404.
- The ``[azure]`` extra (``azure-ai-inference``, ``azure-core``) is no longer
  needed; ``openai`` is already a core dependency.
- ``api_version`` is obsolete — the ``/v1`` endpoint versions implicitly. The
  argument is still accepted but ignored, with a DeprecationWarning.

Reference:
https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/model-inference-to-openai-migration
"""

import warnings
from typing import Any

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature as _shared_clamp_temperature,
)
from eq_chatbot_core.providers.temperature_constraints import (
    get_temperature_constraints as _shared_get_temperature_constraints,
)


class AzureProvider(OpenAICompatibleProvider):
    """
    Azure AI Foundry provider (OpenAI-compatible ``/v1`` endpoint).

    Supports models deployed on Azure AI Foundry — Azure OpenAI models (GPT-4o,
    GPT-5.x, o-series) as well as Foundry Models from other providers (DeepSeek,
    Llama, Mistral, Cohere, ...) — authenticated with an API key.

    ``base_url`` is required and must point at the resource's OpenAI ``/v1``
    endpoint, e.g. ``https://your-resource.openai.azure.com/openai/v1/``.
    """

    PROVIDER_NAME = "azure"
    # No default: the endpoint is resource-specific and cannot be guessed.
    DEFAULT_BASE_URL = None
    DEFAULT_MODEL = "gpt-4o"
    # Azure endpoints are public cloud resources; internal targets are never valid.
    ALLOW_PRIVATE_RANGES = False
    MISSING_BASE_URL_MESSAGE = (
        "base_url is required for the Azure provider. Example: https://your-resource.openai.azure.com/openai/v1/"
    )

    # Substring identifying the retired azure-ai-inference endpoint form.
    _LEGACY_ENDPOINT_MARKER = ".services.ai.azure.com"

    # Reasoning models that don't support temperature and need max_completion_tokens
    REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "codex-mini", "deepseek-r1", "DeepSeek-R1", "MAI-DS-R1")

    # Static model catalog for list_models() (Azure has no list endpoint).
    # Based on: https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure
    KNOWN_MODELS = [
        # --- OpenAI: GPT-4o ---
        {"id": "gpt-4o", "name": "GPT-4o", "context_length": 128000, "max_output_tokens": 16384},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000, "max_output_tokens": 16384},
        # --- OpenAI: GPT-4.1 ---
        {"id": "gpt-4.1", "name": "GPT-4.1", "context_length": 1048576, "max_output_tokens": 32768},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "context_length": 1048576, "max_output_tokens": 32768},
        {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano", "context_length": 1048576, "max_output_tokens": 32768},
        # --- OpenAI: GPT-5 ---
        {"id": "gpt-5", "name": "GPT-5", "context_length": 400000, "max_output_tokens": 128000},
        {"id": "gpt-5-mini", "name": "GPT-5 Mini", "context_length": 400000, "max_output_tokens": 128000},
        {"id": "gpt-5-nano", "name": "GPT-5 Nano", "context_length": 400000, "max_output_tokens": 128000},
        {"id": "gpt-5-chat", "name": "GPT-5 Chat", "context_length": 128000, "max_output_tokens": 16384},
        # --- OpenAI: GPT-5.1 ---
        {"id": "gpt-5.1", "name": "GPT-5.1", "context_length": 400000, "max_output_tokens": 128000},
        {"id": "gpt-5.1-chat", "name": "GPT-5.1 Chat", "context_length": 128000, "max_output_tokens": 16384},
        # --- OpenAI: GPT-5.2 ---
        {"id": "gpt-5.2", "name": "GPT-5.2", "context_length": 400000, "max_output_tokens": 128000},
        {"id": "gpt-5.2-chat", "name": "GPT-5.2 Chat", "context_length": 128000, "max_output_tokens": 16384},
        # --- OpenAI: O-Series (Reasoning) ---
        {"id": "o1", "name": "O1", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "o1-mini", "name": "O1 Mini", "context_length": 128000, "max_output_tokens": 65536},
        {"id": "o3", "name": "O3", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "o3-pro", "name": "O3 Pro", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "o3-mini", "name": "O3 Mini", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "o4-mini", "name": "O4 Mini", "context_length": 200000, "max_output_tokens": 100000},
        {"id": "codex-mini", "name": "Codex Mini", "context_length": 200000, "max_output_tokens": 100000},
        # --- DeepSeek ---
        {"id": "DeepSeek-R1-0528", "name": "DeepSeek R1 0528", "context_length": 163840, "max_output_tokens": 163840},
        {"id": "DeepSeek-R1", "name": "DeepSeek R1", "context_length": 163840, "max_output_tokens": 163840},
        {
            "id": "DeepSeek-V3.2-Speciale",
            "name": "DeepSeek V3.2 Speciale",
            "context_length": 128000,
            "max_output_tokens": 128000,
        },
        {"id": "DeepSeek-V3.2", "name": "DeepSeek V3.2", "context_length": 128000, "max_output_tokens": 128000},
        {"id": "DeepSeek-V3.1", "name": "DeepSeek V3.1", "context_length": 131072, "max_output_tokens": 131072},
        {"id": "DeepSeek-V3-0324", "name": "DeepSeek V3 0324", "context_length": 131072, "max_output_tokens": 131072},
        # --- Meta Llama ---
        {
            "id": "Llama-4-Maverick-17B-128E-Instruct-FP8",
            "name": "Llama 4 Maverick",
            "context_length": 1000000,
            "max_output_tokens": 1000000,
        },
        {"id": "Llama-3.3-70B-Instruct", "name": "Llama 3.3 70B", "context_length": 128000, "max_output_tokens": 8192},
        # --- Mistral ---
        {"id": "Mistral-Large-3", "name": "Mistral Large 3", "context_length": 128000, "max_output_tokens": 8192},
        # --- Cohere ---
        {"id": "Cohere-command-a", "name": "Cohere Command A", "context_length": 131072, "max_output_tokens": 8192},
        # --- xAI Grok ---
        {"id": "grok-4", "name": "Grok 4", "context_length": 262000, "max_output_tokens": 8192},
        {"id": "grok-3", "name": "Grok 3", "context_length": 131072, "max_output_tokens": 131072},
        {"id": "grok-3-mini", "name": "Grok 3 Mini", "context_length": 131072, "max_output_tokens": 131072},
        # --- Microsoft ---
        {"id": "MAI-DS-R1", "name": "MAI DeepSeek R1", "context_length": 163840, "max_output_tokens": 163840},
        # --- Moonshot AI ---
        {"id": "Kimi-K2.5", "name": "Kimi K2.5", "context_length": 262144, "max_output_tokens": 262144},
        {"id": "Kimi-K2-Thinking", "name": "Kimi K2 Thinking", "context_length": 262144, "max_output_tokens": 262144},
    ]

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        model: str | None = None,
        api_version: str | None = None,
    ):
        """
        Initialize the Azure AI provider.

        Args:
            api_key: Azure API key, sent as a Bearer token by the OpenAI SDK.
            base_url: REQUIRED — the resource's OpenAI ``/v1`` endpoint, e.g.
                ``https://your-resource.openai.azure.com/openai/v1/``.
            timeout: Request timeout in seconds.
            max_retries: Number of retries on transient failures.
            model: Default deployment/model id for this instance (overridable per
                call). Falls back to ``DEFAULT_MODEL`` when not given.
            api_version: Deprecated and ignored — the ``/v1`` endpoint versions
                implicitly. Accepted so existing call sites keep working.

        Raises:
            ValueError: If base_url is missing, uses the retired
                ``.services.ai.azure.com/models`` form, or fails URL validation.
        """
        if api_version is not None:
            warnings.warn(
                "api_version is obsolete for the Azure provider: the OpenAI /v1 endpoint "
                "versions implicitly. The argument is ignored and will be removed in a "
                "future release.",
                DeprecationWarning,
                stacklevel=2,
            )

        if base_url and self._LEGACY_ENDPOINT_MARKER in base_url:
            raise ValueError(
                f"base_url points at the retired Azure AI Inference endpoint ({base_url!r}). "
                "That SDK is retired as of 26 August 2026. Use the resource's OpenAI /v1 "
                "endpoint instead, e.g. https://your-resource.openai.azure.com/openai/v1/ — "
                "see https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/"
                "model-inference-to-openai-migration"
            )

        super().__init__(api_key, base_url, timeout, max_retries, model)

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (o-series, DeepSeek-R1, MAI-DS-R1)."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix.lower()) for prefix in self.REASONING_MODEL_PREFIXES)

    def _get_temperature_constraints(self, model: str) -> dict[str, Any]:
        """Get temperature constraints for a specific model. Delegates to shared module."""
        return _shared_get_temperature_constraints(model)

    def _clamp_temperature(self, model: str, temperature: float) -> float | None:
        """Clamp temperature to valid range for the model. Delegates to shared module."""
        return _shared_clamp_temperature(model, temperature)

    def _build_params(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build request params, using max_completion_tokens for reasoning models.

        Azure's o-series deployments follow OpenAI's newer token-parameter
        semantics: ``max_tokens`` is rejected in favour of
        ``max_completion_tokens``.
        """
        params = super()._build_params(messages, model, temperature, max_tokens, tools, **kwargs)

        if max_tokens and self._is_reasoning_model(model):
            params.pop("max_tokens", None)
            params["max_completion_tokens"] = max_tokens

        return params

    def list_models(self) -> list[dict[str, Any]]:
        """
        List known Azure AI models.

        Azure does not expose a usable deployment-listing API here, so this
        returns a static catalog of commonly available models enriched with
        temperature constraints.

        Returns:
            List of model dicts with 'id', 'name', constraints, and metadata.
        """
        models = []
        for model_data in self.KNOWN_MODELS:
            model_id = str(model_data["id"])
            temp_constraints = self._get_temperature_constraints(model_id)
            is_reasoning = self._is_reasoning_model(model_id)

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
                    "supports_reasoning": is_reasoning,
                    "supports_streaming": True,
                }
            )

        models.sort(key=lambda m: m["id"])
        return models
