from uuid import uuid4

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkSetTable,
    ChunkTable,
    DocumentDeletionRequestTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    RetrievalV2CutoverTable,
    WorkspaceTable,
)
from knora.answering.stores import RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.documents import (
    AnswerAvailability,
    DocumentDeletionRequestProjection,
    DocumentListProjection,
    DocumentProjection,
)
from knora.providers.embedding import EmbeddingConfiguration


class PostgresDocumentReader:
    def __init__(
        self,
        session_factory: sessionmaker,
        deployed_embedding_configuration: EmbeddingConfiguration | None = None,
        deployed_retrieval_configuration: RetrievalConfiguration | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._deployed_embedding_configuration = (
            deployed_embedding_configuration or EmbeddingConfiguration.milestone_one_local()
        )
        self._deployed_retrieval_configuration = (
            deployed_retrieval_configuration or RetrievalConfiguration.milestone_one()
        )

    @staticmethod
    def _begin_snapshot(session) -> None:
        bind = session.get_bind()
        if isinstance(bind, Connection) and bind.in_transaction():
            # A caller may inject an already-open transaction (for example a
            # savepoint-scoped unit of work). It must supply the same guarantee.
            if bind.get_isolation_level() not in {"REPEATABLE READ", "SERIALIZABLE"}:
                raise ValueError("Document projections require a consistent read snapshot")
        else:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})

    def _answer_availability(self, session, row, active, workspace_archived) -> AnswerAvailability:
        """Project query-independent eligibility using the existing retrieval predicates.

        This says evidence can participate in a new question, not that any particular
        question meets similarity, lexical-match or downstream sufficiency thresholds.
        """
        if row.archived or workspace_archived is True:
            return "unavailable"
        if workspace_archived is None:
            return "unknown"
        if active is None:
            return "unknown" if row.active_embedding_set_id is not None else "unavailable"
        configuration = self._deployed_embedding_configuration
        if active.embedding_configuration_id != configuration.id or active.status != "completed":
            return "unavailable"
        # One incompatible completed active set blocks retrieval for the whole corpus.
        incompatible = exists(
            select(EmbeddingSetTable.id)
            .join(DocumentTable, DocumentTable.active_embedding_set_id == EmbeddingSetTable.id)
            .where(
                DocumentTable.workspace_id == row.workspace_id,
                DocumentTable.archived.is_(False),
                EmbeddingSetTable.status == "completed",
                EmbeddingSetTable.embedding_configuration_id != configuration.id,
            )
        )
        if session.scalar(select(incompatible)):
            return "unavailable"
        retrieval = self._deployed_retrieval_configuration
        if retrieval.id in {"retrieval-m3-vector-v2", "retrieval-m3-rrf-v2"}:
            cutover = session.get(RetrievalV2CutoverTable, (row.workspace_id, configuration.id))
            if cutover is None or cutover.status != "completed":
                return "unavailable"
        chunks = select(ChunkTable.id).where(ChunkTable.chunk_set_id == active.chunk_set_id)
        if retrieval.strategy == "vector-only":
            chunks = chunks.join(
                ChunkEmbeddingTable, ChunkEmbeddingTable.chunk_id == ChunkTable.id
            ).where(
                ChunkEmbeddingTable.embedding_set_id == row.active_embedding_set_id,
                func.vector_dims(ChunkEmbeddingTable.embedding) == configuration.dimensions,
                # A zero vector has undefined cosine similarity for every query.
                func.vector_norm(ChunkEmbeddingTable.embedding) > 0,
            )
        elif retrieval.strategy != "hybrid":
            return "unknown"
        return "available" if session.scalar(select(exists(chunks))) else "unavailable"

    def _projection(self, session, row: DocumentTable) -> DocumentProjection:
        active = session.execute(
            select(
                ChunkSetTable.document_version_id,
                EmbeddingSetTable.embedding_configuration_id,
                EmbeddingSetTable.chunk_set_id,
                EmbeddingSetTable.status,
            )
            .join(EmbeddingSetTable, EmbeddingSetTable.chunk_set_id == ChunkSetTable.id)
            .join(
                DocumentVersionTable, DocumentVersionTable.id == ChunkSetTable.document_version_id
            )
            .where(
                EmbeddingSetTable.id == row.active_embedding_set_id,
                DocumentVersionTable.document_id == row.id,
            )
        ).first()
        served_document_version_id = active[0] if active is not None else None
        active_embedding_configuration_id = active[1] if active is not None else None
        latest_job = session.scalar(
            select(IngestionJobTable)
            .where(
                IngestionJobTable.workspace_id == row.workspace_id,
                IngestionJobTable.document_id == row.id,
            )
            .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
            .limit(1)
        )
        last_processed_at = (
            session.scalar(
                select(func.max(IngestionJobTable.terminal_at)).where(
                    IngestionJobTable.workspace_id == row.workspace_id,
                    IngestionJobTable.document_id == row.id,
                    IngestionJobTable.target_document_version_id == served_document_version_id,
                    IngestionJobTable.status == "succeeded",
                )
            )
            if served_document_version_id is not None
            else None
        )
        deletion = session.scalar(
            select(DocumentDeletionRequestTable)
            .where(
                DocumentDeletionRequestTable.workspace_id == row.workspace_id,
                DocumentDeletionRequestTable.document_id == row.id,
            )
            .order_by(
                DocumentDeletionRequestTable.created_at.desc(),
                DocumentDeletionRequestTable.id.desc(),
            )
            .limit(1)
        )
        if served_document_version_id is None:
            serving_state = "unavailable"
        elif served_document_version_id == row.current_document_version_id:
            serving_state = "current"
        else:
            serving_state = "previous"
        if active_embedding_configuration_id is None:
            embedding_readiness = "not_indexed"
        elif (
            serving_state == "current"
            and active_embedding_configuration_id == self._deployed_embedding_configuration.id
        ):
            embedding_readiness = "ready"
        else:
            embedding_readiness = "reindex_required"
        source_object_id = session.scalar(
            select(OriginalSourceObjectTable.id)
            .join(
                DocumentVersionTable,
                DocumentVersionTable.id == OriginalSourceObjectTable.document_version_id,
            )
            .where(
                DocumentVersionTable.id == row.current_document_version_id,
                DocumentVersionTable.document_id == row.id,
                DocumentVersionTable.media_type == "application/pdf",
                OriginalSourceObjectTable.workspace_id == row.workspace_id,
                OriginalSourceObjectTable.deleted_at.is_(None),
            )
        )
        workspace_archived = session.scalar(
            select(WorkspaceTable.archived).where(WorkspaceTable.id == row.workspace_id)
        )
        reprocess_supported = bool(
            source_object_id and not row.archived and workspace_archived is False
        )
        return DocumentProjection(
            document_id=row.id,
            workspace_id=row.workspace_id,
            source_key=row.source_key,
            source_name=row.source_name,
            archived=row.archived,
            revision=row.revision,
            current_document_version_id=row.current_document_version_id,
            serving_state=serving_state,
            ingestion_job_id=latest_job.id if latest_job is not None else None,
            ingestion_status=latest_job.status if latest_job is not None else None,
            active_embedding_configuration_id=active_embedding_configuration_id,
            embedding_readiness=embedding_readiness,
            reprocess_supported=reprocess_supported,
            served_document_version_id=served_document_version_id,
            last_processed_at=last_processed_at,
            answer_availability=self._answer_availability(session, row, active, workspace_archived),
            deletion_request=DocumentDeletionRequestProjection(
                deletion.id, deletion.document_id, deletion.state, deletion.failure_reason
            )
            if deletion is not None
            else None,
        )

    def list_documents(
        self, *, workspace_id: str, principal: WorkspacePrincipal
    ) -> DocumentListProjection:
        if principal.workspace_id != workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        with self._session_factory() as session:
            self._begin_snapshot(session)
            rows = session.scalars(
                select(DocumentTable)
                .where(DocumentTable.workspace_id == workspace_id)
                .order_by(DocumentTable.source_key)
            ).all()
            return DocumentListProjection(tuple(self._projection(session, row) for row in rows))

    def read_document(
        self, *, workspace_id: str, document_id: str, principal: WorkspacePrincipal
    ) -> DocumentProjection:
        if principal.workspace_id != workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        with self._session_factory() as session:
            self._begin_snapshot(session)
            row = session.scalar(
                select(DocumentTable).where(
                    DocumentTable.id == document_id, DocumentTable.workspace_id == workspace_id
                )
            )
            if row is None:
                raise KnoraError("DOCUMENT_NOT_FOUND")
            return self._projection(session, row)

    def _mutate_archive(
        self, *, workspace_id: str, document_id: str, archived: bool, expected_revision: int | None
    ) -> DocumentProjection:
        try:
            with self._session_factory.begin() as session:
                self._begin_snapshot(session)
                row = session.scalar(
                    select(DocumentTable)
                    .where(
                        DocumentTable.id == document_id, DocumentTable.workspace_id == workspace_id
                    )
                    .with_for_update()
                )
                if row is None:
                    raise KnoraError("DOCUMENT_NOT_FOUND")
                if expected_revision is not None and row.revision != expected_revision:
                    raise KnoraError("DOCUMENT_CONCURRENTLY_UPDATED")
                if row.archived == archived:
                    return self._projection(session, row)
                row.archived = archived
                row.revision += 1
                session.flush()
                return self._projection(session, row)
        except OperationalError as error:
            if getattr(error.orig, "sqlstate", None) == "40001":
                raise KnoraError("DOCUMENT_CONCURRENTLY_UPDATED") from error
            raise

    def archive(
        self,
        *,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        expected_revision: int | None = None,
    ) -> DocumentProjection:
        return self._mutate_archive(
            workspace_id=workspace_id,
            document_id=document_id,
            archived=True,
            expected_revision=expected_revision,
        )

    def unarchive(
        self,
        *,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        expected_revision: int | None = None,
    ) -> DocumentProjection:
        return self._mutate_archive(
            workspace_id=workspace_id,
            document_id=document_id,
            archived=False,
            expected_revision=expected_revision,
        )

    def request_deletion(
        self,
        *,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        idempotency_key: str,
    ) -> DocumentDeletionRequestProjection:
        with self._session_factory.begin() as session:
            document = session.scalar(
                select(DocumentTable).where(
                    DocumentTable.id == document_id, DocumentTable.workspace_id == workspace_id
                )
            )
            if document is None:
                raise KnoraError("DOCUMENT_NOT_FOUND")
            request_id = str(uuid4())
            session.execute(
                postgres_insert(DocumentDeletionRequestTable)
                .values(
                    id=request_id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    idempotency_key=idempotency_key,
                    state="blocked",
                    failure_reason="DOCUMENT_DELETION_POLICY_UNAVAILABLE",
                )
                .on_conflict_do_nothing(
                    index_elements=["workspace_id", "document_id", "idempotency_key"]
                )
            )
            existing = session.scalar(
                select(DocumentDeletionRequestTable).where(
                    DocumentDeletionRequestTable.workspace_id == workspace_id,
                    DocumentDeletionRequestTable.document_id == document_id,
                    DocumentDeletionRequestTable.idempotency_key == idempotency_key,
                )
            )
            if existing is None:
                raise KnoraError("PERSISTENCE_OPERATION_FAILED")
            return DocumentDeletionRequestProjection(
                existing.id,
                existing.document_id,
                existing.state,
                existing.failure_reason,
            )
