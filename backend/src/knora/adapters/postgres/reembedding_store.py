from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    RetrievalV2CutoverTable,
)
from knora.answering.reembedding_v2 import CorpusChunk, CorpusChunkSet, ReembeddingStore
from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class PostgresReembeddingStore(ReembeddingStore):
    """Persist Gemini vectors on existing authority-bound Chunk Sets."""

    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        authority_source_keys: tuple[str, ...],
    ) -> None:
        if not authority_source_keys or len(set(authority_source_keys)) != len(
            authority_source_keys
        ):
            raise ValueError("authority source keys must be non-empty and unique")
        self._session_factory = session_factory
        self._authority_source_keys = tuple(sorted(authority_source_keys))

    def authority_bound_population(
        self, *, workspace_id: str
    ) -> tuple[CorpusChunkSet, ...]:
        statement = (
            select(DocumentTable, ChunkSetTable, ChunkTable)
            .join(
                EmbeddingSetTable,
                EmbeddingSetTable.id == DocumentTable.active_embedding_set_id,
            )
            .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
            .join(ChunkTable, ChunkTable.chunk_set_id == ChunkSetTable.id)
            .where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.source_key.in_(self._authority_source_keys),
                EmbeddingSetTable.status == "completed",
                ChunkSetTable.status == "completed",
            )
            .order_by(DocumentTable.source_key, ChunkTable.ordinal)
        )
        with self._session_factory() as session:
            rows = session.execute(statement).all()
        grouped: dict[str, tuple[DocumentTable, ChunkSetTable, list[ChunkTable]]] = {}
        for document, chunk_set, chunk in rows:
            current = grouped.get(document.source_key)
            if current is None:
                grouped[document.source_key] = (document, chunk_set, [chunk])
            elif current[1].id != chunk_set.id:
                raise KnoraError("AUTHORITY_CORPUS_AMBIGUOUS")
            else:
                current[2].append(chunk)
        if set(grouped) != set(self._authority_source_keys):
            raise KnoraError("AUTHORITY_CORPUS_INCOMPLETE")
        return tuple(
            CorpusChunkSet(
                source_key=source_key,
                document_id=document.id,
                chunk_set_id=chunk_set.id,
                chunk_set_digest=_chunk_set_digest(chunks),
                chunks=tuple(
                    CorpusChunk(chunk.id, chunk.ordinal, chunk.content) for chunk in chunks
                ),
            )
            for source_key, (document, chunk_set, chunks) in sorted(grouped.items())
        )

    def persist_embedding_set(
        self,
        *,
        member: CorpusChunkSet,
        configuration: EmbeddingConfiguration,
        batch: EmbeddingBatch,
    ) -> str:
        with self._session_factory.begin() as session:
            _persist_configuration(session, configuration)
            existing = session.scalar(
                select(EmbeddingSetTable).where(
                    EmbeddingSetTable.chunk_set_id == member.chunk_set_id,
                    EmbeddingSetTable.embedding_configuration_id == configuration.id,
                )
            )
            if existing is not None:
                if existing.status != "completed":
                    raise KnoraError("EMBEDDING_SET_INCOMPLETE")
                return existing.id
            embedding_set_id = str(uuid4())
            session.add(
                EmbeddingSetTable(
                    id=embedding_set_id,
                    chunk_set_id=member.chunk_set_id,
                    embedding_configuration_id=configuration.id,
                    status="completed",
                )
            )
            session.flush()
            for chunk, vector in zip(member.chunks, batch.vectors, strict=True):
                session.add(
                    ChunkEmbeddingTable(
                        id=str(uuid4()),
                        embedding_set_id=embedding_set_id,
                        chunk_id=chunk.chunk_id,
                        embedding=list(vector),
                    )
                )
            return embedding_set_id

    def activate_embedding_set(
        self, *, member: CorpusChunkSet, embedding_set_id: str
    ) -> None:
        with self._session_factory.begin() as session:
            document = session.get(DocumentTable, member.document_id, with_for_update=True)
            embedding_set = session.get(EmbeddingSetTable, embedding_set_id)
            if (
                document is None
                or embedding_set is None
                or embedding_set.chunk_set_id != member.chunk_set_id
                or embedding_set.embedding_configuration_id != "embedding-gemini-m1-v1"
                or embedding_set.status != "completed"
            ):
                raise KnoraError("EMBEDDING_ACTIVATION_INVALID")
            session.execute(
                update(DocumentTable)
                .where(DocumentTable.id == document.id, DocumentTable.revision == document.revision)
                .values(
                    active_embedding_set_id=embedding_set.id,
                    active_embedding_configuration_id=embedding_set.embedding_configuration_id,
                    revision=DocumentTable.revision + 1,
                )
            )

    def enable_v2_retrieval(
        self, *, workspace_id: str, population_digest: str
    ) -> None:
        with self._session_factory.begin() as session:
            active = session.execute(
                select(DocumentTable.source_key, EmbeddingSetTable.chunk_set_id)
                .join(
                    EmbeddingSetTable,
                    EmbeddingSetTable.id == DocumentTable.active_embedding_set_id,
                )
                .where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.source_key.in_(self._authority_source_keys),
                    EmbeddingSetTable.embedding_configuration_id
                    == "embedding-gemini-m1-v1",
                    EmbeddingSetTable.status == "completed",
                )
            ).all()
            if {source_key for source_key, _ in active} != set(self._authority_source_keys):
                raise KnoraError("RETRIEVAL_V2_CUTOVER_INCOMPLETE")
            session.merge(
                RetrievalV2CutoverTable(
                    workspace_id=workspace_id,
                    embedding_configuration_id="embedding-gemini-m1-v1",
                    population_digest=population_digest,
                    status="completed",
                )
            )


def _chunk_set_digest(chunks: list[ChunkTable]) -> str:
    digest = sha256()
    for chunk in chunks:
        digest.update(str(chunk.ordinal).encode())
        digest.update(b"\0")
        digest.update(chunk.content_checksum.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _persist_configuration(session, config: EmbeddingConfiguration) -> None:
    row = session.get(EmbeddingConfigurationTable, config.id)
    values = (
        config.provider,
        config.model,
        config.dimensions,
        config.distance_metric,
        config.deployment_identity,
        config.api_contract_version,
        config.input_normalization,
        config.input_policy_id,
        config.output_dimensionality,
        config.vector_normalization,
    )
    if row is None:
        session.add(
            EmbeddingConfigurationTable(
                id=config.id,
                provider=config.provider,
                model=config.model,
                dimensions=config.dimensions,
                distance_metric=config.distance_metric,
                deployment_identity=config.deployment_identity,
                api_contract_version=config.api_contract_version,
                input_normalization=config.input_normalization,
                input_policy_id=config.input_policy_id,
                output_dimensionality=config.output_dimensionality,
                vector_normalization=config.vector_normalization,
            )
        )
        session.flush()
        return
    persisted = (
        row.provider,
        row.model,
        row.dimensions,
        row.distance_metric,
        row.deployment_identity,
        row.api_contract_version,
        row.input_normalization,
        row.input_policy_id,
        row.output_dimensionality,
        row.vector_normalization,
    )
    if persisted != values:
        raise KnoraError("EMBEDDING_CONFIGURATION_IMMUTABLE")
