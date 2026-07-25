"""
Melious.ai provider implementation.

Connects to Melious — a sovereign, EU-hosted, OpenAI-compatible inference
gateway (GDPR-compliant, green hosting, European infrastructure). Built on the
standard ``openai`` SDK (already a core dependency); no extra package is required.

Like the IONOS provider, Melious exposes a **fixed public endpoint**, so
``base_url`` defaults to the official Melious URL and is optional. The API key
(prefix ``sk-mel-``) is generated in the Melious account dashboard and sent as a
Bearer token. The default model is a soft default (overridable per call or via the
``model`` constructor argument).

The wire protocol is plain OpenAI Chat Completions, so all request/response
handling is inherited from :class:`OpenAICompatibleProvider`.

Reference endpoints (OpenAI-compatible):
- POST /v1/chat/completions   (chat + streaming)
- GET  /v1/models

Note: Melious additionally offers embeddings, reranking, image generation and
speech-to-text, but those are out of scope for this chat-focused provider.
Melious-specific response fields (``environment_impact``, ``billing_cost``) and
request extras (``preset``, ``:flavor`` model suffix) pass through transparently
via ``**kwargs`` and are ignored by the OpenAI SDK.
"""

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider


class MeliousProvider(OpenAICompatibleProvider):
    """
    Provider for Melious.ai (sovereign EU-hosted, OpenAI-compatible).

    Uses an ``api_key`` sent as a Bearer token and a ``base_url`` that defaults to
    the official Melious endpoint. Supports chat completion, streaming, tool calls,
    and model listing via the OpenAI-compatible Chat Completions / Models API.
    """

    PROVIDER_NAME = "melious"
    # Official Melious OpenAI-compatible endpoint (sovereign EU infrastructure).
    DEFAULT_BASE_URL = "https://api.melious.ai/v1"
    # Soft default — overridable per call or via the ``model`` constructor argument.
    DEFAULT_MODEL = "minimax-428b-m3"
    # Fixed public cloud endpoint: private/internal targets are never legitimate.
    ALLOW_PRIVATE_RANGES = False


# Module-level aliases kept for backwards compatibility with existing importers.
DEFAULT_BASE_URL = MeliousProvider.DEFAULT_BASE_URL
DEFAULT_MODEL = MeliousProvider.DEFAULT_MODEL
