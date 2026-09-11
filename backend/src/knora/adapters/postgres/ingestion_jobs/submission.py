"""Private PostgreSQL persistence for PDF submission and read projections."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ChunkingConfigurationTable,
    ChunkSetTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IdempotencyRecordTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    ReprocessAuditTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import (
    JobStatusProjection,
    PdfSubmissionConfiguration,
    PdfSubmissionResult,
    PdfSubmissionStore,
    PreparedPdfSubmission,
    PreparedReprocess,
    ReprocessAuditProjection,
    ReprocessContext,
    ReprocessResult,
)
from knora.ingestion.object_store import ObjectMetadata

_PUBLIC_FAILURE_REASONS = frozenset(
    {"retry_exhausted", "terminal_input", "terminal_config", "resource_limit"}
)
_SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class PostgresPdfSubmissionStore(PdfSubmissionStore):
    def __init__(
        self,
        session_factory: sessionmaker,
        database_now: Callable[[Session], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._database_now = database_now

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
                            OriginalSourceObjectTable.deleted_at.is_(None),
                        )
                    )
                    is not None
                )
        except SQLAlchemyError:
            return True

    def get_job_status(
        self, *, workspace_id: str, ingestion_job_id: str
    ) -> JobStatusProjection | None:
        """Read one Workspace-scoped public projection from one PostgreSQL snapshot."""

        from sqlalchemy.orm import aliased

        served_version = aliased(DocumentVersionTable)
        statement = (
            select(
                IngestionJobTable,
                DocumentTable,
                served_version,
                ChunkSetTable,
                EmbeddingSetTable,
            )
            .join(
                DocumentTable,
                and_(
                    DocumentTable.id == IngestionJobTable.document_id,
                    DocumentTable.workspace_id == IngestionJobTable.workspace_id,
                ),
            )
            .outerjoin(
                EmbeddingSetTable,
                and_(
                    EmbeddingSetTable.id == DocumentTable.active_embedding_set_id,
                    EmbeddingSetTable.status == "completed",
                ),
            )
            .outerjoin(
                ChunkSetTable,
                ChunkSetTable.id == EmbeddingSetTable.chunk_set_id,
            )
            .outerjoin(
                served_version,
                served_version.id == ChunkSetTable.document_version_id,
            )
            .where(
                IngestionJobTable.id == ingestion_job_id,
                IngestionJobTable.workspace_id == workspace_id,
            )
        )
        with self._session_factory() as session:
            row = session.execute(statement).first()
            if row is None:
                return None
            job, document, served, _chunk_set, _embedding_set = row
            served_id = served.id if served is not None else None
            current_id = document.current_document_version_id
            if served_id is None:
                serving_state = "unavailable"
            elif current_id == served_id:
                serving_state = "current"
            else:
                serving_state = "previous"
            failure_reason = (
                job.failure_reason
                if job.failure_reason in _PUBLIC_FAILURE_REASONS
                else None
            )
            error_code = (
                job.safe_failure_code
                if isinstance(job.safe_failure_code, str)
                and _SAFE_ERROR_CODE.fullmatch(job.safe_failure_code)
                else None
            )
            return JobStatusProjection(
                ingestion_job_id=job.id,
                status=job.status,
                attempt_count=job.attempt_count,
                max_attempts=job.max_attempts,
                next_attempt_at=job.next_attempt_at,
                created_at=job.created_at,
                started_at=job.started_at,
                updated_at=job.updated_at,
                terminal_at=job.terminal_at,
                target_document_version_id=job.target_document_version_id,
                current_document_version_id=current_id,
                served_document_version_id=served_id,
                serving_state=serving_state,
                failure_reason=failure_reason,
                error_code=error_code,
                result_document_version_id=(
                    job.target_document_version_id if job.status == "succeeded" else None
                ),
                replacement_document_version_id=job.replacement_document_version_id,
                replacement_ingestion_job_id=job.replacement_ingestion_job_id,
                reprocess_of_job_id=job.reprocess_of_job_id,
            )

    def read_reprocess_context(
        self,
        *,
        workspace_id: str,
        document_version_id: str,
        config_mode: str,
        config_source_job_id: str | None,
    ) -> ReprocessContext | None:
        """Resolve a current PDF version and immutable configuration snapshot for reprocess."""


        with self._session_factory() as session:
            row = session.execute(
                select(DocumentTable, DocumentVersionTable)
                .join(
                    DocumentVersionTable,
                    and_(
                        DocumentVersionTable.id == document_version_id,
                        DocumentVersionTable.document_id == DocumentTable.id,
                    ),
                )
                .where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentVersionTable.id == document_version_id,
                )
            ).first()
            if row is None:
                return None
            document, version = row
            if document.current_document_version_id != version.id:
                raise KnoraError("DOCUMENT_VERSION_NOT_CURRENT")
            source_object = session.scalar(
                select(OriginalSourceObjectTable).where(
                    OriginalSourceObjectTable.workspace_id == workspace_id,
                    OriginalSourceObjectTable.document_version_id == version.id,
                )
            )
            if source_object is None:
                raise KnoraError("SOURCE_OBJECT_NOT_AVAILABLE")

            source_job = None
            if config_mode == "same_as_job":
                source_job = session.scalar(
                    select(IngestionJobTable).where(
                        IngestionJobTable.id == config_source_job_id,
                        IngestionJobTable.workspace_id == workspace_id,
                        IngestionJobTable.target_document_version_id == version.id,
                    )
                )
                if source_job is None:
                    raise KnoraError("CONFIG_SOURCE_JOB_INVALID")
                configuration = self._configuration_from_job(session, source_job)
                prior_job_id = source_job.id
            else:
                configuration = self._current_configuration_for_document(
                    session=session,
                    document=document,
                    document_version_id=version.id,
                )
                prior_job = session.scalar(
                    select(IngestionJobTable)
                    .where(
                        IngestionJobTable.workspace_id == workspace_id,
                        IngestionJobTable.target_document_version_id == version.id,
                    )
                    .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
                    .limit(1)
                )
                prior_job_id = prior_job.id if prior_job is not None else None

            return ReprocessContext(
                workspace_id=workspace_id,
                document_id=document.id,
                document_version_id=version.id,
                source_object=ObjectMetadata(
                    workspace_id=source_object.workspace_id,
                    object_key=source_object.object_key,
                    sha256=source_object.raw_sha256,
                    byte_size=source_object.byte_size,
                    media_type=source_object.media_type,
                ),
                configuration=configuration,
                config_source_job_id=config_source_job_id,
                prior_job_id=prior_job_id,
            )

    def read_reprocess_replay(
        self, *, workspace_id: str, idempotency_key: str, request_fingerprint: str
    ) -> ReprocessResult | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(IdempotencyRecordTable).where(
                    IdempotencyRecordTable.workspace_id == workspace_id,
                    IdempotencyRecordTable.operation == "reprocess_document_version",
                    IdempotencyRecordTable.key == idempotency_key,
                )
            )
            if record is None or record.expires_at <= datetime.now(UTC):
                return None
            if record.request_fingerprint != request_fingerprint:
                raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
            job = session.scalar(
                select(IngestionJobTable).where(
                    IngestionJobTable.id == record.ingestion_job_id,
                    IngestionJobTable.workspace_id == workspace_id,
                )
            )
            if job is None:
                raise KnoraError("PERSISTENCE_OPERATION_FAILED")
            return ReprocessResult(
                ingestion_job_id=job.id,
                document_version_id=job.target_document_version_id,
                outcome="idempotency_replay",
                status=job.status,
                audit_id=self._existing_audit_id(
                    session=session,
                    workspace_id=workspace_id,
                    ingestion_job_id=job.id,
                ),
            )

    def commit_reprocess(self, prepared: PreparedReprocess) -> ReprocessResult:
        for attempt in range(2):
            try:
                return self._commit_reprocess_once(prepared)
            except KnoraError:
                raise
            except IntegrityError:
                if attempt == 0:
                    continue
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
            except SQLAlchemyError:
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
        raise AssertionError("unreachable")

    def _commit_reprocess_once(self, prepared: PreparedReprocess) -> ReprocessResult:
        with self._session_factory.begin() as session:
            document = session.scalar(
                select(DocumentTable)
                .where(
                    DocumentTable.id == prepared.document_id,
                    DocumentTable.workspace_id == prepared.workspace_id,
                )
                .with_for_update()
            )
            version = session.scalar(
                select(DocumentVersionTable).where(
                    DocumentVersionTable.id == prepared.document_version_id,
                    DocumentVersionTable.document_id == prepared.document_id,
                )
            )
            if document is None or version is None:
                raise KnoraError("DOCUMENT_VERSION_NOT_FOUND")
            if document.current_document_version_id != version.id:
                raise KnoraError("DOCUMENT_VERSION_NOT_CURRENT")
            source_object = session.scalar(
                select(OriginalSourceObjectTable).where(
                    OriginalSourceObjectTable.id == self._source_object_id(
                        session, prepared.source_object
                    ),
                    OriginalSourceObjectTable.workspace_id == prepared.workspace_id,
                    OriginalSourceObjectTable.document_version_id == version.id,
                )
            )
            if source_object is None:
                raise KnoraError("SOURCE_OBJECT_NOT_AVAILABLE")

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
                if replay.request_fingerprint != prepared.request_fingerprint:
                    raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
                job = session.scalar(
                    select(IngestionJobTable).where(
                        IngestionJobTable.id == replay.ingestion_job_id,
                        IngestionJobTable.workspace_id == prepared.workspace_id,
                    )
                )
                if job is None:
                    raise KnoraError("PERSISTENCE_OPERATION_FAILED")
                return ReprocessResult(
                    ingestion_job_id=job.id,
                    document_version_id=job.target_document_version_id,
                    outcome="idempotency_replay",
                    status=job.status,
                    audit_id=self._existing_audit_id(
                        session=session,
                        workspace_id=prepared.workspace_id,
                        ingestion_job_id=job.id,
                    ),
                )

            self._get_or_create_chunking_configuration(session, prepared)
            self._get_or_create_embedding_configuration(session, prepared)
            config = prepared.configuration
            job = session.scalar(
                select(IngestionJobTable)
                .where(
                    IngestionJobTable.workspace_id == prepared.workspace_id,
                    IngestionJobTable.target_document_version_id == prepared.document_version_id,
                    IngestionJobTable.parser_configuration_id == config.parser_configuration_id,
                    IngestionJobTable.normalizer_configuration_id
                    == config.normalizer_configuration_id,
                    IngestionJobTable.chunking_configuration_id == config.chunking_configuration.id,
                    IngestionJobTable.embedding_configuration_id
                    == config.embedding_configuration.id,
                    IngestionJobTable.status.in_(("processing", "succeeded")),
                )
                .order_by(IngestionJobTable.created_at, IngestionJobTable.id)
                .limit(1)
            )
            outcome = "reused"
            database_now = self._database_now(session)
            if job is None:
                job = IngestionJobTable(
                    id=str(uuid4()),
                    workspace_id=prepared.workspace_id,
                    operation=prepared.idempotency_operation,
                    document_id=prepared.document_id,
                    target_document_version_id=prepared.document_version_id,
                    source_object_id=source_object.id,
                    content_fingerprint=prepared.request_fingerprint,
                    parser_configuration_id=config.parser_configuration_id,
                    normalizer_configuration_id=config.normalizer_configuration_id,
                    chunking_configuration_id=config.chunking_configuration.id,
                    embedding_configuration_id=config.embedding_configuration.id,
                    status="queued",
                    attempt_count=0,
                    max_attempts=4,
                    created_at=database_now,
                    updated_at=database_now,
                    reprocess_of_job_id=(
                        prepared.config_source_job_id or prepared.prior_job_id
                    ),
                )
                session.add(job)
                session.flush()
                outcome = "created"

            session.add(
                IdempotencyRecordTable(
                    id=str(uuid4()),
                    workspace_id=prepared.workspace_id,
                    operation=prepared.idempotency_operation,
                    key=prepared.idempotency_key,
                    request_fingerprint=prepared.request_fingerprint,
                    ingestion_job_id=job.id,
                    expires_at=prepared.idempotency_expires_at,
                    created_at=database_now,
                )
            )
            audit = ReprocessAuditTable(
                id=str(uuid4()),
                workspace_id=prepared.workspace_id,
                actor_key_id=prepared.actor_key_id,
                action="document_version.reprocess",
                target_document_version_id=prepared.document_version_id,
                requested_config_mode=prepared.requested_config_mode,
                resolved_config_mode=prepared.resolved_config_mode,
                config_source_job_id=prepared.config_source_job_id,
                ingestion_job_id=job.id,
                outcome=outcome,
                trace_id=None,
                created_at=database_now,
            )
            session.add(audit)
            session.flush()
            return ReprocessResult(
                ingestion_job_id=job.id,
                document_version_id=job.target_document_version_id,
                outcome=outcome,
                status=job.status,
                audit_id=audit.id,
            )

    def read_reprocess_audit(
        self, *, workspace_id: str, audit_event_id: str
    ) -> ReprocessAuditProjection | None:
        with self._session_factory() as session:
            audit = session.scalar(
                select(ReprocessAuditTable).where(
                    ReprocessAuditTable.id == audit_event_id,
                    ReprocessAuditTable.workspace_id == workspace_id,
                )
            )
            if audit is None:
                return None
            return ReprocessAuditProjection(
                audit_event_id=audit.id,
                workspace_id=audit.workspace_id,
                actor_key_id=audit.actor_key_id,
                action=audit.action,
                target_document_version_id=audit.target_document_version_id,
                requested_config_mode=audit.requested_config_mode,
                resolved_config_mode=audit.resolved_config_mode,
                config_source_job_id=audit.config_source_job_id,
                ingestion_job_id=audit.ingestion_job_id,
                outcome=audit.outcome,
                created_at=audit.created_at,
                trace_id=audit.trace_id,
            )

    @staticmethod
    def _existing_audit_id(
        *, session: Session, workspace_id: str, ingestion_job_id: str
    ) -> str | None:
        audit = session.scalar(
            select(ReprocessAuditTable)
            .where(
                ReprocessAuditTable.workspace_id == workspace_id,
                ReprocessAuditTable.ingestion_job_id == ingestion_job_id,
            )
            .order_by(ReprocessAuditTable.created_at, ReprocessAuditTable.id)
            .limit(1)
        )
        return audit.id if audit is not None else None

    @staticmethod
    def _source_object_id(session: Session, metadata: ObjectMetadata) -> str | None:
        return session.scalar(
            select(OriginalSourceObjectTable.id).where(
                OriginalSourceObjectTable.workspace_id == metadata.workspace_id,
                OriginalSourceObjectTable.object_key == metadata.object_key,
                OriginalSourceObjectTable.raw_sha256 == metadata.sha256,
                OriginalSourceObjectTable.byte_size == metadata.byte_size,
            )
        )

    @staticmethod
    def _configuration_from_job(
        session: Session, job: IngestionJobTable
    ) -> PdfSubmissionConfiguration:
        chunking = session.get(ChunkingConfigurationTable, job.chunking_configuration_id)
        embedding = session.get(EmbeddingConfigurationTable, job.embedding_configuration_id)
        if chunking is None or embedding is None:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        from knora.ingestion.processing import ChunkingConfiguration
        from knora.providers.embedding import EmbeddingConfiguration

        return PdfSubmissionConfiguration(
            parser_configuration_id=job.parser_configuration_id,
            normalizer_configuration_id=job.normalizer_configuration_id,
            chunking_configuration=ChunkingConfiguration(
                id=chunking.id,
                parser_version=chunking.parser_version,
                chunker_version=chunking.chunker_version,
                tokenizer_name=chunking.tokenizer_name,
                tokenizer_version=chunking.tokenizer_version,
                target_tokens=chunking.target_tokens,
                overlap_tokens=chunking.overlap_tokens,
                max_tokens=chunking.max_tokens,
            ),
            embedding_configuration=EmbeddingConfiguration(
                id=embedding.id,
                provider=embedding.provider,
                model=embedding.model,
                dimensions=embedding.dimensions,
                distance_metric=embedding.distance_metric,
            ),
        )

    @classmethod
    def _current_configuration_for_document(
        cls, *, session: Session, document: DocumentTable, document_version_id: str
    ) -> PdfSubmissionConfiguration:
        active_set = None
        if document.active_embedding_set_id is not None:
            active_set = session.get(EmbeddingSetTable, document.active_embedding_set_id)
        if active_set is None:
            job = session.scalar(
                select(IngestionJobTable)
                .where(
                    IngestionJobTable.document_id == document.id,
                    IngestionJobTable.target_document_version_id == document_version_id,
                    IngestionJobTable.status == "succeeded",
                )
                .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
                .limit(1)
            )
            if job is None:
                raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
            return cls._configuration_from_job(session, job)
        chunk_set = session.get(ChunkSetTable, active_set.chunk_set_id)
        if chunk_set is None or chunk_set.document_version_id != document_version_id:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        embedding = session.get(EmbeddingConfigurationTable, active_set.embedding_configuration_id)
        if embedding is None:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        job = session.scalar(
            select(IngestionJobTable)
            .where(
                IngestionJobTable.document_id == document.id,
                IngestionJobTable.target_document_version_id == document_version_id,
                IngestionJobTable.parser_configuration_id
                == chunk_set.parser_configuration_id,
                IngestionJobTable.normalizer_configuration_id
                == chunk_set.normalizer_configuration_id,
                IngestionJobTable.chunking_configuration_id == chunk_set.chunking_configuration_id,
                IngestionJobTable.embedding_configuration_id == embedding.id,
            )
            .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
            .limit(1)
        )
        if job is not None:
            return cls._configuration_from_job(session, job)
        chunking = session.get(ChunkingConfigurationTable, chunk_set.chunking_configuration_id)
        if chunking is None or chunk_set.parser_configuration_id is None:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        from knora.ingestion.processing import ChunkingConfiguration
        from knora.providers.embedding import EmbeddingConfiguration

        return PdfSubmissionConfiguration(
            parser_configuration_id=chunk_set.parser_configuration_id,
            normalizer_configuration_id=chunk_set.normalizer_configuration_id or "",
            chunking_configuration=ChunkingConfiguration(
                id=chunking.id,
                parser_version=chunking.parser_version,
                chunker_version=chunking.chunker_version,
                tokenizer_name=chunking.tokenizer_name,
                tokenizer_version=chunking.tokenizer_version,
                target_tokens=chunking.target_tokens,
                overlap_tokens=chunking.overlap_tokens,
                max_tokens=chunking.max_tokens,
            ),
            embedding_configuration=EmbeddingConfiguration(
                id=embedding.id,
                provider=embedding.provider,
                model=embedding.model,
                dimensions=embedding.dimensions,
                distance_metric=embedding.distance_metric,
            ),
        )

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
                    select(
                        func.coalesce(func.max(DocumentVersionTable.version_number), 0) + 1
                    ).where(DocumentVersionTable.document_id == document.id)
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
                database_now = self._database_now(session)
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
                    created_at=database_now,
                    updated_at=database_now,
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
