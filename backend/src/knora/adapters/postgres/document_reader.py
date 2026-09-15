from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    DocumentDeletionRequestTable,
    DocumentTable,
    DocumentVersionTable,
    OriginalSourceObjectTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.documents import (
    DocumentDeletionRequestProjection,
    DocumentListProjection,
    DocumentProjection,
)
from knora.ingestion.object_lifecycle import (
    LifecycleWorkState,
    ObjectLifecycleMaintenance,
    ObjectLifecycleWorkItem,
)


class PostgresDocumentReader:
    def __init__(
        self,
        session_factory: sessionmaker,
        lifecycle_maintenance: ObjectLifecycleMaintenance | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._lifecycle_maintenance = lifecycle_maintenance

    @staticmethod
    def _projection(row: DocumentTable) -> DocumentProjection:
        return DocumentProjection(
            document_id=row.id,
            workspace_id=row.workspace_id,
            source_key=row.source_key,
            source_name=row.source_name,
            archived=row.archived,
            revision=row.revision,
            current_document_version_id=row.current_document_version_id,
            serving_state="current" if row.active_embedding_set_id else "unavailable",
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
            return DocumentListProjection(tuple(self._projection(row) for row in rows))

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
            return self._projection(row)

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
                return self._projection(row)
            row.archived = archived
            row.revision += 1
            session.flush()
            return self._projection(row)

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
                    state="requested",
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
            source_keys = list(
                session.scalars(
                    select(OriginalSourceObjectTable.object_key)
                    .join(
                        DocumentVersionTable,
                        DocumentVersionTable.id
                        == OriginalSourceObjectTable.document_version_id,
                    )
                    .where(
                        DocumentVersionTable.document_id == document_id,
                        OriginalSourceObjectTable.workspace_id == workspace_id,
                        OriginalSourceObjectTable.deleted_at.is_(None),
                    )
                )
            )
            projection = DocumentDeletionRequestProjection(
                existing.id, existing.document_id, existing.state
            )
        if self._lifecycle_maintenance is not None:
            for object_key in source_keys:
                self._lifecycle_maintenance.enqueue(
                    ObjectLifecycleWorkItem(
                        work_id=str(uuid4()),
                        workspace_id=workspace_id,
                        object_key=object_key,
                        state=LifecycleWorkState.QUEUED,
                        artifact_class="document_deletion",
                        lifecycle_generation=existing.id,
                    )
                )
        return projection
