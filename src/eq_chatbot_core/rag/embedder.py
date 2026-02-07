"""
Embedding adapters for RAG pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseEmbedder(ABC):
    """Abstract base class for embedding models."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return embedding vector dimensions."""
        ...

    @abstractmethod
    def embed(self, texts: str | list[str]) -> np.ndarray:
        """
        Generate embeddings for text(s).

        Args:
            texts: Single text or list of texts

        Returns:
            numpy array of shape (n_texts, dimensions)
        """
        ...


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI text-embedding models."""

    MODELS = {
        "text-embedding-3-small": {"dimensions": 1536, "price_per_1m": 0.02},
        "text-embedding-3-large": {"dimensions": 3072, "price_per_1m": 0.13},
        "text-embedding-ada-002": {"dimensions": 1536, "price_per_1m": 0.10},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str | None = None,
    ):
        """
        Initialize OpenAI embedder.

        Args:
            api_key: OpenAI API key
            model: Embedding model name
            base_url: Optional custom base URL (for LangDock)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client: Any = None

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}. Available: {', '.join(self.MODELS.keys())}")

    @property
    def dimensions(self) -> int:
        return self.MODELS[self.model]["dimensions"]

    @property
    def client(self) -> Any:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Install with: pip install openai") from e

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def embed(self, texts: str | list[str]) -> np.ndarray:
        """Generate embeddings using OpenAI API."""
        if isinstance(texts, str):
            texts = [texts]

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        return np.array([d.embedding for d in response.data])


class LangDockEmbedder(OpenAIEmbedder):
    """LangDock embedding API (OpenAI-compatible)."""

    BASE_URLS = {
        "eu": "https://api.langdock.com/openai/eu/v1",
        "us": "https://api.langdock.com/openai/us/v1",
    }

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        region: str = "eu",
    ):
        """
        Initialize LangDock embedder.

        Args:
            api_key: LangDock API key
            model: Embedding model name
            region: API region ('eu' or 'us')
        """
        base_url = self.BASE_URLS.get(region, self.BASE_URLS["eu"])
        super().__init__(api_key, model, base_url)
        self.region = region
