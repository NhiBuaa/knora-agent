"""LangChain Embeddings adapter wrapping Knora EmbeddingProvider."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingConfiguration, EmbeddingProvider


@runtime_checkable
class LangChainEmbeddings(Protocol):
    """Protocol matching langchain_core.embeddings.Embeddings interface."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class KnoraLangChainEmbeddings:
    """Thin LangChain Embeddings adapter preserving Knora semantics and invariants."""

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        configuration: EmbeddingConfiguration,
    ) -> None:
        if provider is None or configuration is None:
            raise ValueError("provider and configuration are required")
        self._provider = provider
        self._configuration = configuration

    @property
    def configuration(self) -> EmbeddingConfiguration:
        return self._configuration

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(t, str) for t in texts):
            raise TypeError("texts must be a list of strings")
        embed_fn = getattr(self._provider, "embed_documents", None) or getattr(
            self._provider, "embed", None
        )
        if embed_fn is None:
            raise KnoraError("EMBEDDING_PROVIDER_UNAVAILABLE")
        batch = embed_fn(texts, self._configuration)
        if len(batch.vectors) != len(texts):
            raise KnoraError("EMBEDDING_OUTPUT_LENGTH_MISMATCH")
        return [list(vector) for vector in batch.vectors]

    def embed_query(self, text: str) -> list[float]:
        if not isinstance(text, str):
            raise TypeError("query text must be a string")
        embed_fn = getattr(self._provider, "embed_queries", None) or getattr(
            self._provider, "embed", None
        )
        if embed_fn is None:
            raise KnoraError("EMBEDDING_PROVIDER_UNAVAILABLE")
        batch = embed_fn([text], self._configuration)
        if not batch.vectors or len(batch.vectors) != 1:
            raise KnoraError("EMBEDDING_OUTPUT_LENGTH_MISMATCH")
        return list(batch.vectors[0])
