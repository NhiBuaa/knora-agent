"""Real persistence recovery for lexical jobs; receipts here are structural fixtures."""

from uuid import uuid4

import pytest
import test_s2_two_job_transactions as transactions
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    LexicalHeadTable,
    WorkspaceTable,
)
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    ExpiredAttemptObservation,
    FailureCauseV1,
    Fenced,
    FinalizationApplied,
    InvalidTransition,
    RecoveryRetryScheduled,
    ScheduleRetry,
    TransitionOperationId,
)
from knora.ingestion.search_indexing import LexicalIndexSuccess, StageReceipt

extraction_job = transactions.extraction_job


@pytest.fixture
def loaded_index_job(extraction_job):
    store, extraction_claim, extraction_success = extraction_job
    assert isinstance(
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=extraction_claim,
            success=extraction_success,
        ),
        FinalizationApplied,
    )
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="s2-before-crash",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    assert claim.work.derivation_kind == "lexical_index"
    generation = PostgresSearchIndexStore(SessionFactory).load_generation(claim.work).generation
    success = LexicalIndexSuccess(
        generation,
        StageReceipt(generation.generation_id, 1, generation.content_digest()),
    )
    return store, claim, success


def recover_expired_index(store, old_claim):
    with SessionFactory.begin() as session:
        expired_at = session.scalar(select(func.clock_timestamp() - text("interval '1 second'")))
        job = session.get(IngestionJobTable, old_claim.token.job_id)
        job.lease_expires_at = expired_at
        observation = ExpiredAttemptObservation(
            job.id,
            old_claim.token.attempt_number,
            old_claim.token.worker_id,
            old_claim.token.lease_version,
            job.attempt_count,
            job.max_attempts,
            expired_at,
        )
    operation = TransitionOperationId(uuid4().hex)
    failure = CanonicalFailureV1(
        FailureCauseV1.LEASE_EXPIRED, "lease_expired", None, "failure-causes-v1", "cause-mapping-v1"
    )
    decision = ScheduleRetry(delay_microseconds=0, window_upper_bound_microseconds=5_000_000)
    recovered = store.apply_expired_recovery(
        operation_id=operation, observation=observation, failure=failure, decision=decision
    )
    assert isinstance(recovered, RecoveryRetryScheduled)
    assert (
        store.apply_expired_recovery(
            operation_id=operation, observation=observation, failure=failure, decision=decision
        )
        == recovered
    )
    replacement = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="s2-after-crash",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(replacement, ClaimedAttempt)
    assert replacement.token.job_id == old_claim.token.job_id
    assert replacement.token.attempt_number == 2
    return replacement


def test_expired_index_attempt_cannot_publish_after_recovery(loaded_index_job):
    store, old_claim, success = loaded_index_job
    replacement = recover_expired_index(store, old_claim)
    assert replacement.work.lexical_generation_id == success.generation.generation_id
    assert isinstance(
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex), claim=old_claim, success=success
        ),
        InvalidTransition,
    )
    with SessionFactory() as session:
        assert (
            session.get(LexicalHeadTable, old_claim.work.document_id).active_generation_id is None
        )
    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex), claim=replacement, success=success
    )
    assert isinstance(result, FinalizationApplied) and result.outcome == "succeeded"
    with SessionFactory() as session:
        head = session.get(LexicalHeadTable, old_claim.work.document_id)
        assert head.active_generation_id == success.generation.generation_id
        attempts = session.scalars(
            select(IngestionJobAttemptTable)
            .where(IngestionJobAttemptTable.ingestion_job_id == old_claim.token.job_id)
            .order_by(IngestionJobAttemptTable.attempt_number)
        ).all()
        assert [(a.attempt_number, a.disposition) for a in attempts] == [
            (1, "retry_scheduled"),
            (2, "succeeded"),
        ]


@pytest.mark.parametrize("change", ["source_switch", "document_cycle", "workspace_cycle"])
def test_loaded_index_job_cannot_activate_after_source_change(loaded_index_job, change):
    store, claim, success = loaded_index_job
    with SessionFactory.begin() as session:
        document = session.get(DocumentTable, claim.work.document_id)
        if change == "source_switch":
            replacement = DocumentVersionTable(
                id=str(uuid4()), document_id=document.id, version_number=2
            )
            session.add(replacement)
            session.flush()
            document.current_document_version_id = replacement.id
        elif change == "document_cycle":
            # An archive/unarchive cycle leaves archived=false and advances revision twice.
            document.revision += 2
        else:
            session.get(WorkspaceTable, claim.work.workspace_id).revision += 2
    operation = TransitionOperationId(uuid4().hex)
    result = store.finalize_success(operation_id=operation, claim=claim, success=success)
    assert isinstance(result, FinalizationApplied) and result.outcome == "superseded"
    assert store.finalize_success(operation_id=operation, claim=claim, success=success) == result
    with SessionFactory() as session:
        assert session.get(LexicalHeadTable, claim.work.document_id).active_generation_id is None
        job = session.get(IngestionJobTable, claim.token.job_id)
        assert job.status == "superseded"
        assert job.terminal_outcome_code == "stale_derivation_snapshot"


def test_index_commit_with_lost_response_reconciles_without_second_activation(
    loaded_index_job, monkeypatch
):
    store, claim, success = loaded_index_job
    original = store._coordination_store._finalize_lexical_index_once

    def lose_response(**kwargs):
        assert isinstance(original(**kwargs), FinalizationApplied)
        raise OperationalError("commit response lost", {}, RuntimeError("connection lost"))

    monkeypatch.setattr(store._coordination_store, "_finalize_lexical_index_once", lose_response)
    operation = TransitionOperationId(uuid4().hex)
    result = store.finalize_success(operation_id=operation, claim=claim, success=success)
    assert isinstance(result, FinalizationApplied) and result.outcome == "succeeded"
    assert store.finalize_success(operation_id=operation, claim=claim, success=success) == result
    with SessionFactory() as session:
        head = session.get(LexicalHeadTable, claim.work.document_id)
        assert head.active_generation_id == success.generation.generation_id
        assert head.revision == 1
        job = session.get(IngestionJobTable, claim.token.job_id)
        assert job.attempt_count == 1 and job.status == "succeeded"


def test_final_lease_guard_rolls_back_tentative_activation(loaded_index_job, monkeypatch):
    store, claim, success = loaded_index_job
    monkeypatch.setattr(
        store._coordination_store, "_finalize_pdf_job_if_current_and_live", lambda **kwargs: False
    )
    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex), claim=claim, success=success
    )
    assert isinstance(result, Fenced)
    with SessionFactory() as session:
        head = session.get(LexicalHeadTable, claim.work.document_id)
        assert head.active_generation_id is None
        assert head.desired_generation_id == success.generation.generation_id
        job = session.get(IngestionJobTable, claim.token.job_id)
        attempt = session.get(
            IngestionJobAttemptTable, (claim.token.job_id, claim.token.attempt_number)
        )
        assert job.status == "processing" and attempt.closed_at is None
