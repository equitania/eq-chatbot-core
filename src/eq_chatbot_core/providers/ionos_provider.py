"""
IONOS AI Model Hub provider implementation.

Connects to the IONOS Cloud AI Model Hub — a German/EU-hosted, OpenAI-compatible
inference gateway (region ``de-txl``/Berlin). Built on the standard ``openai``
SDK (already a core dependency); no extra package is required.

Unlike the LiteLLM gateway provider, IONOS exposes a **fixed public endpoint**,
so ``base_url`` defaults to the official IONOS URL and is optional. The API token
is generated in the IONOS DCD Token Manager and sent as a Bearer token. The
default model is a soft default (overridable per call or via the ``model``
constructor argument).

The wire protocol is plain OpenAI Chat Completions, so all request/response
handling is inherited from :class:`OpenAICompatibleProvider`.

Reference endpoints (OpenAI-compatible):
- POST /v1/chat/completions   (chat + streaming)
- GET  /v1/models

Note: IONOS additionally offers image generation, embeddings and reranking, but
those are out of scope for this chat-focused provider.
"""

from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider


class IonosProvider(OpenAICompatibleProvider):
    """
    Provider for the IONOS Cloud AI Model Hub (EU-hosted, OpenAI-compatible).

    Uses an ``api_key`` sent as a Bearer token and a ``base_url`` that defaults to
    the official IONOS endpoint. Supports chat completion, streaming, tool calls,
    and model listing via the OpenAI-compatible Chat Completions / Models API.
    """

    PROVIDER_NAME = "ionos"
    # Official IONOS AI Model Hub OpenAI-compatible endpoint (Berlin / de-txl, EU).
    DEFAULT_BASE_URL = "https://openai.inference.de-txl.ionos.com/v1"
    # Soft default — overridable per call or via the ``model`` constructor argument.
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
    # Fixed public cloud endpoint: private/internal targets are never legitimate.
    ALLOW_PRIVATE_RANGES = False


# Module-level aliases kept for backwards compatibility with existing importers.
DEFAULT_BASE_URL = IonosProvider.DEFAULT_BASE_URL
DEFAULT_MODEL = IonosProvider.DEFAULT_MODEL
