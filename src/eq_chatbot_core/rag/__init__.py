"""
RAG (Retrieval-Augmented Generation) pipeline.

- Chunker: Document chunking with overlap
- Embedder: Embedding adapters (OpenAI, local)
- Retriever: Qdrant-based retrieval
- Context Manager: Token budget management
"""

from eq_chatbot_core.rag.chunker import Chunk, DocumentChunker
from eq_chatbot_core.rag.context_manager import ContextBudget, ContextWindowManager

__all__ = [
    "Chunk",
    "DocumentChunker",
    "ContextBudget",
    "ContextWindowManager",
]
