"""
LangDock provider implementation.

LangDock is a unified API gateway supporting multiple LLM providers:
- OpenAI (GPT-4, GPT-5, O1-O4 series)
- Anthropic (Claude models)
- Google (Gemini models via Vertex AI)
- Codestral (Mistral code generation)
- Agents (LangDock custom agents with knowledge)

Documentation: https://docs.langdock.com/api-endpoints/api-introduction
"""

import json
import logging
from collections.abc import Iterable, Iterator
from contextlib import ExitStack
from typing import Any

import httpx2

from eq_chatbot_core.providers import param_learning
from eq_chatbot_core.providers.anthropic_shared import create_message, list_anthropic_models, open_message_stream
from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
    ToolDefinition,
    normalize_tools,
)
from eq_chatbot_core.providers.openai_compatible import OpenAICompatibleProvider
from eq_chatbot_core.providers.temperature_constraints import (
    apply_anthropic_temperature,
    clamp_temperature,
)

_logger = logging.getLogger(__name__)

# Max length of an upstream error body surfaced in logs / exceptions.
_ERROR_DETAIL_MAX = 500

# SSE payload marker of the AI SDK 5 data stream the Agent endpoint speaks.
_SSE_MARKER = "data: "


def _scrub(text: str) -> str:
    """Mask credential shapes in text (lazy import to avoid an import cycle)."""
    from eq_chatbot_core.utils.secret_scrub import scrub_secrets as _ss

    return _ss(text)


def _safe_detail(text: str) -> str:
    """Scrub credentials from an upstream error body and bound its length.

    Provider error bodies may echo request headers (Authorization), API-key
    query parameters, or other sensitive context. Always pass them through this
    before logging or embedding in a raised exception.
    """
    return _scrub(text or "")[:_ERROR_DETAIL_MAX]


# The Agent API answers three unrelated situations with the same HTTP 400 and an
# upstream body no end user can act on: the agent is unknown, the agent is not
# shared with this API key, or the agent resolves to no model at all. Verified
# live on 23.08.2026: an agent whose model is set to "Auto" fails this way, and a
# top-level `model` in the payload does NOT override it — the Auto router is only
# available in the chat UI, so the setting has to change in LangDock itself.
_AGENT_NO_MODEL_MARKERS = ("no valid model", "no default model")


def _iter_sse_data(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Yield the JSON objects of an AI SDK 5 data stream, one per `data:` block.

    LangDock's Agent endpoint streams Server-Sent Events whose payloads are typed
    objects (`text-delta`, `finish`, …). Two properties of the real stream shape
    this parser:

    * `data:` blocks are NOT reliably separated by a blank line — a captured run
      contained two events glued into a single line — so the split is on the
      marker itself, not on line boundaries.
    * A malformed block must not abort a live answer. A stream that dies on one
      bad frame loses everything the model already produced, so unparseable
      blocks are logged and skipped.

    The `[DONE]` sentinel is consumed here and never surfaces to the caller.
    """
    for line in lines:
        if not line:
            continue
        text = line.decode() if isinstance(line, bytes) else line
        if _SSE_MARKER not in text:
            continue
        # Skip whatever precedes the first marker (an SSE `event:` field, say).
        for block in text.split(_SSE_MARKER)[1:]:
            payload = block.strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                event = json.loads(payload)
            except ValueError:
                _logger.debug("Agent stream: skipping unparseable SSE block: %s", _safe_detail(payload))
                continue
            if isinstance(event, dict):
                yield event


def _agent_error_message(status_code: int, detail: str) -> str:
    """Turn an Agent API error body into an actionable, German-language message.

    The upstream text is appended verbatim (already scrubbed by _safe_detail) so
    the original cause stays diagnosable in logs and support tickets.
    """
    lowered = (detail or "").lower()
    base = f"Agent API error {status_code}"

    if any(marker in lowered for marker in _AGENT_NO_MODEL_MARKERS):
        hint = (
            "Der LangDock-Agent liefert kein Modell. Steht das Modell des Agenten in "
            "LangDock auf „Auto“, stelle dort ein festes Modell ein — der "
            "Auto-Modus wird über die Agent-API nicht unterstützt."
        )
    elif status_code == 400:
        hint = (
            "Der Agent wurde nicht gefunden. Prüfe die Agent-ID und ob der Agent in "
            "LangDock mit diesem API-Key geteilt ist."
        )
    elif status_code in (401, 403):
        hint = "Der API-Key wurde abgelehnt. Prüfe den LangDock-API-Key und ob er die Agent-API nutzen darf."
    else:
        hint = ""

    return f"{base}: {hint} ({detail})" if hint else f"{base}: {detail}"


class _LangDockOpenAIBackend(OpenAICompatibleProvider):
    """LangDock's `/openai/{region}/v1` backend, driven by the shared base class.

    LangDockProvider serves five different APIs; only this one is OpenAI wire,
    so it is delegated rather than inherited.
    """

    PROVIDER_NAME = "langdock"

    def __init__(self, owner: "LangDockProvider"):
        self._owner = owner
        super().__init__(owner.api_key, owner._get_backend_url(), owner.timeout, owner.max_retries)

    def _token_param(self, model: str) -> str:
        return "max_completion_tokens" if self._owner._uses_new_token_api(model) else "max_tokens"

    def _build_params(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        effort = kwargs.pop("reasoning_effort", None) or self._owner.reasoning_effort
        params = super()._build_params(messages, model, temperature, max_tokens, tools, **kwargs)
        if effort and self._owner._is_reasoning_model(model):
            params["reasoning_effort"] = effort
        return params


class LangDockProvider(BaseLLMProvider):
    """
    LangDock unified API gateway provider.

    LangDock provides access to multiple LLM providers through a single API:

    Backends:
    - openai: GPT-4 Turbo, GPT-4o, GPT-5, O1/O3/O4 series
    - anthropic: Claude 3.5, Claude 4 models
    - google: Gemini models via Vertex AI
    - codestral: Mistral Codestral for code generation (FIM)
    - agent: LangDock custom agents with knowledge folders

    Features:
    - EU/US region selection (GDPR compliance)
    - Unified API key for all providers
    - Reasoning effort control for O1/O3/O4 models
    - Agent integration with knowledge folders
    """

    BASE_URL = "https://api.langdock.com"

    # Backend endpoint patterns
    # Note: Anthropic SDK appends /v1/messages, so we don't include /v1 here
    BACKENDS = {
        "openai": "/openai/{region}/v1",
        "anthropic": "/anthropic/{region}",  # SDK adds /v1/messages
        "google": "/google/{region}/v1beta",
        "codestral": "/mistral/{region}/v1",
        "agent": "/agent/v1",
    }

    # Models that don't support temperature (reasoning models)
    REASONING_MODELS = ("o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4", "o4-mini")

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        region: str = "eu",
        backend: str = "openai",
        reasoning_effort: str | None = None,
        agent_id: str | None = None,
        model: str | None = None,
    ):
        """
        Initialize LangDock provider.

        Args:
            api_key: LangDock API key
            base_url: Custom base URL (overrides default)
            timeout: Request timeout in seconds
            max_retries: Number of retries on transient failures
            region: API region - 'eu' or 'us' (default: eu for GDPR)
            backend: LangDock backend - 'openai', 'anthropic', 'google', 'codestral', 'agent'
            reasoning_effort: For O1/O3/O4 models - 'low', 'medium', 'high'
            agent_id: LangDock Agent ID (required for backend='agent')
            model: Model used when a call passes none (not used by the agent
                backend, whose model is configured in LangDock)
        """
        # Initialize clients BEFORE validation to ensure __del__ works even when
        # the SSRF guard below rejects the URL.
        self._http_client: httpx2.Client | None = None
        self._openai_backend: _LangDockOpenAIBackend | None = None
        self._anthropic_client: Any = None

        # SSRF guard: only a caller-supplied base_url is validated — the fixed
        # public default needs no DNS round-trip. Imported lazily to avoid an
        # import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        super().__init__(api_key, base_url or self.BASE_URL, timeout, max_retries, model)

        self.region = region.lower()
        self.backend = backend.lower()
        self.reasoning_effort = reasoning_effort
        self.agent_id = agent_id

        # Validate backend
        if self.backend not in self.BACKENDS:
            raise ValueError(f"Invalid backend '{backend}'. Must be one of: {list(self.BACKENDS.keys())}")

        # Agent backend requires agent_id
        if self.backend == "agent" and not self.agent_id:
            raise ValueError("agent_id is required when using backend='agent'")

    @property
    def provider_name(self) -> str:
        return "langdock"

    def resolve_model(self, model: str | None = None) -> str:
        """Model for one call; the agent backend needs none (its model lives in LangDock)."""
        if self.backend == "agent":
            return model or ""
        return super().resolve_model(model)

    def _get_backend_url(self) -> str:
        """Get the full base URL for the current backend."""
        pattern = self.BACKENDS[self.backend]
        if "{region}" in pattern:
            return f"{self.base_url}{pattern.format(region=self.region)}"
        return f"{self.base_url}{pattern}"

    @property
    def http_client(self) -> httpx2.Client:
        """Get or create HTTP client for direct API calls."""
        if self._http_client is None:
            # Pin the resolved addresses against DNS rebinding (see
            # utils.url_validation.build_pinned_transport_for_url).
            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            backend_url = self._get_backend_url()
            self._http_client = httpx2.Client(
                base_url=backend_url,
                transport=build_pinned_transport_for_url(backend_url),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._http_client

    def _get_openai_backend(self) -> _LangDockOpenAIBackend:
        if self._openai_backend is None:
            try:
                self._openai_backend = _LangDockOpenAIBackend(self)
            except ValueError as e:
                # The delegate re-validates the backend URL (DNS lookup); callers
                # catch ProviderError, so a failed build must not surface raw.
                raise ProviderError(
                    f"LangDock OpenAI backend unavailable: {_scrub(str(e))}", provider="langdock"
                ) from e
        return self._openai_backend

    @property
    def openai_client(self) -> Any:
        """OpenAI SDK client for the openai backend (pinned transport, shared base class)."""
        return self._get_openai_backend().client

    @property
    def anthropic_client(self) -> Any:
        """Get or create Anthropic client for Anthropic backend."""
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise ImportError("Anthropic package not installed. Install with: pip install anthropic") from e

            # As above, this client was never pinned.
            import httpx2

            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            backend_url = self._get_backend_url()
            self._anthropic_client = Anthropic(
                api_key=self.api_key,
                base_url=backend_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                http_client=httpx2.Client(
                    transport=build_pinned_transport_for_url(backend_url),
                    timeout=self.timeout,
                ),
            )
        return self._anthropic_client

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model that doesn't support temperature."""
        model_lower = model.lower()
        return any(model_lower.startswith(prefix) for prefix in self.REASONING_MODELS)

    def _extract_system_prompt(self, messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
        """Extract system prompt for Anthropic backend."""
        system_prompt = None
        filtered_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if system_prompt:
                    system_prompt = f"{system_prompt}\n\n{content}"
                else:
                    system_prompt = content
            else:
                filtered_messages.append(msg)

        return system_prompt, filtered_messages

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        *,
        reasoning_effort: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Send a chat completion request through LangDock.

        Routes to the appropriate backend based on configuration.
        """
        model = self.resolve_model(model)
        # Accept ToolDefinition instances as the base class promises; the
        # backends below build request payloads from plain dicts.
        tools = normalize_tools(tools)

        if self.backend == "agent":
            return self._agent_chat_completion(messages, max_tokens, **kwargs)
        elif self.backend == "openai":
            return self._openai_chat_completion(
                messages, model, temperature, max_tokens, tools, reasoning_effort, **kwargs
            )
        elif self.backend == "anthropic":
            return self._anthropic_chat_completion(messages, model, temperature, max_tokens, tools, **kwargs)
        elif self.backend == "google":
            return self._google_chat_completion(messages, model, temperature, max_tokens, **kwargs)
        elif self.backend == "codestral":
            return self._codestral_completion(messages, model, max_tokens, **kwargs)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def _openai_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        reasoning_effort: str | None,
        **kwargs: Any,
    ) -> LLMResponse:
        """OpenAI-compatible chat completion."""
        extra = dict(kwargs)
        if reasoning_effort:
            extra["reasoning_effort"] = reasoning_effort
        return self._get_openai_backend().chat_completion(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, tools=tools, **extra
        )

    def _uses_new_token_api(self, model: str) -> bool:
        """Check if model uses max_completion_tokens instead of max_tokens."""
        model_lower = model.lower()
        new_api_prefixes = (
            "gpt-4o",
            "gpt-5",
            "o1",
            "o3",
            "o4",
        )
        return any(model_lower.startswith(prefix) for prefix in new_api_prefixes)

    def _filter_agent_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter messages for Agent API compatibility.

        LangDock Agent API only accepts: user, assistant, tool roles.
        System messages are not supported - agent instructions are configured in LangDock.
        """
        filtered = []
        for msg in messages:
            role = msg.get("role", "")
            if role in ("user", "assistant", "tool"):
                filtered.append(msg)
            elif role == "system":
                _logger.debug("Skipping system message for agent (configured in LangDock)")
            else:
                _logger.warning(f"Unknown message role '{role}' - skipping")
        return filtered

    def _convert_to_agent_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert internal message format to Vercel AI SDK UIMessage format.

        Filters messages, converts content to parts array, and moves
        attachmentIds to metadata.attachments.

        Returns:
            List of UIMessage dicts ready for Agent API.
        """
        filtered = self._filter_agent_messages(messages)
        agent_messages = []

        for i, msg in enumerate(filtered):
            content = msg.get("content", "")
            attachment_ids = msg.get("attachmentIds", [])

            # Convert multimodal list content to plain text
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = " ".join(text_parts)

            text = str(content) if content else ""
            parts = [{"type": "text", "text": text}]

            agent_msg: dict[str, Any] = {
                "id": f"msg_{i}",
                "role": msg.get("role"),
                "parts": parts,
            }

            if attachment_ids:
                agent_msg["metadata"] = {"attachments": attachment_ids}
                _logger.info(f"Agent message includes {len(attachment_ids)} attachments")

            agent_messages.append(agent_msg)

        return agent_messages

    def _agent_request_events(self, agent_messages: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """POST the agent request as a stream and yield its SSE events.

        Both agent paths go through here — the streaming one and the synchronous
        one, which assembles the deltas itself. Nothing asks LangDock for a
        buffered response any more: it aborts a non-streaming request with HTTP
        524 after 100 seconds, which an agent that runs tools or searches a
        knowledge base reaches without trying.

        Raises:
            ProviderError: On a non-200 status, and on an ``error`` event, which
                the stream can still emit after a successful 200.
        """
        payload = {
            "agentId": self.agent_id,
            "messages": agent_messages,
            "stream": True,
        }

        agent_url = f"{self.base_url}/agent/v1/chat/completions"
        _logger.info(f"Agent request to {agent_url}")
        _logger.info(f"Agent payload: agentId={self.agent_id}, messages_count={len(agent_messages)}")
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(f"Full payload: {_scrub(json.dumps(payload, default=str))}")

        # Go through the pinned client rather than the module-level httpx2 API:
        # agent_url is derived from a caller-supplied base_url, so a bare request
        # here would bypass the DNS-rebinding guard every other path uses.
        # http_client's base_url is _get_backend_url(), which for this backend is
        # "<base_url>/agent/v1" — the relative path below resolves to agent_url.
        with self.http_client.stream(
            "POST",
            "/chat/completions",
            json=payload,
            timeout=120.0,
        ) as response:
            if response.status_code != 200:
                # A streamed response has no body yet; reading it first is what
                # keeps this from raising ResponseNotRead instead of reporting
                # the actual upstream error.
                response.read()
                detail = _safe_detail(response.text)
                message = _agent_error_message(response.status_code, detail)
                _logger.error(message)
                raise ProviderError(
                    message,
                    provider="langdock",
                    status_code=response.status_code,
                )

            for event in _iter_sse_data(response.iter_lines()):
                if event.get("type") == "error":
                    detail = _safe_detail(str(event.get("errorText") or event.get("error") or event))
                    _logger.error(f"Agent stream error event: {detail}")
                    raise ProviderError(f"Agent stream error: {detail}", provider="langdock")
                yield event

    def _agent_chat_completion(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None,
        **kwargs: Any,
    ) -> LLMResponse:
        """LangDock Agent chat completion using httpx directly.

        LangDock Agent API requires agentId parameter, not model.
        Uses Vercel AI SDK UIMessage format with agent-specific endpoint.
        System messages are filtered out - agent instructions are in LangDock.
        """
        try:
            _logger.info(f"Agent sync: Original messages count: {len(messages)}")

            # Convert to Vercel AI SDK UIMessage format
            agent_messages = self._convert_to_agent_messages(messages)

            _logger.info(f"Agent sync: Converted messages count: {len(agent_messages)}")

            if not agent_messages:
                _logger.warning("Agent sync: No messages after filtering!")
                return LLMResponse(
                    content="Der Agent benötigt eine Benutzernachricht. Bitte geben Sie Ihre Frage ein.",
                    model=f"agent:{self.agent_id}",
                    input_tokens=0,
                    output_tokens=0,
                    finish_reason="error",
                    tool_calls=[],
                    raw_response={},
                )

            content_parts: list[str] = []
            model_name = ""
            metadata: dict[str, Any] = {}

            for event in self._agent_request_events(agent_messages):
                kind = event.get("type")
                if kind == "text-delta":
                    delta = event.get("delta") or ""
                    if delta:
                        content_parts.append(delta)
                elif kind == "start":
                    metadata = event.get("messageMetadata") or {}
                    model_name = metadata.get("modelName") or ""

            content = "".join(content_parts)
            if not content:
                _logger.warning("Agent sync: stream carried no text-delta events")
            else:
                _logger.info(f"Agent sync: assembled {len(content)} chars from {len(content_parts)} deltas")

            return LLMResponse(
                content=content,
                model=model_name or f"agent:{self.agent_id}",
                input_tokens=0,
                output_tokens=0,
                finish_reason="stop",
                tool_calls=[],
                raw_response={"messageMetadata": metadata},
            )

        except httpx2.HTTPError as e:
            safe = _scrub(str(e))
            _logger.error(f"Agent HTTP error: {safe}")
            raise ProviderError(f"Agent HTTP error: {safe}", provider="langdock") from e
        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _anthropic_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Anthropic-compatible chat completion."""
        try:
            system_prompt, filtered_messages = self._extract_system_prompt(messages)

            params: dict[str, Any] = {
                "model": model,
                "messages": filtered_messages,
                "max_tokens": max_tokens or 4096,
            }

            # Clamp temperature per model constraints
            apply_anthropic_temperature(params, model, temperature)

            if system_prompt:
                params["system"] = system_prompt

            if tools:
                # Convert OpenAI-style tools to Anthropic format
                anthropic_tools = []
                for tool in tools:
                    if tool.get("type") == "function":
                        func = tool.get("function", {})
                        anthropic_tools.append(
                            {
                                "name": func.get("name"),
                                "description": func.get("description", ""),
                                "input_schema": func.get("parameters", {}),
                            }
                        )
                if anthropic_tools:
                    params["tools"] = anthropic_tools

            params.update(kwargs)

            response = create_message(
                self.anthropic_client, params, base_url=self._get_backend_url(), provider="langdock", logger=_logger
            )

            # Extract text content
            content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    # Serialize tool input as JSON string for downstream compatibility
                    arguments = json.dumps(block.input) if isinstance(block.input, dict) else str(block.input)
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": arguments,
                            },
                        }
                    )

            return LLMResponse(
                content=content,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=response.stop_reason,
                tool_calls=tool_calls,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _google_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Google Gemini chat completion via Vertex AI compatible API."""
        try:
            # Convert messages to Gemini format
            contents = []
            system_instruction = None

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    # System instruction must be a string
                    if isinstance(content, list):
                        system_instruction = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
                    else:
                        system_instruction = content
                elif role == "assistant":
                    # Assistant messages are always text
                    if isinstance(content, list):
                        text = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
                        contents.append({"role": "model", "parts": [{"text": text}]})
                    else:
                        contents.append({"role": "model", "parts": [{"text": content}]})
                else:
                    # User messages can be multimodal
                    parts = self._convert_to_gemini_parts(content)
                    contents.append({"role": "user", "parts": parts})

            # Clamp temperature per model constraints
            clamped = clamp_temperature(model, temperature)

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": clamped if clamped is not None else temperature,
                    "maxOutputTokens": max_tokens or 8192,
                },
            }

            if system_instruction:
                # LangDock expects systemInstruction as simple string
                payload["systemInstruction"] = system_instruction

            # Make direct HTTP request to Gemini endpoint
            url = f"/models/{model}:generateContent"
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(f"Google API request URL: {_scrub(self._get_backend_url() + url)}")
                _logger.debug(f"Google API payload: {_scrub(json.dumps(payload, indent=2))}")

            response = self.http_client.post(url, json=payload)

            if response.status_code >= 400:
                self._raise_http_error(response, "Google API")

            data = response.json()

            # Extract content from Gemini response
            content = ""
            if "candidates" in data and data["candidates"]:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "text" in part:
                            content += part["text"]

            # Extract usage metadata
            usage = data.get("usageMetadata", {})

            return LLMResponse(
                content=content,
                model=model,
                input_tokens=usage.get("promptTokenCount", 0),
                output_tokens=usage.get("candidatesTokenCount", 0),
                # `candidates` is present but empty when the response was blocked,
                # so index into it only after confirming it is non-empty.
                finish_reason=(data.get("candidates") or [{}])[0].get("finishReason", "STOP"),
                tool_calls=[],
                raw_response=data,
            )

        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _codestral_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Codestral FIM (fill-in-the-middle) code completion."""
        try:
            # Extract prompt and suffix from messages
            prompt = ""
            suffix = ""

            for msg in messages:
                content = msg.get("content", "")
                if msg.get("role") == "user":
                    # Check for FIM markers
                    if "<|fim_prefix|>" in content:
                        parts = content.split("<|fim_prefix|>")
                        if len(parts) > 1:
                            prompt = parts[1].split("<|fim_suffix|>")[0] if "<|fim_suffix|>" in parts[1] else parts[1]
                        if "<|fim_suffix|>" in content:
                            suffix = content.split("<|fim_suffix|>")[-1].split("<|fim_middle|>")[0]
                    else:
                        prompt = content

            payload = {
                "model": model,
                "prompt": prompt,
                "suffix": suffix,
                "max_tokens": max_tokens or 2048,
            }
            payload.update(kwargs)

            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(f"Codestral FIM payload: {_scrub(json.dumps(payload, indent=2))}")

            response = self.http_client.post("/fim/completions", json=payload)

            if response.status_code >= 400:
                self._raise_http_error(response, "Codestral FIM")

            data = response.json()

            content = ""
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("text", "")

            usage = data.get("usage", {})

            return LLMResponse(
                content=content,
                model=model,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                finish_reason=(data.get("choices") or [{}])[0].get("finish_reason", "stop"),
                tool_calls=[],
                raw_response=data,
            )

        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: "list[ToolDefinition] | list[dict[str, Any]] | None" = None,
        *,
        reasoning_effort: str | None = None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """
        Stream a chat completion response through LangDock.

        Routes to the appropriate backend based on configuration.
        """
        model = self.resolve_model(model)
        # Accept ToolDefinition instances as the base class promises; the
        # backends below build request payloads from plain dicts.
        tools = normalize_tools(tools)

        if self.backend == "agent":
            yield from self._agent_stream_completion(messages, max_tokens, **kwargs)
        elif self.backend == "openai":
            yield from self._openai_stream_completion(
                messages, model, temperature, max_tokens, tools, reasoning_effort, **kwargs
            )
        elif self.backend == "anthropic":
            yield from self._anthropic_stream_completion(messages, model, temperature, max_tokens, tools, **kwargs)
        elif self.backend == "google":
            yield from self._google_stream_completion(messages, model, temperature, max_tokens, **kwargs)
        elif self.backend == "codestral":
            # Codestral doesn't support streaming well for FIM
            # Fall back to non-streaming
            response = self._codestral_completion(messages, model, max_tokens, **kwargs)
            yield StreamChunk(
                content=response.content,
                is_final=True,
                finish_reason=response.finish_reason,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def _openai_stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        reasoning_effort: str | None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """OpenAI-compatible streaming."""
        extra = dict(kwargs)
        if reasoning_effort:
            extra["reasoning_effort"] = reasoning_effort
        yield from self._get_openai_backend().stream_completion(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, tools=tools, **extra
        )

    def _agent_stream_completion(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """LangDock Agent streaming over the AI SDK 5 data-stream protocol.

        Sends the UIMessage payload with ``stream: true`` and translates the
        Server-Sent Events into StreamChunks as they arrive. Until 23.08.2026
        this sent ``stream: false`` and yielded one final chunk — which not only
        defeated streaming but risked LangDock's HTTP 524, raised on any
        non-streaming request that runs past 100 seconds.

        System messages are filtered out — agent instructions live in LangDock.
        """
        try:
            _logger.info(f"Agent stream: Original messages count: {len(messages)}")

            # Convert to Vercel AI SDK UIMessage format
            agent_messages = self._convert_to_agent_messages(messages)

            _logger.info(f"Agent stream: Converted messages count: {len(agent_messages)}")

            if not agent_messages:
                _logger.warning("Agent stream: No messages after filtering!")
                yield StreamChunk(
                    content="Der Agent benötigt eine Benutzernachricht. Bitte geben Sie Ihre Frage ein.",
                    is_final=True,
                    finish_reason="error",
                    input_tokens=0,
                    output_tokens=0,
                )
                return

            # Remove any conflicting kwargs
            kwargs.pop("model", None)
            kwargs.pop("temperature", None)
            kwargs.pop("max_tokens", None)

            emitted = 0
            for event in self._agent_request_events(agent_messages):
                kind = event.get("type")

                if kind == "text-delta":
                    delta = event.get("delta") or ""
                    if delta:
                        emitted += 1
                        yield StreamChunk(
                            content=delta,
                            is_final=False,
                            finish_reason=None,
                            input_tokens=0,
                            output_tokens=0,
                        )
                elif kind == "start":
                    model_name = (event.get("messageMetadata") or {}).get("modelName")
                    if model_name:
                        _logger.info(f"Agent stream: answering with {model_name}")
                # reasoning-*, text-start/-end, start-step, finish-step, tool-*
                # and data-* carry no user-visible text; ignoring unknown types
                # keeps a protocol addition from breaking us.

            if not emitted:
                _logger.warning("Agent stream: no text-delta events in the response")

            yield StreamChunk(
                content="",
                is_final=True,
                finish_reason="stop",
                input_tokens=0,
                output_tokens=0,
            )

        except httpx2.HTTPError as e:
            safe = _scrub(str(e))
            _logger.error(f"Agent stream HTTP error: {safe}")
            raise ProviderError(f"Agent HTTP error: {safe}", provider="langdock") from e
        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _anthropic_stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Anthropic-compatible streaming."""
        try:
            system_prompt, filtered_messages = self._extract_system_prompt(messages)

            params: dict[str, Any] = {
                "model": model,
                "messages": filtered_messages,
                "max_tokens": max_tokens or 4096,
            }

            # Clamp temperature per model constraints
            apply_anthropic_temperature(params, model, temperature)

            if system_prompt:
                params["system"] = system_prompt

            if tools:
                anthropic_tools = []
                for tool in tools:
                    if tool.get("type") == "function":
                        func = tool.get("function", {})
                        anthropic_tools.append(
                            {
                                "name": func.get("name"),
                                "description": func.get("description", ""),
                                "input_schema": func.get("parameters", {}),
                            }
                        )
                if anthropic_tools:
                    params["tools"] = anthropic_tools

            params.update(kwargs)

            # Track usage for final chunk
            final_input_tokens = 0
            final_output_tokens = 0

            # Accumulate tool calls from stream events
            # Key: content block index, Value: tool call data
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}
            current_block_index = 0

            with ExitStack() as stack:
                stream = open_message_stream(
                    stack,
                    self.anthropic_client,
                    params,
                    base_url=self._get_backend_url(),
                    provider="langdock",
                    logger=_logger,
                )
                for event in stream:
                    # Capture input tokens from message_start event
                    if event.type == "message_start":
                        if hasattr(event, "message") and hasattr(event.message, "usage"):
                            final_input_tokens = event.message.usage.input_tokens or 0

                    # Capture output tokens from message_delta event
                    elif event.type == "message_delta":
                        if hasattr(event, "usage"):
                            final_output_tokens = event.usage.output_tokens or 0

                    # Track content block index and handle tool_use blocks
                    elif event.type == "content_block_start":
                        current_block_index = getattr(event, "index", 0)
                        # Check if this is a tool_use block
                        if hasattr(event, "content_block"):
                            block = event.content_block
                            if hasattr(block, "type") and block.type == "tool_use":
                                # Initialize tool call accumulator
                                accumulated_tool_calls[current_block_index] = {
                                    "id": getattr(block, "id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": getattr(block, "name", ""),
                                        "arguments": "",
                                    },
                                }
                                # Emit tool_call_delta for the start
                                yield StreamChunk(
                                    content="",
                                    is_final=False,
                                    tool_call_delta={
                                        "index": current_block_index,
                                        "id": getattr(block, "id", ""),
                                        "function": {
                                            "name": getattr(block, "name", ""),
                                            "arguments": None,
                                        },
                                    },
                                )

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            yield StreamChunk(
                                content=delta.text,
                                is_final=False,
                            )
                        # Handle tool input JSON deltas
                        elif hasattr(delta, "type") and delta.type == "input_json_delta":
                            partial_json = getattr(delta, "partial_json", "")
                            if current_block_index in accumulated_tool_calls:
                                # Accumulate the JSON arguments
                                accumulated_tool_calls[current_block_index]["function"]["arguments"] += partial_json
                                # Emit tool_call_delta
                                yield StreamChunk(
                                    content="",
                                    is_final=False,
                                    tool_call_delta={
                                        "index": current_block_index,
                                        "id": None,
                                        "function": {
                                            "name": None,
                                            "arguments": partial_json,
                                        },
                                    },
                                )

                    elif event.type == "message_stop":
                        # Build complete tool calls list
                        complete_tool_calls = None
                        if accumulated_tool_calls:
                            complete_tool_calls = [
                                accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())
                            ]

                        yield StreamChunk(
                            content="",
                            is_final=True,
                            finish_reason="end_turn",
                            tool_calls=complete_tool_calls,
                            input_tokens=final_input_tokens,
                            output_tokens=final_output_tokens,
                        )

        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _convert_to_gemini_parts(self, content: str | list[Any]) -> list[dict[str, Any]]:
        """Convert OpenAI-style content to Gemini parts format.

        Args:
            content: Either a string or OpenAI multimodal content array

        Returns:
            List of Gemini parts (text or inlineData)
        """
        # Simple string content
        if isinstance(content, str):
            return [{"text": content}] if content else [{"text": ""}]

        # Multimodal content array (OpenAI format)
        parts = []
        for item in content:
            item_type = item.get("type", "")

            if item_type == "text":
                text = item.get("text", "")
                if text:
                    parts.append({"text": text})

            elif item_type == "image_url":
                # OpenAI format: {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
                image_url = item.get("image_url", {})
                url = image_url.get("url", "")

                if url.startswith("data:"):
                    # Parse data URL: data:image/png;base64,<data>
                    try:
                        # Format: data:<mime>;base64,<data>
                        header, data = url.split(",", 1)
                        mime_type = header.split(":")[1].split(";")[0]
                        parts.append(
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": data,
                                }
                            }
                        )
                    except (ValueError, IndexError) as e:
                        _logger.warning(f"Failed to parse image data URL: {e}")
                else:
                    # External URL - Gemini doesn't support external URLs in inlineData
                    _logger.warning(f"Gemini does not support external image URLs: {url[:50]}...")

        # Ensure at least one part
        if not parts:
            parts.append({"text": ""})

        return parts

    def _google_stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Google Gemini streaming via Server-Sent Events."""
        try:
            contents = []
            system_instruction = None

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    # System instruction must be a string
                    if isinstance(content, list):
                        # Extract text from multimodal content
                        system_instruction = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
                    else:
                        system_instruction = content
                elif role == "assistant":
                    # Assistant messages are always text
                    if isinstance(content, list):
                        text = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
                        contents.append({"role": "model", "parts": [{"text": text}]})
                    else:
                        contents.append({"role": "model", "parts": [{"text": content}]})
                else:
                    # User messages can be multimodal
                    parts = self._convert_to_gemini_parts(content)
                    contents.append({"role": "user", "parts": parts})

            # Clamp temperature per model constraints
            clamped = clamp_temperature(model, temperature)

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": clamped if clamped is not None else temperature,
                    "maxOutputTokens": max_tokens or 8192,
                },
            }

            if system_instruction:
                # LangDock expects systemInstruction as simple string
                payload["systemInstruction"] = system_instruction

            # `alt=sse` is not optional: without it the endpoint answers
            # Content-Type application/json with a single JSON *array* of chunks,
            # the `data: ` parser below matches nothing, and the caller gets an
            # empty stream with no error to show for it. With it, the same
            # endpoint returns text/event-stream. Verified live 23.08.2026.
            url = f"/models/{model}:streamGenerateContent?alt=sse"
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(f"Google streaming URL: {_scrub(self._get_backend_url() + url)}")
                _logger.debug(f"Google streaming payload: {_scrub(json.dumps(payload, indent=2))}")

            with self.http_client.stream("POST", url, json=payload) as response:
                if response.status_code >= 400:
                    # A streamed response has no body yet — read it before use.
                    response.read()
                    self._raise_http_error(response, "Google streaming")

                total_input_tokens = 0
                total_output_tokens = 0

                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    content = ""
                    if "candidates" in data and data["candidates"]:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            for part in candidate["content"]["parts"]:
                                if "text" in part:
                                    content += part["text"]

                    usage = data.get("usageMetadata", {})
                    if usage:
                        total_input_tokens = usage.get("promptTokenCount", total_input_tokens)
                        total_output_tokens = usage.get("candidatesTokenCount", total_output_tokens)

                    is_final = (
                        "candidates" in data
                        and data["candidates"]
                        and data["candidates"][0].get("finishReason") is not None
                    )

                    yield StreamChunk(
                        content=content,
                        is_final=is_final,
                        finish_reason=data.get("candidates", [{}])[0].get("finishReason"),
                        input_tokens=total_input_tokens if is_final else 0,
                        output_tokens=total_output_tokens if is_final else 0,
                    )

        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models from LangDock.

        Returns models based on the configured backend.
        For agent backend, returns the agent's available models.

        Returns:
            List of model dicts with 'id', 'name', constraints, and metadata.
        """
        try:
            if self.backend == "openai":
                return self._list_openai_models()
            elif self.backend == "anthropic":
                return self._list_anthropic_models()
            elif self.backend == "google":
                return self._list_google_models()
            elif self.backend == "codestral":
                return self._list_codestral_models()
            elif self.backend == "agent":
                return self._list_agent_models()
            else:
                return []

        except ProviderError:
            # Already a typed error carrying status/context. Routing it through
            # _handle_error() again would flatten it to a bare ProviderError and
            # drop the status code the caller needs.
            raise
        except Exception as e:
            raise self._handle_error(e) from e

    def _list_openai_models(self) -> list[dict[str, Any]]:
        """Every model LangDock's OpenAI endpoint lists for this workspace."""
        models = self.openai_client.models.list()
        base = self._get_backend_url()
        result = [
            {
                "id": model.id,
                "name": model.id,
                "created": getattr(model, "created", None),
                "owned_by": getattr(model, "owned_by", "langdock"),
                "provider": self.provider_name,
                "backend": self.backend,
                "region": self.region,
                **param_learning.model_metadata(base, model.id),
            }
            for model in models.data
        ]
        result.sort(key=lambda m: m["id"])
        return result

    def _list_anthropic_models(self) -> list[dict[str, Any]]:
        """Anthropic models LangDock lists, with what the Models API reports."""
        try:
            return list_anthropic_models(
                self.anthropic_client,
                self._get_backend_url(),
                self.provider_name,
                backend=self.backend,
                region=self.region,
            )
        except (AttributeError, KeyError, TypeError) as e:
            # No static fallback list: an unknown model list is an empty one.
            _logger.warning("Anthropic model listing not supported by this endpoint: %s", e)
            return []

    def _list_google_models(self) -> list[dict[str, Any]]:
        """List Google Gemini models by asking LangDock, not from a hardcoded list.

        This used to return a hand-maintained ("gemini-2.5-flash", "gemini-2.5-pro")
        pair. LangDock retired 2.5-flash, so both the catalogue and the backend
        default pointed at a model that answers
        ``400 Invalid model, available models are: …`` — every default-model call
        to this backend failed. The endpoint below is the same one that error
        message is generated from, so it cannot go stale.

        Gemini reports ids as ``models/<id>``; the prefix is stripped because
        sending it back is itself a 400.
        """
        response = self.http_client.get("/models")
        response.raise_for_status()
        data = response.json()

        result = []
        for model in data.get("models", []):
            model_id = str(model.get("name", "")).removeprefix("models/")
            if not model_id:
                continue
            thinking = model.get("thinking")
            result.append(
                {
                    "id": model_id,
                    "name": model_id.replace("-", " ").title(),
                    "provider": self.provider_name,
                    "backend": self.backend,
                    "region": self.region,
                    **param_learning.model_metadata(
                        self._get_backend_url(),
                        model_id,
                        context_length=model.get("inputTokenLimit"),
                        max_output_tokens=model.get("outputTokenLimit"),
                        default_temperature=model.get("temperature"),
                        max_temperature=model.get("maxTemperature"),
                        supports_reasoning=thinking if isinstance(thinking, bool) else None,
                    ),
                }
            )
        return result

    def _list_codestral_models(self) -> list[dict[str, Any]]:
        """Deliberately empty: Codestral is FIM-only, not a chat model.

        LangDock does serve ``GET /mistral/eu/v1/models``, but surfacing that
        here would put a fill-in-the-middle model into a chat model picker, where
        it cannot answer. Callers address it explicitly with ``model=``.
        """
        return []

    def _list_agent_models(self) -> list[dict[str, Any]]:
        """List models available for LangDock agents."""
        try:
            response = self.http_client.get("/models")
            response.raise_for_status()
            data = response.json()

            result = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                result.append(
                    {
                        "id": model_id,
                        "name": model.get("name", model_id),
                        "provider": self.provider_name,
                        "backend": self.backend,
                        **param_learning.model_metadata(self._get_backend_url(), model_id),
                    }
                )
            return result
        except (AttributeError, KeyError, TypeError, ConnectionError) as e:
            _logger.warning("Agent model listing failed, returning empty list: %s", e)
            return []

    def _raise_http_error(self, response: Any, label: str) -> None:
        """Raise a typed error that carries the upstream body, not just the status.

        ``response.raise_for_status()`` produces "Client error '400 Bad Request'
        for url …" and nothing else, so the reason — a retired model id, a
        missing workspace entitlement — only ever reached a log line. Feeding the
        body through _handle_error keeps the typed mapping (401 -> Authentication,
        429 -> RateLimit) while making the cause visible to the caller.
        """
        detail = _safe_detail(response.text)
        message = f"{label} error {response.status_code}: {detail}"
        _logger.error(message)
        error = self._handle_error(Exception(message))
        if error.status_code is None:
            error.status_code = response.status_code
        raise error

    def _handle_error(self, error: Exception) -> ProviderError:
        """Convert exceptions to ProviderError types."""
        error_str = str(error).lower()

        if "rate limit" in error_str or "429" in error_str:
            return RateLimitError(
                message=str(error),
                provider=self.provider_name,
                status_code=429,
            )

        if "authentication" in error_str or "401" in error_str or "unauthorized" in error_str:
            return AuthenticationError(
                message=str(error),
                provider=self.provider_name,
                status_code=401,
            )

        if "context" in error_str or "token" in error_str:
            return ContextLengthError(
                message=str(error),
                provider=self.provider_name,
            )

        return ProviderError(
            message=str(error),
            provider=self.provider_name,
        )

    def upload_attachment(
        self,
        file_data: bytes,
        filename: str,
        mimetype: str,
    ) -> dict[str, Any]:
        """
        Upload a file attachment for use with LangDock Agents.

        This is a wrapper method that delegates to LangDockAgentManager.
        Used when sending files to Agent-based conversations.

        Args:
            file_data: Raw file bytes
            filename: Original filename
            mimetype: MIME type of the file

        Returns:
            dict containing:
                - attachmentId: UUID to reference in messages
                - file: File metadata from LangDock
        """
        manager = LangDockAgentManager(api_key=self.api_key, timeout=self.timeout)
        return manager.upload_attachment(
            file_data=file_data,
            filename=filename,
            mimetype=mimetype,
        )

    def __del__(self) -> None:
        """Cleanup HTTP client on deletion."""
        if self._http_client is not None:
            try:
                self._http_client.close()
            except (OSError, RuntimeError):
                pass  # Ignore cleanup errors during interpreter shutdown
        backend = getattr(self, "_openai_backend", None)
        if backend is not None:
            try:
                backend.close()
            except (OSError, RuntimeError):
                pass  # Ignore cleanup errors during interpreter shutdown


# ============================================================================
# Agent API Foundation (for future expansion)
# ============================================================================


class LangDockAgentManager:
    """
    Manager for LangDock Agents.

    Provides methods to create, update, and manage LangDock agents
    with knowledge folders.

    Future feature - foundation for Phase 4 (MCP Integration).
    """

    BASE_URL = "https://api.langdock.com/agent/v1"

    def __init__(self, api_key: str, timeout: float = 60.0):
        """
        Initialize Agent Manager.

        Args:
            api_key: LangDock API key
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx2.Client | None = None

    @property
    def client(self) -> httpx2.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx2.Client(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    # -------------------------------------------------------------------------
    # Agent Attachment Upload
    # -------------------------------------------------------------------------

    def upload_attachment(
        self,
        file_data: bytes,
        filename: str,
        mimetype: str,
    ) -> dict[str, Any]:
        """
        Upload a file attachment for use with LangDock Agents.

        LangDock Agent API uses attachmentIds instead of inline base64 content.
        Files must be uploaded first, then referenced by ID in agent messages.

        API: POST https://api.langdock.com/attachment/v1/upload

        Args:
            file_data: Raw file bytes
            filename: Original filename
            mimetype: MIME type of the file

        Returns:
            dict with:
                - attachmentId: UUID string to reference in agent messages
                - file: {name, mimeType, sizeInBytes}

        Raises:
            ProviderError: If upload fails
        """
        # IMPORTANT: Attachment endpoint is NOT under /agent/v1
        # It's directly at https://api.langdock.com/attachment/v1/upload
        upload_url = "https://api.langdock.com/attachment/v1/upload"

        try:
            # Use multipart/form-data for file upload
            files = {
                "file": (filename, file_data, mimetype),
            }

            response = httpx2.post(
                upload_url,
                files=files,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    # Don't set Content-Type - httpx sets it automatically for multipart
                },
                timeout=120.0,  # Longer timeout for file uploads
                follow_redirects=False,
            )

            if response.status_code != 200:
                detail = _safe_detail(response.text)
                _logger.error(f"Attachment upload failed {response.status_code}: {detail}")
                raise ProviderError(
                    f"Attachment upload failed: {detail}",
                    provider="langdock",
                    status_code=response.status_code,
                )

            result = response.json()
            attachment_id = result.get("attachmentId")
            file_info = result.get("file", {})

            _logger.info(
                f"Uploaded attachment '{filename}' ({mimetype}, {len(file_data)} bytes) "
                f"-> attachmentId: {attachment_id}"
            )

            return {
                "attachmentId": attachment_id,
                "file": file_info,
            }

        except httpx2.RequestError as e:
            _logger.error(f"Attachment upload request error: {_scrub(str(e))}")
            raise ProviderError(
                f"Attachment upload failed: {_scrub(str(e))}",
                provider="langdock",
            ) from e

    def create_agent(
        self,
        name: str,
        instruction: str,
        model: str,
        knowledge_folder_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Create a new LangDock agent.

        Args:
            name: Agent name
            instruction: System instruction for the agent
            model: Model the agent runs (required; there is no default)
            knowledge_folder_ids: List of knowledge folder IDs to attach
            **kwargs: Additional agent configuration (e.g. creativity, webSearch)

        Returns:
            Created agent data
        """
        payload: dict[str, Any] = {
            "name": name,
            "instruction": instruction,
            "model": model,
        }

        if knowledge_folder_ids:
            payload["knowledgeFolderIds"] = knowledge_folder_ids

        payload.update(kwargs)

        response = self.client.post("/create", json=payload)
        response.raise_for_status()
        value: dict[str, Any] = response.json()
        return value

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        """
        Get agent details.

        Args:
            agent_id: Agent ID

        Returns:
            Agent data
        """
        response = self.client.get("/get", params={"agentId": agent_id})
        response.raise_for_status()
        value: dict[str, Any] = response.json()
        return value

    def update_agent(self, agent_id: str, **kwargs: Any) -> dict[str, Any]:
        """
        Update an existing agent.

        Args:
            agent_id: Agent ID
            **kwargs: Fields to update

        Returns:
            Updated agent data
        """
        payload = {"agentId": agent_id, **kwargs}
        response = self.client.patch("/update", json=payload)
        response.raise_for_status()
        value: dict[str, Any] = response.json()
        return value

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models for agents.

        Returns:
            List of available models
        """
        response = self.client.get("/models")
        response.raise_for_status()
        value: list[dict[str, Any]] = response.json().get("data", [])
        return value

    def __del__(self) -> None:
        """Cleanup HTTP client."""
        if self._client is not None:
            try:
                self._client.close()
            except (OSError, RuntimeError):
                pass  # Ignore cleanup errors during interpreter shutdown


# ============================================================================
# Knowledge Folder API Foundation (for future RAG expansion)
# ============================================================================


class LangDockKnowledgeManager:
    """
    Manager for LangDock Knowledge Folders.

    Provides methods to manage knowledge folders and files
    for RAG-based retrieval.

    Future feature - foundation for Phase 3 (RAG Integration).
    """

    BASE_URL = "https://api.langdock.com"

    def __init__(self, api_key: str, timeout: float = 120.0):
        """
        Initialize Knowledge Manager.

        Args:
            api_key: LangDock API key
            timeout: Request timeout (longer for file uploads)
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx2.Client | None = None

    @property
    def client(self) -> httpx2.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx2.Client(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=self.timeout,
            )
        return self._client

    def upload_file(
        self,
        folder_id: str,
        file_path: str,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file to a knowledge folder.

        Args:
            folder_id: Knowledge folder ID
            file_path: Path to the file
            filename: Optional custom filename

        Returns:
            Upload result
        """
        import os

        if filename is None:
            filename = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            response = self.client.post(
                f"/knowledge/{folder_id}",
                files=files,
            )
            response.raise_for_status()
            value: dict[str, Any] = response.json()
            return value

    def list_files(self, folder_id: str) -> list[dict[str, Any]]:
        """
        List files in a knowledge folder.

        Args:
            folder_id: Knowledge folder ID

        Returns:
            List of files
        """
        response = self.client.get(f"/knowledge/{folder_id}/list")
        response.raise_for_status()
        value: list[dict[str, Any]] = response.json().get("result", [])
        return value

    def delete_file(self, folder_id: str, file_id: str) -> bool:
        """
        Delete a file from a knowledge folder.

        Args:
            folder_id: Knowledge folder ID
            file_id: File ID

        Returns:
            True if successful
        """
        response = self.client.delete(f"/knowledge/{folder_id}/{file_id}")
        response.raise_for_status()
        return True

    def search(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge folders for relevant content.

        Searches across all knowledge folders assigned to the API key.
        Folder access is controlled via explicit API key assignment in LangDock.

        Args:
            query: Search query

        Returns:
            List of matching documents/chunks
        """
        response = self.client.post(
            "/knowledge/search",
            json={"query": query},
        )
        response.raise_for_status()
        value: list[dict[str, Any]] = response.json().get("result", [])
        return value

    def __del__(self) -> None:
        """Cleanup HTTP client."""
        if self._client is not None:
            try:
                self._client.close()
            except (OSError, RuntimeError):
                pass  # Ignore cleanup errors during interpreter shutdown
