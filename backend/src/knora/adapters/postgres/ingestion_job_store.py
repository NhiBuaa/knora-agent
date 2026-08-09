"""PostgreSQL adapter for durable Ingestion Job submission."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    IngestionJobAttemptTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.job_processing import (
    AttemptRef,
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    ClaimResult,
    CoordinationInvariantError,
    Fenced,
    FencingToken,
    FinalizationApplied,
    FinalizationResult,
    IngestionWork,
    InvalidTransition,
    NoEligibleClaim,
    TransitionOperationId,
)
from knora.ingestion.jobs import (
    PdfSubmissionResult,
    PdfSubmissionStore,
    PreparedPdfSubmission,
)
from knora.ingestion.object_store import ObjectMetadata


def _duration_microseconds(value: timedelta) -> int:
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


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

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimResult:
        """Atomically claim at most one queued job and insert its first open attempt."""

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
                raise CoordinationInvariantError("claim operation ID was already applied")

            job = session.scalar(
                select(IngestionJobTable)
                .where(
                    IngestionJobTable.status == "queued",
                    IngestionJobTable.attempt_count < IngestionJobTable.max_attempts,
                )
                .order_by(IngestionJobTable.created_at, IngestionJobTable.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return NoEligibleClaim()

            database_now = self._database_now(session)
            if job.status != "queued" or job.attempt_count >= job.max_attempts:
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
            job.worker_id = worker_id
            job.lease_expires_at = lease_expires_at
            job.current_attempt_number = attempt_number
            job.current_attempt_started_at = database_now
            job.current_attempt_deadline_at = deadline_at
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

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
    ) -> FinalizationResult:
        """Fenced `processing -> failed` plus matching immutable attempt closure."""

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
            transition_fingerprint = self._transition_fingerprint(claim=claim, failure=failure)
            existing = session.scalar(
                select(IngestionJobAttemptTable).where(
                    IngestionJobAttemptTable.transition_operation_id == transition_operation_id
                )
            )
            if existing is not None:
                if existing.transition_request_fingerprint != transition_fingerprint:
                    raise CoordinationInvariantError(
                        "transition operation ID was reused incompatibly"
                    )
                raise CoordinationInvariantError("transition operation ID was already applied")

            attempt.closed_at = database_now
            attempt.disposition = "failed"
            attempt.closure_cause = failure.cause.value
            attempt.failure_cause = failure.cause.value
            attempt.failure_cause_version = failure.cause_version
            attempt.cause_mapping_version = failure.mapping_version
            attempt.safe_failure_code = failure.safe_code
            attempt.failure_reason = failure.failure_reason
            attempt.transition_operation_id = transition_operation_id
            attempt.transition_request_fingerprint = transition_fingerprint

            job.status = "failed"
            job.worker_id = None
            job.lease_expires_at = None
            job.current_attempt_number = None
            job.current_attempt_started_at = None
            job.current_attempt_deadline_at = None
            job.terminal_at = database_now
            job.failure_reason = failure.failure_reason
            job.safe_failure_code = failure.safe_code
            session.flush()
            return FinalizationApplied(
                attempt=AttemptRef(
                    job_id=claim.token.job_id,
                    attempt_number=claim.token.attempt_number,
                )
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
    def _transition_fingerprint(*, claim: ClaimedAttempt, failure: CanonicalFailureV1) -> str:
        return "\n".join(
            (
                claim.token.job_id,
                str(claim.token.attempt_number),
                claim.token.worker_id,
                str(claim.token.lease_version),
                failure.cause.value,
                failure.safe_code,
                failure.failure_reason,
                failure.cause_version,
                failure.mapping_version,
            )
        )

    @staticmethod
    def _owns_current_unexpired_attempt(
        job: IngestionJobTable,
        claim: ClaimedAttempt,
        database_now: datetime,
    ) -> bool:
        return (
            job.status == "processing"
            and job.worker_id == claim.token.worker_id
            and job.lease_version == claim.token.lease_version
            and job.current_attempt_number == claim.token.attempt_number
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
