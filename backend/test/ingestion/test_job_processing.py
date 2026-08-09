from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from knora.ingestion.job_processing import (
    AttemptRef,
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    FailedTerminal,
    FailureCauseV1,
    FencingToken,
    FinalizationApplied,
    HandlerFailureKindV1,
    IngestionWork,
    ProcessIngestionJob,
    TransitionOperationId,
    WorkFailed,
)


@dataclass
class RecordingStore:
    claim: ClaimedAttempt
    claims: list[tuple[ClaimOperationId, str, AttemptTimingV1]] = field(default_factory=list)
    finalizations: list[tuple[TransitionOperationId, ClaimedAttempt, CanonicalFailureV1]] = (
        field(default_factory=list)
    )

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimedAttempt:
        self.claims.append((operation_id, worker_id, timing))
        return self.claim

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
    ) -> FinalizationApplied:
        self.finalizations.append((operation_id, claim, failure))
        return FinalizationApplied(attempt=AttemptRef(job_id=claim.token.job_id, attempt_number=1))


@dataclass
class FailingHandler:
    received: list[IngestionWork] = field(default_factory=list)

    def execute(self, work: IngestionWork) -> WorkFailed:
        self.received.append(work)
        return WorkFailed(
            failure_kind=HandlerFailureKindV1.INVALID_INPUT,
            safe_code="invalid_input",
        )


@dataclass
class FixedOperationIds:
    claim_id: ClaimOperationId = ClaimOperationId("claim-op-1")
    transition_id: TransitionOperationId = TransitionOperationId("terminal-op-1")

    def new_claim_id(self) -> ClaimOperationId:
        return self.claim_id

    def new_transition_id(self) -> TransitionOperationId:
        return self.transition_id


def claimed_attempt() -> ClaimedAttempt:
    started = datetime(2026, 8, 9, 6, 0, tzinfo=UTC)
    return ClaimedAttempt(
        token=FencingToken(
            job_id="job-1",
            attempt_number=1,
            worker_id="worker-a",
            lease_version=1,
        ),
        work=IngestionWork(
            workspace_id="workspace-1",
            document_id="document-1",
            document_version_id="version-1",
            source_object_id="object-1",
            source_object_key="opaque/object-1",
            source_media_type="application/pdf",
            parser_configuration_id="parser-v1",
            normalizer_configuration_id="normalizer-v1",
            chunking_configuration_id="chunking-v1",
            embedding_configuration_id="embedding-v1",
        ),
        attempt_count=1,
        max_attempts=4,
        attempt_started_at=started,
        initial_lease_expires_at=started + timedelta(minutes=2),
        deadline_at=started + timedelta(minutes=15),
    )


def test_run_once_claims_then_fenced_finalizes_non_retryable_failure() -> None:
    claim = claimed_attempt()
    store = RecordingStore(claim=claim)
    handler = FailingHandler()
    processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=FixedOperationIds(),
        timing=AttemptTimingV1.standard(),
    )

    result = processor.run_once("worker-a")

    assert result == FailedTerminal(
        attempt=AttemptRef(job_id="job-1", attempt_number=1),
        failure_reason="terminal_input",
        safe_code="invalid_input",
    )
    assert handler.received == [claim.work]
    assert store.claims == [
        (ClaimOperationId("claim-op-1"), "worker-a", AttemptTimingV1.standard())
    ]
    assert store.finalizations == [
        (
            TransitionOperationId("terminal-op-1"),
            claim,
            CanonicalFailureV1(
                cause=FailureCauseV1.INVALID_INPUT,
                safe_code="invalid_input",
                failure_reason="terminal_input",
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
        )
    ]
