"""Transactional generation requests and activation; no projection I/O."""

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    WorkspaceTable,
)
from knora.ingestion.search_indexing import LexicalGeneration, StageReceipt, StaleGenerationError


class PostgresSearchIndexStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._sessions = session_factory

    @staticmethod
    def _lock_document(
        session: Session, workspace_id: str, document_id: str, *, allow_archived: bool = False
    ) -> tuple[WorkspaceTable, DocumentTable]:
        workspace = session.scalar(
            select(WorkspaceTable)
            .where(
                WorkspaceTable.id == workspace_id,
            )
            .with_for_update()
        )
        document = session.scalar(
            select(DocumentTable)
            .where(
                DocumentTable.id == document_id,
                DocumentTable.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        if (
            workspace is None
            or document is None
            or (not allow_archived and (workspace.archived or document.archived))
        ):
            raise StaleGenerationError("lexical source is unavailable")
        return workspace, document

    def request_generation(self, generation: LexicalGeneration, *, expected_revision: int) -> None:
        with self._sessions.begin() as session:
            workspace, document = self._lock_document(
                session, generation.workspace_id, generation.document_id
            )
            existing = session.get(LexicalGenerationTable, generation.generation_id)
            if existing is not None:
                if (
                    existing.content_digest != generation.content_digest()
                    or existing.status == "revoked"
                ):
                    raise StaleGenerationError("generation identity cannot be reused")
                return
            if document.current_document_version_id != generation.document_version_id:
                raise StaleGenerationError("generation targets an obsolete source version")
            chunk_set = session.get(ChunkSetTable, generation.chunk_set_id)
            if (
                chunk_set is None
                or chunk_set.document_version_id != generation.document_version_id
                or chunk_set.status != "completed"
            ):
                raise StaleGenerationError("generation targets an incomplete chunk set")
            chunks = session.scalars(
                select(ChunkTable)
                .where(
                    ChunkTable.chunk_set_id == generation.chunk_set_id,
                )
                .order_by(ChunkTable.ordinal)
            ).all()
            if [(c.id, c.ordinal, c.content_checksum) for c in chunks] != [
                (c.chunk_id, c.ordinal, c.content_checksum) for c in generation.chunks
            ]:
                raise StaleGenerationError("generation manifest differs from authoritative chunks")
            head = session.get(LexicalHeadTable, document.id)
            current_revision = head.revision if head is not None else 0
            if (
                current_revision != expected_revision
                or generation.revision != expected_revision + 1
            ):
                raise StaleGenerationError("desired generation compare-and-set failed")
            row = LexicalGenerationTable(
                id=generation.generation_id,
                workspace_id=generation.workspace_id,
                document_id=document.id,
                document_version_id=generation.document_version_id,
                chunk_set_id=generation.chunk_set_id,
                revision=generation.revision,
                source_revision=document.revision,
                workspace_revision=workspace.revision,
                profile_digest=generation.lexical_profile.digest(),
                content_digest=generation.content_digest(),
                expected_count=len(generation.chunks),
                manifest=asdict(generation),
                status="requested",
            )
            session.add(row)
            session.flush()
            if head is None:
                head = LexicalHeadTable(document_id=document.id, revision=0)
                session.add(head)
            active = (
                session.get(LexicalGenerationTable, head.active_generation_id)
                if head.active_generation_id
                else None
            )
            if active is not None and (
                active.document_version_id != generation.document_version_id
                or active.profile_digest != row.profile_digest
                or active.source_revision != document.revision
                or active.workspace_revision != workspace.revision
            ):
                head.active_generation_id = None
            head.revision = generation.revision
            head.desired_generation_id = generation.generation_id

    def activate_ready(self, generation: LexicalGeneration, receipt: StageReceipt) -> None:
        receipt.validate(generation)
        with self._sessions.begin() as session:
            workspace, document = self._lock_document(
                session, generation.workspace_id, generation.document_id
            )
            head = session.get(LexicalHeadTable, document.id)
            row = session.get(LexicalGenerationTable, generation.generation_id)
            if (
                head is None
                or row is None
                or head.desired_generation_id != row.id
                or head.revision != generation.revision
                or row.revision != generation.revision
                or row.status == "revoked"
                or row.source_revision != document.revision
                or row.workspace_revision != workspace.revision
                or document.current_document_version_id != row.document_version_id
                or row.content_digest != receipt.content_digest
                or row.expected_count != receipt.point_count
            ):
                raise StaleGenerationError("activation compare-and-set failed")
            if row.acknowledged_count not in (None, receipt.point_count):
                raise StaleGenerationError("conflicting acknowledgement replay")
            row.acknowledged_count = receipt.point_count
            row.status = "active"
            head.active_generation_id = row.id

    def revoke(self, *, workspace_id: str, document_id: str) -> None:
        with self._sessions.begin() as session:
            self._lock_document(session, workspace_id, document_id, allow_archived=True)
            head = session.get(LexicalHeadTable, document_id)
            if head is None:
                return
            if head.desired_generation_id is None and head.active_generation_id is None:
                return
            for row in session.scalars(
                select(LexicalGenerationTable).where(
                    LexicalGenerationTable.document_id == document_id,
                )
            ):
                row.status = "revoked"
            head.revision += 1
            head.desired_generation_id = None
            head.active_generation_id = None
