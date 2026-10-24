"""Tests for Knora LangChain Embeddings adapter."""

from __future__ import annotations

import pytest

from knora.adapters.langchain.embedding import KnoraLangChainEmbeddings, LangChainEmbeddings
from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class DeterministicEmbeddingProvider:
    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions
        self.doc_calls: list[list[str]] = []
        self.query_calls: list[list[str]] = []

    def embed_documents(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        self.doc_calls.append(texts)
        vectors = tuple(tuple(float(i + 0.1) for i in range(self.dimensions)) for _ in texts)
        return EmbeddingBatch(
            vectors=vectors,
            provider=configuration.provider,
            model=configuration.model,
            usage={"total_tokens": len(texts) * 5},
        )

    def embed_queries(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        self.query_calls.append(texts)
        vectors = tuple(tuple(float(i + 0.5) for i in range(self.dimensions)) for _ in texts)
        return EmbeddingBatch(
            vectors=vectors,
            provider=configuration.provider,
            model=configuration.model,
            usage={"total_tokens": len(texts) * 3},
        )


@pytest.fixture
def test_config() -> EmbeddingConfiguration:
    return EmbeddingConfiguration.cloudflare_bge_base_en()


def test_adapter_satisfies_langchain_protocol(test_config: EmbeddingConfiguration) -> None:
    provider = DeterministicEmbeddingProvider()
    adapter = KnoraLangChainEmbeddings(provider=provider, configuration=test_config)
    assert isinstance(adapter, LangChainEmbeddings)


def test_embed_documents_preserves_order_and_types(test_config: EmbeddingConfiguration) -> None:
    provider = DeterministicEmbeddingProvider(dimensions=768)
    adapter = KnoraLangChainEmbeddings(provider=provider, configuration=test_config)

    texts = ["First document", "Second document", "Third document"]
    embeddings = adapter.embed_documents(texts)

    assert len(embeddings) == 3
    assert len(provider.doc_calls) == 1
    assert provider.doc_calls[0] == texts

    for doc_vec in embeddings:
        assert isinstance(doc_vec, list)
        assert len(doc_vec) == 768
        assert all(isinstance(v, float) for v in doc_vec)


def test_embed_documents_empty_returns_empty(test_config: EmbeddingConfiguration) -> None:
    provider = DeterministicEmbeddingProvider()
    adapter = KnoraLangChainEmbeddings(provider=provider, configuration=test_config)

    assert adapter.embed_documents([]) == []
    assert len(provider.doc_calls) == 0


def test_embed_query_delegates_to_embed_queries(test_config: EmbeddingConfiguration) -> None:
    provider = DeterministicEmbeddingProvider(dimensions=768)
    adapter = KnoraLangChainEmbeddings(provider=provider, configuration=test_config)

    query = "Search query"
    vec = adapter.embed_query(query)

    assert isinstance(vec, list)
    assert len(vec) == 768
    assert all(isinstance(v, float) for v in vec)
    assert len(provider.query_calls) == 1
    assert provider.query_calls[0] == [query]


def test_invalid_input_types_raise_type_error(test_config: EmbeddingConfiguration) -> None:
    provider = DeterministicEmbeddingProvider()
    adapter = KnoraLangChainEmbeddings(provider=provider, configuration=test_config)

    with pytest.raises(TypeError, match="texts must be a list of strings"):
        adapter.embed_documents([123, "valid"])  # type: ignore

    with pytest.raises(TypeError, match="query text must be a string"):
        adapter.embed_query(None)  # type: ignore


def test_provider_length_mismatch_raises_knora_error(test_config: EmbeddingConfiguration) -> None:
    class BadProvider:
        def embed_documents(self, texts, config):
            return EmbeddingBatch(vectors=(), provider="test", model="test")

    adapter = KnoraLangChainEmbeddings(provider=BadProvider(), configuration=test_config)  # type: ignore
    with pytest.raises(KnoraError, match="EMBEDDING_OUTPUT_LENGTH_MISMATCH"):
        adapter.embed_documents(["hello"])
