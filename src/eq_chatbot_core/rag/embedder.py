"""
Embedding adapters for RAG pipeline.

The embedding model is always the caller's choice — there is no default — and the
vector size is either passed as ``dimensions`` or read from the first embedding
response. Nothing is looked up from a model table.
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from eq_chatbot_core.providers.base import ModelNotSpecifiedError


class BaseEmbedder(ABC):
    """Abstract base class for embedding models."""

    @property
    @abstractmethod
    def dimensions(self) -> int | None:
        """Embedding vector size; ``None`` until it is known."""
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
    """Embeddings through the OpenAI API or any OpenAI-compatible ``/embeddings`` endpoint."""

    PROVIDER_NAME = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
    ):
        """
        Initialize the embedder.

        Args:
            api_key: API key
            model: Embedding model id (required; there is no default)
            base_url: Optional custom base URL
            dimensions: Vector size the model produces. Pass it when a vector
                collection must be created before the first ``embed()`` call;
                otherwise it is read from the first response.

        Raises:
            ModelNotSpecifiedError: If ``model`` is missing.
            ValueError: If ``base_url`` fails URL validation.
        """
        if not model:
            raise ModelNotSpecifiedError(
                self.PROVIDER_NAME,
                what="embedding model",
                hint=f'Pass model="..." to {type(self).__name__}(...).',
            )
        self.api_key = api_key
        self.model = model
        self._client: Any = None
        self._dimensions = dimensions

        # SSRF guard: only a caller-supplied base_url is validated — fixed public
        # defaults set by subclasses are trusted and need no DNS round-trip.
        # Imported lazily to avoid an import cycle.
        if base_url:
            from eq_chatbot_core.utils.url_validation import validate_url

            validate_url(base_url, allow_private_ranges=False)

        self.base_url = base_url

    @property
    def dimensions(self) -> int | None:
        return self._dimensions

    @property
    def client(self) -> Any:
        """Lazy initialization of OpenAI client.

        Built on the same pinned httpx2 client as the chat providers: the SDK's
        default client follows redirects and re-resolves DNS on every connect,
        so a URL that passed validation could still be steered to an internal
        address.
        """
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Install with: pip install openai") from e

            import httpx2

            from eq_chatbot_core.utils.url_validation import build_pinned_transport_for_url

            effective_url = self.base_url or self.DEFAULT_BASE_URL
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=effective_url,
                http_client=httpx2.Client(transport=build_pinned_transport_for_url(effective_url)),
            )
        return self._client

    def embed(self, texts: str | list[str]) -> np.ndarray:
        """Generate embeddings; the first response fixes ``dimensions`` if it was not passed."""
        if isinstance(texts, str):
            texts = [texts]

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        vectors = np.array([d.embedding for d in response.data])
        self._check_dimensions(vectors)
        return vectors

    def _check_dimensions(self, vectors: np.ndarray) -> None:
        if vectors.ndim != 2 or vectors.shape[0] == 0:
            return
        size = int(vectors.shape[1])
        if self._dimensions is None:
            self._dimensions = size
        elif size != self._dimensions:
            raise ValueError(
                f"Embedding model {self.model!r} returned {size}-dimensional vectors, "
                f"but dimensions={self._dimensions} was configured."
            )


class LangDockEmbedder(OpenAIEmbedder):
    """LangDock embedding API (OpenAI-compatible)."""

    PROVIDER_NAME = "langdock"
    BASE_URLS = {
        "eu": "https://api.langdock.com/openai/eu/v1",
        "us": "https://api.langdock.com/openai/us/v1",
    }

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        region: str = "eu",
        dimensions: int | None = None,
    ):
        """
        Initialize LangDock embedder.

        Args:
            api_key: LangDock API key
            model: Embedding model id (required; there is no default)
            region: API region ('eu' or 'us')
            dimensions: Vector size the model produces (else read from the first response)
        """
        # The region endpoints are fixed, built-in public URLs — assign after the
        # super() call so the SSRF guard's DNS round-trip is not paid for a URL
        # the caller cannot influence.
        super().__init__(api_key, model, None, dimensions)
        self.base_url = self.BASE_URLS.get(region, self.BASE_URLS["eu"])
        self.region = region


class MeliousEmbedder(OpenAIEmbedder):
    """Melious.ai embedding API (OpenAI-compatible, sovereign EU-hosted).

    The embedding model ids are advertised by Melious ``/v1/models``; pass one as
    ``model``. ``dimensions`` may be passed, else it is read from the first response.
    """

    PROVIDER_NAME = "melious"
    DEFAULT_BASE_URL = "https://api.melious.ai/v1"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
    ):
        """
        Initialize the Melious embedder.

        Args:
            api_key: Melious API key (sent as a Bearer token).
            model: Embedding model id as advertised by Melious ``/v1/models`` (required).
            base_url: OpenAI-compatible endpoint. Defaults to the official
                Melious URL; override only to route through a proxy.
            dimensions: Vector size the model produces (else read from the first response).

        Raises:
            ModelNotSpecifiedError: If ``model`` is missing.
            ValueError: If ``base_url`` fails URL validation.
        """
        super().__init__(api_key, model, base_url, dimensions)
        self.base_url = base_url or self.DEFAULT_BASE_URL
