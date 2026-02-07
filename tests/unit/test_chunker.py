"""
Unit tests for the DocumentChunker and Chunk classes.

Tests chunking logic, empty text guard, overlap behavior, sentence boundary
adjustment, metadata propagation, token counting, edge cases, and lazy
tiktoken initialization. All tiktoken calls are fully mocked.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock tiktoken before importing the module under test
# ---------------------------------------------------------------------------


def _make_mock_encoder():
    """Create a fresh mock encoder with deterministic encode/decode."""
    encoder = MagicMock()
    # encode: each whitespace-separated word becomes one token (integer)
    encoder.encode.side_effect = lambda text: list(range(len(text.split())))
    # decode: reconstruct text from token IDs (returns a real string, not Mock)
    encoder.decode.side_effect = lambda tokens: " ".join(f"word{t}" for t in tokens)
    return encoder


mock_encoder = _make_mock_encoder()

mock_tiktoken = MagicMock()
mock_tiktoken.get_encoding.return_value = mock_encoder

sys.modules["tiktoken"] = mock_tiktoken

from eq_chatbot_core.rag.chunker import Chunk, DocumentChunker  # noqa: E402


# =============================================================================
# Helper utilities
# =============================================================================

MAX_CHUNKS = 200  # Safety bail-out for generators


def _collect_chunks(
    chunker: DocumentChunker, text: str, metadata: dict | None = None
) -> list[Chunk]:
    """Materialize the chunk_text generator into a list with safety limit."""
    chunks = []
    for i, chunk in enumerate(chunker.chunk_text(text, metadata=metadata)):
        chunks.append(chunk)
        if i >= MAX_CHUNKS:
            break
    return chunks


def _fresh_chunker(**kwargs) -> DocumentChunker:
    """Create a DocumentChunker with a freshly injected mock encoder."""
    chunker = DocumentChunker(**kwargs)
    # Inject mock encoder directly to bypass lazy init
    chunker._encoder = _make_mock_encoder()
    return chunker


# =============================================================================
# Basic Chunking Tests
# =============================================================================


@pytest.mark.unit
class TestBasicChunking:
    """Test fundamental chunking behaviour for small and large texts."""

    def test_single_chunk_for_small_text(self):
        """Text shorter than chunk_size produces exactly one chunk."""
        chunker = _fresh_chunker(chunk_size=512, chunk_overlap=64)
        text = "Hello world"  # 2 tokens with our mock
        chunks = _collect_chunks(chunker, text)

        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].token_count == 2
        assert chunks[0].start_index == 0
        assert chunks[0].end_index == len(text)
        assert chunks[0].chunk_index == 0

    def test_multiple_chunks_for_large_text(self):
        """Text longer than chunk_size produces multiple chunks."""
        chunker = _fresh_chunker(chunk_size=3, chunk_overlap=1)
        # 6 words -> 6 tokens, chunk_size=3, overlap=1 -> multiple chunks
        text = "one two three four five six"
        chunks = _collect_chunks(chunker, text)

        assert len(chunks) > 1
        # chunk_index must be sequential
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx

    def test_chunk_indices_are_sequential(self):
        """All chunk_index values are sequential starting from 0."""
        chunker = _fresh_chunker(chunk_size=2, chunk_overlap=0)
        text = "alpha beta gamma delta epsilon"
        chunks = _collect_chunks(chunker, text)

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))


# =============================================================================
# Empty Text Guard Tests
# =============================================================================


@pytest.mark.unit
class TestEmptyTextGuard:
    """Test early return for empty, whitespace-only, or falsy input."""

    def test_empty_string_yields_no_chunks(self):
        """Empty string must produce zero chunks."""
        chunker = _fresh_chunker()
        chunks = _collect_chunks(chunker, "")

        assert chunks == []

    def test_whitespace_only_yields_no_chunks(self):
        """String containing only whitespace must produce zero chunks."""
        chunker = _fresh_chunker()
        chunks = _collect_chunks(chunker, "   \t\n  ")

        assert chunks == []

    def test_none_like_empty_yields_no_chunks(self):
        """Falsy empty string (bool False) must produce zero chunks."""
        chunker = _fresh_chunker()
        chunks = _collect_chunks(chunker, "")

        assert chunks == []

    def test_encoder_not_called_for_empty_text(self):
        """Encoder must not be accessed when text is empty (performance guard)."""
        chunker = _fresh_chunker()
        chunker._encoder.encode.reset_mock()

        _collect_chunks(chunker, "")
        _collect_chunks(chunker, "   ")

        chunker._encoder.encode.assert_not_called()


# =============================================================================
# Overlap Tests
# =============================================================================


@pytest.mark.unit
class TestOverlapBehavior:
    """Test that chunk overlap produces correct sliding window advancement."""

    def test_overlap_causes_token_reuse(self):
        """With overlap > 0 the start of the next chunk overlaps the previous end."""
        chunker = _fresh_chunker(chunk_size=4, chunk_overlap=2)
        text = "a b c d e f g h"  # 8 tokens
        chunks = _collect_chunks(chunker, text)

        # First chunk tokens: 0..3, next start = max(4 - 2, 0 + 1) = 2
        assert len(chunks) >= 2
        assert chunks[0].start_index == 0
        assert chunks[0].end_index == 4
        assert chunks[1].start_index == 2  # overlap of 2

    def test_zero_overlap_produces_non_overlapping_chunks(self):
        """With overlap 0 chunks are contiguous with no reuse."""
        chunker = _fresh_chunker(chunk_size=3, chunk_overlap=0)
        text = "a b c d e f"  # 6 tokens
        chunks = _collect_chunks(chunker, text)

        assert len(chunks) == 2
        assert chunks[0].start_index == 0
        assert chunks[0].end_index == 3
        assert chunks[1].start_index == 3
        assert chunks[1].end_index == 6


# =============================================================================
# Sentence Boundary Adjustment Tests
# =============================================================================


@pytest.mark.unit
class TestSentenceBoundaryAdjustment:
    """Test _adjust_to_sentence_boundary respects the 70% retention threshold."""

    def test_trims_to_sentence_ending_above_70_percent(self):
        """Sentence boundary found in the last 30% of text is used for trimming."""
        chunker = _fresh_chunker()
        # Place ". " at ~80% position (above threshold)
        text = "A" * 80 + ". " + "B" * 18

        result = chunker._adjust_to_sentence_boundary(text)

        assert result.endswith(".")
        assert len(result) == 81  # up to and including the period

    def test_no_trim_when_boundary_below_70_percent(self):
        """Sentence boundary before 70% position is ignored, text unchanged."""
        chunker = _fresh_chunker()
        # Place ". " at ~30% position (below threshold)
        text = "A" * 30 + ". " + "B" * 68

        result = chunker._adjust_to_sentence_boundary(text)

        assert result == text  # unchanged

    def test_no_trim_when_no_sentence_boundary(self):
        """Text without sentence-ending punctuation is returned as-is."""
        chunker = _fresh_chunker()
        text = "no punctuation here at all"

        result = chunker._adjust_to_sentence_boundary(text)

        assert result == text

    def test_recognizes_all_ending_patterns(self):
        """All supported ending patterns (. ! ? followed by space or newline) work."""
        chunker = _fresh_chunker()
        patterns = [". ", "! ", "? ", ".\n", "!\n", "?\n"]

        for pattern in patterns:
            # Place pattern at ~85% of a 100-char string
            prefix = "X" * 85
            suffix = "Y" * (100 - 85 - len(pattern))
            text = prefix + pattern + suffix

            result = chunker._adjust_to_sentence_boundary(text)

            assert result == prefix + pattern[0], (
                f"Failed for pattern {pattern!r}: got {result[-5:]!r}"
            )


# =============================================================================
# Metadata Propagation Tests
# =============================================================================


@pytest.mark.unit
class TestMetadataPropagation:
    """Test that user metadata and chunk_index are attached to chunks."""

    def test_metadata_passed_through_single_chunk(self):
        """Single-chunk path copies metadata without chunk_index injection."""
        chunker = _fresh_chunker(chunk_size=512)
        meta = {"source": "test.pdf", "page": 3}
        chunks = _collect_chunks(chunker, "short text", metadata=meta)

        assert len(chunks) == 1
        assert chunks[0].metadata == meta

    def test_metadata_with_chunk_index_in_multi_chunk(self):
        """Multi-chunk path injects chunk_index into metadata dict."""
        chunker = _fresh_chunker(chunk_size=2, chunk_overlap=0)
        meta = {"source": "doc.txt"}
        text = "alpha beta gamma delta"  # 4 tokens, chunk_size=2 -> 2 chunks
        chunks = _collect_chunks(chunker, text, metadata=meta)

        for idx, chunk in enumerate(chunks):
            assert chunk.metadata["source"] == "doc.txt"
            assert chunk.metadata["chunk_index"] == idx

    def test_none_metadata_defaults_to_empty_dict(self):
        """Passing None metadata defaults to empty dict, no KeyError."""
        chunker = _fresh_chunker(chunk_size=512)
        chunks = _collect_chunks(chunker, "hello world", metadata=None)

        assert len(chunks) == 1
        assert chunks[0].metadata == {}

    def test_original_metadata_not_mutated(self):
        """The caller's original metadata dict must not be modified."""
        chunker = _fresh_chunker(chunk_size=2, chunk_overlap=0)
        meta = {"source": "immutable.pdf"}
        original_keys = set(meta.keys())
        text = "one two three four"
        _collect_chunks(chunker, text, metadata=meta)

        assert set(meta.keys()) == original_keys


# =============================================================================
# Token Counting Tests
# =============================================================================


@pytest.mark.unit
class TestTokenCounting:
    """Test the count_tokens convenience method."""

    def test_count_tokens_returns_word_count(self):
        """With our mock encoder, token count equals word count."""
        chunker = _fresh_chunker()
        count = chunker.count_tokens("one two three four")

        assert count == 4

    def test_count_tokens_single_word(self):
        """Single word produces 1 token."""
        chunker = _fresh_chunker()
        assert chunker.count_tokens("hello") == 1


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Test boundary and degenerate inputs."""

    def test_single_character_text(self):
        """A single non-whitespace character produces exactly one chunk."""
        chunker = _fresh_chunker(chunk_size=512)
        chunks = _collect_chunks(chunker, "x")

        assert len(chunks) == 1
        assert chunks[0].content == "x"

    def test_text_with_only_punctuation(self):
        """Text consisting only of punctuation still produces chunks."""
        chunker = _fresh_chunker(chunk_size=512)
        text = "... !!! ???"
        chunks = _collect_chunks(chunker, text)

        assert len(chunks) == 1
        assert chunks[0].token_count == 3  # 3 whitespace-separated groups

    def test_very_small_chunk_size(self):
        """chunk_size=1 produces one chunk per token (with overlap=0)."""
        chunker = _fresh_chunker(chunk_size=1, chunk_overlap=0)
        text = "alpha beta gamma"  # 3 tokens
        chunks = _collect_chunks(chunker, text)

        assert len(chunks) == 3

    def test_overlap_equal_to_chunk_size_does_not_infinite_loop(self):
        """When overlap >= chunk_size the infinite-loop fix ensures progress."""
        chunker = _fresh_chunker(chunk_size=2, chunk_overlap=2)
        text = "a b c d"  # 4 tokens

        # With the fix, start advances by at least 1 per iteration
        chunks = _collect_chunks(chunker, text)

        # Should produce chunks without hanging (MAX_CHUNKS bail-out)
        assert len(chunks) > 0
        assert len(chunks) <= MAX_CHUNKS


# =============================================================================
# Tiktoken Lazy Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestLazyInitialization:
    """Test that the tiktoken encoder is lazily initialized on first access."""

    def test_encoder_is_none_before_first_access(self):
        """Internal _encoder starts as None."""
        chunker = DocumentChunker(encoding_name="cl100k_base")
        assert chunker._encoder is None

    def test_encoder_initialized_on_first_property_access(self):
        """Accessing .encoder triggers tiktoken.get_encoding."""
        chunker = DocumentChunker(encoding_name="cl100k_base")
        # Ensure _encoder is None so lazy init fires
        chunker._encoder = None

        # Use a local mock to avoid interference from other tests
        local_mock = MagicMock()
        local_mock.get_encoding.return_value = _make_mock_encoder()

        with patch.dict(sys.modules, {"tiktoken": local_mock}):
            _ = chunker.encoder

        local_mock.get_encoding.assert_called_once_with("cl100k_base")
        assert chunker._encoder is not None

    def test_encoder_cached_after_initialization(self):
        """Second access does not call get_encoding again."""
        chunker = DocumentChunker()
        # Force re-init
        chunker._encoder = None

        local_mock = MagicMock()
        local_mock.get_encoding.return_value = _make_mock_encoder()

        with patch.dict(sys.modules, {"tiktoken": local_mock}):
            _ = chunker.encoder
            _ = chunker.encoder  # second access

        local_mock.get_encoding.assert_called_once()

    def test_import_error_raised_when_tiktoken_missing(self):
        """ImportError is raised with helpful message when tiktoken is absent."""
        chunker = DocumentChunker()
        chunker._encoder = None  # force re-init

        with patch.dict(sys.modules, {"tiktoken": None}):
            # We need a fresh chunker so the import inside the property fires
            chunker2 = DocumentChunker()
            with pytest.raises(ImportError, match="tiktoken package not installed"):
                _ = chunker2.encoder
