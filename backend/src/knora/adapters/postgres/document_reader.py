from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentDeletionRequestTable,
    DocumentTable,
    EmbeddingSetTable,
    IngestionJobTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.documents import (
    DocumentDeletionRequestProjection,
    DocumentListProjection,
    DocumentProjection,
)


class PostgresDocumentReader:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _projection(session, row: DocumentTable) -> DocumentProjection:
        served_document_version_id = session.scalar(
            select(ChunkSetTable.document_version_id)
            .join(EmbeddingSetTable, EmbeddingSetTable.chunk_set_id == ChunkSetTable.id)
            .where(EmbeddingSetTable.id == row.active_embedding_set_id)
        )
        latest_job = session.scalar(
            select(IngestionJobTable)
            .where(
                IngestionJobTable.workspace_id == row.workspace_id,
                IngestionJobTable.document_id == row.id,
            )
            .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
            .limit(1)
        )
        if served_document_version_id is None:
            serving_state = "unavailable"
        elif served_document_version_id == row.current_document_version_id:
            serving_state = "current"
        else:
            serving_state = "previous"
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
        )

    def list_documents(
        self, *, workspace_id: str, principal: WorkspacePrincipal
    ) -> DocumentListProjection:
        if principal.workspace_id != workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        with self._session_factory() as session:
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
        with self._session_factory.begin() as session:
            row = session.scalar(
                select(DocumentTable)
                .where(DocumentTable.id == document_id, DocumentTable.workspace_id == workspace_id)
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
