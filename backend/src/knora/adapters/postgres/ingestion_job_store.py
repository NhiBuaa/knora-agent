"""PostgreSQL adapter for durable Ingestion Job submission."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import TypeVar
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkingConfigurationTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IdempotencyRecordTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    ReprocessAuditTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.job_processing import (
    AttemptRef,
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimLeaseLost,
    ClaimOperationId,
    ClaimResult,
    CoordinationInvariantError,
    CoordinationOutcomeIndeterminate,
    ExpiredAttemptObservation,
    FailTerminal,
    FailureCauseV1,
    Fenced,
    FencingToken,
    FinalizationApplied,
    FinalizationResult,
    HeartbeatApplied,
    HeartbeatOperationId,
    HeartbeatResult,
    IngestionWork,
    InvalidTransition,
    NoEligibleClaim,
    NotExpired,
    PdfDerivationSuccess,
    RecoveryFailedExhausted,
    RecoveryResult,
    RecoveryRetryScheduled,
    RetryExhausted,
    RetryScheduleApplied,
    RetryScheduleResult,
    ScheduleRetry,
    StaleObservation,
    TransitionOperationId,
    WorkSuperseded,
)
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

MutationResultT = TypeVar("MutationResultT")
_PUBLIC_FAILURE_REASONS = frozenset(
    {"retry_exhausted", "terminal_input", "terminal_config", "resource_limit"}
)
_SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _duration_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


class _FinalizationFenceLost(RuntimeError):
    """Roll back tentative PDF derivation state when the final lease guard fails."""


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

    def pdf_profile_for_work(self, work):
        """Resolve the worker's immutable profile from the claimed Job configuration IDs."""

        from knora.ingestion.job_processing import PdfDerivationProfile
        from knora.ingestion.pdf import PdfExtractionConfiguration
        from knora.providers.embedding import EmbeddingConfiguration

        with self._session_factory() as session:
            chunking = session.get(ChunkingConfigurationTable, work.chunking_configuration_id)
            embedding = session.get(
                EmbeddingConfigurationTable, work.embedding_configuration_id
            )
            if chunking is None or embedding is None:
                raise CoordinationInvariantError("claimed Job references missing configuration")
            return PdfDerivationProfile(
                parser_configuration_id=work.parser_configuration_id,
                normalizer_configuration_id=work.normalizer_configuration_id,
                chunking_configuration_id=work.chunking_configuration_id,
                extraction_configuration=PdfExtractionConfiguration.milestone_two(),
                embedding_configuration=EmbeddingConfiguration(
                    id=embedding.id,
                    provider=embedding.provider,
                    model=embedding.model,
                    dimensions=embedding.dimensions,
                    distance_metric=embedding.distance_metric,
                ),
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

    def observe_expired_attempt(self) -> ExpiredAttemptObservation | None:
        """Return one unlocked, database-time observation of an ownerless attempt."""

        with self._session_factory() as session:
            database_now = self._database_now(session)
            row = session.execute(
                select(IngestionJobTable, IngestionJobAttemptTable)
                .join(
                    IngestionJobAttemptTable,
                    IngestionJobAttemptTable.ingestion_job_id == IngestionJobTable.id,
                )
                .where(
                    IngestionJobTable.status == "processing",
                    IngestionJobTable.lease_expires_at.is_not(None),
                    IngestionJobTable.lease_expires_at <= database_now,
                    IngestionJobAttemptTable.closed_at.is_(None),
                    IngestionJobAttemptTable.attempt_number
                    == IngestionJobTable.current_attempt_number,
                )
                .order_by(IngestionJobTable.lease_expires_at, IngestionJobTable.id)
                .limit(1)
            ).first()
            if row is None:
                return None
            job, attempt = row
            if job.lease_expires_at is None:
                raise CoordinationInvariantError("expired processing job had no lease expiry")
            return ExpiredAttemptObservation(
                job_id=job.id,
                attempt_number=attempt.attempt_number,
                worker_id=job.worker_id,
                lease_version=job.lease_version,
                attempt_count=job.attempt_count,
                max_attempts=job.max_attempts,
                lease_expires_at=job.lease_expires_at,
            )

    def apply_expired_recovery(
        self,
        *,
        operation_id: TransitionOperationId,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry | RetryExhausted,
    ) -> RecoveryResult:
        self._validate_expired_recovery_input(
            observation=observation,
            failure=failure,
            decision=decision,
        )
        disposition = "retry_scheduled" if isinstance(decision, ScheduleRetry) else "failed"
        transition_fingerprint = self._expired_recovery_fingerprint(
            observation=observation,
            failure=failure,
            disposition=disposition,
            decision=decision,
        )
        replay = self._read_expired_recovery_replay(
            operation_id=str(operation_id),
            request_fingerprint=transition_fingerprint,
            operation_kind="expired_recovery",
        )
        if replay is not None:
            return replay
        return self._reconcile_database_error(
            operation_kind="expired_recovery",
            operation_id=str(operation_id),
            job_id=observation.job_id,
            attempt_number=observation.attempt_number,
            apply=lambda: self._apply_expired_recovery_once(
                operation_id=operation_id,
                observation=observation,
                failure=failure,
                decision=decision,
            ),
            read_back=lambda: self._read_expired_recovery_replay(
                operation_id=str(operation_id),
                request_fingerprint=transition_fingerprint,
                operation_kind="expired_recovery",
            ),
        )

    def _apply_expired_recovery_once(
        self,
        *,
        operation_id: TransitionOperationId,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry | RetryExhausted,
    ) -> RecoveryResult:
        """Conditionally close an observed expired attempt without claiming its replacement."""

        self._validate_expired_recovery_input(
            observation=observation,
            failure=failure,
            decision=decision,
        )
        disposition = "retry_scheduled" if isinstance(decision, ScheduleRetry) else "failed"
        transition_fingerprint = self._expired_recovery_fingerprint(
            observation=observation,
            failure=failure,
            disposition=disposition,
            decision=decision,
        )
        with self._session_factory.begin() as session:
            job = session.scalar(
                select(IngestionJobTable)
                .where(IngestionJobTable.id == observation.job_id)
                .with_for_update()
            )
            if job is None:
                return StaleObservation()
            attempt = session.scalar(
                select(IngestionJobAttemptTable)
                .where(
                    IngestionJobAttemptTable.ingestion_job_id == observation.job_id,
                    IngestionJobAttemptTable.attempt_number == observation.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None:
                return StaleObservation()

            database_now = self._database_now(session)
            if not self._matches_expired_observation(job, attempt, observation):
                return StaleObservation()
            if database_now < observation.lease_expires_at:
                return NotExpired()

            transition_operation_id = str(operation_id)
            self._assert_new_transition_operation(
                session=session,
                operation_id=transition_operation_id,
                request_fingerprint=transition_fingerprint,
                operation_kind="expired_recovery",
            )

            attempt.closed_at = database_now
            attempt.disposition = disposition
            attempt.closure_cause = FailureCauseV1.LEASE_EXPIRED.value
            attempt.failure_cause = failure.cause.value
            attempt.failure_cause_version = failure.cause_version
            attempt.cause_mapping_version = failure.mapping_version
            attempt.safe_failure_code = failure.safe_code
            attempt.transition_operation_id = transition_operation_id
            attempt.transition_operation_kind = "expired_recovery"
            attempt.transition_request_fingerprint = transition_fingerprint
            attempt.retry_policy_version = decision.policy_version

            job.worker_id = None
            job.lease_expires_at = None
            job.current_attempt_number = None
            job.current_attempt_started_at = None
            job.current_attempt_deadline_at = None

            if isinstance(decision, ScheduleRetry):
                next_attempt_at = database_now + timedelta(microseconds=decision.delay_microseconds)
                attempt.retry_policy_result = "schedule_retry"
                attempt.retry_jitter_version = decision.jitter_version
                attempt.retry_window_upper_bound_microseconds = (
                    decision.window_upper_bound_microseconds
                )
                attempt.retry_delay_microseconds = decision.delay_microseconds
                attempt.retry_next_attempt_at = next_attempt_at
                job.status = "retry_scheduled"
                job.next_attempt_at = next_attempt_at
                job.updated_at = database_now
                job.terminal_at = None
                job.failure_reason = None
                job.safe_failure_code = None
                session.flush()
                return RecoveryRetryScheduled(
                    attempt=AttemptRef(job_id=job.id, attempt_number=attempt.attempt_number),
                    next_attempt_at=next_attempt_at,
                )

            attempt.failure_reason = "retry_exhausted"
            attempt.retry_policy_result = "retry_exhausted"
            job.status = "failed"
            job.next_attempt_at = None
            job.terminal_at = database_now
            job.updated_at = database_now
            job.failure_reason = "retry_exhausted"
            job.safe_failure_code = failure.safe_code
            session.flush()
            return RecoveryFailedExhausted(
                attempt=AttemptRef(job_id=job.id, attempt_number=attempt.attempt_number)
            )

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimResult:
        claim_fingerprint = self._claim_fingerprint(worker_id=worker_id, timing=timing)
        return self._reconcile_database_error(
            operation_kind="claim",
            operation_id=str(operation_id),
            job_id=None,
            attempt_number=None,
            apply=lambda: self._claim_next_attempt_once(
                operation_id=operation_id,
                worker_id=worker_id,
                timing=timing,
            ),
            read_back=lambda: self._read_claim_replay(
                operation_id=str(operation_id), request_fingerprint=claim_fingerprint
            ),
        )

    def _claim_next_attempt_once(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimResult:
        """Atomically claim at most one queued or due-retry job and insert one attempt."""

        claim_operation_id = str(operation_id)
        claim_fingerprint = self._claim_fingerprint(worker_id=worker_id, timing=timing)
        with self._session_factory.begin() as session:
            existing = session.scalar(
                select(IngestionJobAttemptTable).where(
                    IngestionJobAttemptTable.claim_operation_id == claim_operation_id
                )
            )
            if existing is not None:
                if existing.claim_request_fingerprint != claim_fingerprint:
                    raise CoordinationInvariantError("claim operation ID was reused incompatibly")
                job = session.scalar(
                    select(IngestionJobTable)
                    .where(IngestionJobTable.id == existing.ingestion_job_id)
                    .with_for_update()
                )
                if job is None:
                    raise CoordinationInvariantError("claim operation refers to a missing job")
                database_now = self._database_now(session)
                if not self._owns_current_unexpired_token(
                    job,
                    self._token(
                        job_id=existing.ingestion_job_id,
                        attempt_number=existing.attempt_number,
                        worker_id=existing.worker_id,
                        lease_version=existing.lease_version,
                    ),
                    database_now,
                ):
                    return ClaimLeaseLost(
                        attempt=AttemptRef(
                            job_id=existing.ingestion_job_id,
                            attempt_number=existing.attempt_number,
                        )
                    )
                source_object = session.get(OriginalSourceObjectTable, job.source_object_id)
                if source_object is None:
                    raise CoordinationInvariantError("claimed job has no Original Source Object")
                return ClaimedAttempt(
                    token=self._token(
                        job_id=job.id,
                        attempt_number=existing.attempt_number,
                        worker_id=existing.worker_id,
                        lease_version=existing.lease_version,
                    ),
                    work=IngestionWork(
                        workspace_id=job.workspace_id,
                        document_id=job.document_id,
                        document_version_id=job.target_document_version_id,
                        source_object_id=source_object.id,
                        source_object_key=source_object.object_key,
                        source_media_type=source_object.media_type,
                        source_sha256=source_object.raw_sha256,
                        source_byte_size=source_object.byte_size,
                        parser_configuration_id=job.parser_configuration_id,
                        normalizer_configuration_id=job.normalizer_configuration_id,
                        chunking_configuration_id=job.chunking_configuration_id,
                        embedding_configuration_id=job.embedding_configuration_id,
                    ),
                    attempt_count=existing.attempt_number,
                    max_attempts=job.max_attempts,
                    attempt_started_at=existing.attempt_started_at,
                    initial_lease_expires_at=existing.initial_lease_expires_at,
                    deadline_at=existing.deadline_at,
                )

            job = session.scalar(
                select(IngestionJobTable)
                .where(
                    or_(
                        IngestionJobTable.status == "queued",
                        and_(
                            IngestionJobTable.status == "retry_scheduled",
                            IngestionJobTable.next_attempt_at <= func.clock_timestamp(),
                        ),
                    ),
                    IngestionJobTable.attempt_count < IngestionJobTable.max_attempts,
                )
                .order_by(
                    IngestionJobTable.next_attempt_at.nullsfirst(),
                    IngestionJobTable.created_at,
                    IngestionJobTable.id,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return NoEligibleClaim()

            database_now = self._database_now(session)
            if job.attempt_count >= job.max_attempts or not self._is_claim_eligible(
                job, database_now
            ):
                return NoEligibleClaim()

            attempt_number = job.attempt_count + 1
            lease_version = job.lease_version + 1
            lease_expires_at = database_now + timing.lease_duration
            deadline_at = database_now + timing.max_attempt_runtime
            source_object = session.get(OriginalSourceObjectTable, job.source_object_id)
            if source_object is None:
                raise CoordinationInvariantError("claimed job has no Original Source Object")

            job.status = "processing"
            job.attempt_count = attempt_number
            job.lease_version = lease_version
            if job.started_at is None:
                job.started_at = database_now
            job.updated_at = database_now
            job.worker_id = worker_id
            job.lease_expires_at = lease_expires_at
            job.current_attempt_number = attempt_number
            job.current_attempt_started_at = database_now
            job.current_attempt_deadline_at = deadline_at
            job.next_attempt_at = None
            job.last_heartbeat_operation_id = None
            job.last_heartbeat_request_fingerprint = None
            job.last_heartbeat_resulting_lease_expires_at = None
            session.add(
                IngestionJobAttemptTable(
                    ingestion_job_id=job.id,
                    attempt_number=attempt_number,
                    worker_id=worker_id,
                    lease_version=lease_version,
                    attempt_started_at=database_now,
                    deadline_at=deadline_at,
                    initial_lease_expires_at=lease_expires_at,
                    claim_operation_id=claim_operation_id,
                    claim_request_fingerprint=claim_fingerprint,
                )
            )
            session.flush()
            return ClaimedAttempt(
                token=self._token(
                    job_id=job.id,
                    attempt_number=attempt_number,
                    worker_id=worker_id,
                    lease_version=lease_version,
                ),
                work=IngestionWork(
                    workspace_id=job.workspace_id,
                    document_id=job.document_id,
                    document_version_id=job.target_document_version_id,
                    source_object_id=source_object.id,
                    source_object_key=source_object.object_key,
                    source_media_type=source_object.media_type,
                    source_sha256=source_object.raw_sha256,
                    source_byte_size=source_object.byte_size,
                    parser_configuration_id=job.parser_configuration_id,
                    normalizer_configuration_id=job.normalizer_configuration_id,
                    chunking_configuration_id=job.chunking_configuration_id,
                    embedding_configuration_id=job.embedding_configuration_id,
                ),
                attempt_count=attempt_number,
                max_attempts=job.max_attempts,
                attempt_started_at=database_now,
                initial_lease_expires_at=lease_expires_at,
                deadline_at=deadline_at,
            )

    def heartbeat(
        self,
        *,
        operation_id: HeartbeatOperationId,
        token: FencingToken,
        lease_duration: timedelta,
    ) -> HeartbeatResult:
        """Renew one owned lease, reconciling an ambiguous acknowledgement by operation ID."""

        for attempt in range(2):
            try:
                return self._heartbeat_once(
                    operation_id=operation_id,
                    token=token,
                    lease_duration=lease_duration,
                )
            except SQLAlchemyError:
                if attempt == 1:
                    raise CoordinationOutcomeIndeterminate(
                        operation_id=operation_id, token=token
                    ) from None
        raise AssertionError("unreachable")

    def _heartbeat_once(
        self,
        *,
        operation_id: HeartbeatOperationId,
        token: FencingToken,
        lease_duration: timedelta,
    ) -> HeartbeatResult:
        with self._session_factory.begin() as session:
            job = session.scalar(
                select(IngestionJobTable)
                .where(IngestionJobTable.id == token.job_id)
                .with_for_update()
            )
            if job is None:
                return Fenced()
            database_now = self._database_now(session)
            request_fingerprint = self._heartbeat_fingerprint(token, lease_duration)
            if job.last_heartbeat_operation_id == str(operation_id):
                if job.last_heartbeat_request_fingerprint != request_fingerprint:
                    raise CoordinationInvariantError(
                        "heartbeat operation ID was reused incompatibly"
                    )
                if not self._owns_current_unexpired_token(job, token, database_now):
                    return Fenced()
                if job.last_heartbeat_resulting_lease_expires_at is None:
                    raise CoordinationInvariantError(
                        "heartbeat replay has no recorded lease expiry"
                    )
                return HeartbeatApplied(
                    lease_expires_at=job.last_heartbeat_resulting_lease_expires_at
                )
            if not self._owns_current_unexpired_token(job, token, database_now):
                return Fenced()
            lease_expires_at = database_now + lease_duration
            job.lease_expires_at = lease_expires_at
            job.last_heartbeat_operation_id = str(operation_id)
            job.last_heartbeat_request_fingerprint = request_fingerprint
            job.last_heartbeat_resulting_lease_expires_at = lease_expires_at
            session.flush()
            return HeartbeatApplied(lease_expires_at=lease_expires_at)

    def schedule_retry(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry,
    ) -> RetryScheduleResult:
        transition_fingerprint = self._transition_fingerprint(
            claim=claim,
            failure=failure,
            disposition="retry_scheduled",
            decision=decision,
        )
        replay = self._read_retry_schedule_replay(
            operation_id=str(operation_id),
            request_fingerprint=transition_fingerprint,
            operation_kind="schedule_retry",
        )
        if replay is not None:
            return replay
        return self._reconcile_database_error(
            operation_kind="schedule_retry",
            operation_id=str(operation_id),
            job_id=claim.token.job_id,
            attempt_number=claim.token.attempt_number,
            apply=lambda: self._schedule_retry_once(
                operation_id=operation_id,
                claim=claim,
                failure=failure,
                decision=decision,
            ),
            read_back=lambda: self._read_retry_schedule_replay(
                operation_id=str(operation_id),
                request_fingerprint=transition_fingerprint,
                operation_kind="schedule_retry",
            ),
        )

    def _schedule_retry_once(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry,
    ) -> RetryScheduleResult:
        """Fenced `processing -> retry_scheduled` with one durable DB-time anchor."""

        if failure.failure_reason is not None:
            raise CoordinationInvariantError(
                "retry scheduling cannot carry a terminal failure reason"
            )
        if claim.attempt_count >= claim.max_attempts:
            raise CoordinationInvariantError("retry scheduling exceeds the claimed attempt budget")

        transition_fingerprint = self._transition_fingerprint(
            claim=claim,
            failure=failure,
            disposition="retry_scheduled",
            decision=decision,
        )

        with self._session_factory.begin() as session:
            job = session.scalar(
                select(IngestionJobTable)
                .where(IngestionJobTable.id == claim.token.job_id)
                .with_for_update()
            )
            if job is None:
                return Fenced()

            attempt = session.scalar(
                select(IngestionJobAttemptTable)
                .where(
                    IngestionJobAttemptTable.ingestion_job_id == claim.token.job_id,
                    IngestionJobAttemptTable.attempt_number == claim.token.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None or attempt.closed_at is not None:
                return InvalidTransition()

            database_now = self._database_now(session)
            if not self._owns_current_unexpired_attempt(job, claim, database_now):
                return Fenced()
            if job.attempt_count >= job.max_attempts:
                raise CoordinationInvariantError(
                    "retry scheduling exceeds the current attempt budget"
                )
            if (
                attempt.worker_id != claim.token.worker_id
                or attempt.lease_version != claim.token.lease_version
                or attempt.attempt_number != job.current_attempt_number
            ):
                return InvalidTransition()

            transition_operation_id = str(operation_id)
            self._assert_new_transition_operation(
                session=session,
                operation_id=transition_operation_id,
                request_fingerprint=transition_fingerprint,
                operation_kind="schedule_retry",
            )
            next_attempt_at = database_now + timedelta(microseconds=decision.delay_microseconds)

            attempt.closed_at = database_now
            attempt.disposition = "retry_scheduled"
            attempt.closure_cause = failure.cause.value
            attempt.failure_cause = failure.cause.value
            attempt.failure_cause_version = failure.cause_version
            attempt.cause_mapping_version = failure.mapping_version
            attempt.safe_failure_code = failure.safe_code
            attempt.transition_operation_id = transition_operation_id
            attempt.transition_operation_kind = "schedule_retry"
            attempt.transition_request_fingerprint = transition_fingerprint
            attempt.retry_policy_version = decision.policy_version
            attempt.retry_policy_result = "schedule_retry"
            attempt.retry_jitter_version = decision.jitter_version
            attempt.retry_window_upper_bound_microseconds = decision.window_upper_bound_microseconds
            attempt.retry_delay_microseconds = decision.delay_microseconds
            attempt.retry_next_attempt_at = next_attempt_at

            job.status = "retry_scheduled"
            job.worker_id = None
            job.lease_expires_at = None
            job.current_attempt_number = None
            job.current_attempt_started_at = None
            job.current_attempt_deadline_at = None
            job.next_attempt_at = next_attempt_at
            job.updated_at = database_now
            job.terminal_at = None
            job.failure_reason = None
            job.safe_failure_code = None
            session.flush()
            return RetryScheduleApplied(
                attempt=AttemptRef(
                    job_id=claim.token.job_id,
                    attempt_number=claim.token.attempt_number,
                ),
                next_attempt_at=next_attempt_at,
            )

    def finalize_success[SuccessT](
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        success: SuccessT,
    ) -> FinalizationResult:
        if not isinstance(success, PdfDerivationSuccess):
            raise CoordinationInvariantError(
                "generic success persistence requires Issue #18's fenced derivation and activation "
                "transaction"
            )
        transition_fingerprint = self._pdf_success_fingerprint(claim=claim, success=success)
        replay = self._read_finalization_replay(
            operation_id=str(operation_id),
            request_fingerprint=transition_fingerprint,
            operation_kind="pdf_success",
        )
        if replay is not None:
            return replay
        return self._reconcile_database_error(
            operation_kind="pdf_success",
            operation_id=str(operation_id),
            job_id=claim.token.job_id,
            attempt_number=claim.token.attempt_number,
            apply=lambda: self._finalize_pdf_success_once(
                operation_id=operation_id,
                claim=claim,
                success=success,
            ),
            read_back=lambda: self._read_finalization_replay(
                operation_id=str(operation_id),
                request_fingerprint=transition_fingerprint,
                operation_kind="pdf_success",
            ),
        )

    def _finalize_pdf_success_once(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        success: PdfDerivationSuccess,
    ) -> FinalizationResult:
        transition_fingerprint = self._pdf_success_fingerprint(claim=claim, success=success)
        try:
            with self._session_factory.begin() as session:
                job = session.scalar(
                    select(IngestionJobTable)
                    .where(IngestionJobTable.id == claim.token.job_id)
                    .with_for_update()
                )
                if job is None:
                    return Fenced()
                attempt = session.scalar(
                    select(IngestionJobAttemptTable)
                    .where(
                        IngestionJobAttemptTable.ingestion_job_id == claim.token.job_id,
                        IngestionJobAttemptTable.attempt_number == claim.token.attempt_number,
                    )
                    .with_for_update()
                )
                if attempt is None or attempt.closed_at is not None:
                    return InvalidTransition()

                database_now = self._database_now(session)
                if not self._owns_current_unexpired_attempt(job, claim, database_now):
                    return Fenced()
                if (
                    attempt.worker_id != claim.token.worker_id
                    or attempt.lease_version != claim.token.lease_version
                    or attempt.attempt_number != job.current_attempt_number
                ):
                    return InvalidTransition()

                self._assert_new_transition_operation(
                    session=session,
                    operation_id=str(operation_id),
                    request_fingerprint=transition_fingerprint,
                    operation_kind="pdf_success",
                )

                document = session.scalar(
                    select(DocumentTable)
                    .where(
                        DocumentTable.id == job.document_id,
                        DocumentTable.workspace_id == job.workspace_id,
                    )
                    .with_for_update()
                )
                source_object = session.scalar(
                    select(OriginalSourceObjectTable)
                    .where(
                        OriginalSourceObjectTable.id == job.source_object_id,
                        OriginalSourceObjectTable.workspace_id == job.workspace_id,
                        OriginalSourceObjectTable.document_version_id
                        == job.target_document_version_id,
                    )
                    .with_for_update()
                )
                version = session.scalar(
                    select(DocumentVersionTable)
                    .where(
                        DocumentVersionTable.id == job.target_document_version_id,
                        DocumentVersionTable.document_id == job.document_id,
                    )
                    .with_for_update()
                )
                chunking = session.scalar(
                    select(ChunkingConfigurationTable)
                    .where(ChunkingConfigurationTable.id == job.chunking_configuration_id)
                    .with_for_update()
                )
                embedding_configuration = session.scalar(
                    select(EmbeddingConfigurationTable)
                    .where(EmbeddingConfigurationTable.id == job.embedding_configuration_id)
                    .with_for_update()
                )
                if document is None or source_object is None or version is None:
                    raise CoordinationInvariantError(
                        "PDF success references missing owned resources"
                    )
                if chunking is None or embedding_configuration is None:
                    raise CoordinationInvariantError(
                        "PDF success references missing pinned configuration"
                    )
                self._validate_pdf_success_inputs(
                    job=job,
                    claim=claim,
                    success=success,
                    source_object=source_object,
                    version=version,
                    chunking=chunking,
                    embedding_configuration=embedding_configuration,
                )

                chunk_set = session.scalar(
                    select(ChunkSetTable)
                    .where(
                        ChunkSetTable.document_version_id == version.id,
                        ChunkSetTable.parser_configuration_id == job.parser_configuration_id,
                        ChunkSetTable.normalizer_configuration_id
                        == job.normalizer_configuration_id,
                        ChunkSetTable.chunking_configuration_id == chunking.id,
                    )
                    .with_for_update()
                )
                if chunk_set is None:
                    chunk_set = ChunkSetTable(
                        id=str(uuid4()),
                        document_version_id=version.id,
                        parser_configuration_id=job.parser_configuration_id,
                        normalizer_configuration_id=job.normalizer_configuration_id,
                        chunking_configuration_id=chunking.id,
                        status="pending",
                    )
                    session.add(chunk_set)
                    session.flush()
                    for chunk in success.extraction.chunks:
                        session.add(
                            ChunkTable(
                                id=str(uuid4()),
                                chunk_set_id=chunk_set.id,
                                ordinal=chunk.ordinal,
                                heading_path=[],
                                start_line=self._pdf_line_number(
                                    success.extraction.pages, chunk.page_number, chunk.start_offset
                                ),
                                end_line=self._pdf_line_number(
                                    success.extraction.pages, chunk.page_number, chunk.end_offset
                                ),
                                content=chunk.content,
                                content_checksum=chunk.content_checksum,
                                token_count=chunk.token_count,
                                page_start=chunk.page_start,
                                page_end=chunk.page_end,
                                start_offset=chunk.start_offset,
                                end_offset=chunk.end_offset,
                            )
                        )
                    chunk_set.status = "completed"
                    session.flush()
                else:
                    self._validate_existing_pdf_chunk_set(
                        session=session,
                        chunk_set=chunk_set,
                        success=success,
                    )

                embedding_set = session.scalar(
                    select(EmbeddingSetTable)
                    .where(
                        EmbeddingSetTable.chunk_set_id == chunk_set.id,
                        EmbeddingSetTable.embedding_configuration_id == embedding_configuration.id,
                    )
                    .with_for_update()
                )
                if embedding_set is None:
                    embedding_set = EmbeddingSetTable(
                        id=str(uuid4()),
                        chunk_set_id=chunk_set.id,
                        embedding_configuration_id=embedding_configuration.id,
                        status="pending",
                    )
                    session.add(embedding_set)
                    session.flush()
                    chunks = session.scalars(
                        select(ChunkTable)
                        .where(ChunkTable.chunk_set_id == chunk_set.id)
                        .order_by(ChunkTable.ordinal)
                    ).all()
                    for chunk, vector in zip(chunks, success.vectors, strict=True):
                        session.add(
                            ChunkEmbeddingTable(
                                id=str(uuid4()),
                                embedding_set_id=embedding_set.id,
                                chunk_id=chunk.id,
                                embedding=list(vector),
                            )
                        )
                    embedding_set.status = "completed"
                    session.flush()
                else:
                    self._validate_existing_embedding_set(
                        session=session,
                        embedding_set=embedding_set,
                        chunk_set=chunk_set,
                        expected_vectors=success.vectors,
                        dimensions=embedding_configuration.dimensions,
                    )

                if document.current_document_version_id != job.target_document_version_id:
                    replacement_document_version_id = document.current_document_version_id
                    replacement_ingestion_job_id = self._replacement_job_id(
                        session=session,
                        job=job,
                        replacement_document_version_id=replacement_document_version_id,
                    )
                    final_database_now = self._database_now(session)
                    self._close_pdf_attempt(
                        attempt=attempt,
                        operation_id=operation_id,
                        transition_fingerprint=transition_fingerprint,
                        database_now=final_database_now,
                        disposition="superseded",
                        terminal_outcome_code="stale_document_version",
                        replacement_document_version_id=replacement_document_version_id,
                        replacement_ingestion_job_id=replacement_ingestion_job_id,
                    )
                    if not self._finalize_pdf_job_if_current_and_live(
                        session=session,
                        claim=claim,
                        database_now=final_database_now,
                        disposition="superseded",
                        terminal_outcome_code="stale_document_version",
                        replacement_document_version_id=replacement_document_version_id,
                        replacement_ingestion_job_id=replacement_ingestion_job_id,
                    ):
                        raise _FinalizationFenceLost()
                    return FinalizationApplied(
                        attempt=AttemptRef(
                            job_id=claim.token.job_id,
                            attempt_number=claim.token.attempt_number,
                        ),
                        outcome="superseded",
                        replacement_document_version_id=replacement_document_version_id,
                        replacement_ingestion_job_id=replacement_ingestion_job_id,
                    )

                activated = session.execute(
                    update(DocumentTable)
                    .where(
                        DocumentTable.id == document.id,
                        DocumentTable.workspace_id == job.workspace_id,
                        DocumentTable.current_document_version_id == job.target_document_version_id,
                    )
                    .values(
                        active_embedding_set_id=embedding_set.id,
                        active_embedding_configuration_id=embedding_configuration.id,
                        revision=DocumentTable.revision + 1,
                    )
                )
                if activated.rowcount != 1:
                    raise CoordinationInvariantError("PDF activation CAS lost its target")

                final_database_now = self._database_now(session)
                self._close_pdf_attempt(
                    attempt=attempt,
                    operation_id=operation_id,
                    transition_fingerprint=transition_fingerprint,
                    database_now=final_database_now,
                    disposition="succeeded",
                    terminal_outcome_code="succeeded",
                )
                if not self._finalize_pdf_job_if_current_and_live(
                    session=session,
                    claim=claim,
                    database_now=final_database_now,
                    disposition="succeeded",
                    terminal_outcome_code="succeeded",
                ):
                    raise _FinalizationFenceLost()
                return FinalizationApplied(
                    attempt=AttemptRef(
                        job_id=claim.token.job_id,
                        attempt_number=claim.token.attempt_number,
                    )
                )
        except _FinalizationFenceLost:
            return Fenced()

    @staticmethod
    def _validate_pdf_success_inputs(
        *,
        job: IngestionJobTable,
        claim: ClaimedAttempt,
        success: PdfDerivationSuccess,
        source_object: OriginalSourceObjectTable,
        version: DocumentVersionTable,
        chunking: ChunkingConfigurationTable,
        embedding_configuration: EmbeddingConfigurationTable,
    ) -> None:
        extraction = success.extraction
        if (
            job.workspace_id != claim.work.workspace_id
            or job.document_id != claim.work.document_id
            or job.target_document_version_id != claim.work.document_version_id
            or job.source_object_id != claim.work.source_object_id
            or job.parser_configuration_id != claim.work.parser_configuration_id
            or job.normalizer_configuration_id != claim.work.normalizer_configuration_id
            or job.chunking_configuration_id != claim.work.chunking_configuration_id
            or job.embedding_configuration_id != claim.work.embedding_configuration_id
            or source_object.document_version_id != version.id
            or source_object.workspace_id != job.workspace_id
            or source_object.raw_sha256 != version.raw_sha256
            or source_object.media_type != version.media_type
            or claim.work.source_sha256
            and source_object.raw_sha256 != claim.work.source_sha256
            or claim.work.source_byte_size
            and source_object.byte_size != claim.work.source_byte_size
            or job.normalizer_configuration_id != extraction.normalizer_version
            or chunking.parser_version != extraction.parser_version
            or chunking.chunker_version != extraction.chunking_policy_version
            or chunking.tokenizer_name != extraction.tokenizer_name
            or chunking.tokenizer_version != extraction.tokenizer_version
            or chunking.target_tokens != 500
            or chunking.overlap_tokens != 75
            or chunking.max_tokens != 650
            or embedding_configuration.id != job.embedding_configuration_id
            or embedding_configuration.provider != success.embedding_provider
            or embedding_configuration.model != success.embedding_model
            or len(success.vectors) != len(extraction.chunks)
            or not extraction.chunks
        ):
            raise CoordinationInvariantError("PDF success does not match its pinned target")

        if len({page.page_number for page in extraction.pages}) != len(extraction.pages) or any(
            page.page_number < 1
            or page.content_checksum != hashlib.sha256(page.text.encode()).hexdigest()
            for page in extraction.pages
        ):
            raise CoordinationInvariantError("PDF success contains invalid page provenance")
        pages = {page.page_number: page for page in extraction.pages}
        for ordinal, chunk in enumerate(extraction.chunks):
            page = pages.get(chunk.page_number)
            if (
                chunk.ordinal != ordinal
                or page is None
                or chunk.page_start != chunk.page_number
                or chunk.page_end != chunk.page_number
                or chunk.start_offset < 0
                or chunk.start_offset >= chunk.end_offset
                or chunk.end_offset > len(page.text)
                or chunk.content != page.text[chunk.start_offset : chunk.end_offset]
                or chunk.content_checksum != hashlib.sha256(chunk.content.encode()).hexdigest()
                or chunk.token_count <= 0
            ):
                raise CoordinationInvariantError("PDF success contains invalid chunk provenance")
            vector = success.vectors[ordinal]
            if len(vector) != embedding_configuration.dimensions or any(
                not isfinite(float(value)) for value in vector
            ):
                raise CoordinationInvariantError("PDF success contains invalid vectors")

    @staticmethod
    def _pdf_line_number(pages, page_number: int, offset: int) -> int:
        page = next((page for page in pages if page.page_number == page_number), None)
        if page is None:
            raise CoordinationInvariantError("PDF chunk refers to a missing page")
        return page.text.count("\n", 0, offset) + 1

    @staticmethod
    def _validate_existing_pdf_chunk_set(*, session: Session, chunk_set, success) -> None:
        if chunk_set.status != "completed":
            raise CoordinationInvariantError("PDF Chunk Set is not complete")
        rows = session.scalars(
            select(ChunkTable)
            .where(ChunkTable.chunk_set_id == chunk_set.id)
            .order_by(ChunkTable.ordinal)
        ).all()
        if len(rows) != len(success.extraction.chunks):
            raise CoordinationInvariantError("PDF Chunk Set is incomplete")
        for row, expected in zip(rows, success.extraction.chunks, strict=True):
            if (
                row.ordinal != expected.ordinal
                or row.content != expected.content
                or row.content_checksum != expected.content_checksum
                or row.token_count != expected.token_count
                or row.page_start != expected.page_start
                or row.page_end != expected.page_end
                or row.start_offset != expected.start_offset
                or row.end_offset != expected.end_offset
            ):
                raise CoordinationInvariantError("existing PDF Chunk Set is incompatible")

    @staticmethod
    def _validate_existing_embedding_set(
        *, session: Session, embedding_set, chunk_set, expected_vectors, dimensions: int
    ) -> None:
        if embedding_set.status != "completed":
            raise CoordinationInvariantError("Embedding Set is not complete")
        chunks = session.scalars(
            select(ChunkTable)
            .where(ChunkTable.chunk_set_id == chunk_set.id)
            .order_by(ChunkTable.ordinal)
        ).all()
        embeddings = session.scalars(
            select(ChunkEmbeddingTable).where(
                ChunkEmbeddingTable.embedding_set_id == embedding_set.id
            )
        ).all()
        by_chunk = {embedding.chunk_id: embedding for embedding in embeddings}
        if len(embeddings) != len(chunks) or len(expected_vectors) != len(chunks):
            raise CoordinationInvariantError("Embedding Set is incomplete")
        for chunk in chunks:
            embedding = by_chunk.get(chunk.id)
            if embedding is None or len(embedding.embedding) != dimensions:
                raise CoordinationInvariantError("Embedding Set has invalid vectors")

    @staticmethod
    def _replacement_job_id(
        *, session: Session, job: IngestionJobTable, replacement_document_version_id: str | None
    ) -> str | None:
        if replacement_document_version_id is None:
            return None
        replacement = session.scalar(
            select(IngestionJobTable)
            .where(
                IngestionJobTable.id != job.id,
                IngestionJobTable.workspace_id == job.workspace_id,
                IngestionJobTable.document_id == job.document_id,
                IngestionJobTable.target_document_version_id == replacement_document_version_id,
            )
            .order_by(IngestionJobTable.created_at, IngestionJobTable.id)
            .limit(1)
        )
        return replacement.id if replacement is not None else None

    @staticmethod
    def _close_pdf_attempt(
        *,
        attempt: IngestionJobAttemptTable,
        operation_id: TransitionOperationId,
        transition_fingerprint: str,
        database_now: datetime,
        disposition: str,
        terminal_outcome_code: str,
        replacement_document_version_id: str | None = None,
        replacement_ingestion_job_id: str | None = None,
    ) -> None:
        attempt.closed_at = database_now
        attempt.disposition = disposition
        attempt.closure_cause = terminal_outcome_code
        attempt.failure_cause = None
        attempt.failure_cause_version = None
        attempt.cause_mapping_version = None
        attempt.safe_failure_code = None
        attempt.failure_reason = None
        attempt.terminal_outcome_code = terminal_outcome_code
        attempt.transition_operation_id = str(operation_id)
        attempt.transition_operation_kind = "pdf_success"
        attempt.transition_request_fingerprint = transition_fingerprint
        attempt.replacement_document_version_id = replacement_document_version_id
        attempt.replacement_ingestion_job_id = replacement_ingestion_job_id

    @staticmethod
    def _finalize_pdf_job_if_current_and_live(
        *,
        session: Session,
        claim: ClaimedAttempt,
        database_now: datetime,
        disposition: str,
        terminal_outcome_code: str,
        replacement_document_version_id: str | None = None,
        replacement_ingestion_job_id: str | None = None,
    ) -> bool:
        """Apply the terminal job transition only while the lease remains authoritative.

        This is intentionally the final mutable job operation in PDF success finalization.  The
        database evaluates both a fresh PostgreSQL sample and ``clock_timestamp()`` in the same
        conditional UPDATE; a zero-row result rolls back all tentative derivation and attempt work.
        """

        transition = session.execute(
            update(IngestionJobTable)
            .where(
                IngestionJobTable.id == claim.token.job_id,
                IngestionJobTable.workspace_id == claim.work.workspace_id,
                IngestionJobTable.status == "processing",
                IngestionJobTable.worker_id == claim.token.worker_id,
                IngestionJobTable.lease_version == claim.token.lease_version,
                IngestionJobTable.current_attempt_number == claim.token.attempt_number,
                IngestionJobTable.lease_expires_at.is_not(None),
                IngestionJobTable.lease_expires_at > database_now,
                IngestionJobTable.lease_expires_at > func.clock_timestamp(),
            )
            .values(
                status="succeeded" if disposition == "succeeded" else "superseded",
                worker_id=None,
                lease_expires_at=None,
                current_attempt_number=None,
                current_attempt_started_at=None,
                current_attempt_deadline_at=None,
                next_attempt_at=None,
                terminal_at=database_now,
                updated_at=database_now,
                failure_reason=None,
                safe_failure_code=None,
                terminal_outcome_code=terminal_outcome_code,
                replacement_document_version_id=replacement_document_version_id,
                replacement_ingestion_job_id=replacement_ingestion_job_id,
            )
        )
        return transition.rowcount == 1

    @staticmethod
    def _pdf_success_fingerprint(*, claim: ClaimedAttempt, success: PdfDerivationSuccess) -> str:
        digest = hashlib.sha256()
        extraction = success.extraction
        digest.update(extraction.derivation_identity.encode())
        for chunk in extraction.chunks:
            digest.update(
                repr(
                    (
                        chunk.ordinal,
                        chunk.page_number,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.start_offset,
                        chunk.end_offset,
                        chunk.content_checksum,
                        chunk.token_count,
                    )
                ).encode()
            )
        for vector in success.vectors:
            digest.update(repr(tuple(float(value) for value in vector)).encode())
        return "\n".join(
            (
                claim.token.job_id,
                str(claim.token.attempt_number),
                claim.token.worker_id,
                str(claim.token.lease_version),
                "pdf_success",
                success.embedding_provider,
                success.embedding_model,
                digest.hexdigest(),
            )
        )

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: RetryExhausted | FailTerminal | None = None,
    ) -> FinalizationResult:
        transition_fingerprint = self._transition_fingerprint(
            claim=claim,
            failure=failure,
            disposition="failed",
            terminal_decision=decision,
        )
        replay = self._read_finalization_replay(
            operation_id=str(operation_id),
            request_fingerprint=transition_fingerprint,
            operation_kind="terminal_failure",
        )
        if replay is not None:
            return replay
        return self._reconcile_database_error(
            operation_kind="terminal_failure",
            operation_id=str(operation_id),
            job_id=claim.token.job_id,
            attempt_number=claim.token.attempt_number,
            apply=lambda: self._finalize_terminal_failure_once(
                operation_id=operation_id,
                claim=claim,
                failure=failure,
                decision=decision,
            ),
            read_back=lambda: self._read_finalization_replay(
                operation_id=str(operation_id),
                request_fingerprint=transition_fingerprint,
                operation_kind="terminal_failure",
            ),
        )

    def _finalize_terminal_failure_once(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: RetryExhausted | FailTerminal | None = None,
    ) -> FinalizationResult:
        """Fenced `processing -> failed` plus matching immutable attempt closure."""

        transition_fingerprint = self._transition_fingerprint(
            claim=claim,
            failure=failure,
            disposition="failed",
            terminal_decision=decision,
        )

        with self._session_factory.begin() as session:
            job = session.scalar(
                select(IngestionJobTable)
                .where(IngestionJobTable.id == claim.token.job_id)
                .with_for_update()
            )
            if job is None:
                return Fenced()

            database_now = self._database_now(session)
            if not self._owns_current_unexpired_attempt(job, claim, database_now):
                return Fenced()

            attempt = session.scalar(
                select(IngestionJobAttemptTable)
                .where(
                    IngestionJobAttemptTable.ingestion_job_id == claim.token.job_id,
                    IngestionJobAttemptTable.attempt_number == claim.token.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None or attempt.closed_at is not None:
                return InvalidTransition()

            database_now = self._database_now(session)
            if not self._owns_current_unexpired_attempt(job, claim, database_now):
                return Fenced()
            if (
                attempt.worker_id != claim.token.worker_id
                or attempt.lease_version != claim.token.lease_version
                or attempt.attempt_number != job.current_attempt_number
            ):
                return InvalidTransition()

            transition_operation_id = str(operation_id)
            self._assert_new_transition_operation(
                session=session,
                operation_id=transition_operation_id,
                request_fingerprint=transition_fingerprint,
                operation_kind="terminal_failure",
            )

            attempt.closed_at = database_now
            attempt.disposition = "failed"
            attempt.closure_cause = failure.cause.value
            attempt.failure_cause = failure.cause.value
            attempt.failure_cause_version = failure.cause_version
            attempt.cause_mapping_version = failure.mapping_version
            attempt.safe_failure_code = failure.safe_code
            attempt.failure_reason = failure.failure_reason
            attempt.transition_operation_id = transition_operation_id
            attempt.transition_operation_kind = "terminal_failure"
            attempt.transition_request_fingerprint = transition_fingerprint
            if decision is not None:
                attempt.retry_policy_version = decision.policy_version
                attempt.retry_policy_result = self._terminal_policy_result(decision)

            job.status = "failed"
            job.worker_id = None
            job.lease_expires_at = None
            job.current_attempt_number = None
            job.current_attempt_started_at = None
            job.current_attempt_deadline_at = None
            job.next_attempt_at = None
            job.terminal_at = database_now
            job.updated_at = database_now
            job.failure_reason = failure.failure_reason
            job.safe_failure_code = failure.safe_code
            session.flush()
            return FinalizationApplied(
                attempt=AttemptRef(
                    job_id=claim.token.job_id,
                    attempt_number=claim.token.attempt_number,
                )
            )

    def finalize_superseded(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        outcome: WorkSuperseded,
    ) -> FinalizationResult:
        transition_fingerprint = self._superseded_fingerprint(claim=claim, outcome=outcome)
        replay = self._read_superseded_replay(
            operation_id=str(operation_id), request_fingerprint=transition_fingerprint
        )
        if replay is not None:
            return replay
        return self._reconcile_database_error(
            operation_kind="superseded",
            operation_id=str(operation_id),
            job_id=claim.token.job_id,
            attempt_number=claim.token.attempt_number,
            apply=lambda: self._finalize_superseded_once(
                operation_id=operation_id,
                claim=claim,
                outcome=outcome,
            ),
            read_back=lambda: self._read_superseded_replay(
                operation_id=str(operation_id), request_fingerprint=transition_fingerprint
            ),
        )

    def _finalize_superseded_once(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        outcome: WorkSuperseded,
    ) -> FinalizationResult:
        """Fenced `processing -> superseded` for a target made stale by a newer version."""

        transition_fingerprint = self._superseded_fingerprint(claim=claim, outcome=outcome)
        with self._session_factory.begin() as session:
            job = session.scalar(
                select(IngestionJobTable)
                .where(IngestionJobTable.id == claim.token.job_id)
                .with_for_update()
            )
            if job is None:
                return Fenced()
            attempt = session.scalar(
                select(IngestionJobAttemptTable)
                .where(
                    IngestionJobAttemptTable.ingestion_job_id == claim.token.job_id,
                    IngestionJobAttemptTable.attempt_number == claim.token.attempt_number,
                )
                .with_for_update()
            )
            if attempt is None or attempt.closed_at is not None:
                return InvalidTransition()

            database_now = self._database_now(session)
            if not self._owns_current_unexpired_attempt(job, claim, database_now):
                return Fenced()
            if (
                attempt.worker_id != claim.token.worker_id
                or attempt.lease_version != claim.token.lease_version
                or attempt.attempt_number != job.current_attempt_number
            ):
                return InvalidTransition()

            document = session.get(DocumentTable, job.document_id)
            if (
                document is None
                or document.current_document_version_id == job.target_document_version_id
            ):
                return InvalidTransition()
            if (
                outcome.replacement_document_version_id is not None
                and outcome.replacement_document_version_id != document.current_document_version_id
            ):
                return InvalidTransition()
            if outcome.replacement_ingestion_job_id is not None:
                replacement_job = session.get(
                    IngestionJobTable, outcome.replacement_ingestion_job_id
                )
                if (
                    replacement_job is None
                    or replacement_job.document_id != job.document_id
                    or replacement_job.target_document_version_id
                    != document.current_document_version_id
                ):
                    return InvalidTransition()

            transition_operation_id = str(operation_id)
            self._assert_new_transition_operation(
                session=session,
                operation_id=transition_operation_id,
                request_fingerprint=transition_fingerprint,
                operation_kind="superseded",
            )
            attempt.closed_at = database_now
            attempt.disposition = "superseded"
            attempt.closure_cause = "stale_document_version"
            attempt.terminal_outcome_code = "stale_document_version"
            attempt.transition_operation_id = transition_operation_id
            attempt.transition_operation_kind = "superseded"
            attempt.transition_request_fingerprint = transition_fingerprint
            attempt.replacement_document_version_id = outcome.replacement_document_version_id
            attempt.replacement_ingestion_job_id = outcome.replacement_ingestion_job_id

            job.status = "superseded"
            job.worker_id = None
            job.lease_expires_at = None
            job.current_attempt_number = None
            job.current_attempt_started_at = None
            job.current_attempt_deadline_at = None
            job.next_attempt_at = None
            job.terminal_at = database_now
            job.updated_at = database_now
            job.failure_reason = None
            job.safe_failure_code = None
            job.terminal_outcome_code = "stale_document_version"
            job.replacement_document_version_id = outcome.replacement_document_version_id
            job.replacement_ingestion_job_id = outcome.replacement_ingestion_job_id
            session.flush()
            return FinalizationApplied(
                attempt=AttemptRef(
                    job_id=claim.token.job_id,
                    attempt_number=claim.token.attempt_number,
                ),
                outcome="superseded",
                replacement_document_version_id=outcome.replacement_document_version_id,
                replacement_ingestion_job_id=outcome.replacement_ingestion_job_id,
            )

    @staticmethod
    def _database_now(session: Session) -> datetime:
        database_now = session.scalar(select(func.clock_timestamp()))
        if not isinstance(database_now, datetime):
            raise CoordinationInvariantError("PostgreSQL did not return an authoritative timestamp")
        return database_now

    @staticmethod
    def _claim_fingerprint(*, worker_id: str, timing: AttemptTimingV1) -> str:
        return "\n".join(
            (
                worker_id,
                str(_duration_microseconds(timing.lease_duration)),
                str(_duration_microseconds(timing.max_attempt_runtime)),
            )
        )

    @staticmethod
    def _heartbeat_fingerprint(token: FencingToken, lease_duration: timedelta) -> str:
        return "\n".join(
            (
                token.job_id,
                str(token.attempt_number),
                token.worker_id,
                str(token.lease_version),
                str(_duration_microseconds(lease_duration)),
            )
        )

    @staticmethod
    def _transition_fingerprint(
        *,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        disposition: str,
        decision: ScheduleRetry | None = None,
        terminal_decision: RetryExhausted | FailTerminal | None = None,
    ) -> str:
        values = [
            claim.token.job_id,
            str(claim.token.attempt_number),
            claim.token.worker_id,
            str(claim.token.lease_version),
            disposition,
            failure.cause.value,
            failure.safe_code,
            failure.failure_reason or "",
            failure.cause_version,
            failure.mapping_version,
        ]
        if decision is not None:
            values.extend(
                (
                    decision.policy_version,
                    decision.jitter_version,
                    str(decision.window_upper_bound_microseconds),
                    str(decision.delay_microseconds),
                )
            )
        if terminal_decision is not None:
            values.extend(
                (
                    terminal_decision.policy_version,
                    PostgresIngestionJobStore._terminal_policy_result(terminal_decision),
                )
            )
        return "\n".join(values)

    @staticmethod
    def _terminal_policy_result(decision: RetryExhausted | FailTerminal) -> str:
        if isinstance(decision, RetryExhausted):
            return "retry_exhausted"
        return "fail_terminal"

    @staticmethod
    def _superseded_fingerprint(*, claim: ClaimedAttempt, outcome: WorkSuperseded) -> str:
        return "\n".join(
            (
                claim.token.job_id,
                str(claim.token.attempt_number),
                claim.token.worker_id,
                str(claim.token.lease_version),
                "superseded",
                "stale_document_version",
                outcome.replacement_document_version_id or "",
                outcome.replacement_ingestion_job_id or "",
            )
        )

    @staticmethod
    def _validate_expired_recovery_input(
        *,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry | RetryExhausted,
    ) -> None:
        if not isinstance(decision, (ScheduleRetry, RetryExhausted)):
            raise CoordinationInvariantError(
                "expired recovery requires ScheduleRetry or RetryExhausted"
            )
        if (
            failure.cause != FailureCauseV1.LEASE_EXPIRED
            or failure.safe_code != "lease_expired"
            or failure.failure_reason is not None
        ):
            raise CoordinationInvariantError("expired recovery requires the lease-expired fact")
        if observation.attempt_count > observation.max_attempts:
            raise CoordinationInvariantError("expired observation exceeds the attempt budget")
        if (
            isinstance(decision, ScheduleRetry)
            and observation.attempt_count >= observation.max_attempts
        ):
            raise CoordinationInvariantError("expired final attempt cannot schedule another retry")
        if (
            isinstance(decision, RetryExhausted)
            and observation.attempt_count < observation.max_attempts
        ):
            raise CoordinationInvariantError("non-final expired attempt cannot be exhausted")

    @staticmethod
    def _matches_expired_observation(
        job: IngestionJobTable,
        attempt: IngestionJobAttemptTable,
        observation: ExpiredAttemptObservation,
    ) -> bool:
        return (
            job.status == "processing"
            and job.worker_id == observation.worker_id
            and job.lease_version == observation.lease_version
            and job.current_attempt_number == observation.attempt_number
            and job.attempt_count == observation.attempt_count
            and job.max_attempts == observation.max_attempts
            and job.lease_expires_at == observation.lease_expires_at
            and attempt.closed_at is None
            and attempt.worker_id == observation.worker_id
            and attempt.lease_version == observation.lease_version
            and attempt.attempt_number == observation.attempt_number
        )

    @staticmethod
    def _expired_recovery_fingerprint(
        *,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        disposition: str,
        decision: ScheduleRetry | RetryExhausted,
    ) -> str:
        values = [
            observation.job_id,
            str(observation.attempt_number),
            observation.worker_id,
            str(observation.lease_version),
            str(observation.attempt_count),
            str(observation.max_attempts),
            observation.lease_expires_at.isoformat(),
            disposition,
            failure.cause.value,
            failure.safe_code,
            failure.cause_version,
            failure.mapping_version,
            decision.policy_version,
        ]
        if isinstance(decision, ScheduleRetry):
            values.extend(
                (
                    decision.jitter_version,
                    str(decision.window_upper_bound_microseconds),
                    str(decision.delay_microseconds),
                )
            )
        else:
            values.append("retry_exhausted")
        return "\n".join(values)

    @staticmethod
    def _assert_new_transition_operation(
        *,
        session: Session,
        operation_id: str,
        request_fingerprint: str,
        operation_kind: str,
    ) -> None:
        existing = session.scalar(
            select(IngestionJobAttemptTable).where(
                IngestionJobAttemptTable.transition_operation_kind == operation_kind,
                IngestionJobAttemptTable.transition_operation_id == operation_id,
            )
        )
        if existing is not None:
            if existing.transition_request_fingerprint != request_fingerprint:
                raise CoordinationInvariantError("transition operation ID was reused incompatibly")
            raise CoordinationInvariantError("transition operation ID was already applied")

    def _reconcile_database_error(
        self,
        *,
        operation_kind: str,
        operation_id: str,
        job_id: str | None,
        attempt_number: int | None,
        apply: Callable[[], MutationResultT],
        read_back: Callable[[], MutationResultT | None],
    ) -> MutationResultT:
        """Retry a proven no-commit write once; otherwise expose an indeterminate outcome."""

        for retry in range(2):
            try:
                return apply()
            except SQLAlchemyError as write_error:
                try:
                    durable_result = read_back()
                except SQLAlchemyError as read_error:
                    raise CoordinationOutcomeIndeterminate(
                        operation_kind=operation_kind,
                        operation_id=operation_id,
                        job_id=job_id,
                        attempt_number=attempt_number,
                    ) from read_error
                if durable_result is not None:
                    return durable_result
                if retry == 1:
                    raise CoordinationOutcomeIndeterminate(
                        operation_kind=operation_kind,
                        operation_id=operation_id,
                        job_id=job_id,
                        attempt_number=attempt_number,
                    ) from write_error
        raise AssertionError("unreachable reconciliation loop")

    def _read_claim_replay(
        self, *, operation_id: str, request_fingerprint: str
    ) -> ClaimedAttempt | ClaimLeaseLost | None:
        with self._session_factory.begin() as session:
            attempt = session.scalar(
                select(IngestionJobAttemptTable).where(
                    IngestionJobAttemptTable.claim_operation_id == operation_id
                )
            )
            if attempt is None:
                return None
            if attempt.claim_request_fingerprint != request_fingerprint:
                raise CoordinationInvariantError("claim operation ID was reused incompatibly")
            job = session.scalar(
                select(IngestionJobTable)
                .where(IngestionJobTable.id == attempt.ingestion_job_id)
                .with_for_update()
            )
            if job is None:
                raise CoordinationInvariantError("claim operation refers to a missing job")
            token = self._token(
                job_id=attempt.ingestion_job_id,
                attempt_number=attempt.attempt_number,
                worker_id=attempt.worker_id,
                lease_version=attempt.lease_version,
            )
            if not self._owns_current_unexpired_token(job, token, self._database_now(session)):
                return ClaimLeaseLost(
                    attempt=AttemptRef(
                        job_id=attempt.ingestion_job_id, attempt_number=attempt.attempt_number
                    )
                )
            source_object = session.get(OriginalSourceObjectTable, job.source_object_id)
            if source_object is None:
                raise CoordinationInvariantError("claimed job has no Original Source Object")
            return ClaimedAttempt(
                token=token,
                work=IngestionWork(
                    workspace_id=job.workspace_id,
                    document_id=job.document_id,
                    document_version_id=job.target_document_version_id,
                    source_object_id=source_object.id,
                    source_object_key=source_object.object_key,
                    source_media_type=source_object.media_type,
                    source_sha256=source_object.raw_sha256,
                    source_byte_size=source_object.byte_size,
                    parser_configuration_id=job.parser_configuration_id,
                    normalizer_configuration_id=job.normalizer_configuration_id,
                    chunking_configuration_id=job.chunking_configuration_id,
                    embedding_configuration_id=job.embedding_configuration_id,
                ),
                attempt_count=attempt.attempt_number,
                max_attempts=job.max_attempts,
                attempt_started_at=attempt.attempt_started_at,
                initial_lease_expires_at=attempt.initial_lease_expires_at,
                deadline_at=attempt.deadline_at,
            )

    def _read_retry_schedule_replay(
        self, *, operation_id: str, request_fingerprint: str, operation_kind: str
    ) -> RetryScheduleApplied | None:
        with self._session_factory() as session:
            attempt = session.scalar(
                select(IngestionJobAttemptTable).where(
                    IngestionJobAttemptTable.transition_operation_kind == operation_kind,
                    IngestionJobAttemptTable.transition_operation_id == operation_id,
                )
            )
            if attempt is None:
                return None
            if attempt.transition_request_fingerprint != request_fingerprint:
                raise CoordinationInvariantError("transition operation ID was reused incompatibly")
            if attempt.disposition != "retry_scheduled" or attempt.retry_next_attempt_at is None:
                raise CoordinationInvariantError("transition replay has no scheduled-retry result")
            return RetryScheduleApplied(
                attempt=AttemptRef(
                    job_id=attempt.ingestion_job_id, attempt_number=attempt.attempt_number
                ),
                next_attempt_at=attempt.retry_next_attempt_at,
            )

    def _read_finalization_replay(
        self, *, operation_id: str, request_fingerprint: str, operation_kind: str
    ) -> FinalizationApplied | None:
        with self._session_factory() as session:
            attempt = session.scalar(
                select(IngestionJobAttemptTable).where(
                    IngestionJobAttemptTable.transition_operation_kind == operation_kind,
                    IngestionJobAttemptTable.transition_operation_id == operation_id,
                )
            )
            if attempt is None:
                return None
            if attempt.transition_request_fingerprint != request_fingerprint:
                raise CoordinationInvariantError("transition operation ID was reused incompatibly")
            if operation_kind == "pdf_success":
                if attempt.disposition not in {"succeeded", "superseded"}:
                    raise CoordinationInvariantError("transition replay has no PDF success result")
                return FinalizationApplied(
                    attempt=AttemptRef(
                        job_id=attempt.ingestion_job_id, attempt_number=attempt.attempt_number
                    ),
                    outcome=attempt.disposition,
                    replacement_document_version_id=attempt.replacement_document_version_id,
                    replacement_ingestion_job_id=attempt.replacement_ingestion_job_id,
                )
            if attempt.disposition != "failed":
                raise CoordinationInvariantError("transition replay has no terminal-failure result")
            return FinalizationApplied(
                attempt=AttemptRef(
                    job_id=attempt.ingestion_job_id, attempt_number=attempt.attempt_number
                )
            )

    def _read_superseded_replay(
        self, *, operation_id: str, request_fingerprint: str
    ) -> FinalizationApplied | None:
        with self._session_factory() as session:
            attempt = session.scalar(
                select(IngestionJobAttemptTable).where(
                    IngestionJobAttemptTable.transition_operation_kind == "superseded",
                    IngestionJobAttemptTable.transition_operation_id == operation_id,
                )
            )
            if attempt is None:
                return None
            if attempt.transition_request_fingerprint != request_fingerprint:
                raise CoordinationInvariantError("transition operation ID was reused incompatibly")
            if (
                attempt.disposition != "superseded"
                or attempt.terminal_outcome_code != "stale_document_version"
            ):
                raise CoordinationInvariantError("transition replay has no superseded result")
            return FinalizationApplied(
                attempt=AttemptRef(
                    job_id=attempt.ingestion_job_id, attempt_number=attempt.attempt_number
                ),
                outcome="superseded",
                replacement_document_version_id=attempt.replacement_document_version_id,
                replacement_ingestion_job_id=attempt.replacement_ingestion_job_id,
            )

    def _read_expired_recovery_replay(
        self, *, operation_id: str, request_fingerprint: str, operation_kind: str
    ) -> RecoveryRetryScheduled | RecoveryFailedExhausted | None:
        with self._session_factory() as session:
            attempt = session.scalar(
                select(IngestionJobAttemptTable).where(
                    IngestionJobAttemptTable.transition_operation_kind == operation_kind,
                    IngestionJobAttemptTable.transition_operation_id == operation_id,
                )
            )
            if attempt is None:
                return None
            if attempt.transition_request_fingerprint != request_fingerprint:
                raise CoordinationInvariantError("transition operation ID was reused incompatibly")
            attempt_ref = AttemptRef(
                job_id=attempt.ingestion_job_id, attempt_number=attempt.attempt_number
            )
            if (
                attempt.closure_cause != FailureCauseV1.LEASE_EXPIRED.value
                or attempt.failure_cause != FailureCauseV1.LEASE_EXPIRED.value
            ):
                raise CoordinationInvariantError("transition replay has no expired-recovery result")
            if (
                attempt.disposition == "retry_scheduled"
                and attempt.retry_next_attempt_at is not None
            ):
                return RecoveryRetryScheduled(
                    attempt=attempt_ref, next_attempt_at=attempt.retry_next_attempt_at
                )
            if attempt.disposition == "failed" and attempt.failure_reason == "retry_exhausted":
                return RecoveryFailedExhausted(attempt=attempt_ref)
            raise CoordinationInvariantError("expired-recovery replay has no persisted disposition")

    @staticmethod
    def _is_claim_eligible(job: IngestionJobTable, database_now: datetime) -> bool:
        return job.status == "queued" or (
            job.status == "retry_scheduled"
            and job.next_attempt_at is not None
            and job.next_attempt_at <= database_now
        )

    @staticmethod
    def _owns_current_unexpired_attempt(
        job: IngestionJobTable,
        claim: ClaimedAttempt,
        database_now: datetime,
    ) -> bool:
        return PostgresIngestionJobStore._owns_current_unexpired_token(
            job, claim.token, database_now
        )

    @staticmethod
    def _owns_current_unexpired_token(
        job: IngestionJobTable,
        token: FencingToken,
        database_now: datetime,
    ) -> bool:
        return (
            job.status == "processing"
            and job.worker_id == token.worker_id
            and job.lease_version == token.lease_version
            and job.current_attempt_number == token.attempt_number
            and job.lease_expires_at is not None
            and database_now < job.lease_expires_at
        )

    @staticmethod
    def _token(
        *, job_id: str, attempt_number: int, worker_id: str, lease_version: int
    ) -> FencingToken:
        return FencingToken(
            job_id=job_id,
            attempt_number=attempt_number,
            worker_id=worker_id,
            lease_version=lease_version,
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
