"""
Qdrant-based document retrieval.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result from retrieval operation."""

    content: str
    """The retrieved text content."""

    score: float
    """Similarity score (0-1)."""

    metadata: dict[str, Any]
    """Document metadata."""

    source: str
    """Source identifier (filename, URL, etc.)."""


class HybridRetriever:
    """
    Hybrid retrieval combining semantic search with keyword matching.

    Uses Qdrant for vector storage and retrieval.
    """

    def __init__(
        self,
        qdrant_client: Any,
        collection_name: str,
        embedder: Any,
        top_k: int = 5,
        score_threshold: float = 0.7,
        rerank: bool = True,
    ):
        """
        Initialize retriever.

        Args:
            qdrant_client: Qdrant client instance
            collection_name: Name of the collection
            embedder: Embedder for query encoding
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            rerank: Whether to apply keyword reranking
        """
        self.client = qdrant_client
        self.collection = collection_name
        self.embedder = embedder
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.rerank = rerank

    def retrieve(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve relevant documents.

        Args:
            query: Search query
            filters: Optional metadata filters
            top_k: Override default top_k

        Returns:
            List of RetrievalResult objects
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        if not query or not query.strip():
            return []

        top_k = top_k or self.top_k

        # Generate query embedding
        try:
            query_embedding = self.embedder.embed(query)[0]
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise RuntimeError(f"Failed to generate embedding for query: {e}") from e

        # Build Qdrant filter
        qdrant_filter = None
        if filters:
            conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()]
            qdrant_filter = Filter(must=conditions)

        # Search
        try:
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_embedding.tolist(),
                limit=top_k * 2 if self.rerank else top_k,
                query_filter=qdrant_filter,
                score_threshold=self.score_threshold,
            )
        except Exception as e:
            logger.error(f"Qdrant search failed for collection '{self.collection}': {e}")
            raise ConnectionError(f"Vector database search failed: {e}") from e

        # Convert to RetrievalResult
        retrieval_results = [
            RetrievalResult(
                content=r.payload.get("content", ""),
                score=r.score,
                metadata=r.payload.get("metadata", {}),
                source=r.payload.get("source", "unknown"),
            )
            for r in results
        ]

        # Rerank with keyword boosting
        if self.rerank and len(retrieval_results) > top_k:
            retrieval_results = self._rerank(query, retrieval_results)

        return retrieval_results[:top_k]

    def _rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Rerank results using keyword boosting.

        Args:
            query: Original query
            results: Retrieved results

        Returns:
            Reranked results
        """
        query_terms = set(query.lower().split())

        for result in results:
            content_terms = set(result.content.lower().split())
            keyword_overlap = len(query_terms & content_terms) / max(len(query_terms), 1)

            # Boost score based on keyword overlap
            result.score = result.score * 0.7 + keyword_overlap * 0.3

        return sorted(results, key=lambda x: x.score, reverse=True)

    def ensure_collection(self, vector_size: int | None = None) -> str:
        """
        Ensure collection exists, create if not.

        Args:
            vector_size: Vector dimensions (required for creation)

        Returns:
            Collection name
        """
        from qdrant_client.models import Distance, VectorParams

        try:
            collections = self.client.get_collections().collections
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise ConnectionError(f"Vector database connection failed: {e}") from e

        exists = any(c.name == self.collection for c in collections)

        if not exists:
            if vector_size is None:
                vector_size = self.embedder.dimensions

            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )

        return self.collection

    def upsert(
        self,
        chunks: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """
        Upsert chunks to collection.

        Args:
            chunks: List of dicts with 'content', 'metadata', 'source'
            batch_size: Batch size for upserts

        Returns:
            Number of points upserted
        """
        import uuid

        from qdrant_client.models import PointStruct

        if not chunks:
            return 0

        total = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # Generate embeddings
            contents = [c["content"] for c in batch]
            try:
                embeddings = self.embedder.embed(contents)
            except Exception as e:
                logger.error(f"Embedding generation failed for batch {i // batch_size}: {e}")
                raise RuntimeError(f"Failed to generate embeddings: {e}") from e

            # Create points
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embeddings[j].tolist(),
                    payload={
                        "content": batch[j]["content"],
                        "metadata": batch[j].get("metadata", {}),
                        "source": batch[j].get("source", "unknown"),
                    },
                )
                for j in range(len(batch))
            ]

            try:
                self.client.upsert(
                    collection_name=self.collection,
                    points=points,
                )
            except Exception as e:
                logger.error(f"Qdrant upsert failed for batch {i // batch_size}: {e}")
                raise ConnectionError(f"Vector database upsert failed: {e}") from e

            total += len(points)

        return total
