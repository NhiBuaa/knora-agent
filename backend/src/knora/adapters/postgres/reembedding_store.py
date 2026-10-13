import math
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    RetrievalV2CutoverTable,
    WorkspaceTable,
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

    def authority_bound_population(self, *, workspace_id: str) -> tuple[CorpusChunkSet, ...]:
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

    def activate_embedding_set(self, *, member: CorpusChunkSet, embedding_set_id: str) -> None:
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

    def enable_v2_retrieval(self, *, workspace_id: str, population_digest: str) -> None:
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
                    EmbeddingSetTable.embedding_configuration_id == "embedding-gemini-m1-v1",
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


@dataclass(frozen=True, slots=True)
class ReindexDocument:
    workspace_id: str
    document_id: str
    source_key: str
    source_name: str
    version_id: str
    revision: int
    archived: bool
    active_embedding_set_id: str | None
    active_embedding_configuration_id: str | None
    active_vector_count: int
    chunk_set_id: str
    chunk_set_digest: str
    chunks: tuple[CorpusChunk, ...]


@dataclass(frozen=True, slots=True)
class ReindexInventory:
    workspace_ids: tuple[str, ...]
    all_workspaces: bool
    document_ids: tuple[str, ...]
    eligible: tuple[ReindexDocument, ...]
    unindexable: tuple[tuple[str, str], ...]
    excluded_snapshots: tuple["ReindexExcluded", ...]
    blockers: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ReindexExcluded:
    document_id: str
    version_id: str
    revision: int
    active_embedding_set_id: str | None
    active_embedding_configuration_id: str | None
    archived: bool


class PostgresCloudflareReindexStore:
    """One-time retained-corpus staging and atomic Cloudflare activation."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def inventory(
        self,
        *,
        workspace_ids: tuple[str, ...] | None = None,
        approved_unindexable_ids: tuple[str, ...] = (),
    ) -> ReindexInventory:
        approved = set(approved_unindexable_ids)
        if len(approved) != len(approved_unindexable_ids):
            raise KnoraError("REINDEX_DUPLICATE_EXCLUSION")
        with self._session_factory() as session:
            selected = tuple(sorted(session.scalars(select(WorkspaceTable.id)).all()))
            if workspace_ids is not None:
                if len(set(workspace_ids)) != len(workspace_ids) or not set(workspace_ids) <= set(
                    selected
                ):
                    raise KnoraError("REINDEX_WORKSPACE_INVALID")
                selected = tuple(sorted(workspace_ids))
            documents = session.scalars(
                select(DocumentTable)
                .where(DocumentTable.workspace_id.in_(selected))
                .order_by(DocumentTable.workspace_id, DocumentTable.id)
            ).all()
            eligible: list[ReindexDocument] = []
            unindexable: list[tuple[str, str]] = []
            excluded_snapshots: list[ReindexExcluded] = []
            blockers: list[tuple[str, str]] = []
            for document in documents:
                result = self._inspect_document(session, document)
                if isinstance(result, ReindexDocument):
                    eligible.append(result)
                elif result == "PDF_TEXT_INSUFFICIENT" and document.id in approved:
                    unindexable.append((document.id, result))
                    excluded_snapshots.append(
                        ReindexExcluded(
                            document_id=document.id,
                            version_id=document.current_document_version_id,
                            revision=document.revision,
                            active_embedding_set_id=document.active_embedding_set_id,
                            active_embedding_configuration_id=document.active_embedding_configuration_id,
                            archived=document.archived,
                        )
                    )
                else:
                    blockers.append((document.id, result))
            for unexpected in sorted(approved - {document_id for document_id, _ in unindexable}):
                blockers.append((unexpected, "EXCLUSION_NOT_PROVEN"))
            return ReindexInventory(
                workspace_ids=selected,
                all_workspaces=workspace_ids is None,
                document_ids=tuple(document.id for document in documents),
                eligible=tuple(eligible),
                unindexable=tuple(unindexable),
                excluded_snapshots=tuple(excluded_snapshots),
                blockers=tuple(blockers),
            )

    @staticmethod
    def _inspect_document(session, document: DocumentTable) -> ReindexDocument | str:
        if document.current_document_version_id is None:
            return "CURRENT_VERSION_MISSING"
        version = session.get(DocumentVersionTable, document.current_document_version_id)
        if version is None or version.document_id != document.id:
            return "CURRENT_VERSION_MISSING"
        active_set = (
            session.get(EmbeddingSetTable, document.active_embedding_set_id)
            if document.active_embedding_set_id is not None
            else None
        )
        if document.active_embedding_set_id is not None and active_set is None:
            return "ACTIVE_SET_MISSING"
        if active_set is not None:
            active_chunks = session.get(ChunkSetTable, active_set.chunk_set_id)
            if active_chunks is None or active_chunks.document_version_id != version.id:
                return "STALE_SERVING_VERSION_REPROCESS_REQUIRED"
            if (
                active_set.status != "completed"
                or active_set.embedding_configuration_id
                != document.active_embedding_configuration_id
            ):
                return "ACTIVE_SET_INCOMPLETE"
        chunk_sets = session.scalars(
            select(ChunkSetTable).where(ChunkSetTable.document_version_id == version.id)
        ).all()
        completed = [row for row in chunk_sets if row.status == "completed"]
        if not completed:
            source = session.scalar(
                select(OriginalSourceObjectTable).where(
                    OriginalSourceObjectTable.document_version_id == version.id,
                    OriginalSourceObjectTable.workspace_id == document.workspace_id,
                )
            )
            latest_job = session.scalar(
                select(IngestionJobTable)
                .where(
                    IngestionJobTable.document_id == document.id,
                    IngestionJobTable.target_document_version_id == version.id,
                )
                .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
                .limit(1)
            )
            if (
                not chunk_sets
                and version.media_type == "application/pdf"
                and source is not None
                and latest_job is not None
                and latest_job.status == "failed"
                and latest_job.safe_failure_code == "PDF_TEXT_INSUFFICIENT"
            ):
                return "PDF_TEXT_INSUFFICIENT"
            return "CURRENT_TEXT_DERIVATION_MISSING_REPROCESS_REQUIRED"
        if len(completed) != 1 and active_set is None:
            return "CURRENT_TEXT_DERIVATION_AMBIGUOUS"
        chunk_set = (
            next((row for row in completed if row.id == active_set.chunk_set_id), None)
            if active_set is not None
            else completed[0]
        )
        if chunk_set is None:
            return "CURRENT_TEXT_DERIVATION_INCOMPLETE_REPROCESS_REQUIRED"
        chunks = session.scalars(
            select(ChunkTable)
            .where(ChunkTable.chunk_set_id == chunk_set.id)
            .order_by(ChunkTable.ordinal)
        ).all()
        if not chunks or [chunk.ordinal for chunk in chunks] != list(range(len(chunks))):
            return "CURRENT_CHUNKS_INCOMPLETE_REPROCESS_REQUIRED"
        if any(
            not chunk.content.strip()
            or sha256(chunk.content.encode()).hexdigest() != chunk.content_checksum
            for chunk in chunks
        ):
            return "CURRENT_CHUNKS_INVALID_REPROCESS_REQUIRED"
        active_vector_count = 0
        if active_set is not None:
            active_config = session.get(
                EmbeddingConfigurationTable, active_set.embedding_configuration_id
            )
            if active_config is None:
                return "ACTIVE_PROFILE_MISSING"
            vectors = session.execute(
                select(
                    ChunkEmbeddingTable.chunk_id,
                    func.vector_dims(ChunkEmbeddingTable.embedding),
                ).where(ChunkEmbeddingTable.embedding_set_id == active_set.id)
            ).all()
            active_vector_count = len(vectors)
            if {chunk_id for chunk_id, _ in vectors} != {chunk.id for chunk in chunks} or any(
                dimensions != active_config.dimensions for _, dimensions in vectors
            ):
                return "ACTIVE_VECTOR_COVERAGE_INCOMPLETE"
        return ReindexDocument(
            workspace_id=document.workspace_id,
            document_id=document.id,
            source_key=document.source_key,
            source_name=document.source_name,
            version_id=version.id,
            revision=document.revision,
            archived=document.archived,
            active_embedding_set_id=document.active_embedding_set_id,
            active_embedding_configuration_id=document.active_embedding_configuration_id,
            active_vector_count=active_vector_count,
            chunk_set_id=chunk_set.id,
            chunk_set_digest=_chunk_set_digest(chunks),
            chunks=tuple(CorpusChunk(chunk.id, chunk.ordinal, chunk.content) for chunk in chunks),
        )

    @staticmethod
    def _assert_snapshot(session, expected: ReindexDocument, document: DocumentTable) -> None:
        if (
            document.workspace_id != expected.workspace_id
            or document.source_key != expected.source_key
            or document.source_name != expected.source_name
            or document.current_document_version_id != expected.version_id
            or document.revision != expected.revision
            or document.archived != expected.archived
            or document.active_embedding_set_id != expected.active_embedding_set_id
            or document.active_embedding_configuration_id
            != expected.active_embedding_configuration_id
        ):
            raise KnoraError("REINDEX_SNAPSHOT_DRIFT")
        current = PostgresCloudflareReindexStore._inspect_document(session, document)
        if (
            not isinstance(current, ReindexDocument)
            or current.chunk_set_id != expected.chunk_set_id
            or current.chunk_set_digest != expected.chunk_set_digest
            or current.chunks != expected.chunks
        ):
            raise KnoraError("REINDEX_CHUNK_DRIFT")

    @staticmethod
    def _coverage(
        session, embedding_set_id: str, document: ReindexDocument, config: EmbeddingConfiguration
    ) -> None:
        embedding_set = session.get(EmbeddingSetTable, embedding_set_id)
        if (
            embedding_set is None
            or embedding_set.status != "completed"
            or embedding_set.chunk_set_id != document.chunk_set_id
            or embedding_set.embedding_configuration_id != config.id
        ):
            raise KnoraError("REINDEX_SET_INVALID")
        rows = session.execute(
            select(ChunkEmbeddingTable.chunk_id, ChunkEmbeddingTable.embedding)
            .where(ChunkEmbeddingTable.embedding_set_id == embedding_set_id)
            .order_by(ChunkEmbeddingTable.chunk_id)
        ).all()
        if [chunk_id for chunk_id, _ in rows] != sorted(
            chunk.chunk_id for chunk in document.chunks
        ):
            raise KnoraError("REINDEX_VECTOR_COVERAGE_INCOMPLETE")
        if any(
            len(vector) != config.dimensions or any(not math.isfinite(value) for value in vector)
            for _, vector in rows
        ):
            raise KnoraError("REINDEX_VECTOR_INVALID")

    def completed_set(
        self, document: ReindexDocument, config: EmbeddingConfiguration
    ) -> str | None:
        with self._session_factory() as session:
            embedding_set = session.scalar(
                select(EmbeddingSetTable).where(
                    EmbeddingSetTable.chunk_set_id == document.chunk_set_id,
                    EmbeddingSetTable.embedding_configuration_id == config.id,
                )
            )
            if embedding_set is None:
                return None
            row = session.get(EmbeddingConfigurationTable, config.id)
            if row is None:
                raise KnoraError("REINDEX_PROFILE_MISSING")
            _assert_configuration(row, config)
            self._coverage(session, embedding_set.id, document, config)
            return embedding_set.id

    def stage(
        self, document: ReindexDocument, config: EmbeddingConfiguration, batch: EmbeddingBatch
    ) -> str:
        with self._session_factory.begin() as session:
            current = session.get(DocumentTable, document.document_id, with_for_update=True)
            if current is None:
                raise KnoraError("REINDEX_SNAPSHOT_DRIFT")
            self._assert_snapshot(session, document, current)
            _persist_configuration(session, config)
            existing = session.scalar(
                select(EmbeddingSetTable).where(
                    EmbeddingSetTable.chunk_set_id == document.chunk_set_id,
                    EmbeddingSetTable.embedding_configuration_id == config.id,
                )
            )
            if existing is not None:
                self._coverage(session, existing.id, document, config)
                return existing.id
            if (
                batch.provider != config.provider
                or batch.model != config.model
                or len(batch.vectors) != len(document.chunks)
                or any(
                    len(vector) != config.dimensions
                    or any(not math.isfinite(value) for value in vector)
                    for vector in batch.vectors
                )
            ):
                raise KnoraError("REINDEX_BATCH_INVALID")
            embedding_set = EmbeddingSetTable(
                id=str(uuid4()),
                chunk_set_id=document.chunk_set_id,
                embedding_configuration_id=config.id,
                status="completed",
            )
            session.add(embedding_set)
            session.flush()
            for chunk, vector in zip(document.chunks, batch.vectors, strict=True):
                session.add(
                    ChunkEmbeddingTable(
                        id=str(uuid4()),
                        embedding_set_id=embedding_set.id,
                        chunk_id=chunk.chunk_id,
                        embedding=list(vector),
                    )
                )
            session.flush()
            self._coverage(session, embedding_set.id, document, config)
            return embedding_set.id

    def _lock_population(self, session, inventory: ReindexInventory) -> dict[str, DocumentTable]:
        session.scalars(
            select(WorkspaceTable)
            .where(WorkspaceTable.id.in_(inventory.workspace_ids))
            .order_by(WorkspaceTable.id)
            .with_for_update()
        ).all()
        if (
            inventory.all_workspaces
            and tuple(sorted(session.scalars(select(WorkspaceTable.id)).all()))
            != inventory.workspace_ids
        ):
            raise KnoraError("REINDEX_POPULATION_DRIFT")
        documents = session.scalars(
            select(DocumentTable)
            .where(DocumentTable.workspace_id.in_(inventory.workspace_ids))
            .order_by(DocumentTable.workspace_id, DocumentTable.id)
            .with_for_update()
        ).all()
        if tuple(document.id for document in documents) != inventory.document_ids:
            raise KnoraError("REINDEX_POPULATION_DRIFT")
        by_id = {document.id: document for document in documents}
        for excluded in inventory.excluded_snapshots:
            current = by_id[excluded.document_id]
            if (
                current.current_document_version_id != excluded.version_id
                or current.revision != excluded.revision
                or current.active_embedding_set_id != excluded.active_embedding_set_id
                or current.active_embedding_configuration_id
                != excluded.active_embedding_configuration_id
                or current.archived != excluded.archived
                or self._inspect_document(session, current) != "PDF_TEXT_INSUFFICIENT"
            ):
                raise KnoraError("REINDEX_EXCLUSION_DRIFT")
        return by_id

    def activate(
        self,
        inventory: ReindexInventory,
        staged: dict[str, str],
        config: EmbeddingConfiguration,
    ) -> None:
        if (
            inventory.blockers
            or not inventory.eligible
            or set(staged) != {document.document_id for document in inventory.eligible}
        ):
            raise KnoraError("REINDEX_POPULATION_INCOMPLETE")
        with self._session_factory.begin() as session:
            documents = self._lock_population(session, inventory)
            for document in inventory.eligible:
                self._assert_snapshot(session, document, documents[document.document_id])
                self._coverage(session, staged[document.document_id], document, config)
            for document in inventory.eligible:
                current = documents[document.document_id]
                if current.active_embedding_set_id != staged[document.document_id]:
                    current.active_embedding_set_id = staged[document.document_id]
                    current.active_embedding_configuration_id = config.id
                    current.revision += 1

    def cleanup(
        self, inventory: ReindexInventory, config: EmbeddingConfiguration, *, e2e_confirmed: bool
    ) -> int:
        if not e2e_confirmed or inventory.blockers or not inventory.eligible:
            raise KnoraError("REINDEX_CLEANUP_NOT_READY")
        with self._session_factory.begin() as session:
            documents = self._lock_population(session, inventory)
            for document in inventory.eligible:
                current = documents[document.document_id]
                self._assert_snapshot(session, document, current)
                if (
                    current.active_embedding_configuration_id != config.id
                    or not current.active_embedding_set_id
                ):
                    raise KnoraError("REINDEX_CLEANUP_NOT_READY")
                self._coverage(session, current.active_embedding_set_id, document, config)
            obsolete_sets = session.scalars(
                select(EmbeddingSetTable)
                .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
                .join(
                    DocumentVersionTable,
                    DocumentVersionTable.id == ChunkSetTable.document_version_id,
                )
                .where(
                    DocumentVersionTable.document_id.in_(
                        document.document_id for document in inventory.eligible
                    ),
                    EmbeddingSetTable.embedding_configuration_id != config.id,
                )
            ).all()
            if not obsolete_sets:
                return 0
            for embedding_set in obsolete_sets:
                configuration = session.get(
                    EmbeddingConfigurationTable, embedding_set.embedding_configuration_id
                )
                if embedding_set.status != "completed" or configuration is None:
                    raise KnoraError("REINDEX_CLEANUP_OLD_SET_INVALID")
                chunk_ids = set(
                    session.scalars(
                        select(ChunkTable.id).where(
                            ChunkTable.chunk_set_id == embedding_set.chunk_set_id
                        )
                    ).all()
                )
                vectors = session.execute(
                    select(ChunkEmbeddingTable.chunk_id, ChunkEmbeddingTable.embedding).where(
                        ChunkEmbeddingTable.embedding_set_id == embedding_set.id
                    )
                ).all()
                if vectors and (
                    {chunk_id for chunk_id, _ in vectors} != chunk_ids
                    or any(
                        len(vector) != configuration.dimensions
                        or any(not math.isfinite(value) for value in vector)
                        for _, vector in vectors
                    )
                ):
                    raise KnoraError("REINDEX_CLEANUP_OLD_SET_INCOMPLETE")
            result = session.execute(
                delete(ChunkEmbeddingTable).where(
                    ChunkEmbeddingTable.embedding_set_id.in_(row.id for row in obsolete_sets)
                )
            )
            return result.rowcount


def _assert_configuration(row: EmbeddingConfigurationTable, config: EmbeddingConfiguration) -> None:
    from knora.adapters.postgres.embedding_configuration import configuration_from_row

    if configuration_from_row(row) != config:
        raise KnoraError("EMBEDDING_CONFIGURATION_IMMUTABLE")
