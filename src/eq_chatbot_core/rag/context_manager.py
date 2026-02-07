"""
Context window management for LLM conversations.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ContextBudget:
    """Token budget allocation for context window."""

    total_tokens: int
    """Total available tokens for the model."""

    system_tokens: int
    """Tokens used by system prompt."""

    history_tokens: int
    """Tokens allocated for conversation history."""

    rag_tokens: int
    """Tokens allocated for RAG context."""

    response_tokens: int
    """Tokens reserved for response generation."""

    @property
    def available_for_content(self) -> int:
        """Tokens available for history + RAG."""
        return self.total_tokens - self.system_tokens - self.response_tokens


class ContextWindowManager:
    """
    Manage token allocation across system prompt, history, RAG, and response.

    Ensures conversations fit within model context limits.
    """

    MODEL_LIMITS = {
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4": 8192,
        "claude-3-5-sonnet-latest": 200000,
        "claude-3-5-haiku-latest": 200000,
        "claude-3-opus-latest": 200000,
    }

    def __init__(
        self,
        model: str,
        max_response_tokens: int = 4096,
        history_ratio: float = 0.3,
        rag_ratio: float = 0.4,
    ):
        """
        Initialize context manager.

        Args:
            model: Model name for context limit lookup
            max_response_tokens: Tokens reserved for response
            history_ratio: Ratio of available tokens for history
            rag_ratio: Ratio of available tokens for RAG context
        """
        if history_ratio + rag_ratio > 1.0:
            raise ValueError(
                f"history_ratio ({history_ratio}) + rag_ratio ({rag_ratio}) = {history_ratio + rag_ratio} exceeds 1.0"
            )
        if history_ratio < 0 or rag_ratio < 0:
            raise ValueError("history_ratio and rag_ratio must be non-negative")

        self.model = model
        self.max_tokens = self._get_model_limit(model)
        self.max_response = max_response_tokens
        self.history_ratio = history_ratio
        self.rag_ratio = rag_ratio
        self._encoder = None

    def _get_model_limit(self, model: str) -> int:
        """Get context limit for model."""
        # Try exact match
        if model in self.MODEL_LIMITS:
            return self.MODEL_LIMITS[model]

        # Try prefix match
        for key, limit in self.MODEL_LIMITS.items():
            if model.startswith(key.split("-")[0]):
                return limit

        # Default fallback
        return 128000

    @property
    def encoder(self):
        """Lazy initialization of tiktoken encoder."""
        if self._encoder is None:
            try:
                import tiktoken

                self._encoder = tiktoken.get_encoding("cl100k_base")
            except ImportError as e:
                raise ImportError("tiktoken package not installed. Install with: pip install tiktoken") from e
        return self._encoder

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))

    def allocate_budget(self, system_prompt: str) -> ContextBudget:
        """
        Calculate token budget for each context component.

        Args:
            system_prompt: The system prompt text

        Returns:
            ContextBudget with allocations
        """
        system_tokens = self.count_tokens(system_prompt)
        available = self.max_tokens - system_tokens - self.max_response

        return ContextBudget(
            total_tokens=self.max_tokens,
            system_tokens=system_tokens,
            history_tokens=int(available * self.history_ratio),
            rag_tokens=int(available * self.rag_ratio),
            response_tokens=self.max_response,
        )

    def truncate_messages(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> list[dict[str, Any]]:
        """
        Truncate message history to fit token budget.

        Keeps most recent messages.

        Args:
            messages: List of message dicts
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated message list
        """
        result = []
        current_tokens = 0

        # Iterate from newest to oldest
        for msg in reversed(messages):
            content = msg.get("content", "")
            msg_tokens = self.count_tokens(content)

            if current_tokens + msg_tokens <= max_tokens:
                result.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break

        return result

    def truncate_rag_context(
        self,
        results: list[Any],
        max_tokens: int,
    ) -> list[Any]:
        """
        Truncate RAG results to fit token budget.

        Keeps highest scoring results.

        Args:
            results: List of RetrievalResult objects
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated result list
        """
        # Sort by score (descending)
        sorted_results = sorted(results, key=lambda x: x.score, reverse=True)

        selected = []
        current_tokens = 0

        for result in sorted_results:
            result_tokens = self.count_tokens(result.content)

            if current_tokens + result_tokens <= max_tokens:
                selected.append(result)
                current_tokens += result_tokens
            else:
                break

        return selected

    def build_context(
        self,
        system_prompt: str,
        history: list[dict[str, Any]],
        rag_results: list[Any],
        user_message: str,
    ) -> list[dict[str, Any]]:
        """
        Build complete message context within token limits.

        Args:
            system_prompt: System prompt text
            history: Conversation history
            rag_results: RAG retrieval results
            user_message: Current user message

        Returns:
            List of messages ready for LLM
        """
        budget = self.allocate_budget(system_prompt)

        # Truncate components
        truncated_history = self.truncate_messages(history, budget.history_tokens)
        truncated_rag = self.truncate_rag_context(rag_results, budget.rag_tokens)

        # Format RAG context
        rag_context = self._format_rag_context(truncated_rag)

        # Assemble messages
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if rag_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Relevant context:\n{rag_context}",
                }
            )

        messages.extend(truncated_history)
        messages.append({"role": "user", "content": user_message})

        return messages

    def _format_rag_context(self, results: list[Any]) -> str:
        """Format RAG results for inclusion in prompt."""
        if not results:
            return ""

        formatted = []
        for i, r in enumerate(results, 1):
            source = r.source or "Unknown"
            formatted.append(f"[{i}] Source: {source}\n{r.content}")

        return "\n\n---\n\n".join(formatted)
