"""
Unit tests for RAG embedding adapters (OpenAI, LangDock, Melious).

The OpenAI SDK is never hit: the lazily-initialized client is injected as a
mock where an actual ``embed()`` call is exercised.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from eq_chatbot_core.rag.embedder import (
    LangDockEmbedder,
    MeliousEmbedder,
    OpenAIEmbedder,
)


class TestOpenAIEmbedder:
    """OpenAI embedder validates against its static catalog."""

    def test_unknown_model_raises(self):
        """An unknown model id is rejected at construction time."""
        with pytest.raises(ValueError):
            OpenAIEmbedder(api_key="sk-test", model="not-a-real-model")

    def test_dimensions_from_catalog(self):
        """Dimensions are read from the static MODELS map."""
        emb = OpenAIEmbedder(api_key="sk-test", model="text-embedding-3-large")
        assert emb.dimensions == 3072


class TestLangDockEmbedder:
    """LangDock embedder maps the region to the correct base URL."""

    def test_region_sets_base_url(self):
        emb = LangDockEmbedder(api_key="k", region="us")
        assert emb.base_url == LangDockEmbedder.BASE_URLS["us"]
        assert emb.region == "us"

    def test_default_region_is_eu(self):
        emb = LangDockEmbedder(api_key="k")
        assert emb.base_url == LangDockEmbedder.BASE_URLS["eu"]


class TestMeliousEmbedder:
    """Melious embedder skips model validation and takes dimensions explicitly."""

    def test_default_base_url(self):
        emb = MeliousEmbedder(api_key="sk-mel-x", model="melious-embed")
        assert emb.base_url == "https://api.melious.ai/v1"

    def test_base_url_override(self):
        # Loopback URL keeps the SSRF guard's validate_url hermetic (no DNS).
        emb = MeliousEmbedder(api_key="k", model="m", base_url="http://localhost:9000/v1")
        assert emb.base_url == "http://localhost:9000/v1"

    def test_ssrf_metadata_blocked(self):
        with pytest.raises(ValueError):
            MeliousEmbedder(api_key="k", model="m", base_url="http://169.254.169.254/v1")

    def test_private_range_blocked(self):
        with pytest.raises(ValueError):
            MeliousEmbedder(api_key="k", model="m", base_url="http://10.0.0.5/v1")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(ValueError):
            MeliousEmbedder(api_key="k", model="m", base_url="file:///etc/passwd")

    def test_default_dimensions(self):
        emb = MeliousEmbedder(api_key="k", model="m")
        assert emb.dimensions == 1536

    def test_configurable_dimensions(self):
        emb = MeliousEmbedder(api_key="k", model="m", dimensions=1024)
        assert emb.dimensions == 1024

    def test_skips_static_model_validation(self):
        """A dynamic (non-catalog) model id must be accepted."""
        emb = MeliousEmbedder(api_key="k", model="some-dynamic-model")
        assert emb.model == "some-dynamic-model"

    def test_embed_uses_openai_compatible_client(self):
        """embed() delegates to the OpenAI-compatible embeddings endpoint."""
        emb = MeliousEmbedder(api_key="k", model="m", dimensions=3)

        mock_client = MagicMock()
        mock_response = MagicMock()
        item = MagicMock()
        item.embedding = [0.1, 0.2, 0.3]
        mock_response.data = [item]
        mock_client.embeddings.create.return_value = mock_response
        emb._client = mock_client  # inject mock, bypass lazy init

        result = emb.embed("hello world")

        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 3)
        mock_client.embeddings.create.assert_called_once_with(model="m", input=["hello world"])
