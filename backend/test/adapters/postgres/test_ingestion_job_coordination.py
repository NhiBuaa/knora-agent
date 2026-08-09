from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    IdempotencyRecordTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    WorkspaceTable,
)
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    CoordinationInvariantError,
    FailedTerminal,
    FailureCauseV1,
    Fenced,
    FinalizationApplied,
    HandlerFailureKindV1,
    ProcessIngestionJob,
    TransitionOperationId,
    WorkFailed,
)
from knora.ingestion.jobs import PdfSubmissionConfiguration, PreparedPdfSubmission
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration


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


@dataclass
class DatabaseLockProbeHandler:
    job_id: str

    def execute(self, work) -> WorkFailed:
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


def test_run_once_releases_claim_transaction_before_handler_work() -> None:
    store, job_id = submit_queued_job()
    processor = ProcessIngestionJob(
        store=store,
        handler=DatabaseLockProbeHandler(job_id=job_id),
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
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
    with pytest.raises(CoordinationInvariantError, match="already applied"):
        store.claim_next_attempt(
            operation_id=operation_id,
            worker_id="worker-a",
            timing=AttemptTimingV1.standard(),
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
