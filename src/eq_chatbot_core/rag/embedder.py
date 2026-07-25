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

        Raises:
            ValueError: If ``base_url`` fails URL validation, or ``model`` is unknown.
        """
        self.api_key = api_key
        self.model = model
        self._client: Any = None

        # SSRF guard: only a caller-supplied base_url is validated — fixed public
        # defaults set by subclasses are trusted and need no DNS round-trip.
        # Imported lazily to avoid an import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        self.base_url = base_url

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
        # The region endpoints are fixed, built-in public URLs — assign after the
        # super() call so the SSRF guard's DNS round-trip is not paid for a URL
        # the caller cannot influence.
        super().__init__(api_key, model, None)
        self.base_url = self.BASE_URLS.get(region, self.BASE_URLS["eu"])
        self.region = region


class MeliousEmbedder(OpenAIEmbedder):
    """Melious.ai embedding API (OpenAI-compatible, sovereign EU-hosted).

    Melious exposes embeddings through the same OpenAI-compatible gateway as its
    chat API (GDPR-compliant, green hosting). Unlike OpenAI/LangDock, the live
    embedding model ids and their vector dimensions are not a fixed catalog —
    they are advertised dynamically via ``/v1/models``. Therefore this embedder
    does NOT validate ``model`` against a static ``MODELS`` map, and the vector
    ``dimensions`` are supplied explicitly (defaulting to 1536, the common
    sentence-embedding size). Override ``dimensions`` to match the chosen model.
    """

    DEFAULT_BASE_URL = "https://api.melious.ai/v1"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        dimensions: int = 1536,
    ):
        """
        Initialize the Melious embedder.

        Args:
            api_key: Melious API key (sent as a Bearer token).
            model: Embedding model id as advertised by Melious ``/v1/models``.
            base_url: OpenAI-compatible endpoint. Defaults to the official
                Melious URL; override only to route through a proxy.
            dimensions: Vector dimensions produced by the chosen model
                (must match the Qdrant collection's vector size).

        Raises:
            ValueError: If ``base_url`` fails URL validation.

        Note:
            ``OpenAIEmbedder.__init__`` is intentionally bypassed because it
            validates ``model`` against a static catalog that does not cover
            Melious' dynamic model ids. The SSRF guard is therefore applied here.
        """
        # Set attributes directly (skip the OpenAIEmbedder MODELS validation).
        self.api_key = api_key
        self.model = model
        self._client: Any = None
        self._dimensions = dimensions

        # SSRF guard: only a caller-supplied base_url is validated — the fixed
        # public default needs no DNS round-trip.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        self.base_url = base_url or self.DEFAULT_BASE_URL

    @property
    def dimensions(self) -> int:
        return self._dimensions
