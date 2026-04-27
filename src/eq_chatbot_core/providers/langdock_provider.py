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
from collections.abc import Iterator
from typing import Any

import httpx

from eq_chatbot_core.providers.base import (
    AuthenticationError,
    BaseLLMProvider,
    ContextLengthError,
    LLMResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
)
from eq_chatbot_core.providers.temperature_constraints import (
    clamp_temperature,
    get_temperature_constraints,
)

_logger = logging.getLogger(__name__)


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

    # Model context lengths
    MODEL_CONTEXT_LENGTHS = {
        # OpenAI models
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-5": 200000,
        "o1": 200000,
        "o1-mini": 128000,
        "o1-preview": 128000,
        "o3": 200000,
        "o3-mini": 200000,
        "o4-mini": 200000,
        # Anthropic models
        "claude-3-5-sonnet": 200000,
        "claude-3-5-haiku": 200000,
        "claude-sonnet-4": 200000,
        "claude-opus-4": 200000,
        # Google models (LangDock supports 2.5 series)
        "gemini-2.5-flash": 1000000,
        "gemini-2.5-pro": 1000000,
        # Codestral
        "codestral": 32000,
    }

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
        """
        super().__init__(api_key, base_url or self.BASE_URL, timeout, max_retries)

        # Initialize clients BEFORE validation to ensure __del__ works
        self._http_client: httpx.Client | None = None
        self._openai_client: Any = None
        self._anthropic_client: Any = None

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

    @property
    def default_model(self) -> str:
        """Return default model based on backend."""
        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "google": "gemini-2.5-flash",
            "codestral": "codestral-latest",
            "agent": None,  # Agent uses its configured model
        }
        return defaults.get(self.backend, "gpt-4o")

    def _get_backend_url(self) -> str:
        """Get the full base URL for the current backend."""
        pattern = self.BACKENDS[self.backend]
        if "{region}" in pattern:
            return f"{self.base_url}{pattern.format(region=self.region)}"
        return f"{self.base_url}{pattern}"

    @property
    def http_client(self) -> httpx.Client:
        """Get or create HTTP client for direct API calls."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                base_url=self._get_backend_url(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._http_client

    @property
    def openai_client(self) -> Any:
        """Get or create OpenAI client for OpenAI-compatible backends."""
        if self._openai_client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Install with: pip install openai") from e

            self._openai_client = OpenAI(
                api_key=self.api_key,
                base_url=self._get_backend_url(),
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._openai_client

    @property
    def anthropic_client(self) -> Any:
        """Get or create Anthropic client for Anthropic backend."""
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise ImportError("Anthropic package not installed. Install with: pip install anthropic") from e

            self._anthropic_client = Anthropic(
                api_key=self.api_key,
                base_url=self._get_backend_url(),
                timeout=self.timeout,
                max_retries=self.max_retries,
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
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Send a chat completion request through LangDock.

        Routes to the appropriate backend based on configuration.
        """
        model = model or self.default_model

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
        **kwargs,
    ) -> LLMResponse:
        """OpenAI-compatible chat completion."""
        try:
            params: dict[str, Any] = {
                "messages": messages,
                "model": model,
            }

            # Clamp temperature per model constraints (skip for reasoning models)
            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

            # Handle max_tokens
            if max_tokens:
                # New API models use max_completion_tokens
                if self._uses_new_token_api(model):
                    params["max_completion_tokens"] = max_tokens
                else:
                    params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

            # Add reasoning_effort for compatible models
            effort = reasoning_effort or self.reasoning_effort
            if effort and self._is_reasoning_model(model):
                params["reasoning_effort"] = effort

            params.update(kwargs)

            response = self.openai_client.chat.completions.create(**params)

            choice = response.choices[0]
            tool_calls = []

            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

        except Exception as e:
            raise self._handle_error(e) from e

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

    def _agent_chat_completion(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None,
        **kwargs,
    ) -> LLMResponse:
        """LangDock Agent chat completion using httpx directly.

        LangDock Agent API requires agentId parameter, not model.
        Uses Vercel AI SDK UIMessage format with agent-specific endpoint.
        System messages are filtered out - agent instructions are in LangDock.
        """
        try:
            agent_url = f"{self.base_url}/agent/v1/chat/completions"

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

            payload = {
                "agentId": self.agent_id,
                "messages": agent_messages,
                "stream": False,
            }

            _logger.info(f"Agent request to {agent_url}")
            _logger.info(f"Agent payload: agentId={self.agent_id}, messages_count={len(agent_messages)}")
            _logger.debug(f"Full payload: {json.dumps(payload, default=str)}")

            response = httpx.post(
                agent_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
                follow_redirects=False,
            )

            if response.status_code != 200:
                error_text = response.text
                _logger.error(f"Agent API error {response.status_code}: {error_text}")
                raise ProviderError(
                    f"Agent API error {response.status_code}: {error_text}",
                    provider="langdock",
                    status_code=response.status_code,
                )

            data = response.json()
            _logger.info(f"Agent sync response keys: {list(data.keys())}")
            _logger.debug(f"Agent response: {json.dumps(data, default=str)[:500]}")

            content = ""
            finish_reason = "stop"

            # Vercel AI SDK format: {"messages": [{"id": "...", "role": "assistant", "content": "..."}]}
            resp_messages = data.get("messages", [])
            if resp_messages:
                _logger.info(f"Agent sync: Found {len(resp_messages)} response messages")
                # Find the last assistant message
                for item in reversed(resp_messages):
                    if item.get("role") == "assistant":
                        content = item.get("content", "")
                        if content:
                            _logger.info(f"Agent sync: Found text content with {len(content)} chars")
                            break

            return LLMResponse(
                content=content,
                model=data.get("model", f"agent:{self.agent_id}"),
                input_tokens=0,
                output_tokens=0,
                finish_reason=finish_reason,
                tool_calls=[],
                raw_response=data,
            )

        except httpx.HTTPError as e:
            _logger.error(f"Agent HTTP error: {e}")
            raise ProviderError(f"Agent HTTP error: {e}", provider="langdock") from e
        except Exception as e:
            raise self._handle_error(e) from e

    def _anthropic_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs,
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
            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

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

            response = self.anthropic_client.messages.create(**params)

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

        except Exception as e:
            raise self._handle_error(e) from e

    def _google_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        **kwargs,
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
            _logger.debug(f"Google API request URL: {self._get_backend_url()}{url}")
            _logger.debug(f"Google API payload: {json.dumps(payload, indent=2)}")

            response = self.http_client.post(url, json=payload)

            # Log error details before raising
            if response.status_code >= 400:
                _logger.error(f"Google API error {response.status_code}: {response.text}")

            response.raise_for_status()

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
                finish_reason=data.get("candidates", [{}])[0].get("finishReason", "STOP"),
                tool_calls=[],
                raw_response=data,
            )

        except Exception as e:
            raise self._handle_error(e) from e

    def _codestral_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int | None,
        **kwargs,
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

            _logger.debug(f"Codestral FIM payload: {json.dumps(payload, indent=2)}")

            response = self.http_client.post("/fim/completions", json=payload)

            # Log error details before raising
            if response.status_code >= 400:
                _logger.error(f"Codestral FIM error {response.status_code}: {response.text}")

            response.raise_for_status()

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
                finish_reason=data.get("choices", [{}])[0].get("finish_reason", "stop"),
                tool_calls=[],
                raw_response=data,
            )

        except Exception as e:
            raise self._handle_error(e) from e

    def stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        reasoning_effort: str | None = None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """
        Stream a chat completion response through LangDock.

        Routes to the appropriate backend based on configuration.
        """
        model = model or self.default_model

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
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """OpenAI-compatible streaming."""
        try:
            params: dict[str, Any] = {
                "messages": messages,
                "model": model,
                "stream": True,
                "stream_options": {"include_usage": True},
            }

            # Clamp temperature per model constraints (skip for reasoning models)
            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

            if max_tokens:
                if self._uses_new_token_api(model):
                    params["max_completion_tokens"] = max_tokens
                else:
                    params["max_tokens"] = max_tokens

            if tools:
                params["tools"] = tools

            effort = reasoning_effort or self.reasoning_effort
            if effort and self._is_reasoning_model(model):
                params["reasoning_effort"] = effort

            params.update(kwargs)

            stream = self.openai_client.chat.completions.create(**params)

            final_input_tokens = 0
            final_output_tokens = 0

            # Accumulate tool calls from deltas
            # Key: tool call index, Value: accumulated tool call data
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            for chunk in stream:
                if hasattr(chunk, "usage") and chunk.usage:
                    final_input_tokens = chunk.usage.prompt_tokens or 0
                    final_output_tokens = chunk.usage.completion_tokens or 0

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                content = delta.content or ""
                is_final = choice.finish_reason is not None

                tool_call_delta = None
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        tool_call_delta = {
                            "index": idx,
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name if tc.function else None,
                                "arguments": tc.function.arguments if tc.function else None,
                            },
                        }

                        # Accumulate tool call data
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            }

                        # Update with new data (deltas send partial data)
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                # On final chunk, include accumulated tool calls
                complete_tool_calls = None
                if is_final and accumulated_tool_calls:
                    # Convert dict to sorted list by index
                    complete_tool_calls = [accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())]

                yield StreamChunk(
                    content=content,
                    is_final=is_final,
                    finish_reason=choice.finish_reason,
                    tool_call_delta=tool_call_delta,
                    tool_calls=complete_tool_calls,
                    input_tokens=final_input_tokens if is_final else 0,
                    output_tokens=final_output_tokens if is_final else 0,
                )

        except Exception as e:
            raise self._handle_error(e) from e

    def _agent_stream_completion(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None,
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """LangDock Agent streaming using httpx directly.

        LangDock Agent API requires agentId parameter, not model.
        Uses Vercel AI SDK UIMessage format. Currently non-streaming POST.
        System messages are filtered out - agent instructions are in LangDock.
        """
        try:
            agent_url = f"{self.base_url}/agent/v1/chat/completions"

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

            payload = {
                "agentId": self.agent_id,
                "messages": agent_messages,
                "stream": False,
            }

            # Remove any conflicting kwargs
            kwargs.pop("model", None)
            kwargs.pop("temperature", None)
            kwargs.pop("max_tokens", None)

            _logger.info(f"Agent stream request to {agent_url}")
            _logger.info(f"Agent stream payload: agentId={self.agent_id}, messages_count={len(agent_messages)}")
            _logger.debug(f"Full payload: {json.dumps(payload, default=str)}")

            response = httpx.post(
                agent_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
                follow_redirects=False,
            )

            if response.status_code != 200:
                _logger.error(f"Agent error {response.status_code}: {response.text}")
                raise ProviderError(
                    f"Agent API error {response.status_code}: {response.text}",
                    provider="langdock",
                    status_code=response.status_code,
                )

            data = response.json()
            _logger.info(f"Agent stream response keys: {list(data.keys())}")

            content = ""
            finish_reason = "stop"

            # Vercel AI SDK format: {"messages": [{"id": "...", "role": "assistant", "content": "..."}]}
            resp_messages = data.get("messages", [])
            if resp_messages:
                _logger.info(f"Agent stream: Found {len(resp_messages)} response messages")
                for item in reversed(resp_messages):
                    if item.get("role") == "assistant":
                        content = item.get("content", "")
                        if content:
                            _logger.info(f"Agent stream: Found content with {len(content)} chars")
                            break

            if content:
                yield StreamChunk(
                    content=content,
                    is_final=True,
                    finish_reason=finish_reason,
                    input_tokens=0,
                    output_tokens=0,
                )
            else:
                _logger.warning(f"Agent stream: No content found. Keys: {list(data.keys())}")

        except httpx.HTTPError as e:
            _logger.error(f"Agent stream HTTP error: {e}")
            raise ProviderError(f"Agent HTTP error: {e}", provider="langdock") from e
        except Exception as e:
            raise self._handle_error(e) from e

    def _anthropic_stream_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
        **kwargs,
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
            clamped = clamp_temperature(model, temperature)
            if clamped is not None:
                params["temperature"] = clamped

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

            with self.anthropic_client.messages.stream(**params) as stream:
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

        except Exception as e:
            raise self._handle_error(e) from e

    def _convert_to_gemini_parts(self, content: str | list) -> list[dict[str, Any]]:
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
        **kwargs,
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

            # LangDock Google API uses standard streaming endpoint
            url = f"/models/{model}:streamGenerateContent"
            _logger.debug(f"Google streaming URL: {self._get_backend_url()}{url}")
            _logger.debug(f"Google streaming payload: {json.dumps(payload, indent=2)}")

            with self.http_client.stream("POST", url, json=payload) as response:
                # Log error details before raising
                if response.status_code >= 400:
                    error_text = response.read().decode("utf-8", errors="replace")
                    _logger.error(f"Google streaming error {response.status_code}: {error_text}")
                response.raise_for_status()

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

        except Exception as e:
            raise self._handle_error(e) from e

    def _get_model_constraints(self, model_id: str) -> dict[str, Any]:
        """Get temperature, token, and capability constraints for a model."""
        model_lower = model_id.lower()

        # Use shared temperature constraints for accurate min/max
        temp_constraints = get_temperature_constraints(model_id)
        is_reasoning = not temp_constraints["supports_temperature"]

        # Check if model supports vision
        # GPT-4o/4-turbo/5, Claude 3+, Gemini, O1/O3/O4 support vision
        supports_vision = False

        # GPT vision models
        if any(model_lower.startswith(p) for p in ("gpt-4o", "gpt-4-turbo", "gpt-5")):
            supports_vision = True
        # O-series reasoning models with vision
        elif any(model_lower.startswith(p) for p in ("o1", "o3", "o4")):
            supports_vision = True
        # Gemini models
        elif model_lower.startswith("gemini"):
            supports_vision = True
        # Claude 3+ models (various naming patterns)
        elif "claude" in model_lower:
            if any(v in model_lower for v in ("-3-", "-3.", "-4-", "-4.", "haiku", "sonnet", "opus")):
                supports_vision = True

        # Get context length
        context_length = None
        for prefix, length in self.MODEL_CONTEXT_LENGTHS.items():
            if model_lower.startswith(prefix):
                context_length = length
                break

        if is_reasoning:
            return {
                "supports_temperature": False,
                "default_temperature": 1.0,
                "min_temperature": 1.0,
                "max_temperature": 1.0,
                "supports_reasoning": True,
                "supports_vision": supports_vision,
                "max_output_tokens": 100000 if "o1" in model_lower else 65536,
                "default_max_tokens": 16384,
                "context_length": context_length or 200000,
            }
        else:
            # Determine max_output based on model family
            if "claude" in model_lower:
                max_output = 8192
            elif "gemini" in model_lower:
                max_output = 8192
            elif "codestral" in model_lower:
                max_output = 16384
            else:
                max_output = 16384

            return {
                "supports_temperature": True,
                "default_temperature": 1.0,
                "min_temperature": temp_constraints["min"],
                "max_temperature": temp_constraints["max"],
                "supports_reasoning": False,
                "supports_vision": supports_vision,
                "max_output_tokens": max_output,
                "default_max_tokens": 4096,
                "context_length": context_length or 128000,
            }

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

        except Exception as e:
            raise self._handle_error(e) from e

    def _list_openai_models(self) -> list[dict[str, Any]]:
        """List OpenAI models available via LangDock."""
        models = self.openai_client.models.list()

        # LangDock-supported OpenAI models
        supported_prefixes = (
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-5",
            "o1",
            "o3",
            "o4",
        )

        result = []
        for model in models.data:
            model_id = model.id.lower()
            if any(model_id.startswith(prefix) for prefix in supported_prefixes):
                constraints = self._get_model_constraints(model.id)
                result.append(
                    {
                        "id": model.id,
                        "name": model.id,
                        "created": getattr(model, "created", None),
                        "owned_by": getattr(model, "owned_by", "langdock"),
                        "provider": self.provider_name,
                        "backend": self.backend,
                        "region": self.region,
                        **constraints,
                    }
                )

        result.sort(key=lambda m: m["id"])
        return result

    def _list_anthropic_models(self) -> list[dict[str, Any]]:
        """List Anthropic models available via LangDock."""
        try:
            models_response = self.anthropic_client.models.list(limit=100)

            result = []
            for model in models_response.data:
                constraints = self._get_model_constraints(model.id)
                # Use 'or' to handle None values (getattr returns None if attr is None)
                model_name = getattr(model, "display_name", None) or model.id
                result.append(
                    {
                        "id": model.id,
                        "name": model_name,
                        "created": getattr(model, "created_at", None),
                        "provider": self.provider_name,
                        "backend": self.backend,
                        "region": self.region,
                        **constraints,
                    }
                )

            result.sort(key=lambda m: m.get("created") or "", reverse=True)
            return result
        except (AttributeError, KeyError, TypeError) as e:
            # Fallback to known models if API doesn't support listing
            _logger.warning("Anthropic model listing not supported, using known models: %s", e)
            return self._get_known_anthropic_models()

    def _get_known_anthropic_models(self) -> list[dict[str, Any]]:
        """Return known Anthropic models as fallback."""
        known_models = [
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ]
        result = []
        for model_id in known_models:
            constraints = self._get_model_constraints(model_id)
            result.append(
                {
                    "id": model_id,
                    "name": model_id,
                    "provider": self.provider_name,
                    "backend": self.backend,
                    "region": self.region,
                    **constraints,
                }
            )
        return result

    def _list_google_models(self) -> list[dict[str, Any]]:
        """List Google Gemini models available via LangDock."""
        # LangDock supports only Gemini 2.5 series
        known_models = [
            ("gemini-2.5-flash", "Gemini 2.5 Flash"),
            ("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ]

        result = []
        for model_id, name in known_models:
            constraints = self._get_model_constraints(model_id)
            result.append(
                {
                    "id": model_id,
                    "name": name,
                    "provider": self.provider_name,
                    "backend": self.backend,
                    "region": self.region,
                    **constraints,
                }
            )
        return result

    def _list_codestral_models(self) -> list[dict[str, Any]]:
        """List Codestral models available via LangDock.

        NOTE: Codestral is disabled for chat - it only supports FIM (fill-in-the-middle)
        code completion, which is not suitable for conversational chat interfaces.
        """
        # Disabled: Codestral only supports FIM, not chat
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
                constraints = self._get_model_constraints(model_id)
                result.append(
                    {
                        "id": model_id,
                        "name": model.get("name", model_id),
                        "provider": self.provider_name,
                        "backend": self.backend,
                        **constraints,
                    }
                )
            return result
        except (AttributeError, KeyError, TypeError, ConnectionError) as e:
            _logger.warning("Agent model listing failed, returning empty list: %s", e)
            return []

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

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if self._http_client is not None:
            try:
                self._http_client.close()
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
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
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

            response = httpx.post(
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
                error_text = response.text
                _logger.error(f"Attachment upload failed {response.status_code}: {error_text}")
                raise ProviderError(
                    f"Attachment upload failed: {error_text}",
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

        except httpx.RequestError as e:
            _logger.error(f"Attachment upload request error: {e}")
            raise ProviderError(
                f"Attachment upload failed: {e}",
                provider="langdock",
            ) from e

    def create_agent(
        self,
        name: str,
        instruction: str,
        model: str = "gpt-4o",
        knowledge_folder_ids: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create a new LangDock agent.

        Args:
            name: Agent name
            instruction: System instruction for the agent
            model: LLM model to use
            knowledge_folder_ids: List of knowledge folder IDs to attach
            **kwargs: Additional agent configuration (e.g. creativity, webSearch)

        Returns:
            Created agent data
        """
        payload = {
            "name": name,
            "instruction": instruction,
            "model": model,
        }

        if knowledge_folder_ids:
            payload["knowledgeFolderIds"] = knowledge_folder_ids

        payload.update(kwargs)

        response = self.client.post("/create", json=payload)
        response.raise_for_status()
        return response.json()

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
        return response.json()

    def update_agent(self, agent_id: str, **kwargs) -> dict[str, Any]:
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
        return response.json()

    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models for agents.

        Returns:
            List of available models
        """
        response = self.client.get("/models")
        response.raise_for_status()
        return response.json().get("data", [])

    def __del__(self):
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
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
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
            return response.json()

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
        return response.json().get("result", [])

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
        return response.json().get("result", [])

    def __del__(self):
        """Cleanup HTTP client."""
        if self._client is not None:
            try:
                self._client.close()
            except (OSError, RuntimeError):
                pass  # Ignore cleanup errors during interpreter shutdown
