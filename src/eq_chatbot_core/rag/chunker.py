"""
Document chunking for RAG pipeline.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    content: str
    """The text content of this chunk."""

    metadata: dict[str, Any]
    """Metadata (source, page, etc.)."""

    token_count: int
    """Number of tokens in this chunk."""

    start_index: int
    """Start character index in original document."""

    end_index: int
    """End character index in original document."""

    chunk_index: int = 0
    """Index of this chunk in the sequence."""


class DocumentChunker:
    """
    Intelligent document chunking with overlap and semantic boundaries.

    Uses tiktoken for accurate token counting.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target tokens per chunk
            chunk_overlap: Token overlap between chunks
            encoding_name: Tiktoken encoding name
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._encoder: Any = None
        self._encoding_name = encoding_name

    @property
    def encoder(self) -> Any:
        """Lazy initialization of tiktoken encoder."""
        if self._encoder is None:
            try:
                import tiktoken

                self._encoder = tiktoken.get_encoding(self._encoding_name)
            except ImportError as e:
                raise ImportError("tiktoken package not installed. Install with: pip install tiktoken") from e
        return self._encoder

    def chunk_text(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[Chunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Yields:
            Chunk objects with content and metadata
        """
        if not text or not text.strip():
            return

        if metadata is None:
            metadata = {}

        tokens = self.encoder.encode(text)

        # Single chunk if text is small enough
        if len(tokens) <= self.chunk_size:
            yield Chunk(
                content=text,
                metadata=metadata,
                token_count=len(tokens),
                start_index=0,
                end_index=len(text),
                chunk_index=0,
            )
            return

        # Split with overlap
        chunk_index = 0
        start = 0

        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoder.decode(chunk_tokens)

            # Adjust to sentence boundary if possible
            adjusted_text = self._adjust_to_sentence_boundary(chunk_text)

            yield Chunk(
                content=adjusted_text,
                metadata={**metadata, "chunk_index": chunk_index},
                token_count=len(chunk_tokens),
                start_index=start,
                end_index=end,
                chunk_index=chunk_index,
            )

            chunk_index += 1
            # Ensure start advances by at least 1 to prevent infinite loop
            # when chunk_overlap >= chunk_size
            start = max(end - self.chunk_overlap, start + 1)

    def _adjust_to_sentence_boundary(self, text: str) -> str:
        """
        Trim text to last complete sentence if possible.

        Args:
            text: Text to adjust

        Returns:
            Text ending at a sentence boundary (if found)
        """
        # Sentence-ending punctuation patterns
        endings = [". ", "! ", "? ", ".\n", "!\n", "?\n"]

        for punct in endings:
            last_idx = text.rfind(punct)
            # Only trim if we don't lose too much content (>70% retained)
            if last_idx > len(text) * 0.7:
                return text[: last_idx + 1]

        return text

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count

        Returns:
            Token count
        """
        return len(self.encoder.encode(text))
