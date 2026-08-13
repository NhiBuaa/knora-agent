from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration, EmbeddingProvider


@dataclass(frozen=True, slots=True)
class CorpusChunk:
    chunk_id: str
    ordinal: int
    content: str


@dataclass(frozen=True, slots=True)
class CorpusChunkSet:
    source_key: str
    document_id: str
    chunk_set_id: str
    chunk_set_digest: str
    chunks: tuple[CorpusChunk, ...]


class ReembeddingStore(Protocol):
    def authority_bound_population(
        self, *, workspace_id: str
    ) -> tuple[CorpusChunkSet, ...]: ...

    def persist_embedding_set(
        self,
        *,
        member: CorpusChunkSet,
        configuration: EmbeddingConfiguration,
        batch: EmbeddingBatch,
    ) -> str: ...

    def activate_embedding_set(
        self, *, member: CorpusChunkSet, embedding_set_id: str
    ) -> None: ...

    def enable_v2_retrieval(
        self, *, workspace_id: str, population_digest: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ReembeddingResult:
    population_digest: str
    reembedded_source_keys: tuple[str, ...]


class ReembedProductionCorpus:
    def __init__(self, *, provider: EmbeddingProvider, store: ReembeddingStore) -> None:
        self._provider = provider
        self._store = store

    def execute(
        self, *, workspace_id: str, configuration: EmbeddingConfiguration
    ) -> ReembeddingResult:
        if configuration != EmbeddingConfiguration.gemini_m3():
            raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
        population = self._store.authority_bound_population(workspace_id=workspace_id)
        if not population or len({member.source_key for member in population}) != len(population):
            raise ValueError("authority-bound corpus population must be non-empty and unique")
        ordered = tuple(sorted(population, key=lambda member: member.source_key))
        population_digest = _population_digest(ordered)
        completed: list[tuple[CorpusChunkSet, str]] = []
        for member in ordered:
            chunks = sorted(member.chunks, key=lambda chunk: chunk.ordinal)
            texts = [chunk.content for chunk in chunks]
            batch = self._provider.embed_documents(texts, configuration)
            if len(batch.vectors) != len(texts) or any(
                len(vector) != configuration.dimensions for vector in batch.vectors
            ):
                raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")
            if batch.provider != configuration.provider or batch.model != configuration.model:
                raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")
            embedding_set_id = self._store.persist_embedding_set(
                member=member, configuration=configuration, batch=batch
            )
            completed.append((member, embedding_set_id))
        for member, embedding_set_id in completed:
            self._store.activate_embedding_set(
                member=member, embedding_set_id=embedding_set_id
            )
        self._store.enable_v2_retrieval(
            workspace_id=workspace_id, population_digest=population_digest
        )
        return ReembeddingResult(
            population_digest=population_digest,
            reembedded_source_keys=tuple(member.source_key for member, _ in completed),
        )


def _population_digest(population: tuple[CorpusChunkSet, ...]) -> str:
    digest = sha256()
    for member in population:
        digest.update(member.source_key.encode())
        digest.update(b"\0")
        digest.update(member.chunk_set_id.encode())
        digest.update(b"\0")
        digest.update(member.chunk_set_digest.encode())
        digest.update(b"\n")
    return digest.hexdigest()
