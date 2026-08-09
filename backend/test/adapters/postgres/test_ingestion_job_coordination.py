from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError

from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    IdempotencyRecordTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.ingestion.job_processing import (
    AttemptRef,
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimLeaseLost,
    ClaimOperationId,
    CoordinationInvariantError,
    CoordinationOutcomeIndeterminate,
    ExpiredAttemptObservation,
    FailedTerminal,
    FailTerminal,
    FailureCauseV1,
    Fenced,
    FinalizationApplied,
    HandlerFailureKindV1,
    HeartbeatApplied,
    HeartbeatOperationId,
    InvalidTransition,
    NoEligibleClaim,
    NotExpired,
    ProcessIngestionJob,
    RecoveryFailedExhausted,
    RecoveryRetryScheduled,
    RetryExhausted,
    RetryPolicyV1,
    RetryScheduleApplied,
    ScheduleRetry,
    StaleObservation,
    TransitionOperationId,
    WorkFailed,
    WorkSuperseded,
)
from knora.ingestion.jobs import PdfSubmissionConfiguration, PreparedPdfSubmission
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration


def clear_coordination_jobs() -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text("TRUNCATE TABLE idempotency_records, ingestion_job_attempts, ingestion_jobs")
        )


def submit_queued_job() -> tuple[PostgresIngestionJobStore, str]:
    with SessionFactory.begin() as session:
        queued_job_ids = select(IngestionJobTable.id).where(IngestionJobTable.status == "queued")
        session.execute(
            delete(IdempotencyRecordTable).where(
                IdempotencyRecordTable.ingestion_job_id.in_(queued_job_ids)
            )
        )
        session.execute(delete(IngestionJobTable).where(IngestionJobTable.status == "queued"))

    workspace_id = f"coordination-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Worker coordination"))
    configuration = PdfSubmissionConfiguration(
        parser_configuration_id="pdf-parser-pypdf-m2-v1",
        normalizer_configuration_id="pdf-normalizer-m2-v1",
        chunking_configuration=ChunkingConfiguration(
            id="chunking-m2-pdf-v1",
            parser_version="pypdf-baseline-v1",
            chunker_version="page-block-v1",
            tokenizer_name="cl100k_base",
            tokenizer_version="tiktoken-0.12.0",
            target_tokens=500,
            overlap_tokens=75,
            max_tokens=650,
        ),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    raw_sha256 = uuid4().hex + uuid4().hex
    prepared = PreparedPdfSubmission(
        workspace_id=workspace_id,
        source_key="support/refund-policy",
        source_name="refund-policy.pdf",
        source_object=ObjectMetadata(
            workspace_id=workspace_id,
            object_key=uuid4().hex,
            sha256=raw_sha256,
            byte_size=123,
            media_type="application/pdf",
        ),
        content_fingerprint="\n".join(
            (
                workspace_id,
                "support/refund-policy",
                raw_sha256,
                configuration.parser_configuration_id,
                configuration.normalizer_configuration_id,
                configuration.chunking_configuration.id,
                configuration.embedding_configuration.id,
            )
        ),
        idempotency_operation="submit_pdf",
        idempotency_key=uuid4().hex,
        idempotency_expires_at=datetime.now(UTC) + timedelta(hours=24),
        configuration=configuration,
    )
    store = PostgresIngestionJobStore(SessionFactory)
    return store, store.commit_pdf_submission(prepared).ingestion_job_id


def terminal_failure() -> CanonicalFailureV1:
    return CanonicalFailureV1(
        cause=FailureCauseV1.INVALID_INPUT,
        safe_code="invalid_input",
        failure_reason="terminal_input",
        cause_version="failure-causes-v1",
        mapping_version="cause-mapping-v1",
    )


def retryable_failure() -> CanonicalFailureV1:
    return CanonicalFailureV1(
        cause=FailureCauseV1.PROVIDER_TRANSIENT,
        safe_code="provider_transient",
        failure_reason=None,
        cause_version="failure-causes-v1",
        mapping_version="cause-mapping-v1",
    )


def exhausted_retryable_failure() -> CanonicalFailureV1:
    return CanonicalFailureV1(
        cause=FailureCauseV1.PROVIDER_TRANSIENT,
        safe_code="provider_transient",
        failure_reason="retry_exhausted",
        cause_version="failure-causes-v1",
        mapping_version="cause-mapping-v1",
    )


def expired_lease_failure() -> CanonicalFailureV1:
    return CanonicalFailureV1(
        cause=FailureCauseV1.LEASE_EXPIRED,
        safe_code="lease_expired",
        failure_reason=None,
        cause_version="failure-causes-v1",
        mapping_version="cause-mapping-v1",
    )


def replace_current_document_version(job_id: str) -> str:
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, job_id)
        assert job is not None
        document = session.get(DocumentTable, job.document_id)
        assert document is not None
        replacement = DocumentVersionTable(
            id=uuid4().hex,
            document_id=document.id,
            normalized_content=None,
            normalized_content_checksum=None,
            raw_sha256=uuid4().hex + uuid4().hex,
            media_type="application/pdf",
            version_number=2,
        )
        session.add(replacement)
        session.flush()
        document.current_document_version_id = replacement.id
        return replacement.id


def create_replacement_job(job_id: str, replacement_version_id: str) -> str:
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, job_id)
        assert job is not None
        version = session.get(DocumentVersionTable, replacement_version_id)
        assert version is not None
        source_object = OriginalSourceObjectTable(
            id=uuid4().hex,
            workspace_id=job.workspace_id,
            document_version_id=replacement_version_id,
            object_key=uuid4().hex,
            raw_sha256=version.raw_sha256,
            byte_size=123,
            media_type="application/pdf",
        )
        session.add(source_object)
        session.flush()
        replacement_job = IngestionJobTable(
            id=uuid4().hex,
            workspace_id=job.workspace_id,
            operation=job.operation,
            document_id=job.document_id,
            target_document_version_id=replacement_version_id,
            source_object_id=source_object.id,
            content_fingerprint=uuid4().hex,
            parser_configuration_id=job.parser_configuration_id,
            normalizer_configuration_id=job.normalizer_configuration_id,
            chunking_configuration_id=job.chunking_configuration_id,
            embedding_configuration_id=job.embedding_configuration_id,
            status="queued",
            attempt_count=0,
            max_attempts=job.max_attempts,
        )
        session.add(replacement_job)
        return replacement_job.id


@dataclass
class DatabaseLockProbeHandler:
    job_id: str

    def execute(self, work, cancellation) -> WorkFailed:
        with SessionFactory.begin() as session:
            session.execute(text("SET LOCAL lock_timeout = '250ms'"))
            session.scalar(
                select(IngestionJobTable)
                .where(IngestionJobTable.id == self.job_id)
                .with_for_update()
            )
        return WorkFailed(
            failure_kind=HandlerFailureKindV1.INVALID_INPUT,
            safe_code="invalid_input",
        )


@dataclass
class FixedOperationIds:
    def new_claim_id(self) -> ClaimOperationId:
        return ClaimOperationId(uuid4().hex)

    def new_transition_id(self) -> TransitionOperationId:
        return TransitionOperationId(uuid4().hex)


@dataclass
class ZeroRandom:
    bounds: list[int]

    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        self.bounds.append(upper_bound_microseconds)
        return 0


@dataclass(frozen=True)
class FakeSuccess:
    derivation_id: str


class CommitAcknowledgementFaults:
    """Inject one known transaction boundary outcome without changing the durable database."""

    def __init__(self, mode: str) -> None:
        self._mode = mode
        self._begin_calls = 0
        self._write_committed = False

    @contextmanager
    def begin(self):
        self._begin_calls += 1
        if self._mode == "not_committed" and self._begin_calls == 1:
            raise OperationalError("BEGIN", {}, RuntimeError("connection dropped before write"))
        if self._mode == "unresolved" and self._write_committed:
            raise OperationalError("READ_BACK", {}, RuntimeError("read-back unavailable"))
        with SessionFactory.begin() as session:
            yield session
        if self._mode in {"committed", "unresolved"} and self._begin_calls == 1:
            self._write_committed = True
            raise OperationalError("COMMIT", {}, RuntimeError("commit acknowledgement lost"))

    def __call__(self):
        if self._mode == "unresolved" and self._write_committed:
            raise OperationalError("READ_BACK", {}, RuntimeError("read-back unavailable"))
        return SessionFactory()


def mutate_with_acknowledgement_fault(operation: str, mode: str):
    store, job_id = submit_queued_job()
    faulted_store = PostgresIngestionJobStore(CommitAcknowledgementFaults(mode))
    if operation == "claim":
        return faulted_store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id="worker-a",
            timing=AttemptTimingV1.standard(),
        )

    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    operation_id = TransitionOperationId(uuid4().hex)
    if operation == "schedule_retry":
        return faulted_store.schedule_retry(
            operation_id=operation_id,
            claim=claim,
            failure=retryable_failure(),
            decision=ScheduleRetry(
                delay_microseconds=0,
                window_upper_bound_microseconds=5_000_000,
            ),
        )
    if operation == "terminal_failure":
        return faulted_store.finalize_terminal_failure(
            operation_id=operation_id,
            claim=claim,
            failure=terminal_failure(),
        )
    if operation == "superseded":
        replacement_version_id = replace_current_document_version(job_id)
        return faulted_store.finalize_superseded(
            operation_id=operation_id,
            claim=claim,
            outcome=WorkSuperseded(replacement_document_version_id=replacement_version_id),
        )

    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )
    observation = store.observe_expired_attempt()
    assert observation is not None
    return faulted_store.apply_expired_recovery(
        operation_id=operation_id,
        observation=observation,
        failure=expired_lease_failure(),
        decision=ScheduleRetry(
            delay_microseconds=0,
            window_upper_bound_microseconds=5_000_000,
        ),
    )


@pytest.mark.parametrize(
    ("operation", "result_type"),
    [
        ("claim", ClaimedAttempt),
        ("schedule_retry", RetryScheduleApplied),
        ("terminal_failure", FinalizationApplied),
        ("superseded", FinalizationApplied),
        ("expired_recovery", RecoveryRetryScheduled),
    ],
)
@pytest.mark.parametrize("mode", ["committed", "not_committed"])
def test_attempt_mutation_reconciles_commit_ack_loss_and_proven_non_commit(
    operation: str, result_type: type, mode: str
) -> None:
    assert isinstance(mutate_with_acknowledgement_fault(operation, mode), result_type)


@pytest.mark.parametrize(
    "operation", ["claim", "schedule_retry", "terminal_failure", "superseded", "expired_recovery"]
)
def test_attempt_mutation_raises_indeterminate_when_read_back_is_unavailable(
    operation: str,
) -> None:
    with pytest.raises(CoordinationOutcomeIndeterminate, match="indeterminate"):
        mutate_with_acknowledgement_fault(operation, "unresolved")


def test_claim_then_fenced_terminal_failure_closes_matching_attempt_atomically() -> None:
    store, job_id = submit_queued_job()

    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "processing"
        assert job.attempt_count == 1
        assert job.lease_version == 1
        assert job.current_attempt_number == 1
        assert job.worker_id == "worker-a"
        assert attempt.closed_at is None
        assert attempt.lease_version == 1
        assert attempt.initial_lease_expires_at == job.lease_expires_at

    result = store.finalize_terminal_failure(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        failure=terminal_failure(),
    )

    assert isinstance(result, FinalizationApplied)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "failed"
        assert job.worker_id is None
        assert job.lease_expires_at is None
        assert job.current_attempt_number is None
        assert job.terminal_at is not None
        assert job.failure_reason == "terminal_input"
        assert job.safe_failure_code == "invalid_input"
        assert attempt.closed_at is not None
        assert attempt.disposition == "failed"
        assert attempt.failure_cause == "invalid_input"
        assert attempt.failure_reason == "terminal_input"

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(safe_failure_code="changed")
        )


def test_finalize_superseded_closes_a_stale_target_attempt_atomically() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    replacement_version_id = replace_current_document_version(job_id)

    result = store.finalize_superseded(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        outcome=WorkSuperseded(replacement_document_version_id=replacement_version_id),
    )

    assert isinstance(result, FinalizationApplied)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "superseded"
        assert job.attempt_count == 1
        assert job.worker_id is None
        assert job.lease_expires_at is None
        assert job.current_attempt_number is None
        assert job.current_attempt_started_at is None
        assert job.current_attempt_deadline_at is None
        assert job.next_attempt_at is None
        assert job.terminal_at is not None
        assert job.failure_reason is None
        assert job.safe_failure_code is None
        assert job.terminal_outcome_code == "stale_document_version"
        assert job.replacement_document_version_id == replacement_version_id
        assert job.replacement_ingestion_job_id is None
        assert attempt.closed_at is not None
        assert attempt.disposition == "superseded"
        assert attempt.closure_cause == "stale_document_version"
        assert attempt.failure_cause is None
        assert attempt.failure_reason is None
        assert attempt.terminal_outcome_code == "stale_document_version"
        assert attempt.replacement_document_version_id == replacement_version_id


def test_postgres_store_rejects_unimplemented_generic_success_without_mutating() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    with pytest.raises(CoordinationInvariantError, match="Issue #18"):
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim,
            success=FakeSuccess(derivation_id="derivation-1"),
        )

    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "processing"
        assert attempt.closed_at is None


def test_superseded_replay_returns_the_exact_durable_result() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    operation_id = TransitionOperationId(uuid4().hex)
    outcome = WorkSuperseded(
        replacement_document_version_id=replace_current_document_version(job_id)
    )

    initial = store.finalize_superseded(
        operation_id=operation_id, claim=claim, outcome=outcome
    )
    replay = store.finalize_superseded(
        operation_id=operation_id, claim=claim, outcome=outcome
    )

    assert isinstance(initial, FinalizationApplied)
    assert replay == initial


def test_superseded_finalization_accepts_matching_replacement_identifiers() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    replacement_version_id = replace_current_document_version(job_id)
    replacement_job_id = create_replacement_job(job_id, replacement_version_id)
    replacement_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="replacement-worker",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(replacement_claim, ClaimedAttempt)
    assert replacement_claim.token.job_id == replacement_job_id
    assert isinstance(
        store.finalize_terminal_failure(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=replacement_claim,
            failure=terminal_failure(),
        ),
        FinalizationApplied,
    )

    result = store.finalize_superseded(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        outcome=WorkSuperseded(
            replacement_document_version_id=replacement_version_id,
            replacement_ingestion_job_id=replacement_job_id,
        ),
    )

    assert isinstance(result, FinalizationApplied)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.replacement_document_version_id == replacement_version_id
        assert job.replacement_ingestion_job_id == replacement_job_id
        assert attempt.replacement_document_version_id == replacement_version_id
        assert attempt.replacement_ingestion_job_id == replacement_job_id


def test_superseded_replay_rejects_an_incompatible_operation_binding() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    operation_id = TransitionOperationId(uuid4().hex)
    store.finalize_superseded(
        operation_id=operation_id,
        claim=claim,
        outcome=WorkSuperseded(
            replacement_document_version_id=replace_current_document_version(job_id)
        ),
    )

    with pytest.raises(CoordinationInvariantError, match="reused incompatibly"):
        store.finalize_superseded(
            operation_id=operation_id,
            claim=claim,
            outcome=WorkSuperseded(),
        )


def test_superseded_finalization_requires_a_stale_target_and_valid_replacements() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    assert store.finalize_superseded(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        outcome=WorkSuperseded(),
    ) == InvalidTransition()

    replacement_version_id = replace_current_document_version(job_id)
    _, unrelated_job_id = submit_queued_job()
    assert store.finalize_superseded(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        outcome=WorkSuperseded(
            replacement_document_version_id=replacement_version_id,
            replacement_ingestion_job_id=unrelated_job_id,
        ),
    ) == InvalidTransition()


def test_superseded_finalization_gives_fencing_precedence_over_stale_target() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    replacement_version_id = replace_current_document_version(job_id)
    with SessionFactory.begin() as session:
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=func.clock_timestamp() - text("interval '1 second'"))
        )

    assert store.finalize_superseded(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        outcome=WorkSuperseded(replacement_document_version_id=replacement_version_id),
    ) == Fenced()

    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "processing"
        assert attempt.closed_at is None


def test_heartbeat_renews_the_current_lease_without_rewriting_attempt_history() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    renewed = store.heartbeat(
        operation_id=HeartbeatOperationId(uuid4().hex),
        token=claim.token,
        lease_duration=timedelta(minutes=2),
    )

    assert isinstance(renewed, HeartbeatApplied)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.lease_version == claim.token.lease_version
        assert job.lease_expires_at == renewed.lease_expires_at
        assert job.last_heartbeat_operation_id is not None
        assert job.last_heartbeat_request_fingerprint is not None
        assert attempt.initial_lease_expires_at == claim.initial_lease_expires_at


def test_heartbeat_replay_returns_the_recorded_expiry_without_renewing_again() -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = HeartbeatOperationId(uuid4().hex)

    assert isinstance(claim, ClaimedAttempt)
    first = store.heartbeat(
        operation_id=operation_id,
        token=claim.token,
        lease_duration=timedelta(minutes=2),
    )
    replay = store.heartbeat(
        operation_id=operation_id,
        token=claim.token,
        lease_duration=timedelta(minutes=2),
    )

    assert isinstance(first, HeartbeatApplied)
    assert replay == first


def test_heartbeat_reconciles_an_acknowledgement_loss_with_the_same_operation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = HeartbeatOperationId(uuid4().hex)
    heartbeat_once = store._heartbeat_once
    operation_ids: list[HeartbeatOperationId] = []

    assert isinstance(claim, ClaimedAttempt)

    def lose_first_acknowledgement(**kwargs: object):
        operation_ids.append(kwargs["operation_id"])
        result = heartbeat_once(**kwargs)
        if len(operation_ids) == 1:
            raise OperationalError("heartbeat", {}, OSError("acknowledgement lost"))
        return result

    monkeypatch.setattr(store, "_heartbeat_once", lose_first_acknowledgement)

    reconciled = store.heartbeat(
        operation_id=operation_id,
        token=claim.token,
        lease_duration=timedelta(minutes=2),
    )

    assert isinstance(reconciled, HeartbeatApplied)
    assert operation_ids == [operation_id, operation_id]


def test_heartbeat_raises_indeterminate_after_an_unresolved_acknowledgement_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = HeartbeatOperationId(uuid4().hex)

    assert isinstance(claim, ClaimedAttempt)

    def lose_acknowledgement(**kwargs: object):
        raise OperationalError("heartbeat", {}, OSError("acknowledgement lost"))

    monkeypatch.setattr(store, "_heartbeat_once", lose_acknowledgement)

    with pytest.raises(CoordinationOutcomeIndeterminate) as error:
        store.heartbeat(
            operation_id=operation_id,
            token=claim.token,
            lease_duration=timedelta(minutes=2),
        )

    assert error.value.operation_id == operation_id
    assert error.value.attempt.job_id == claim.token.job_id
    assert error.value.attempt.attempt_number == claim.token.attempt_number


def test_heartbeat_replay_rejects_an_incompatible_operation_binding() -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = HeartbeatOperationId(uuid4().hex)

    assert isinstance(claim, ClaimedAttempt)
    store.heartbeat(
        operation_id=operation_id,
        token=claim.token,
        lease_duration=timedelta(minutes=2),
    )

    with pytest.raises(
        CoordinationInvariantError, match="heartbeat operation ID was reused incompatibly"
    ):
        store.heartbeat(
            operation_id=operation_id,
            token=replace(claim.token, worker_id="other-worker"),
            lease_duration=timedelta(minutes=2),
        )


def test_heartbeat_replay_rejects_a_different_lease_duration() -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = HeartbeatOperationId(uuid4().hex)

    assert isinstance(claim, ClaimedAttempt)
    store.heartbeat(
        operation_id=operation_id,
        token=claim.token,
        lease_duration=timedelta(minutes=2),
    )

    with pytest.raises(
        CoordinationInvariantError, match="heartbeat operation ID was reused incompatibly"
    ):
        store.heartbeat(
            operation_id=operation_id,
            token=claim.token,
            lease_duration=timedelta(minutes=1),
        )


def test_heartbeat_returns_fenced_for_a_definitely_stale_token() -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    assert store.heartbeat(
        operation_id=HeartbeatOperationId(uuid4().hex),
        token=replace(claim.token, worker_id="other-worker"),
        lease_duration=timedelta(minutes=2),
    ) == Fenced()

def test_schedule_retry_closes_current_attempt_with_one_database_time_anchor() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    transition_id = TransitionOperationId(uuid4().hex)
    result = store.schedule_retry(
        operation_id=transition_id,
        claim=claim,
        failure=retryable_failure(),
        decision=ScheduleRetry(
            delay_microseconds=5_000_000,
            window_upper_bound_microseconds=5_000_000,
        ),
    )

    assert isinstance(result, RetryScheduleApplied)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "retry_scheduled"
        assert job.worker_id is None
        assert job.lease_expires_at is None
        assert job.current_attempt_number is None
        assert job.current_attempt_started_at is None
        assert job.current_attempt_deadline_at is None
        assert job.next_attempt_at is not None
        assert attempt.closed_at is not None
        assert attempt.disposition == "retry_scheduled"
        assert attempt.failure_cause == "provider_transient"
        assert attempt.failure_reason is None
        assert attempt.retry_policy_version == "retry-policy-v1"
        assert attempt.retry_policy_result == "schedule_retry"
        assert attempt.retry_jitter_version == "full-jitter-v1"
        assert attempt.retry_window_upper_bound_microseconds == 5_000_000
        assert attempt.retry_delay_microseconds == 5_000_000
        assert attempt.retry_next_attempt_at == job.next_attempt_at
        assert attempt.transition_operation_id == transition_id
        assert attempt.transition_request_fingerprint is not None
        assert job.next_attempt_at - attempt.closed_at == timedelta(seconds=5)


def test_claim_accepts_only_due_retry_schedules_in_a_subsequent_transaction() -> None:
    clear_coordination_jobs()
    positive_store, _ = submit_queued_job()
    positive_claim = positive_store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-positive",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(positive_claim, ClaimedAttempt)
    positive_schedule = positive_store.schedule_retry(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=positive_claim,
        failure=retryable_failure(),
        decision=ScheduleRetry(
            delay_microseconds=5_000_000,
            window_upper_bound_microseconds=5_000_000,
        ),
    )
    assert isinstance(positive_schedule, RetryScheduleApplied)
    with SessionFactory() as session:
        assert positive_schedule.next_attempt_at > session.scalar(select(func.clock_timestamp()))

    immediate_positive_claim = positive_store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-positive",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(immediate_positive_claim, NoEligibleClaim)

    zero_store, zero_job_id = submit_queued_job()
    zero_claim = zero_store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-zero",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(zero_claim, ClaimedAttempt)
    assert isinstance(
        zero_store.schedule_retry(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=zero_claim,
            failure=retryable_failure(),
            decision=ScheduleRetry(
                delay_microseconds=0,
                window_upper_bound_microseconds=5_000_000,
            ),
        ),
        RetryScheduleApplied,
    )

    next_claim = zero_store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-zero",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(next_claim, ClaimedAttempt)
    assert next_claim.token.attempt_number == 2
    assert next_claim.token.lease_version == 2
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, zero_job_id)
        attempts = session.scalars(
            select(IngestionJobAttemptTable)
            .where(IngestionJobAttemptTable.ingestion_job_id == zero_job_id)
            .order_by(IngestionJobAttemptTable.attempt_number)
        ).all()
        assert job.status == "processing"
        assert job.attempt_count == 2
        assert job.next_attempt_at is None
        assert [attempt.attempt_number for attempt in attempts] == [1, 2]
        assert attempts[0].closed_at is not None
        assert attempts[1].closed_at is None


def test_schedule_retry_replay_returns_the_persisted_disposition_and_timestamp() -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = TransitionOperationId(uuid4().hex)
    decision = ScheduleRetry(
        delay_microseconds=5_000_000,
        window_upper_bound_microseconds=5_000_000,
    )

    assert isinstance(claim, ClaimedAttempt)
    initial = store.schedule_retry(
        operation_id=operation_id,
        claim=claim,
        failure=retryable_failure(),
        decision=decision,
    )
    replay = store.schedule_retry(
        operation_id=operation_id,
        claim=claim,
        failure=retryable_failure(),
        decision=decision,
    )

    assert isinstance(initial, RetryScheduleApplied)
    assert replay == initial


def test_fourth_retryable_attempt_finalizes_exhausted_without_attempt_five() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-exhaustion",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    random = ZeroRandom(bounds=[])
    policy = RetryPolicyV1(random)

    for attempt_number in (1, 2, 3):
        assert claim.token.attempt_number == attempt_number
        decision = policy.decide(
            FailureCauseV1.PROVIDER_TRANSIENT,
            attempt_count=attempt_number,
            max_attempts=4,
        )
        assert isinstance(decision, ScheduleRetry)
        assert isinstance(
            store.schedule_retry(
                operation_id=TransitionOperationId(uuid4().hex),
                claim=claim,
                failure=retryable_failure(),
                decision=decision,
            ),
            RetryScheduleApplied,
        )
        claim = store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id="worker-exhaustion",
            timing=AttemptTimingV1.standard(),
        )
        assert isinstance(claim, ClaimedAttempt)

    exhausted = policy.decide(
        FailureCauseV1.PROVIDER_TRANSIENT,
        attempt_count=4,
        max_attempts=4,
    )
    assert exhausted == RetryExhausted()

    terminal = store.finalize_terminal_failure(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        failure=exhausted_retryable_failure(),
        decision=exhausted,
    )

    assert isinstance(terminal, FinalizationApplied)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempts = session.scalars(
            select(IngestionJobAttemptTable)
            .where(IngestionJobAttemptTable.ingestion_job_id == job_id)
            .order_by(IngestionJobAttemptTable.attempt_number)
        ).all()
        assert job.status == "failed"
        assert job.attempt_count == 4
        assert job.failure_reason == "retry_exhausted"
        assert job.next_attempt_at is None
        assert [attempt.attempt_number for attempt in attempts] == [1, 2, 3, 4]
        assert [attempt.retry_policy_result for attempt in attempts] == [
            "schedule_retry",
            "schedule_retry",
            "schedule_retry",
            "retry_exhausted",
        ]
        assert attempts[3].closure_cause == "provider_transient"
        assert attempts[3].failure_reason == "retry_exhausted"
    assert random.bounds == [5_000_000, 30_000_000, 120_000_000]

    assert isinstance(
        store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id="worker-exhaustion",
            timing=AttemptTimingV1.standard(),
        ),
        NoEligibleClaim,
    )


def test_run_once_releases_claim_transaction_before_handler_work() -> None:
    store, job_id = submit_queued_job()
    processor = ProcessIngestionJob(
        store=store,
        handler=DatabaseLockProbeHandler(job_id=job_id),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(ZeroRandom(bounds=[])),
        runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
    )

    result = processor.run_once("worker-a")

    assert isinstance(result, FailedTerminal)
    assert result.attempt.job_id == job_id
    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            delete(IngestionJobAttemptTable).where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
        )


def test_simultaneous_claims_have_one_winner_and_stale_finalization_is_fenced() -> None:
    store, job_id = submit_queued_job()

    def claim(worker_id: str):
        return store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id=worker_id,
            timing=AttemptTimingV1.standard(),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(claim, ("worker-a", "worker-b")))

    claims = [result for result in (first, second) if isinstance(result, ClaimedAttempt)]
    assert len(claims) == 1
    claim_result = claims[0]
    stale = replace(
        claim_result,
        token=replace(claim_result.token, worker_id="stale-worker"),
    )

    fenced = store.finalize_terminal_failure(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=stale,
        failure=terminal_failure(),
    )

    assert isinstance(fenced, Fenced)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempts = session.scalars(
            select(IngestionJobAttemptTable).where(
                IngestionJobAttemptTable.ingestion_job_id == job_id
            )
        ).all()
        assert job.status == "processing"
        assert job.attempt_count == 1
        assert len(attempts) == 1
        assert attempts[0].closed_at is None


def test_claim_operation_id_is_bound_to_its_immutable_request() -> None:
    store, _ = submit_queued_job()
    operation_id = ClaimOperationId(uuid4().hex)

    claim = store.claim_next_attempt(
        operation_id=operation_id,
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    assert (
        store.claim_next_attempt(
            operation_id=operation_id,
            worker_id="worker-a",
            timing=AttemptTimingV1.standard(),
        )
        == claim
    )
    with pytest.raises(CoordinationInvariantError, match="reused incompatibly"):
        store.claim_next_attempt(
            operation_id=operation_id,
            worker_id="worker-b",
            timing=AttemptTimingV1.standard(),
        )
    with SessionFactory() as session:
        attempt = session.get(
            IngestionJobAttemptTable,
            (claim.token.job_id, claim.token.attempt_number),
        )
        assert attempt.claim_operation_id == operation_id
        assert attempt.claim_request_fingerprint == "worker-a\n120000000\n900000000"


def test_claim_replay_returns_the_current_executable_attempt() -> None:
    store, _ = submit_queued_job()
    operation_id = ClaimOperationId(uuid4().hex)

    initial = store.claim_next_attempt(
        operation_id=operation_id,
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    replay = store.claim_next_attempt(
        operation_id=operation_id,
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(initial, ClaimedAttempt)
    assert replay == initial


def test_claim_replay_reports_lease_loss_without_claiming_another_job() -> None:
    store, job_id = submit_queued_job()
    operation_id = ClaimOperationId(uuid4().hex)
    claim = store.claim_next_attempt(
        operation_id=operation_id,
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory.begin() as session:
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=func.clock_timestamp() - text("interval '1 second'"))
        )

    replay = store.claim_next_attempt(
        operation_id=operation_id,
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert replay == ClaimLeaseLost(AttemptRef(job_id=job_id, attempt_number=1))
    with SessionFactory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(IngestionJobAttemptTable)
                .where(IngestionJobAttemptTable.ingestion_job_id == job_id)
            )
            == 1
        )


def test_noop_claim_keeps_operation_absent_so_eligibility_can_be_retried() -> None:
    clear_coordination_jobs()
    store = PostgresIngestionJobStore(SessionFactory)
    operation_id = ClaimOperationId(uuid4().hex)

    assert (
        store.claim_next_attempt(
            operation_id=operation_id,
            worker_id="worker-a",
            timing=AttemptTimingV1.standard(),
        )
        == NoEligibleClaim()
    )
    submit_queued_job()

    retry = store.claim_next_attempt(
        operation_id=operation_id,
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(retry, ClaimedAttempt)


def test_expired_lease_fences_terminal_finalization() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )

    result = store.finalize_terminal_failure(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        failure=terminal_failure(),
    )

    assert isinstance(result, Fenced)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "processing"
        assert attempt.closed_at is None


def test_expired_observation_applies_scheduled_recovery_before_a_separate_claim() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-expired",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )

    observation = store.observe_expired_attempt()

    assert observation is not None
    assert observation.job_id == job_id
    assert observation.attempt_number == 1
    assert observation.worker_id == "worker-expired"
    assert observation.lease_version == 1
    assert observation.attempt_count == 1
    assert observation.max_attempts == 4

    recovery = store.apply_expired_recovery(
        operation_id=TransitionOperationId(uuid4().hex),
        observation=observation,
        failure=expired_lease_failure(),
        decision=ScheduleRetry(
            delay_microseconds=0,
            window_upper_bound_microseconds=5_000_000,
        ),
    )

    assert isinstance(recovery, RecoveryRetryScheduled)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "retry_scheduled"
        assert job.worker_id is None
        assert job.lease_expires_at is None
        assert job.next_attempt_at == recovery.next_attempt_at
        assert attempt.closed_at is not None
        assert attempt.disposition == "retry_scheduled"
        assert attempt.closure_cause == "lease_expired"
        assert attempt.failure_cause == "lease_expired"
        assert attempt.retry_policy_result == "schedule_retry"

    replacement = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-replacement",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(replacement, ClaimedAttempt)
    assert replacement.token.attempt_number == 2


def test_expired_recovery_replay_returns_the_persisted_disposition_and_timestamp() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-expired",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )
    observation = store.observe_expired_attempt()
    operation_id = TransitionOperationId(uuid4().hex)
    decision = ScheduleRetry(
        delay_microseconds=0,
        window_upper_bound_microseconds=5_000_000,
    )

    assert observation is not None
    initial = store.apply_expired_recovery(
        operation_id=operation_id,
        observation=observation,
        failure=expired_lease_failure(),
        decision=decision,
    )
    replay = store.apply_expired_recovery(
        operation_id=operation_id,
        observation=observation,
        failure=expired_lease_failure(),
        decision=decision,
    )

    assert isinstance(initial, RecoveryRetryScheduled)
    assert replay == initial


def test_expired_recovery_rejects_a_non_recovery_policy_decision() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-expired",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )
    observation = store.observe_expired_attempt()
    assert observation is not None

    with pytest.raises(CoordinationInvariantError, match="ScheduleRetry or RetryExhausted"):
        store.apply_expired_recovery(
            operation_id=TransitionOperationId(uuid4().hex),
            observation=observation,
            failure=expired_lease_failure(),
            decision=FailTerminal(),  # type: ignore[arg-type]
        )

    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "processing"
        assert attempt.closed_at is None


def test_expired_recovery_revalidates_the_exact_observed_lease_expiry() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-expired",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )
    observation = store.observe_expired_attempt()
    assert observation is not None

    with SessionFactory.begin() as session:
        renewed_at = session.scalar(select(func.clock_timestamp() + text("interval '2 minutes'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=renewed_at)
        )

    recovery = store.apply_expired_recovery(
        operation_id=TransitionOperationId(uuid4().hex),
        observation=observation,
        failure=expired_lease_failure(),
        decision=ScheduleRetry(
            delay_microseconds=0,
            window_upper_bound_microseconds=5_000_000,
        ),
    )

    assert recovery == StaleObservation()
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "processing"
        assert attempt.closed_at is None


def test_recovery_reports_not_expired_for_a_current_observation() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-current",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    current_observation = claim
    recovery = store.apply_expired_recovery(
        operation_id=TransitionOperationId(uuid4().hex),
        observation=ExpiredAttemptObservation(
            job_id=job_id,
            attempt_number=current_observation.token.attempt_number,
            worker_id=current_observation.token.worker_id,
            lease_version=current_observation.token.lease_version,
            attempt_count=current_observation.attempt_count,
            max_attempts=current_observation.max_attempts,
            lease_expires_at=current_observation.initial_lease_expires_at,
        ),
        failure=expired_lease_failure(),
        decision=ScheduleRetry(
            delay_microseconds=0,
            window_upper_bound_microseconds=5_000_000,
        ),
    )

    assert recovery == NotExpired()
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "processing"
        assert attempt.closed_at is None


def test_expired_final_attempt_recovers_to_retry_exhausted_without_attempt_two() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-expired",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(max_attempts=1, lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )
    observation = store.observe_expired_attempt()
    assert observation is not None

    operation_id = TransitionOperationId(uuid4().hex)
    recovery = store.apply_expired_recovery(
        operation_id=operation_id,
        observation=observation,
        failure=expired_lease_failure(),
        decision=RetryExhausted(),
    )
    replay = store.apply_expired_recovery(
        operation_id=operation_id,
        observation=observation,
        failure=expired_lease_failure(),
        decision=RetryExhausted(),
    )

    assert isinstance(recovery, RecoveryFailedExhausted)
    assert replay == recovery
    assert isinstance(
        store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id="worker-replacement",
            timing=AttemptTimingV1.standard(),
        ),
        NoEligibleClaim,
    )
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        assert job.status == "failed"
        assert job.attempt_count == 1
        assert job.failure_reason == "retry_exhausted"
        assert attempt.disposition == "failed"
        assert attempt.closure_cause == "lease_expired"
        assert attempt.failure_cause == "lease_expired"
        assert attempt.retry_policy_result == "retry_exhausted"


def test_simultaneous_recovery_has_one_winner_and_one_stale_observation() -> None:
    clear_coordination_jobs()
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-expired",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(lease_expires_at=expired_at)
        )
        session.execute(
            update(IngestionJobAttemptTable)
            .where(
                IngestionJobAttemptTable.ingestion_job_id == job_id,
                IngestionJobAttemptTable.attempt_number == 1,
            )
            .values(initial_lease_expires_at=expired_at)
        )
    observation = store.observe_expired_attempt()
    assert observation is not None

    def recover() -> object:
        return store.apply_expired_recovery(
            operation_id=TransitionOperationId(uuid4().hex),
            observation=observation,
            failure=expired_lease_failure(),
            decision=ScheduleRetry(
                delay_microseconds=0,
                window_upper_bound_microseconds=5_000_000,
            ),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(lambda _: recover(), range(2)))

    assert sum(isinstance(result, RecoveryRetryScheduled) for result in (first, second)) == 1
    assert sum(isinstance(result, StaleObservation) for result in (first, second)) == 1
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempts = session.scalars(
            select(IngestionJobAttemptTable)
            .where(IngestionJobAttemptTable.ingestion_job_id == job_id)
            .order_by(IngestionJobAttemptTable.attempt_number)
        ).all()
        assert job.status == "retry_scheduled"
        assert [attempt.closed_at is not None for attempt in attempts] == [True]


def test_commit_rejects_current_projection_that_does_not_match_open_attempt() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            update(IngestionJobTable)
            .where(IngestionJobTable.id == job_id)
            .values(worker_id="worker-b")
        )


def test_database_rejects_a_second_open_attempt_for_one_job() -> None:
    store, job_id = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(claim, ClaimedAttempt)
    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.add(
            IngestionJobAttemptTable(
                ingestion_job_id=job_id,
                attempt_number=2,
                worker_id="worker-b",
                lease_version=2,
                attempt_started_at=claim.attempt_started_at,
                deadline_at=claim.deadline_at,
                initial_lease_expires_at=claim.initial_lease_expires_at,
                claim_operation_id=uuid4().hex,
                claim_request_fingerprint="other-claim",
            )
        )


def test_transition_operation_id_rejects_a_different_terminal_request() -> None:
    store, _ = submit_queued_job()
    first_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    transition_id = TransitionOperationId(uuid4().hex)

    assert isinstance(first_claim, ClaimedAttempt)
    assert isinstance(
        store.finalize_terminal_failure(
            operation_id=transition_id,
            claim=first_claim,
            failure=terminal_failure(),
        ),
        FinalizationApplied,
    )
    second_store, _ = submit_queued_job()
    second_claim = second_store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-b",
        timing=AttemptTimingV1.standard(),
    )

    assert isinstance(second_claim, ClaimedAttempt)
    with pytest.raises(CoordinationInvariantError, match="reused incompatibly"):
        second_store.finalize_terminal_failure(
            operation_id=transition_id,
            claim=second_claim,
            failure=terminal_failure(),
        )


def test_terminal_failure_replay_returns_the_persisted_disposition() -> None:
    store, _ = submit_queued_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = TransitionOperationId(uuid4().hex)

    assert isinstance(claim, ClaimedAttempt)
    initial = store.finalize_terminal_failure(
        operation_id=operation_id,
        claim=claim,
        failure=terminal_failure(),
    )
    replay = store.finalize_terminal_failure(
        operation_id=operation_id,
        claim=claim,
        failure=terminal_failure(),
    )

    assert isinstance(initial, FinalizationApplied)
    assert replay == initial


def test_transition_operation_ids_are_unique_within_kind_not_across_kinds() -> None:
    first_store, _ = submit_queued_job()
    first_claim = first_store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(first_claim, ClaimedAttempt)
    operation_id = TransitionOperationId(uuid4().hex)
    assert isinstance(
        first_store.schedule_retry(
            operation_id=operation_id,
            claim=first_claim,
            failure=retryable_failure(),
            decision=ScheduleRetry(
                delay_microseconds=0,
                window_upper_bound_microseconds=5_000_000,
            ),
        ),
        RetryScheduleApplied,
    )

    second_store, _ = submit_queued_job()
    second_claim = second_store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-b",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(second_claim, ClaimedAttempt)
    assert isinstance(
        second_store.finalize_terminal_failure(
            operation_id=operation_id,
            claim=second_claim,
            failure=terminal_failure(),
        ),
        FinalizationApplied,
    )
