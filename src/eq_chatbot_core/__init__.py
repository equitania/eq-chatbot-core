"""
eq-chatbot-core: Core library for LLM chatbot integration

This package provides:
- LLM provider adapters (OpenAI, Anthropic, LangDock, OpenRouter, Mammouth, Azure, Local)
- RAG pipeline (chunking, embedding, retrieval)
- Security utilities (encryption, injection protection, rate limiting)
- MCP client integration
- Core services (chat, cost, error handling)
"""

from eq_chatbot_core.version import __version__

__all__ = ["__version__"]
