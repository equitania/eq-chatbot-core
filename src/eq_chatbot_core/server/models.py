"""Pydantic request/response schemas for the eq-chatbot HTTP server."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single message in the conversation history.

    Mirrors the OpenAI ChatML role/content shape that all eq_chatbot_core
    providers accept. Tool messages may carry ``tool_call_id`` and assistant
    messages may carry ``tool_calls`` for multi-turn tool flows.
    """

    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant", "system", "tool"]
    content: str | list[dict[str, Any]]
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatRequest(BaseModel):
    """Body of POST /chat and POST /chat/stream.

    The ``api_key`` is per-request (not stored in the sidecar). The C# parent
    holds the encrypted-at-rest copy and only sends the plaintext on the wire
    to localhost.
    """

    messages: list[ChatMessage] = Field(..., min_length=1)
    provider: str
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0, le=200_000)
    tools: list[dict[str, Any]] | None = None
    extra: dict[str, Any] | None = None
    """Provider-specific extras forwarded as **kwargs to chat_completion."""


class ChatResponse(BaseModel):
    """Body of POST /chat success response."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ListModelsRequest(BaseModel):
    """Body of POST /models. POST (not GET) because some providers need the
    api_key/base_url in the request — keeping them in JSON avoids leaking
    credentials into URL strings or log lines."""

    provider: str
    api_key: str | None = None
    base_url: str | None = None


class ProviderInfo(BaseModel):
    """Body of GET /providers — static catalog of available provider names."""

    cloud: list[str]
    local: list[str]


class HealthResponse(BaseModel):
    """Body of GET /health — auth-free probe."""

    ok: bool
    version: str
    uptime_seconds: float
