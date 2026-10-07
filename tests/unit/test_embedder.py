"""
Unit tests for RAG embedding adapters (OpenAI, LangDock, Melious).

The OpenAI SDK is never hit: the lazily-initialized client is injected as a
mock where an actual ``embed()`` call is exercised.
"""

import socket
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from eq_chatbot_core.rag.embedder import (
    LangDockEmbedder,
    MeliousEmbedder,
    OpenAIEmbedder,
)


class TestOpenAIEmbedder:
    """OpenAI embedder validates against its static catalog."""

    @pytest.mark.xfail(reason="stage 2: no embedding model table", strict=False)
    def test_unknown_model_raises(self):
        """An unknown model id is rejected at construction time."""
        with pytest.raises(ValueError):
            OpenAIEmbedder(api_key="sk-test", model="not-a-real-model")

    @pytest.mark.xfail(reason="stage 2: no embedding model table", strict=False)
    def test_dimensions_from_catalog(self):
        """Dimensions are read from the static MODELS map."""
        emb = OpenAIEmbedder(api_key="sk-test", model="text-embedding-3-large")
        assert emb.dimensions == 3072


class TestLangDockEmbedder:
    """LangDock embedder maps the region to the correct base URL."""

    def test_region_sets_base_url(self):
        emb = LangDockEmbedder(api_key="k", model="test-model", region="us")
        assert emb.base_url == LangDockEmbedder.BASE_URLS["us"]
        assert emb.region == "us"

    def test_default_region_is_eu(self):
        emb = LangDockEmbedder(api_key="k", model="test-model")
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

    @pytest.mark.xfail(reason="stage 2: no embedding model table", strict=False)
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


@pytest.mark.unit
class TestEmbedderTransport:
    """Embedders must use the pinned httpx2 client like the chat providers.

    The OpenAI SDK's own client follows redirects and re-resolves DNS on every
    connect, so a base_url that passed validation could be steered to the
    cloud-metadata endpoint by a 307 or a rebinding DNS answer.
    """

    @staticmethod
    def _addrinfo(ip: str) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    def _http_client(self, emb):
        """Build emb.client against a stand-in SDK and return the http_client it got."""
        mock_openai = MagicMock()
        with (
            patch.dict("sys.modules", {"openai": mock_openai}),
            patch.object(socket, "getaddrinfo", return_value=self._addrinfo("93.184.216.34")),
        ):
            _ = emb.client
        kwargs = mock_openai.OpenAI.call_args[1]
        return kwargs["base_url"], kwargs["http_client"]

    @pytest.mark.parametrize(
        ("factory", "expected_url"),
        [
            (lambda: OpenAIEmbedder(api_key="k", model="test-model"), "https://api.openai.com/v1"),
            (lambda: LangDockEmbedder(api_key="k", model="test-model"), "https://api.langdock.com/openai/eu/v1"),
            (lambda: MeliousEmbedder(api_key="k", model="m"), "https://api.melious.ai/v1"),
        ],
    )
    def test_client_gets_pinned_http_client(self, factory, expected_url):
        import httpx2

        base_url, http_client = self._http_client(factory())

        assert base_url == expected_url
        assert isinstance(http_client, httpx2.Client)
        assert http_client.follow_redirects is False

    def test_rebinding_to_metadata_is_blocked(self):
        import httpx2

        with patch.object(socket, "getaddrinfo", return_value=self._addrinfo("93.184.216.34")):
            emb = MeliousEmbedder(api_key="k", model="m", base_url="https://embed.example.com/v1")
        _, http_client = self._http_client(emb)

        with patch.object(socket, "getaddrinfo", return_value=self._addrinfo("169.254.169.254")):
            with pytest.raises(httpx2.ConnectError, match="rebinding"):
                http_client.post("https://embed.example.com/v1/embeddings", json={})
