"""
Unit tests for the HybridRetriever class.

Tests retrieval, reranking, collection management, and upsert operations
with fully mocked Qdrant client and embedder dependencies.
"""

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# =============================================================================
# Mock qdrant_client before importing HybridRetriever
# =============================================================================

# Create mock qdrant_client modules so the retriever can import from them
_mock_qdrant = MagicMock()
_mock_qdrant_models = MagicMock()

# Provide real-looking mock classes for qdrant_client.models
_mock_qdrant_models.FieldCondition = MagicMock
_mock_qdrant_models.Filter = MagicMock
_mock_qdrant_models.MatchValue = MagicMock
_mock_qdrant_models.Distance = MagicMock()
_mock_qdrant_models.Distance.COSINE = "Cosine"
_mock_qdrant_models.VectorParams = MagicMock
_mock_qdrant_models.PointStruct = MagicMock

with patch.dict(
    "sys.modules",
    {
        "qdrant_client": _mock_qdrant,
        "qdrant_client.models": _mock_qdrant_models,
    },
):
    from eq_chatbot_core.rag.retriever import HybridRetriever, RetrievalResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_embedder():
    """Create a mock embedder returning 3-dimensional vectors."""
    embedder = MagicMock()
    embedder.dimensions = 3
    embedder.embed.return_value = np.array([[0.1, 0.2, 0.3]])
    return embedder


@pytest.fixture
def mock_qdrant_client():
    """Create a mock Qdrant client with a default search result."""
    client = MagicMock()

    mock_result = MagicMock()
    mock_result.payload = {
        "content": "test content about python",
        "metadata": {"chapter": 1},
        "source": "test.txt",
    }
    mock_result.score = 0.85

    client.search.return_value = [mock_result]
    return client


@pytest.fixture
def retriever(mock_qdrant_client, mock_embedder):
    """Create a HybridRetriever with mocked dependencies."""
    return HybridRetriever(
        qdrant_client=mock_qdrant_client,
        collection_name="test_collection",
        embedder=mock_embedder,
        top_k=5,
        score_threshold=0.7,
        rerank=True,
    )


@pytest.fixture
def retriever_no_rerank(mock_qdrant_client, mock_embedder):
    """Create a HybridRetriever with reranking disabled."""
    return HybridRetriever(
        qdrant_client=mock_qdrant_client,
        collection_name="test_collection",
        embedder=mock_embedder,
        top_k=5,
        score_threshold=0.7,
        rerank=False,
    )


# =============================================================================
# Retrieve Success Path Tests
# =============================================================================


@pytest.mark.unit
class TestRetrieveSuccess:
    """Test retrieve() success path with mocked embedder and Qdrant client."""

    def test_retrieve_returns_retrieval_results(self, retriever, mock_qdrant_client):
        """Test that retrieve returns a list of RetrievalResult objects."""
        results = retriever.retrieve("python tutorial")

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], RetrievalResult)

    def test_retrieve_maps_payload_fields_correctly(self, retriever):
        """Test that payload fields are correctly mapped to RetrievalResult."""
        results = retriever.retrieve("python tutorial")

        result = results[0]
        assert result.content == "test content about python"
        assert result.metadata == {"chapter": 1}
        assert result.source == "test.txt"

    def test_retrieve_calls_embedder_with_query(self, retriever, mock_embedder):
        """Test that retrieve passes the query string to the embedder."""
        retriever.retrieve("search query")

        mock_embedder.embed.assert_called_once_with("search query")

    def test_retrieve_calls_qdrant_search(self, retriever, mock_qdrant_client):
        """Test that retrieve calls Qdrant client search with correct params."""
        retriever.retrieve("search query")

        mock_qdrant_client.search.assert_called_once()
        call_kwargs = mock_qdrant_client.search.call_args
        assert call_kwargs.kwargs["collection_name"] == "test_collection"
        assert call_kwargs.kwargs["score_threshold"] == 0.7

    def test_retrieve_respects_custom_top_k(self, retriever, mock_qdrant_client):
        """Test that a custom top_k parameter overrides the default."""
        retriever.retrieve("query", top_k=3)

        call_kwargs = mock_qdrant_client.search.call_args
        # With rerank=True, limit should be top_k * 2
        assert call_kwargs.kwargs["limit"] == 6

    def test_retrieve_uses_default_top_k(self, retriever, mock_qdrant_client):
        """Test that default top_k is used when not overridden."""
        retriever.retrieve("query")

        call_kwargs = mock_qdrant_client.search.call_args
        # top_k=5, rerank=True, so limit = 5 * 2 = 10
        assert call_kwargs.kwargs["limit"] == 10

    def test_retrieve_handles_missing_payload_fields(self, retriever, mock_qdrant_client):
        """Test graceful handling of missing payload fields."""
        sparse_result = MagicMock()
        sparse_result.payload = {}
        sparse_result.score = 0.75
        mock_qdrant_client.search.return_value = [sparse_result]

        results = retriever.retrieve("query")

        assert results[0].content == ""
        assert results[0].metadata == {}
        assert results[0].source == "unknown"


# =============================================================================
# Retrieve Empty Query Tests
# =============================================================================


@pytest.mark.unit
class TestRetrieveEmptyQuery:
    """Test retrieve() with empty or whitespace-only queries."""

    def test_empty_string_returns_empty_list(self, retriever):
        """Test that an empty string query returns an empty list."""
        results = retriever.retrieve("")

        assert results == []

    def test_whitespace_only_returns_empty_list(self, retriever):
        """Test that a whitespace-only query returns an empty list."""
        results = retriever.retrieve("   ")

        assert results == []

    def test_tabs_and_newlines_returns_empty_list(self, retriever):
        """Test that tabs and newlines only returns an empty list."""
        results = retriever.retrieve("\t\n  \r\n")

        assert results == []

    def test_empty_query_does_not_call_embedder(self, retriever, mock_embedder):
        """Test that empty queries do not invoke the embedder."""
        retriever.retrieve("")

        mock_embedder.embed.assert_not_called()

    def test_empty_query_does_not_call_qdrant(self, retriever, mock_qdrant_client):
        """Test that empty queries do not invoke the Qdrant client."""
        retriever.retrieve("")

        mock_qdrant_client.search.assert_not_called()


# =============================================================================
# Retrieve with Filters Tests
# =============================================================================


@pytest.mark.unit
class TestRetrieveWithFilters:
    """Test retrieve() filter conversion to Qdrant conditions."""

    def test_filter_dict_is_passed_to_qdrant(self, retriever, mock_qdrant_client):
        """Test that filters are converted and passed to Qdrant search."""
        retriever.retrieve("query", filters={"source": "manual.pdf"})

        call_kwargs = mock_qdrant_client.search.call_args
        assert call_kwargs.kwargs["query_filter"] is not None

    def test_no_filters_passes_none(self, retriever, mock_qdrant_client):
        """Test that no filters results in query_filter=None."""
        retriever.retrieve("query", filters=None)

        call_kwargs = mock_qdrant_client.search.call_args
        assert call_kwargs.kwargs["query_filter"] is None

    def test_empty_dict_passes_none(self, retriever, mock_qdrant_client):
        """Test that an empty filter dict results in query_filter=None."""
        retriever.retrieve("query", filters={})

        call_kwargs = mock_qdrant_client.search.call_args
        assert call_kwargs.kwargs["query_filter"] is None


# =============================================================================
# Retrieve Embedding Failure Tests
# =============================================================================


@pytest.mark.unit
class TestRetrieveEmbeddingFailure:
    """Test retrieve() behavior when embedder.embed() raises an exception."""

    def test_embedding_failure_raises_runtime_error(self, retriever, mock_embedder):
        """Test that an embedder failure raises RuntimeError."""
        mock_embedder.embed.side_effect = ValueError("Tokenization failed")

        with pytest.raises(RuntimeError, match="Failed to generate embedding for query"):
            retriever.retrieve("query")

    def test_embedding_failure_preserves_original_cause(self, retriever, mock_embedder):
        """Test that the original exception is chained via __cause__."""
        original_error = ValueError("Tokenization failed")
        mock_embedder.embed.side_effect = original_error

        with pytest.raises(RuntimeError) as exc_info:
            retriever.retrieve("query")

        assert exc_info.value.__cause__ is original_error


# =============================================================================
# Retrieve Qdrant Search Failure Tests
# =============================================================================


@pytest.mark.unit
class TestRetrieveQdrantSearchFailure:
    """Test retrieve() behavior when Qdrant client.search() raises an exception."""

    def test_search_failure_raises_connection_error(self, retriever, mock_qdrant_client):
        """Test that a Qdrant search failure raises ConnectionError."""
        mock_qdrant_client.search.side_effect = Exception("Connection refused")

        with pytest.raises(ConnectionError, match="Vector database search failed"):
            retriever.retrieve("query")

    def test_search_failure_preserves_original_cause(self, retriever, mock_qdrant_client):
        """Test that the original exception is chained via __cause__."""
        original_error = Exception("Connection refused")
        mock_qdrant_client.search.side_effect = original_error

        with pytest.raises(ConnectionError) as exc_info:
            retriever.retrieve("query")

        assert exc_info.value.__cause__ is original_error


# =============================================================================
# Retrieve with Reranking Tests
# =============================================================================


@pytest.mark.unit
class TestRetrieveWithReranking:
    """Test retrieve() reranking behavior."""

    def test_reranking_boosts_keyword_matches(self, retriever, mock_qdrant_client):
        """Test that results with keyword overlap get higher scores after reranking."""
        # Create two results: one with keyword overlap, one without
        result_with_keywords = MagicMock()
        result_with_keywords.payload = {
            "content": "python tutorial for beginners",
            "metadata": {},
            "source": "a.txt",
        }
        result_with_keywords.score = 0.80

        result_without_keywords = MagicMock()
        result_without_keywords.payload = {
            "content": "java enterprise architecture",
            "metadata": {},
            "source": "b.txt",
        }
        result_without_keywords.score = 0.82

        mock_qdrant_client.search.return_value = [
            result_without_keywords,
            result_with_keywords,
        ]

        # Query contains "python" which matches first result's content
        # Use top_k=1 so reranking picks the best one
        results = retriever.retrieve("python", top_k=1)

        assert len(results) == 1
        assert results[0].content == "python tutorial for beginners"

    def test_reranking_is_applied_when_results_exceed_top_k(
        self, mock_qdrant_client, mock_embedder
    ):
        """Test that reranking is applied when result count exceeds top_k."""
        # Create more results than top_k
        mock_results = []
        for i in range(6):
            r = MagicMock()
            r.payload = {"content": f"result {i}", "metadata": {}, "source": f"{i}.txt"}
            r.score = 0.9 - i * 0.02
            mock_results.append(r)

        mock_qdrant_client.search.return_value = mock_results

        retriever = HybridRetriever(
            qdrant_client=mock_qdrant_client,
            collection_name="test",
            embedder=mock_embedder,
            top_k=3,
            rerank=True,
        )

        results = retriever.retrieve("query")

        # Should return only top_k results
        assert len(results) == 3


# =============================================================================
# Retrieve without Reranking Tests
# =============================================================================


@pytest.mark.unit
class TestRetrieveWithoutReranking:
    """Test retrieve() behavior with rerank=False."""

    def test_no_rerank_returns_results_in_original_order(
        self, retriever_no_rerank, mock_qdrant_client
    ):
        """Test that results are returned in original Qdrant order when rerank is off."""
        r1 = MagicMock()
        r1.payload = {"content": "first result", "metadata": {}, "source": "a.txt"}
        r1.score = 0.90

        r2 = MagicMock()
        r2.payload = {"content": "second result", "metadata": {}, "source": "b.txt"}
        r2.score = 0.80

        mock_qdrant_client.search.return_value = [r1, r2]

        results = retriever_no_rerank.retrieve("query")

        assert results[0].content == "first result"
        assert results[1].content == "second result"

    def test_no_rerank_uses_top_k_as_limit(
        self, retriever_no_rerank, mock_qdrant_client
    ):
        """Test that without reranking, limit equals top_k (not top_k * 2)."""
        retriever_no_rerank.retrieve("query")

        call_kwargs = mock_qdrant_client.search.call_args
        assert call_kwargs.kwargs["limit"] == 5  # top_k=5, no doubling

    def test_no_rerank_preserves_original_scores(
        self, retriever_no_rerank, mock_qdrant_client
    ):
        """Test that original scores are preserved when reranking is off."""
        r1 = MagicMock()
        r1.payload = {"content": "result", "metadata": {}, "source": "a.txt"}
        r1.score = 0.85

        mock_qdrant_client.search.return_value = [r1]

        results = retriever_no_rerank.retrieve("query")

        assert results[0].score == 0.85


# =============================================================================
# _rerank() Method Tests
# =============================================================================


@pytest.mark.unit
class TestRerank:
    """Test the _rerank() method for score combination logic."""

    def test_rerank_combines_semantic_and_keyword_scores(self, retriever):
        """Test that _rerank uses 0.7 semantic + 0.3 keyword weighting."""
        result = RetrievalResult(
            content="python programming tutorial",
            score=1.0,
            metadata={},
            source="test.txt",
        )

        reranked = retriever._rerank("python", [result])

        # Query "python" matches 1 out of 1 query term in content
        # keyword_overlap = 1/1 = 1.0
        # new_score = 1.0 * 0.7 + 1.0 * 0.3 = 1.0
        assert reranked[0].score == pytest.approx(1.0)

    def test_rerank_no_keyword_overlap(self, retriever):
        """Test reranking when there is no keyword overlap."""
        result = RetrievalResult(
            content="java enterprise beans",
            score=0.8,
            metadata={},
            source="test.txt",
        )

        reranked = retriever._rerank("python tutorial", [result])

        # keyword_overlap = 0/2 = 0.0
        # new_score = 0.8 * 0.7 + 0.0 * 0.3 = 0.56
        assert reranked[0].score == pytest.approx(0.56)

    def test_rerank_partial_keyword_overlap(self, retriever):
        """Test reranking with partial keyword overlap."""
        result = RetrievalResult(
            content="python web development",
            score=0.9,
            metadata={},
            source="test.txt",
        )

        reranked = retriever._rerank("python tutorial", [result])

        # Query terms: {"python", "tutorial"}, content terms include "python"
        # keyword_overlap = 1/2 = 0.5
        # new_score = 0.9 * 0.7 + 0.5 * 0.3 = 0.63 + 0.15 = 0.78
        assert reranked[0].score == pytest.approx(0.78)

    def test_rerank_sorts_by_combined_score_descending(self, retriever):
        """Test that _rerank sorts results by combined score in descending order."""
        result_low_semantic_high_keyword = RetrievalResult(
            content="python basics",
            score=0.6,
            metadata={},
            source="a.txt",
        )
        result_high_semantic_no_keyword = RetrievalResult(
            content="java enterprise",
            score=0.9,
            metadata={},
            source="b.txt",
        )

        reranked = retriever._rerank(
            "python",
            [result_high_semantic_no_keyword, result_low_semantic_high_keyword],
        )

        # result_low_semantic_high_keyword: 0.6 * 0.7 + 1.0 * 0.3 = 0.72
        # result_high_semantic_no_keyword: 0.9 * 0.7 + 0.0 * 0.3 = 0.63
        assert reranked[0].source == "a.txt"
        assert reranked[1].source == "b.txt"

    def test_rerank_empty_query_no_division_error(self, retriever):
        """Test that _rerank handles empty query without division by zero."""
        result = RetrievalResult(
            content="some content",
            score=0.8,
            metadata={},
            source="test.txt",
        )

        # Empty query -> query_terms = set(), max(0, 1) = 1 -> overlap = 0
        reranked = retriever._rerank("", [result])

        # new_score = 0.8 * 0.7 + 0.0 * 0.3 = 0.56
        assert reranked[0].score == pytest.approx(0.56)


# =============================================================================
# ensure_collection() Tests
# =============================================================================


@pytest.mark.unit
class TestEnsureCollection:
    """Test ensure_collection() for collection creation and existence checks."""

    def test_creates_collection_when_not_exists(self, retriever, mock_qdrant_client):
        """Test that a new collection is created when it does not exist."""
        mock_collections = MagicMock()
        mock_collections.collections = []  # No existing collections
        mock_qdrant_client.get_collections.return_value = mock_collections

        result = retriever.ensure_collection(vector_size=3)

        assert result == "test_collection"
        mock_qdrant_client.create_collection.assert_called_once()

    def test_skips_creation_when_collection_exists(self, retriever, mock_qdrant_client):
        """Test that creation is skipped when the collection already exists."""
        existing_collection = MagicMock()
        existing_collection.name = "test_collection"
        mock_collections = MagicMock()
        mock_collections.collections = [existing_collection]
        mock_qdrant_client.get_collections.return_value = mock_collections

        result = retriever.ensure_collection()

        assert result == "test_collection"
        mock_qdrant_client.create_collection.assert_not_called()

    def test_uses_embedder_dimensions_when_vector_size_not_given(
        self, retriever, mock_qdrant_client, mock_embedder
    ):
        """Test that embedder.dimensions is used when vector_size is None."""
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_qdrant_client.get_collections.return_value = mock_collections

        retriever.ensure_collection(vector_size=None)

        mock_qdrant_client.create_collection.assert_called_once()
        call_kwargs = mock_qdrant_client.create_collection.call_args
        vectors_config = call_kwargs.kwargs["vectors_config"]
        # VectorParams should have been created with size=embedder.dimensions (3)
        assert vectors_config.size == mock_embedder.dimensions

    def test_connection_error_on_list_collections_failure(
        self, retriever, mock_qdrant_client
    ):
        """Test that a ConnectionError is raised when listing collections fails."""
        mock_qdrant_client.get_collections.side_effect = Exception("Network error")

        with pytest.raises(ConnectionError, match="Vector database connection failed"):
            retriever.ensure_collection()

    def test_connection_error_preserves_original_cause(
        self, retriever, mock_qdrant_client
    ):
        """Test that the original exception is chained via __cause__."""
        original_error = Exception("Network error")
        mock_qdrant_client.get_collections.side_effect = original_error

        with pytest.raises(ConnectionError) as exc_info:
            retriever.ensure_collection()

        assert exc_info.value.__cause__ is original_error


# =============================================================================
# upsert() Tests
# =============================================================================


@pytest.mark.unit
class TestUpsert:
    """Test upsert() for batched document insertion."""

    def test_upsert_returns_count_of_inserted_points(self, retriever, mock_embedder):
        """Test that upsert returns the total count of upserted points."""
        mock_embedder.embed.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

        chunks = [
            {"content": "first doc", "metadata": {"page": 1}, "source": "a.txt"},
            {"content": "second doc", "metadata": {"page": 2}, "source": "b.txt"},
        ]

        count = retriever.upsert(chunks)

        assert count == 2

    def test_upsert_empty_chunks_returns_zero(self, retriever):
        """Test that upsert with empty chunks list returns 0."""
        count = retriever.upsert([])

        assert count == 0

    def test_upsert_empty_chunks_does_not_call_embedder(self, retriever, mock_embedder):
        """Test that upsert with empty chunks does not invoke the embedder."""
        retriever.upsert([])

        mock_embedder.embed.assert_not_called()

    def test_upsert_calls_embedder_with_contents(self, retriever, mock_embedder):
        """Test that upsert passes chunk contents to the embedder."""
        mock_embedder.embed.return_value = np.array([[0.1, 0.2, 0.3]])

        chunks = [{"content": "hello world", "source": "test.txt"}]
        retriever.upsert(chunks)

        mock_embedder.embed.assert_called_once_with(["hello world"])

    def test_upsert_calls_qdrant_upsert(self, retriever, mock_qdrant_client, mock_embedder):
        """Test that upsert calls client.upsert with correct collection name."""
        mock_embedder.embed.return_value = np.array([[0.1, 0.2, 0.3]])

        chunks = [{"content": "doc", "source": "test.txt"}]
        retriever.upsert(chunks)

        mock_qdrant_client.upsert.assert_called_once()
        call_kwargs = mock_qdrant_client.upsert.call_args
        assert call_kwargs.kwargs["collection_name"] == "test_collection"

    def test_upsert_batches_large_chunk_lists(self, retriever, mock_embedder):
        """Test that upsert processes chunks in batches."""
        # Create 150 chunks with batch_size=100
        chunks = [{"content": f"doc {i}", "source": f"{i}.txt"} for i in range(150)]

        # Return embeddings matching batch sizes
        mock_embedder.embed.side_effect = [
            np.array([[0.1, 0.2, 0.3]] * 100),  # First batch of 100
            np.array([[0.4, 0.5, 0.6]] * 50),  # Second batch of 50
        ]

        count = retriever.upsert(chunks, batch_size=100)

        assert count == 150
        assert mock_embedder.embed.call_count == 2

    def test_upsert_embedding_failure_raises_runtime_error(
        self, retriever, mock_embedder
    ):
        """Test that an embedder failure during upsert raises RuntimeError."""
        mock_embedder.embed.side_effect = ValueError("Model not loaded")

        chunks = [{"content": "doc", "source": "test.txt"}]

        with pytest.raises(RuntimeError, match="Failed to generate embeddings"):
            retriever.upsert(chunks)

    def test_upsert_qdrant_failure_raises_connection_error(
        self, retriever, mock_qdrant_client, mock_embedder
    ):
        """Test that a Qdrant upsert failure raises ConnectionError."""
        mock_embedder.embed.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_qdrant_client.upsert.side_effect = Exception("Write timeout")

        chunks = [{"content": "doc", "source": "test.txt"}]

        with pytest.raises(ConnectionError, match="Vector database upsert failed"):
            retriever.upsert(chunks)

    def test_upsert_handles_missing_optional_fields(self, retriever, mock_embedder):
        """Test that upsert handles chunks with missing metadata and source."""
        mock_embedder.embed.return_value = np.array([[0.1, 0.2, 0.3]])

        # Chunk with only required 'content' field
        chunks = [{"content": "minimal doc"}]
        count = retriever.upsert(chunks)

        assert count == 1
