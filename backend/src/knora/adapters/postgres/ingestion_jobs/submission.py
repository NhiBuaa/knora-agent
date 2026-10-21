"""Private PostgreSQL persistence for PDF submission and read projections."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.embedding_configuration import configuration_from_row
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkingConfigurationTable,
    ChunkSetTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IdempotencyRecordTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    OriginalSourceObjectTable,
    ReprocessAuditTable,
    WorkspaceAdmissionTable,
    WorkspaceTable,
)
from knora.answering.stores import RetrievalConfiguration
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import (
    JobStatusProjection,
    PdfExtractionSubmissionConfiguration,
    PdfSubmissionConfiguration,
    PdfSubmissionResult,
    PdfSubmissionStore,
    PreparedPdfSubmission,
    PreparedReprocess,
    ReprocessAuditProjection,
    ReprocessContext,
    ReprocessResult,
)
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.search_indexing import LexicalProfile

_PUBLIC_FAILURE_REASONS = frozenset(
    {"retry_exhausted", "terminal_input", "terminal_config", "resource_limit"}
)
_SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class PostgresPdfSubmissionStore(PdfSubmissionStore):
    def __init__(
        self,
        session_factory: sessionmaker,
        database_now: Callable[[Session], datetime],
        retrieval_configuration: RetrievalConfiguration | None = None,
        lexical_population: VerifiedLexicalPopulation | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._database_now = database_now
        self._retrieval_configuration = retrieval_configuration
        self._lexical_population = lexical_population
        self._document_reader = PostgresDocumentReader(
            session_factory,
            deployed_retrieval_configuration=retrieval_configuration,
            lexical_population=lexical_population,
        )

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
            lexical = (
                self._retrieval_configuration is not None
                and self._retrieval_configuration.strategy == "bm25-only"
            )
            if lexical:
                self._document_reader._begin_snapshot(session)
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
            projection = self._document_reader._projection(session, document) if lexical else None
            indexing_job = (
                session.scalar(
                    select(IngestionJobTable).where(
                        IngestionJobTable.parent_ingestion_job_id == job.id,
                        IngestionJobTable.workspace_id == workspace_id,
                        IngestionJobTable.document_id == document.id,
                        IngestionJobTable.derivation_kind == "lexical_index",
                    )
                )
                if job.derivation_kind == "pdf_extraction"
                else job
                if job.derivation_kind == "lexical_index"
                else None
            )
            lexical_head = session.get(LexicalHeadTable, document.id) if lexical else None
            failure_reason = (
                job.failure_reason if job.failure_reason in _PUBLIC_FAILURE_REASONS else None
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
                served_document_version_id=(
                    projection.served_document_version_id if projection else served_id
                ),
                serving_state=projection.serving_state if projection else serving_state,
                derivation_kind=job.derivation_kind,
                indexing_job_id=indexing_job.id if indexing_job else None,
                indexing_status=indexing_job.status if indexing_job else None,
                lexical_readiness=projection.lexical_readiness if projection else "not_indexed",
                desired_lexical_generation_id=(
                    projection.desired_lexical_generation_id if projection else None
                ),
                lexical_revision=lexical_head.revision if lexical_head else None,
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

    def commit_reprocess(
        self, prepared: PreparedReprocess, *, admission_id: str | None = None
    ) -> ReprocessResult:
        for attempt in range(2):
            try:
                return self._commit_reprocess_once(prepared, admission_id=admission_id)
            except KnoraError:
                raise
            except IntegrityError:
                if attempt == 0:
                    continue
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
            except SQLAlchemyError:
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
        raise AssertionError("unreachable")

    def _commit_reprocess_once(
        self, prepared: PreparedReprocess, *, admission_id: str | None = None
    ) -> ReprocessResult:
        with self._session_factory.begin() as session:
            workspace = session.scalar(
                select(WorkspaceTable)
                .where(WorkspaceTable.id == prepared.workspace_id)
                .with_for_update()
            )
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
            if workspace is None or document is None or version is None:
                raise KnoraError("DOCUMENT_VERSION_NOT_FOUND")
            if document.current_document_version_id != version.id:
                raise KnoraError("DOCUMENT_VERSION_NOT_CURRENT")
            source_object = session.scalar(
                select(OriginalSourceObjectTable).where(
                    OriginalSourceObjectTable.id
                    == self._source_object_id(session, prepared.source_object),
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
            lexical = isinstance(config, PdfExtractionSubmissionConfiguration)
            content_fingerprint = (
                self._lexical_job_fingerprint(
                    prepared.request_fingerprint,
                    config,
                    source_revision=document.revision,
                    workspace_revision=workspace.revision,
                )
                if lexical
                else prepared.request_fingerprint
            )
            job_query = (
                select(IngestionJobTable)
                .where(
                    IngestionJobTable.workspace_id == prepared.workspace_id,
                    IngestionJobTable.target_document_version_id == prepared.document_version_id,
                    IngestionJobTable.parser_configuration_id == config.parser_configuration_id,
                    IngestionJobTable.normalizer_configuration_id
                    == config.normalizer_configuration_id,
                    IngestionJobTable.chunking_configuration_id == config.chunking_configuration.id,
                    IngestionJobTable.derivation_kind == ("pdf_extraction" if lexical else "dense"),
                    IngestionJobTable.status.in_(
                        ("queued", "processing", "retry_scheduled", "succeeded")
                        if lexical
                        else ("processing", "succeeded")
                    ),
                )
                .order_by(IngestionJobTable.created_at, IngestionJobTable.id)
                .limit(1)
            )
            if lexical:
                job_query = job_query.where(
                    IngestionJobTable.lexical_profile["id"].as_string()
                    == config.lexical_profile.id,
                    IngestionJobTable.lexical_profile["digest"].as_string()
                    == config.lexical_profile.digest(),
                    IngestionJobTable.source_revision == document.revision,
                    IngestionJobTable.workspace_revision == workspace.revision,
                )
            else:
                job_query = job_query.where(
                    IngestionJobTable.embedding_configuration_id
                    == config.embedding_configuration.id
                )
            rollback_revision = self._reserve_lexical_rollback(
                session, prepared, workspace, document, source_object
            )
            if rollback_revision is not None:
                job = None
            elif lexical:
                head = session.get(LexicalHeadTable, document.id)
                job = session.scalar(
                    job_query.where(
                        IngestionJobTable.status.in_(("queued", "processing", "retry_scheduled")),
                        or_(
                            IngestionJobTable.lexical_head_revision.is_(None),
                            IngestionJobTable.lexical_head_revision
                            == (head.revision if head else None),
                        ),
                    )
                )
                if job is None and head is not None and head.desired_generation_id is not None:
                    generation = session.get(LexicalGenerationTable, head.desired_generation_id)
                    child = session.scalar(
                        select(IngestionJobTable).where(
                            IngestionJobTable.workspace_id == document.workspace_id,
                            IngestionJobTable.derivation_kind == "lexical_index",
                            IngestionJobTable.lexical_generation_id == head.desired_generation_id,
                            IngestionJobTable.status.in_(
                                ("queued", "processing", "retry_scheduled", "succeeded")
                            ),
                        )
                    )
                    if (
                        generation is not None
                        and generation.status in {"requested", "active"}
                        and generation.revision == head.revision
                        and generation.workspace_id == document.workspace_id
                        and generation.document_id == document.id
                        and generation.document_version_id == prepared.document_version_id
                        and generation.source_revision == document.revision
                        and generation.workspace_revision == workspace.revision
                        and generation.profile_digest == config.lexical_profile.digest()
                        and child is not None
                    ):
                        job = session.scalar(
                            job_query.where(
                                IngestionJobTable.id == child.parent_ingestion_job_id,
                                IngestionJobTable.status == "succeeded",
                            )
                        )
            else:
                job = session.scalar(job_query)
            outcome = "reused"
            database_now = self._database_now(session)
            if job is None:
                job_id = str(uuid4())
                if lexical:
                    content_fingerprint += "\nlexical-reprocess-job-v1\n" + job_id
                job = IngestionJobTable(
                    id=job_id,
                    workspace_id=prepared.workspace_id,
                    operation=prepared.idempotency_operation,
                    document_id=prepared.document_id,
                    target_document_version_id=prepared.document_version_id,
                    source_object_id=source_object.id,
                    content_fingerprint=content_fingerprint,
                    parser_configuration_id=config.parser_configuration_id,
                    normalizer_configuration_id=config.normalizer_configuration_id,
                    chunking_configuration_id=config.chunking_configuration.id,
                    derivation_kind="pdf_extraction" if lexical else "dense",
                    embedding_configuration_id=(
                        None if lexical else config.embedding_configuration.id
                    ),
                    lexical_profile=(
                        {
                            **asdict(config.lexical_profile),
                            "digest": config.lexical_profile.digest(),
                        }
                        if lexical
                        else None
                    ),
                    source_revision=document.revision if lexical else None,
                    workspace_revision=workspace.revision if lexical else None,
                    status="queued",
                    attempt_count=0,
                    max_attempts=4,
                    created_at=database_now,
                    updated_at=database_now,
                    reprocess_of_job_id=(prepared.config_source_job_id or prepared.prior_job_id),
                    lexical_head_revision=rollback_revision,
                )
                session.add(job)
                session.flush()
                outcome = "created"

            if admission_id is not None:
                admission = session.scalar(
                    select(WorkspaceAdmissionTable)
                    .where(
                        WorkspaceAdmissionTable.id == admission_id,
                        WorkspaceAdmissionTable.workspace_id == prepared.workspace_id,
                        WorkspaceAdmissionTable.operation == prepared.idempotency_operation,
                        WorkspaceAdmissionTable.operation_id == prepared.idempotency_key,
                    )
                    .with_for_update()
                )
                if admission is None:
                    raise KnoraError("PERSISTENCE_OPERATION_FAILED")
                admission.ingestion_job_id = job.id
                if job.status in {"succeeded", "superseded", "failed"}:
                    admission.terminal_at = func.now()

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

    def _reserve_lexical_rollback(
        self,
        session: Session,
        prepared: PreparedReprocess,
        workspace: WorkspaceTable,
        document: DocumentTable,
        source: OriginalSourceObjectTable,
    ) -> int | None:
        expected = prepared.expected_lexical_revision
        if expected is None:
            return None
        config = prepared.configuration
        if (
            type(expected) is not int
            or expected < 0
            or prepared.requested_config_mode != "same_as_job"
            or prepared.resolved_config_mode != "same_as_job"
            or not isinstance(config, PdfExtractionSubmissionConfiguration)
            or self._retrieval_configuration is None
            or self._retrieval_configuration.strategy != "bm25-only"
            or self._lexical_population is None
            or self._lexical_population.profile != config.lexical_profile
            or workspace.archived
            or document.archived
            or source.deleted_at is not None
        ):
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        head = session.scalar(
            select(LexicalHeadTable)
            .where(LexicalHeadTable.document_id == document.id)
            .with_for_update()
        )
        if head is None or head.revision != expected:
            raise KnoraError("REVISION_CONFLICT")
        parent = session.get(IngestionJobTable, prepared.config_source_job_id)
        child = session.scalar(
            select(IngestionJobTable).where(
                IngestionJobTable.parent_ingestion_job_id == prepared.config_source_job_id,
                IngestionJobTable.derivation_kind == "lexical_index",
                IngestionJobTable.status == "succeeded",
            )
        )
        row = session.get(LexicalGenerationTable, child.lexical_generation_id) if child else None
        if (
            parent is None
            or parent.derivation_kind != "pdf_extraction"
            or parent.status != "succeeded"
            or parent.workspace_id != workspace.id
            or parent.document_id != document.id
            or parent.target_document_version_id != prepared.document_version_id
            or parent.source_object_id != source.id
            or parent.source_revision != document.revision
            or parent.workspace_revision != workspace.revision
            or row is None
            or row.status != "active"
            or row.workspace_id != workspace.id
            or row.document_id != document.id
            or row.document_version_id != prepared.document_version_id
            or row.source_revision != document.revision
            or row.workspace_revision != workspace.revision
            or row.acknowledged_count != row.expected_count
        ):
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        try:
            generation = PostgresSearchIndexStore._decode_generation(row)
            if (
                generation.lexical_profile != config.lexical_profile
                or self._configuration_from_job(session, parent) != config
            ):
                raise ValueError("rollback profile is no longer available")
        except (TypeError, ValueError, OverflowError) as error:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE") from error
        chunk_set = session.get(ChunkSetTable, generation.chunk_set_id)
        if (
            chunk_set is None
            or chunk_set.document_version_id != prepared.document_version_id
            or chunk_set.status != "completed"
            or chunk_set.parser_configuration_id != config.parser_configuration_id
            or chunk_set.normalizer_configuration_id != config.normalizer_configuration_id
            or chunk_set.chunking_configuration_id != config.chunking_configuration.id
        ):
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        # Reserve a new request revision now, so B cannot activate during extraction.
        head.revision += 1
        head.desired_generation_id = None
        session.flush()
        return head.revision

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
    ) -> PdfSubmissionConfiguration | PdfExtractionSubmissionConfiguration:
        chunking = session.get(ChunkingConfigurationTable, job.chunking_configuration_id)
        if chunking is None:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        from knora.ingestion.processing import ChunkingConfiguration

        chunking_configuration = ChunkingConfiguration(
            id=chunking.id,
            parser_version=chunking.parser_version,
            chunker_version=chunking.chunker_version,
            tokenizer_name=chunking.tokenizer_name,
            tokenizer_version=chunking.tokenizer_version,
            target_tokens=chunking.target_tokens,
            overlap_tokens=chunking.overlap_tokens,
            max_tokens=chunking.max_tokens,
        )
        if job.derivation_kind == "pdf_extraction":
            if not isinstance(job.lexical_profile, dict):
                raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
            try:
                profile_payload = dict(job.lexical_profile)
                persisted_digest = profile_payload.pop("digest", None)
                profile = LexicalProfile(**profile_payload)
            except (TypeError, ValueError, OverflowError) as error:
                raise KnoraError("CONFIGURATION_NOT_AVAILABLE") from error
            if persisted_digest != profile.digest():
                raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
            return PdfExtractionSubmissionConfiguration(
                parser_configuration_id=job.parser_configuration_id,
                normalizer_configuration_id=job.normalizer_configuration_id,
                chunking_configuration=chunking_configuration,
                lexical_profile=profile,
            )
        if job.derivation_kind != "dense":
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        embedding = session.get(EmbeddingConfigurationTable, job.embedding_configuration_id)
        if embedding is None:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        return PdfSubmissionConfiguration(
            parser_configuration_id=job.parser_configuration_id,
            normalizer_configuration_id=job.normalizer_configuration_id,
            chunking_configuration=chunking_configuration,
            embedding_configuration=configuration_from_row(embedding),
        )

    def _current_configuration_for_document(
        self, *, session: Session, document: DocumentTable, document_version_id: str
    ) -> PdfSubmissionConfiguration | PdfExtractionSubmissionConfiguration:
        if (
            self._retrieval_configuration is not None
            and self._retrieval_configuration.strategy == "bm25-only"
        ):
            return self._current_lexical_configuration(
                session=session, document=document, document_version_id=document_version_id
            )
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
                    IngestionJobTable.derivation_kind == "dense",
                )
                .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
                .limit(1)
            )
            if job is None:
                raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
            return self._configuration_from_job(session, job)
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
                IngestionJobTable.parser_configuration_id == chunk_set.parser_configuration_id,
                IngestionJobTable.normalizer_configuration_id
                == chunk_set.normalizer_configuration_id,
                IngestionJobTable.chunking_configuration_id == chunk_set.chunking_configuration_id,
                IngestionJobTable.embedding_configuration_id == embedding.id,
                IngestionJobTable.derivation_kind == "dense",
            )
            .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
            .limit(1)
        )
        if job is not None:
            return self._configuration_from_job(session, job)
        chunking = session.get(ChunkingConfigurationTable, chunk_set.chunking_configuration_id)
        if chunking is None or chunk_set.parser_configuration_id is None:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        from knora.ingestion.processing import ChunkingConfiguration

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
            embedding_configuration=configuration_from_row(embedding),
        )

    def _current_lexical_configuration(
        self, *, session: Session, document: DocumentTable, document_version_id: str
    ) -> PdfExtractionSubmissionConfiguration:
        workspace = session.get(WorkspaceTable, document.workspace_id)
        head = session.get(LexicalHeadTable, document.id)
        desired = (
            session.get(LexicalGenerationTable, head.desired_generation_id)
            if head is not None and head.desired_generation_id is not None
            else None
        )
        if (
            workspace is None
            or workspace.archived
            or document.archived
            or document.current_document_version_id != document_version_id
            or desired is None
            or desired.status not in {"requested", "active"}
            or desired.workspace_id != document.workspace_id
            or desired.document_id != document.id
            or desired.document_version_id != document_version_id
            or desired.revision != head.revision
            or desired.source_revision != document.revision
            or desired.workspace_revision != workspace.revision
        ):
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        try:
            generation = PostgresSearchIndexStore._decode_generation(desired)
        except (TypeError, ValueError, OverflowError) as error:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE") from error
        chunk_set = session.get(ChunkSetTable, generation.chunk_set_id)
        if (
            chunk_set is None
            or chunk_set.document_version_id != document_version_id
            or chunk_set.status != "completed"
        ):
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        job = session.scalar(
            select(IngestionJobTable)
            .where(
                IngestionJobTable.workspace_id == document.workspace_id,
                IngestionJobTable.document_id == document.id,
                IngestionJobTable.target_document_version_id == document_version_id,
                IngestionJobTable.derivation_kind == "pdf_extraction",
                IngestionJobTable.status == "succeeded",
                IngestionJobTable.parser_configuration_id == chunk_set.parser_configuration_id,
                IngestionJobTable.normalizer_configuration_id
                == chunk_set.normalizer_configuration_id,
                IngestionJobTable.chunking_configuration_id == chunk_set.chunking_configuration_id,
                IngestionJobTable.lexical_profile["digest"].as_string() == desired.profile_digest,
            )
            .order_by(IngestionJobTable.created_at.desc(), IngestionJobTable.id.desc())
            .limit(1)
        )
        if job is None:
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        configuration = self._configuration_from_job(session, job)
        if (
            not isinstance(configuration, PdfExtractionSubmissionConfiguration)
            or configuration.lexical_profile != generation.lexical_profile
        ):
            raise KnoraError("CONFIGURATION_NOT_AVAILABLE")
        return configuration

    def commit_pdf_submission(
        self,
        prepared: PreparedPdfSubmission,
        *,
        admission_id: str | None = None,
    ) -> PdfSubmissionResult:
        for attempt in range(2):
            try:
                return self._commit_pdf_submission(prepared, admission_id=admission_id)
            except KnoraError:
                raise
            except IntegrityError:
                if attempt == 0:
                    continue
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
            except SQLAlchemyError:
                raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
        raise AssertionError("unreachable")

    def read_pdf_submission_replay(
        self, *, workspace_id: str, idempotency_key: str, content_fingerprint: str
    ) -> PdfSubmissionResult | None:
        with self._session_factory() as session:
            replay = session.scalar(
                select(IdempotencyRecordTable).where(
                    IdempotencyRecordTable.workspace_id == workspace_id,
                    IdempotencyRecordTable.operation == "submit_pdf",
                    IdempotencyRecordTable.key == idempotency_key,
                )
            )
            if replay is None or replay.expires_at <= datetime.now(UTC):
                return None
            if replay.request_fingerprint != content_fingerprint:
                raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
            job = session.scalar(
                select(IngestionJobTable).where(
                    IngestionJobTable.id == replay.ingestion_job_id,
                    IngestionJobTable.workspace_id == workspace_id,
                )
            )
            if job is None:
                raise KnoraError("PERSISTENCE_OPERATION_FAILED")
            return self._result(session, job, submission_outcome="idempotency_replay")

    def _commit_pdf_submission(
        self,
        prepared: PreparedPdfSubmission,
        *,
        admission_id: str | None = None,
    ) -> PdfSubmissionResult:
        with self._session_factory.begin() as session:
            workspace = session.scalar(
                select(WorkspaceTable)
                .where(WorkspaceTable.id == prepared.workspace_id)
                .with_for_update()
            )
            if workspace is None:
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
            config = prepared.configuration
            lexical = isinstance(config, PdfExtractionSubmissionConfiguration)
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
            content_fingerprint = (
                self._lexical_job_fingerprint(
                    prepared.content_fingerprint,
                    config,
                    source_revision=document.revision,
                    workspace_revision=workspace.revision,
                )
                if lexical
                else prepared.content_fingerprint
            )
            job_query = select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == prepared.workspace_id,
                IngestionJobTable.operation == prepared.idempotency_operation,
                IngestionJobTable.content_fingerprint == content_fingerprint,
            )
            if lexical:
                job_query = job_query.where(
                    IngestionJobTable.derivation_kind == "pdf_extraction",
                    IngestionJobTable.lexical_profile["digest"].as_string()
                    == config.lexical_profile.digest(),
                    IngestionJobTable.source_revision == document.revision,
                    IngestionJobTable.workspace_revision == workspace.revision,
                )
            job = session.scalar(job_query)
            submission_outcome = "deduplicated"
            if job is None:
                database_now = self._database_now(session)
                job = IngestionJobTable(
                    id=str(uuid4()),
                    workspace_id=prepared.workspace_id,
                    operation=prepared.idempotency_operation,
                    document_id=document.id,
                    target_document_version_id=version.id,
                    source_object_id=source_object.id,
                    content_fingerprint=content_fingerprint,
                    parser_configuration_id=config.parser_configuration_id,
                    normalizer_configuration_id=config.normalizer_configuration_id,
                    chunking_configuration_id=config.chunking_configuration.id,
                    derivation_kind="pdf_extraction" if lexical else "dense",
                    embedding_configuration_id=(
                        None if lexical else config.embedding_configuration.id
                    ),
                    lexical_profile=(
                        {
                            **asdict(config.lexical_profile),
                            "digest": config.lexical_profile.digest(),
                        }
                        if lexical
                        else None
                    ),
                    source_revision=document.revision if lexical else None,
                    workspace_revision=workspace.revision if lexical else None,
                    status="queued",
                    attempt_count=0,
                    max_attempts=4,
                    created_at=database_now,
                    updated_at=database_now,
                )
                session.add(job)
                session.flush()
                submission_outcome = "created"

            if admission_id is not None:
                admission = session.scalar(
                    select(WorkspaceAdmissionTable)
                    .where(
                        WorkspaceAdmissionTable.id == admission_id,
                        WorkspaceAdmissionTable.workspace_id == prepared.workspace_id,
                        WorkspaceAdmissionTable.operation == prepared.idempotency_operation,
                        WorkspaceAdmissionTable.operation_id == prepared.idempotency_key,
                    )
                    .with_for_update()
                )
                if admission is None:
                    raise KnoraError("PERSISTENCE_OPERATION_FAILED")
                admission.ingestion_job_id = job.id
                if job.status in {"succeeded", "superseded", "failed"}:
                    admission.terminal_at = func.now()

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
    def _lexical_job_fingerprint(
        request_fingerprint: str,
        configuration: PdfExtractionSubmissionConfiguration,
        *,
        source_revision: int,
        workspace_revision: int,
    ) -> str:
        # Job uniqueness follows the enqueue snapshot; idempotency retains the original request.
        return "\n".join(
            (
                request_fingerprint,
                "lexical-job-snapshot-v1",
                configuration.lexical_profile.digest(),
                str(source_revision),
                str(workspace_revision),
            )
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
        if isinstance(prepared.configuration, PdfExtractionSubmissionConfiguration):
            return
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
