"""Embedders: the model is the caller's; the vector size is passed or read from the first response."""

import pytest

from eq_chatbot_core.providers import ModelNotSpecifiedError
from eq_chatbot_core.rag.embedder import LangDockEmbedder, MeliousEmbedder, OpenAIEmbedder
from tests.wire_server import Reply, embeddings_body

pytestmark = pytest.mark.unit
EMBED = ("POST", "/v1/embeddings")


@pytest.mark.parametrize("cls", [OpenAIEmbedder, LangDockEmbedder, MeliousEmbedder])
def test_model_is_required(cls):
    with pytest.raises(ModelNotSpecifiedError, match="embedding model") as caught:
        cls(api_key="k")
    assert f"{cls.__name__}(" in str(caught.value)


def test_dimensions_unknown_until_the_first_embedding(wire_server):
    embedder = OpenAIEmbedder(api_key="k", model="emb-test", base_url=wire_server.base_url)
    assert embedder.dimensions is None
    wire_server.expect(*EMBED, Reply(body=embeddings_body([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])))
    vectors = embedder.embed(["a", "b"])
    assert vectors.shape == (2, 3)
    assert embedder.dimensions == 3
    assert wire_server.requests[0].json["model"] == "emb-test"


def test_passed_dimensions_are_known_up_front():
    assert MeliousEmbedder(api_key="k", model="emb-test", dimensions=1024).dimensions == 1024
    assert LangDockEmbedder(api_key="k", model="emb-test", dimensions=256).dimensions == 256


def test_configured_dimensions_mismatch_raises(wire_server):
    """Review focus 4: a wrong size must not reach a vector collection silently."""
    embedder = OpenAIEmbedder(api_key="k", model="emb-test", base_url=wire_server.base_url, dimensions=4)
    wire_server.expect(*EMBED, Reply(body=embeddings_body([[0.1, 0.2, 0.3]])))
    with pytest.raises(ValueError, match="dimensions=4"):
        embedder.embed("a")


def test_collection_size_comes_from_the_embedder(wire_server):
    """Review focus 4: no collection of unknown size; the discovered size is used."""
    from qdrant_client import QdrantClient

    from eq_chatbot_core.rag.retriever import HybridRetriever

    embedder = OpenAIEmbedder(api_key="k", model="emb-test", base_url=wire_server.base_url)
    retriever = HybridRetriever(QdrantClient(location=":memory:"), "docs", embedder)
    with pytest.raises(ValueError, match="(?i)vector size"):
        retriever.ensure_collection()

    wire_server.expect(*EMBED, Reply(body=embeddings_body([[0.1, 0.2, 0.3]])))
    embedder.embed("a")
    retriever.ensure_collection()
    assert retriever.client.get_collection("docs").config.params.vectors.size == 3
