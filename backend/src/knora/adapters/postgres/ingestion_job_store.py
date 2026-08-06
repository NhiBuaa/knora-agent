"""PostgreSQL adapter for durable Ingestion Job submission."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ChunkingConfigurationTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    IdempotencyRecordTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import (
    PdfSubmissionResult,
    PdfSubmissionStore,
    PreparedPdfSubmission,
)
from knora.ingestion.object_store import ObjectMetadata


class PostgresIngestionJobStore(PdfSubmissionStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def authorize_workspace(self, *, workspace_id: str) -> None:
        with self._session_factory() as session:
            if session.get(WorkspaceTable, workspace_id) is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")

    def is_object_referenced(self, *, source_object: ObjectMetadata) -> bool:
        try:
            with self._session_factory() as session:
                return (
                    session.scalar(
                        select(OriginalSourceObjectTable.id).where(
                            OriginalSourceObjectTable.workspace_id == source_object.workspace_id,
                            OriginalSourceObjectTable.object_key == source_object.object_key,
                            OriginalSourceObjectTable.raw_sha256 == source_object.sha256,
                        )
                    )
                    is not None
                )
        except SQLAlchemyError:
            return True

    def commit_pdf_submission(
        self,
        prepared: PreparedPdfSubmission,
    ) -> PdfSubmissionResult:
        for attempt in range(2):
            try:
                return self._commit_pdf_submission(prepared)
            except KnoraError:
                raise
            except IntegrityError:
                if attempt == 0:
                    continue
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
            except SQLAlchemyError:
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
        raise AssertionError("unreachable")

    def _commit_pdf_submission(
        self,
        prepared: PreparedPdfSubmission,
    ) -> PdfSubmissionResult:
        with self._session_factory.begin() as session:
            if session.get(WorkspaceTable, prepared.workspace_id) is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")

            replay = session.scalar(
                select(IdempotencyRecordTable)
                .where(
                    IdempotencyRecordTable.workspace_id == prepared.workspace_id,
                    IdempotencyRecordTable.operation == prepared.idempotency_operation,
                    IdempotencyRecordTable.key == prepared.idempotency_key,
                )
                .with_for_update()
            )
            if replay is not None and replay.expires_at <= datetime.now(UTC):
                session.delete(replay)
                session.flush()
                replay = None
            if replay is not None:
                if replay.request_fingerprint != prepared.content_fingerprint:
                    raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
                job = session.scalar(
                    select(IngestionJobTable).where(
                        IngestionJobTable.id == replay.ingestion_job_id,
                        IngestionJobTable.workspace_id == prepared.workspace_id,
                    )
                )
                if job is None:
                    raise KnoraError("PERSISTENCE_OPERATION_FAILED")
                return self._result(
                    session,
                    job,
                    submission_outcome="idempotency_replay",
                )

            document = session.scalar(
                select(DocumentTable)
                .where(
                    DocumentTable.workspace_id == prepared.workspace_id,
                    DocumentTable.source_key == prepared.source_key,
                )
                .with_for_update()
            )
            if document is None:
                document = DocumentTable(
                    id=str(uuid4()),
                    workspace_id=prepared.workspace_id,
                    source_key=prepared.source_key,
                    source_name=prepared.source_name,
                    revision=0,
                )
                session.add(document)
                session.flush()

            version = session.scalar(
                select(DocumentVersionTable).where(
                    DocumentVersionTable.document_id == document.id,
                    DocumentVersionTable.raw_sha256 == prepared.source_object.sha256,
                )
            )
            if version is None:
                next_version_number = session.scalar(
                    select(func.coalesce(func.max(DocumentVersionTable.version_number), 0) + 1)
                    .where(DocumentVersionTable.document_id == document.id)
                )
                version = DocumentVersionTable(
                    id=str(uuid4()),
                    document_id=document.id,
                    normalized_content=None,
                    normalized_content_checksum=None,
                    raw_sha256=prepared.source_object.sha256,
                    media_type=prepared.source_object.media_type,
                    version_number=next_version_number,
                )
                session.add(version)
                session.flush()
                source_object = OriginalSourceObjectTable(
                    id=str(uuid4()),
                    workspace_id=prepared.workspace_id,
                    document_version_id=version.id,
                    object_key=prepared.source_object.object_key,
                    raw_sha256=prepared.source_object.sha256,
                    byte_size=prepared.source_object.byte_size,
                    media_type=prepared.source_object.media_type,
                )
                session.add(source_object)
                session.flush()
            else:
                source_object = session.scalar(
                    select(OriginalSourceObjectTable).where(
                        OriginalSourceObjectTable.document_version_id == version.id
                    )
                )
                if source_object is None:
                    raise KnoraError("PERSISTENCE_OPERATION_FAILED")

            if document.current_document_version_id != version.id:
                document.current_document_version_id = version.id
                document.revision += 1
                session.flush()

            self._get_or_create_chunking_configuration(session, prepared)
            self._get_or_create_embedding_configuration(session, prepared)
            job = session.scalar(
                select(IngestionJobTable).where(
                    IngestionJobTable.workspace_id == prepared.workspace_id,
                    IngestionJobTable.operation == prepared.idempotency_operation,
                    IngestionJobTable.content_fingerprint == prepared.content_fingerprint,
                )
            )
            submission_outcome = "deduplicated"
            if job is None:
                config = prepared.configuration
                job = IngestionJobTable(
                    id=str(uuid4()),
                    workspace_id=prepared.workspace_id,
                    operation=prepared.idempotency_operation,
                    document_id=document.id,
                    target_document_version_id=version.id,
                    source_object_id=source_object.id,
                    content_fingerprint=prepared.content_fingerprint,
                    parser_configuration_id=config.parser_configuration_id,
                    normalizer_configuration_id=config.normalizer_configuration_id,
                    chunking_configuration_id=config.chunking_configuration.id,
                    embedding_configuration_id=config.embedding_configuration.id,
                    status="queued",
                    attempt_count=0,
                    max_attempts=4,
                )
                session.add(job)
                session.flush()
                submission_outcome = "created"

            session.add(
                IdempotencyRecordTable(
                    id=str(uuid4()),
                    workspace_id=prepared.workspace_id,
                    operation=prepared.idempotency_operation,
                    key=prepared.idempotency_key,
                    request_fingerprint=prepared.content_fingerprint,
                    ingestion_job_id=job.id,
                    expires_at=prepared.idempotency_expires_at,
                )
            )
            session.flush()
            return self._result(
                session,
                job,
                submission_outcome=submission_outcome,
            )

    @staticmethod
    def _result(
        session: Session,
        job: IngestionJobTable,
        *,
        submission_outcome: str,
    ) -> PdfSubmissionResult:
        source_object = session.scalar(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.id == job.source_object_id,
                OriginalSourceObjectTable.workspace_id == job.workspace_id,
                OriginalSourceObjectTable.document_version_id == job.target_document_version_id,
            )
        )
        if source_object is None:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED")
        return PdfSubmissionResult(
            ingestion_job_id=job.id,
            submission_outcome=submission_outcome,
            status=job.status,
            document_id=job.document_id,
            document_version_id=job.target_document_version_id,
            retained_object_key=source_object.object_key,
        )

    @staticmethod
    def _get_or_create_chunking_configuration(
        session: Session,
        prepared: PreparedPdfSubmission,
    ) -> None:
        config = prepared.configuration.chunking_configuration
        row = session.get(ChunkingConfigurationTable, config.id)
        values = (
            config.parser_version,
            config.chunker_version,
            config.tokenizer_name,
            config.tokenizer_version,
            config.target_tokens,
            config.overlap_tokens,
            config.max_tokens,
        )
        if row is None:
            session.add(
                ChunkingConfigurationTable(
                    id=config.id,
                    parser_version=config.parser_version,
                    chunker_version=config.chunker_version,
                    tokenizer_name=config.tokenizer_name,
                    tokenizer_version=config.tokenizer_version,
                    target_tokens=config.target_tokens,
                    overlap_tokens=config.overlap_tokens,
                    max_tokens=config.max_tokens,
                )
            )
            session.flush()
            return
        persisted = (
            row.parser_version,
            row.chunker_version,
            row.tokenizer_name,
            row.tokenizer_version,
            row.target_tokens,
            row.overlap_tokens,
            row.max_tokens,
        )
        if persisted != values:
            raise KnoraError("CHUNKING_CONFIGURATION_IMMUTABLE")

    @staticmethod
    def _get_or_create_embedding_configuration(
        session: Session,
        prepared: PreparedPdfSubmission,
    ) -> None:
        config = prepared.configuration.embedding_configuration
        row = session.get(EmbeddingConfigurationTable, config.id)
        values = (config.provider, config.model, config.dimensions, config.distance_metric)
        if row is None:
            session.add(
                EmbeddingConfigurationTable(
                    id=config.id,
                    provider=config.provider,
                    model=config.model,
                    dimensions=config.dimensions,
                    distance_metric=config.distance_metric,
                )
            )
            session.flush()
            return
        persisted = (row.provider, row.model, row.dimensions, row.distance_metric)
        if persisted != values:
            raise KnoraError("EMBEDDING_CONFIGURATION_IMMUTABLE")
