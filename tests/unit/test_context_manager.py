"""
Unit tests for the ContextWindowManager and ContextBudget classes.

Tests initialization, budget validation, token counting, message truncation,
RAG context truncation, context building, and formatting.
"""

import sys
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock tiktoken before importing the module under test
# ---------------------------------------------------------------------------
mock_encoder = MagicMock()
# Simulate token counting: each whitespace-separated word = 1 token
mock_encoder.encode.side_effect = lambda text: list(range(len(text.split())))

mock_tiktoken = MagicMock()
mock_tiktoken.get_encoding.return_value = mock_encoder

sys.modules["tiktoken"] = mock_tiktoken

from eq_chatbot_core.rag.context_manager import ContextBudget, ContextWindowManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeRetrievalResult:
    """Lightweight stand-in for RetrievalResult used in RAG tests."""

    content: str
    score: float
    source: str
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# =============================================================================
# Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestContextWindowManagerInit:
    """Test ContextWindowManager.__init__ and model limit resolution."""

    def test_default_parameters(self):
        """Default ratios and max_response are stored correctly."""
        mgr = ContextWindowManager(model="gpt-4o")

        assert mgr.model == "gpt-4o"
        assert mgr.max_response == 4096
        assert mgr.history_ratio == 0.3
        assert mgr.rag_ratio == 0.4

    def test_known_model_uses_correct_limit(self):
        """Known model name resolves to its exact context limit."""
        mgr = ContextWindowManager(model="gpt-4")

        assert mgr.max_tokens == 8192

    def test_unknown_model_falls_back_to_128000(self):
        """Unknown model name falls back to 128000 default."""
        mgr = ContextWindowManager(model="totally-unknown-model-xyz")

        assert mgr.max_tokens == 128000

    def test_custom_ratios_are_stored(self):
        """Custom history_ratio and rag_ratio are stored."""
        mgr = ContextWindowManager(
            model="gpt-4o",
            history_ratio=0.5,
            rag_ratio=0.2,
        )

        assert mgr.history_ratio == 0.5
        assert mgr.rag_ratio == 0.2


# =============================================================================
# Budget Validation Tests (NEW FIX)
# =============================================================================


@pytest.mark.unit
class TestBudgetValidation:
    """Test __init__ raises ValueError on invalid ratios."""

    def test_sum_exceeds_one_raises_valueerror(self):
        """history_ratio + rag_ratio > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="exceeds 1.0"):
            ContextWindowManager(model="gpt-4o", history_ratio=0.6, rag_ratio=0.5)

    def test_negative_history_ratio_raises_valueerror(self):
        """Negative history_ratio raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            ContextWindowManager(model="gpt-4o", history_ratio=-0.1, rag_ratio=0.4)

    def test_negative_rag_ratio_raises_valueerror(self):
        """Negative rag_ratio raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            ContextWindowManager(model="gpt-4o", history_ratio=0.3, rag_ratio=-0.2)

    def test_exact_sum_of_one_is_ok(self):
        """history_ratio + rag_ratio == 1.0 does not raise."""
        mgr = ContextWindowManager(model="gpt-4o", history_ratio=0.6, rag_ratio=0.4)

        assert mgr.history_ratio + mgr.rag_ratio == 1.0

    def test_zero_ratios_are_ok(self):
        """Both ratios set to 0.0 does not raise."""
        mgr = ContextWindowManager(model="gpt-4o", history_ratio=0.0, rag_ratio=0.0)

        assert mgr.history_ratio == 0.0
        assert mgr.rag_ratio == 0.0


# =============================================================================
# _get_model_limit Tests
# =============================================================================


@pytest.mark.unit
class TestGetModelLimit:
    """Test _get_model_limit exact match, prefix match, and fallback."""

    def test_exact_match(self):
        """Exact model name returns its documented limit."""
        mgr = ContextWindowManager(model="gpt-4o")

        assert mgr._get_model_limit("gpt-4o") == 128000

    def test_prefix_match(self):
        """Model with a matching prefix returns a known limit."""
        mgr = ContextWindowManager(model="gpt-4o")
        # "gpt-something" starts with "gpt" which matches "gpt-4-turbo".split("-")[0]
        limit = mgr._get_model_limit("gpt-something")

        assert limit in ContextWindowManager.MODEL_LIMITS.values()

    def test_no_match_returns_default(self):
        """Completely unrecognised model returns 128000 default."""
        mgr = ContextWindowManager(model="gpt-4o")

        assert mgr._get_model_limit("llama-3-70b") == 128000

    def test_claude_exact_match(self):
        """Claude model exact match returns 200000."""
        mgr = ContextWindowManager(model="claude-3-5-sonnet-latest")

        assert mgr.max_tokens == 200000


# =============================================================================
# count_tokens Tests
# =============================================================================


@pytest.mark.unit
class TestCountTokens:
    """Test count_tokens delegates to tiktoken encoder."""

    def test_returns_word_count_via_mock(self):
        """count_tokens returns token count from the mocked encoder."""
        mgr = ContextWindowManager(model="gpt-4o")
        # Mock counts words: "hello world" -> 2 tokens
        assert mgr.count_tokens("hello world") == 2

    def test_empty_string(self):
        """Empty string yields 0 tokens (split produces [''] -> length 1,
        but our mock returns range(1) which has length 1).
        Verify actual mock behaviour."""
        mgr = ContextWindowManager(model="gpt-4o")
        # "".split() returns [] -> len 0 -> range(0) -> list length 0
        assert mgr.count_tokens("") == 0


# =============================================================================
# allocate_budget Tests
# =============================================================================


@pytest.mark.unit
class TestAllocateBudget:
    """Test allocate_budget calculations."""

    def test_correct_allocation_with_ratios(self):
        """Budget allocates history and RAG tokens proportionally."""
        mgr = ContextWindowManager(
            model="gpt-4o",
            max_response_tokens=4096,
            history_ratio=0.3,
            rag_ratio=0.4,
        )
        # "system prompt" = 2 words = 2 tokens via mock
        budget = mgr.allocate_budget("system prompt")

        assert budget.total_tokens == 128000
        assert budget.system_tokens == 2
        assert budget.response_tokens == 4096
        available = 128000 - 2 - 4096  # 123902
        assert budget.history_tokens == int(available * 0.3)
        assert budget.rag_tokens == int(available * 0.4)

    def test_available_for_content_property(self):
        """available_for_content = total - system - response."""
        mgr = ContextWindowManager(model="gpt-4o", max_response_tokens=4096)
        budget = mgr.allocate_budget("system prompt")

        expected = budget.total_tokens - budget.system_tokens - budget.response_tokens
        assert budget.available_for_content == expected

    def test_large_system_prompt_reduces_available(self):
        """A longer system prompt consumes more tokens, reducing available budget."""
        mgr = ContextWindowManager(model="gpt-4o", max_response_tokens=4096)
        small = mgr.allocate_budget("hi")
        large = mgr.allocate_budget("this is a much longer system prompt text")

        assert large.available_for_content < small.available_for_content


# =============================================================================
# truncate_messages Tests
# =============================================================================


@pytest.mark.unit
class TestTruncateMessages:
    """Test truncate_messages keeps newest messages within budget."""

    def test_keeps_newest_within_budget(self):
        """Newest messages are retained when total exceeds budget."""
        mgr = ContextWindowManager(model="gpt-4o")
        messages = [
            {"role": "user", "content": "first message here"},      # 3 tokens
            {"role": "assistant", "content": "second message here"}, # 3 tokens
            {"role": "user", "content": "third"},                    # 1 token
        ]
        # Budget of 4 tokens should keep last two messages (3 + 1 = 4)
        result = mgr.truncate_messages(messages, max_tokens=4)

        assert len(result) == 2
        assert result[0]["content"] == "second message here"
        assert result[1]["content"] == "third"

    def test_empty_list_returns_empty(self):
        """Empty message list returns empty result."""
        mgr = ContextWindowManager(model="gpt-4o")

        assert mgr.truncate_messages([], max_tokens=100) == []

    def test_single_message_over_budget_returns_empty(self):
        """Single message exceeding budget returns empty list."""
        mgr = ContextWindowManager(model="gpt-4o")
        messages = [{"role": "user", "content": "a b c d e f g h i j"}]  # 10 tokens

        assert mgr.truncate_messages(messages, max_tokens=5) == []


# =============================================================================
# truncate_rag_context Tests
# =============================================================================


@pytest.mark.unit
class TestTruncateRagContext:
    """Test truncate_rag_context keeps highest-scoring results within budget."""

    def test_highest_scoring_kept(self):
        """Highest-scored results are selected within budget."""
        mgr = ContextWindowManager(model="gpt-4o")
        results = [
            FakeRetrievalResult(content="low score content here", score=0.3, source="a.txt"),    # 4 tokens
            FakeRetrievalResult(content="high", score=0.9, source="b.txt"),                       # 1 token
            FakeRetrievalResult(content="medium score", score=0.6, source="c.txt"),               # 2 tokens
        ]
        # Budget of 3 tokens: should pick "high" (1, score=0.9) + "medium score" (2, score=0.6)
        selected = mgr.truncate_rag_context(results, max_tokens=3)

        assert len(selected) == 2
        scores = [r.score for r in selected]
        assert 0.9 in scores
        assert 0.6 in scores

    def test_empty_results_returns_empty(self):
        """Empty result list returns empty list."""
        mgr = ContextWindowManager(model="gpt-4o")

        assert mgr.truncate_rag_context([], max_tokens=100) == []


# =============================================================================
# build_context Tests
# =============================================================================


@pytest.mark.unit
class TestBuildContext:
    """Test build_context assembles messages correctly."""

    def test_assembles_system_rag_history_user(self):
        """Full context includes system, RAG system message, history, and user."""
        mgr = ContextWindowManager(model="gpt-4o", max_response_tokens=100)
        history = [{"role": "user", "content": "hi"}]
        rag_results = [
            FakeRetrievalResult(content="relevant info", score=0.8, source="doc.pdf"),
        ]

        messages = mgr.build_context(
            system_prompt="You are helpful",
            history=history,
            rag_results=rag_results,
            user_message="What is this?",
        )

        # System prompt
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        # RAG system message
        assert messages[1]["role"] == "system"
        assert "Relevant context:" in messages[1]["content"]
        # History
        assert messages[2]["content"] == "hi"
        # User message (last)
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "What is this?"

    def test_no_rag_results_omits_rag_message(self):
        """Without RAG results, no RAG system message is added."""
        mgr = ContextWindowManager(model="gpt-4o", max_response_tokens=100)

        messages = mgr.build_context(
            system_prompt="Be brief",
            history=[],
            rag_results=[],
            user_message="hello",
        )

        # Only system prompt + user message
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"


# =============================================================================
# _format_rag_context Tests
# =============================================================================


@pytest.mark.unit
class TestFormatRagContext:
    """Test _format_rag_context output formatting."""

    def test_formats_numbered_sources(self):
        """Results are formatted with numbered source headers."""
        mgr = ContextWindowManager(model="gpt-4o")
        results = [
            FakeRetrievalResult(content="Alpha content", score=0.9, source="alpha.pdf"),
            FakeRetrievalResult(content="Beta content", score=0.8, source="beta.pdf"),
        ]

        formatted = mgr._format_rag_context(results)

        assert "[1] Source: alpha.pdf" in formatted
        assert "Alpha content" in formatted
        assert "[2] Source: beta.pdf" in formatted
        assert "Beta content" in formatted
        assert "---" in formatted

    def test_empty_list_returns_empty_string(self):
        """Empty result list returns empty string."""
        mgr = ContextWindowManager(model="gpt-4o")

        assert mgr._format_rag_context([]) == ""

    def test_none_source_shows_unknown(self):
        """Result with source=None shows 'Unknown'."""
        mgr = ContextWindowManager(model="gpt-4o")
        results = [
            FakeRetrievalResult(content="some text", score=0.5, source=None),
        ]

        formatted = mgr._format_rag_context(results)

        assert "[1] Source: Unknown" in formatted


# =============================================================================
# ContextBudget Dataclass Tests
# =============================================================================


@pytest.mark.unit
class TestContextBudget:
    """Test ContextBudget dataclass and its properties."""

    def test_available_for_content_calculation(self):
        """available_for_content = total - system - response."""
        budget = ContextBudget(
            total_tokens=10000,
            system_tokens=500,
            history_tokens=2000,
            rag_tokens=3000,
            response_tokens=1000,
        )

        # 10000 - 500 - 1000 = 8500
        assert budget.available_for_content == 8500

    def test_available_for_content_with_zero_system(self):
        """With zero system tokens, available equals total minus response."""
        budget = ContextBudget(
            total_tokens=10000,
            system_tokens=0,
            history_tokens=3000,
            rag_tokens=4000,
            response_tokens=2000,
        )

        assert budget.available_for_content == 8000
