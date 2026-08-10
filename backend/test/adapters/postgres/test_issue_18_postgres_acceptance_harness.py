from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from backend.test.fixtures.issue_18_acceptance import (
    AcceptanceEmbeddingProvider,
    AcceptanceExtractor,
    AcceptanceObjectStore,
    DefiniteRollbackSentinel,
    ImmediateRunner,
    pdf_extraction,
    pdf_metadata,
    pdf_raw_bytes,
    pdf_success,
)
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory, engine
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentTable,
    EmbeddingSetTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    ClaimedAttempt,
    ClaimOperationId,
    FailedTerminal,
    Fenced,
    FinalizationApplied,
    HeartbeatOperationId,
    NoEligibleJob,
    PdfDerivationHandler,
    PdfDerivationProfile,
    ProcessIngestionJob,
    RetryPolicyV1,
    Succeeded,
    SystemRandomSource,
    TransitionOperationId,
    UuidOperationIds,
)
from knora.ingestion.jobs import PdfSubmissionConfiguration, PreparedPdfSubmission
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import PdfExtractionError
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


@pytest.fixture(autouse=True)
def clean_coordination_state() -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )


@dataclass
class ProbeTransaction:
    transaction_id: str
    connection_id: str
    owner: str | None
    span_kind: str | None
    started_at: float
    ended_at: float | None = None


@dataclass
class ProbeLock:
    transaction_id: str | None
    connection_id: str
    owner: str | None
    span_kind: str | None
    lock_kind: str


@dataclass
class ProbeSpan:
    owner: str
    started_at: float
    ended_at: float


class TransactionProbe:
    def __init__(self) -> None:
        self.transactions: list[ProbeTransaction] = []
        self.locks: list[ProbeLock] = []
        self.spans: list[ProbeSpan] = []
        self._owner: ContextVar[str | None] = ContextVar("issue18_probe_owner", default=None)
        self._open: dict[str, ProbeTransaction] = {}
        self._listeners: list[tuple[object, str, object]] = []

    def __enter__(self) -> TransactionProbe:
        event.listen(engine, "begin", self._on_begin)
        event.listen(engine, "commit", self._on_commit)
        event.listen(engine, "rollback", self._on_rollback)
        event.listen(engine, "before_cursor_execute", self._on_before_cursor_execute)
        self._listeners = [
            (engine, "begin", self._on_begin),
            (engine, "commit", self._on_commit),
            (engine, "rollback", self._on_rollback),
            (engine, "before_cursor_execute", self._on_before_cursor_execute),
        ]
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        for target, name, listener in self._listeners:
            event.remove(target, name, listener)
        self._listeners.clear()

    @contextmanager
    def span(self, owner: str):
        token = self._owner.set(owner)
        started_at = time.perf_counter()
        try:
            yield
        finally:
            ended_at = time.perf_counter()
            self.spans.append(ProbeSpan(owner, started_at, ended_at))
            self._owner.reset(token)

    def _on_begin(self, connection) -> None:
        transaction_id = str(connection.exec_driver_sql("SELECT txid_current()").scalar_one())
        connection_id = str(id(connection.connection))
        transaction = ProbeTransaction(
            transaction_id=transaction_id,
            connection_id=connection_id,
            owner=self._owner.get(),
            span_kind=self._owner.get(),
            started_at=time.perf_counter(),
        )
        self.transactions.append(transaction)
        self._open[connection_id] = transaction

    def _on_before_cursor_execute(
        self,
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        del cursor, parameters, context, executemany
        if "FOR UPDATE" not in statement.upper():
            return
        connection_id = str(id(connection.connection))
        transaction = self._open.get(connection_id)
        self.locks.append(
            ProbeLock(
                transaction_id=transaction.transaction_id if transaction is not None else None,
                connection_id=connection_id,
                owner=self._owner.get(),
                span_kind=self._owner.get(),
                lock_kind="row_lock",
            )
        )

    def _on_commit(self, connection) -> None:
        self._close(connection)

    def _on_rollback(self, connection) -> None:
        self._close(connection)

    def _close(self, connection) -> None:
        transaction = self._open.pop(str(id(connection.connection)), None)
        if transaction is not None:
            transaction.ended_at = time.perf_counter()


class ProbedPostgresStore(PostgresIngestionJobStore):
    def __init__(self, probe: TransactionProbe) -> None:
        super().__init__(SessionFactory)
        self.probe = probe
        self.last_claim: ClaimedAttempt | None = None

    def claim_next_attempt(self, **kwargs):
        with self.probe.span("claim"):
            self.last_claim = super().claim_next_attempt(**kwargs)
            return self.last_claim

    def finalize_success(self, **kwargs):
        with self.probe.span("finalization"):
            return super().finalize_success(**kwargs)


class AdvancingFinalizationClockStore(PostgresIngestionJobStore):
    """Inject two authoritative-time samples around the finalization guard."""

    def __init__(self) -> None:
        super().__init__(SessionFactory)
        self.finalization_times: list[datetime] = []

    def _database_now(self, session: Session) -> datetime:
        if self.finalization_times:
            return self.finalization_times.pop(0)
        return super()._database_now(session)


def submit_pdf_job(
    store: PostgresIngestionJobStore,
    *,
    workspace_id: str | None = None,
    source_key: str | None = None,
    raw: bytes | None = None,
) -> tuple[str, str, PdfSubmissionConfiguration, ObjectMetadata]:
    workspace_id = workspace_id or f"issue18-harness-{uuid4()}"
    source_key = source_key or f"support/issue18-{uuid4()}"
    raw = raw or pdf_raw_bytes(uuid4().hex.encode())
    with SessionFactory.begin() as session:
        if session.get(WorkspaceTable, workspace_id) is None:
            session.add(WorkspaceTable(id=workspace_id, name="Issue 18 harness"))
    configuration = PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    metadata = pdf_metadata(
        workspace_id=workspace_id,
        object_key=uuid4().hex,
        raw=raw,
    )
    prepared = PreparedPdfSubmission(
        workspace_id=workspace_id,
        source_key=source_key,
        source_name="issue18.pdf",
        source_object=metadata,
        content_fingerprint="\n".join(
            (
                workspace_id,
                source_key,
                metadata.sha256,
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
    result = store.commit_pdf_submission(prepared)
    return workspace_id, result.ingestion_job_id, configuration, metadata


def handler_for_claim(
    claim: ClaimedAttempt,
    configuration: PdfSubmissionConfiguration,
    *,
    probe: TransactionProbe | None = None,
    object_store: AcceptanceObjectStore | None = None,
    extractor: AcceptanceExtractor | None = None,
    provider: AcceptanceEmbeddingProvider | None = None,
) -> tuple[PdfDerivationHandler, AcceptanceObjectStore, AcceptanceEmbeddingProvider]:
    extraction = pdf_extraction()
    success = pdf_success(configuration, extraction=extraction)
    object_store = object_store or AcceptanceObjectStore(
        metadata=ObjectMetadata(
            workspace_id=claim.work.workspace_id,
            object_key=claim.work.source_object_key,
            sha256=claim.work.source_sha256,
            byte_size=claim.work.source_byte_size,
            media_type=claim.work.source_media_type,
        )
    )
    extractor = extractor or AcceptanceExtractor(result=extraction, probe=probe)
    provider = provider or AcceptanceEmbeddingProvider(
        batch=EmbeddingBatch(
            vectors=success.vectors,
            provider=success.embedding_provider,
            model=success.embedding_model,
        ),
        probe=probe,
    )
    profile = PdfDerivationProfile.milestone_two(
        embedding_configuration=configuration.embedding_configuration
    )
    return (
        PdfDerivationHandler(
            object_store=object_store,
            extractor=extractor,
            embedding_provider=provider,
            profile=profile,
        ),
        object_store,
        provider,
    )


def reset_claim(job_id: str) -> None:
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        session.delete(attempt)
        job.status = "queued"
        job.attempt_count = 0
        job.started_at = None
        job.worker_id = None
        job.lease_expires_at = None
        job.current_attempt_number = None
        job.current_attempt_started_at = None
        job.current_attempt_deadline_at = None


@dataclass(frozen=True)
class ServingProjection:
    current_document_version_id: str | None
    active_document_version_id: str | None
    served_document_version_id: str | None


def read_serving_projection(*, workspace_id: str, source_key: str) -> ServingProjection:
    with SessionFactory() as session:
        document = session.scalar(
            select(DocumentTable).where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.source_key == source_key,
            )
        )
        assert document is not None
        active_version_id: str | None = None
        served_version_id: str | None = None
        if document.active_embedding_set_id is not None:
            embedding_set = session.get(EmbeddingSetTable, document.active_embedding_set_id)
            assert embedding_set is not None
            chunk_set = session.get(ChunkSetTable, embedding_set.chunk_set_id)
            assert chunk_set is not None
            active_version_id = chunk_set.document_version_id
            if embedding_set.status == "completed" and chunk_set.status == "completed":
                served_version_id = active_version_id
        return ServingProjection(
            current_document_version_id=document.current_document_version_id,
            active_document_version_id=active_version_id,
            served_document_version_id=served_version_id,
        )


class ConstantQueryEmbeddingProvider:
    def embed(self, texts: list[str], configuration: EmbeddingConfiguration) -> EmbeddingBatch:
        del texts
        return EmbeddingBatch(
            vectors=(tuple(0.1 for _ in range(configuration.dimensions)),),
            provider=configuration.provider,
            model=configuration.model,
        )


def answer_pdf_question(workspace_id: str):
    return asyncio.run(
        AnswerQuestion(
            embedding_provider=ConstantQueryEmbeddingProvider(),
            generation_provider=DeterministicGenerationProvider(),
            store=PostgresAnsweringStore(SessionFactory),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ).execute(
            QuestionCommand(workspace_id=workspace_id, question="What is in the PDF fixture?"),
            WorkspacePrincipal(workspace_id=workspace_id, key_id="issue18-harness"),
        )
    )


def test_tc01_real_worker_transaction_probe_keeps_remote_work_outside_db_transactions() -> None:
    probe = TransactionProbe()
    store = ProbedPostgresStore(probe)
    workspace_id, _, configuration, _ = submit_pdf_job(store)
    processor_store = store
    with probe:
        claim_holder: dict[str, ClaimedAttempt] = {}
        provider_holder: dict[str, AcceptanceEmbeddingProvider] = {}

        def heartbeat() -> None:
            claim = claim_holder["claim"]
            with probe.span("heartbeat"):
                processor_store.heartbeat(
                    operation_id=HeartbeatOperationId(uuid4().hex),
                    token=claim.token,
                    lease_duration=timedelta(minutes=2),
                )

        def capture_claim(**kwargs):
            claim = ProbedPostgresStore.claim_next_attempt(store, **kwargs)
            claim_holder["claim"] = claim
            return claim

        store.claim_next_attempt = capture_claim  # type: ignore[method-assign]
        claim = store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id="worker-18",
            timing=AttemptTimingV1.standard(),
        )
        assert isinstance(claim, ClaimedAttempt)
        handler, _, provider = handler_for_claim(claim, configuration, probe=probe)
        provider.heartbeat_callback = heartbeat
        provider_holder["provider"] = provider

        processor = ProcessIngestionJob(
            store=store,
            handler=handler,
            operation_ids=UuidOperationIds(),
            timing=AttemptTimingV1.standard(),
            retry_policy=RetryPolicyV1(SystemRandomSource()),
            runner=ImmediateRunner(),
        )
        # Return the setup claim so run_once exercises the real claim path again.
        with SessionFactory.begin() as session:
            job = session.get(IngestionJobTable, claim.token.job_id)
            attempt = session.get(
                IngestionJobAttemptTable,
                (claim.token.job_id, claim.token.attempt_number),
            )
            session.delete(attempt)
            job.status = "queued"
            job.attempt_count = 0
            job.started_at = None
            job.worker_id = None
            job.lease_expires_at = None
            job.current_attempt_number = None
            job.current_attempt_started_at = None
            job.current_attempt_deadline_at = None

        result = processor.run_once("worker-18")

    assert isinstance(result, Succeeded)
    assert claim_holder["claim"].work.workspace_id == workspace_id
    remote_spans = [span for span in probe.spans if span.owner in {"extractor", "provider"}]
    assert len(remote_spans) == 2
    for transaction in probe.transactions:
        assert transaction.ended_at is not None
        for span in remote_spans:
            assert not (
                transaction.started_at < span.ended_at
                and transaction.ended_at > span.started_at
                and transaction.owner in {"claim", "finalization"}
            )
    assert any(
        transaction.owner == "heartbeat"
        and transaction.ended_at is not None
        and transaction.started_at
        < next(span.ended_at for span in probe.spans if span.owner == "provider")
        for transaction in probe.transactions
    )
    assert provider_holder["provider"].calls == 1
    assert any(
        lock.owner == "finalization"
        and lock.span_kind == "finalization"
        and lock.lock_kind == "row_lock"
        for lock in probe.locks
    )
    answer = answer_pdf_question(workspace_id)
    assert answer.decision == "ANSWER"
    assert len(answer.citations) == 1
    assert answer.citations[0].page_start == 1
    assert answer.citations[0].page_end == 1
    assert answer.citations[0].start_offset == 0
    assert answer.citations[0].end_offset == len("Page one fixture.")


def test_tc02_new_current_failure_preserves_historical_active_and_served_retrieval() -> None:
    store = PostgresIngestionJobStore(SessionFactory)
    raw_a = pdf_raw_bytes(b"historical")
    workspace_id, job_a, configuration, metadata_a = submit_pdf_job(
        store,
        source_key="support/issue18-served",
        raw=raw_a,
    )
    claim_a = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-historical",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim_a, ClaimedAttempt)
    handler_a, _, _ = handler_for_claim(
        claim_a,
        configuration,
        object_store=AcceptanceObjectStore(metadata=metadata_a, raw=raw_a),
    )
    reset_claim(job_a)
    first = ProcessIngestionJob(
        store=store,
        handler=handler_a,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=ImmediateRunner(),
    ).run_once("worker-historical")
    assert isinstance(first, Succeeded)

    historical = read_serving_projection(
        workspace_id=workspace_id,
        source_key="support/issue18-served",
    )
    assert historical.current_document_version_id == claim_a.work.document_version_id
    assert historical.active_document_version_id == claim_a.work.document_version_id
    assert historical.served_document_version_id == claim_a.work.document_version_id

    raw_b = pdf_raw_bytes(b"new-current")
    _, job_b, _, metadata_b = submit_pdf_job(
        store,
        workspace_id=workspace_id,
        source_key="support/issue18-served",
        raw=raw_b,
    )
    queued = read_serving_projection(
        workspace_id=workspace_id,
        source_key="support/issue18-served",
    )
    assert queued.current_document_version_id != claim_a.work.document_version_id
    assert queued.active_document_version_id == claim_a.work.document_version_id
    assert queued.served_document_version_id == claim_a.work.document_version_id
    before_failure = answer_pdf_question(workspace_id)
    assert before_failure.citations[0].document_version_id == claim_a.work.document_version_id
    assert before_failure.citations[0].excerpt == "Page one fixture."

    claim_b = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-new-current",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim_b, ClaimedAttempt)
    handler_b, _, _ = handler_for_claim(
        claim_b,
        configuration,
        object_store=AcceptanceObjectStore(metadata=metadata_b, raw=raw_b),
        extractor=AcceptanceExtractor(
            result=pdf_extraction(),
            failure=PdfExtractionError(
                "PDF_TEXT_INSUFFICIENT",
                reason="INSUFFICIENT_EXTRACTABLE_TEXT",
            ),
        ),
    )
    reset_claim(job_b)
    failed = ProcessIngestionJob(
        store=store,
        handler=handler_b,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=ImmediateRunner(),
    ).run_once("worker-new-current")
    assert isinstance(failed, FailedTerminal)

    after_failure = read_serving_projection(
        workspace_id=workspace_id,
        source_key="support/issue18-served",
    )
    assert after_failure.current_document_version_id != claim_a.work.document_version_id
    assert after_failure.active_document_version_id == claim_a.work.document_version_id
    assert after_failure.served_document_version_id == claim_a.work.document_version_id
    after_question = answer_pdf_question(workspace_id)
    assert after_question.citations[0].document_version_id == claim_a.work.document_version_id
    assert after_question.citations[0].excerpt == "Page one fixture."
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_b)
        attempt = session.get(IngestionJobAttemptTable, (job_b, 1))
        assert job is not None and attempt is not None
        assert job.status == "failed"
        assert job.failure_reason == "terminal_input"
        assert attempt.safe_failure_code == "PDF_TEXT_INSUFFICIENT"
        assert (
            session.scalar(
                select(ChunkSetTable).where(
                    ChunkSetTable.document_version_id == claim_b.work.document_version_id
                )
            )
            is None
        )


def test_tc04_two_job_cas_supersession_keeps_newer_target_active() -> None:
    store = PostgresIngestionJobStore(SessionFactory)
    workspace_id, job_a, configuration, _ = submit_pdf_job(
        store,
        source_key="support/issue18-shared",
        raw=pdf_raw_bytes(b"older"),
    )
    claim_a = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-a",
        timing=AttemptTimingV1.standard(),
    )
    _, job_b, _, _ = submit_pdf_job(
        store,
        workspace_id=workspace_id,
        source_key="support/issue18-shared",
        raw=pdf_raw_bytes(b"newer"),
    )
    assert isinstance(claim_a, ClaimedAttempt)
    claim_b = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-b",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim_b, ClaimedAttempt)
    newer = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim_b,
        success=pdf_success(configuration),
    )
    older = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim_a,
        success=pdf_success(configuration),
    )

    assert isinstance(newer, FinalizationApplied)
    assert isinstance(older, FinalizationApplied)
    with SessionFactory() as session:
        job_a_row = session.get(IngestionJobTable, job_a)
        job_b_row = session.get(IngestionJobTable, job_b)
        document = session.get(DocumentTable, claim_a.work.document_id)
        assert job_a_row.status == "superseded"
        assert job_b_row.status == "succeeded"
        assert document.active_embedding_set_id is not None
    projection = read_serving_projection(
        workspace_id=workspace_id,
        source_key="support/issue18-shared",
    )
    assert projection.current_document_version_id == claim_b.work.document_version_id
    assert projection.active_document_version_id == claim_b.work.document_version_id
    assert projection.served_document_version_id == claim_b.work.document_version_id
    answer = answer_pdf_question(workspace_id)
    assert answer.citations[0].document_version_id == claim_b.work.document_version_id
    assert answer.citations[0].excerpt == "Page one fixture."


def test_tc05a_independent_duplicate_delivery_does_not_repeat_handler_or_provider() -> None:
    store = PostgresIngestionJobStore(SessionFactory)
    _, _, configuration, metadata = submit_pdf_job(store)
    setup_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="setup-worker",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(setup_claim, ClaimedAttempt)
    handler, object_store, provider = handler_for_claim(setup_claim, configuration)
    reset_claim(setup_claim.token.job_id)
    processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=ImmediateRunner(),
    )
    first = processor.run_once("worker-18")
    second = processor.run_once("worker-18")

    assert isinstance(first, Succeeded)
    assert isinstance(second, NoEligibleJob)
    assert provider.calls == 1
    assert object_store.metadata == metadata


def test_tc05b_same_transition_operation_replays_after_response_loss() -> None:
    store = PostgresIngestionJobStore(SessionFactory)
    _, job_id, configuration, _ = submit_pdf_job(store)
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-18",
        timing=AttemptTimingV1.standard(),
    )
    operation_id = TransitionOperationId(uuid4().hex)
    success = pdf_success(configuration)

    class ResponseLostAfterCommit(RuntimeError):
        pass

    with pytest.raises(ResponseLostAfterCommit):
        store.finalize_success(
            operation_id=operation_id,
            claim=claim,
            success=success,
        )
        raise ResponseLostAfterCommit()

    replay = store.finalize_success(
        operation_id=operation_id,
        claim=claim,
        success=success,
    )

    assert isinstance(replay, FinalizationApplied)
    with SessionFactory() as session:
        assert session.get(IngestionJobTable, job_id).status == "succeeded"
        assert (
            session.scalar(
                select(ChunkSetTable).where(
                    ChunkSetTable.document_version_id == claim.work.document_version_id
                )
            )
            is not None
        )


def test_tc05c_definite_precommit_rollback_leaves_no_pdf_derivation_or_lifecycle_mutation() -> None:
    store = PostgresIngestionJobStore(SessionFactory)
    _, job_id, configuration, _ = submit_pdf_job(store)
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-18",
        timing=AttemptTimingV1.standard(),
    )
    should_fail = ContextVar("issue18_definite_rollback", default=False)

    def fail_after_flush(session, flush_context) -> None:
        if should_fail.get():
            raise DefiniteRollbackSentinel()

    event.listen(Session, "after_flush", fail_after_flush)
    token = should_fail.set(True)
    try:
        with pytest.raises(DefiniteRollbackSentinel):
            store.finalize_success(
                operation_id=TransitionOperationId(uuid4().hex),
                claim=claim,
                success=pdf_success(configuration),
            )
    finally:
        should_fail.reset(token)
        event.remove(Session, "after_flush", fail_after_flush)

    with SessionFactory() as session:
        assert session.get(IngestionJobTable, job_id).status == "processing"
        assert session.get(IngestionJobAttemptTable, (job_id, 1)).closed_at is None
        assert (
            session.scalar(
                select(ChunkSetTable).where(
                    ChunkSetTable.document_version_id == claim.work.document_version_id
                )
            )
            is None
        )
        assert (
            session.scalar(
                select(EmbeddingSetTable)
                .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
                .where(ChunkSetTable.document_version_id == claim.work.document_version_id)
            )
            is None
        )


def test_finalization_fences_lease_expiry_at_the_final_guard_and_rolls_back() -> None:
    store = AdvancingFinalizationClockStore()
    _, job_id, configuration, _ = submit_pdf_job(store)
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-final-fence",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        assert job is not None and job.lease_expires_at is not None
        lease_expires_at = job.lease_expires_at
    store.finalization_times = [
        lease_expires_at - timedelta(microseconds=1),
        lease_expires_at + timedelta(microseconds=1),
    ]

    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        success=pdf_success(configuration),
    )

    assert isinstance(result, Fenced)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        document = session.get(DocumentTable, claim.work.document_id)
        assert job is not None and attempt is not None and document is not None
        assert job.status == "processing"
        assert job.current_attempt_number == 1
        assert attempt.closed_at is None
        assert attempt.transition_operation_id is None
        assert document.active_embedding_set_id is None
        assert (
            session.scalar(
                select(ChunkSetTable).where(
                    ChunkSetTable.document_version_id == claim.work.document_version_id
                )
            )
            is None
        )
        assert (
            session.scalar(
                select(EmbeddingSetTable)
                .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
                .where(ChunkSetTable.document_version_id == claim.work.document_version_id)
            )
            is None
        )


def test_tc09_original_source_object_remains_after_concrete_success_and_failure() -> None:
    store = PostgresIngestionJobStore(SessionFactory)
    _, success_job_id, configuration, success_metadata = submit_pdf_job(store)
    success_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-success",
        timing=AttemptTimingV1.standard(),
    )
    success_object_store = AcceptanceObjectStore(metadata=success_metadata)
    success_handler, _, _ = handler_for_claim(
        success_claim,
        configuration,
        object_store=success_object_store,
    )
    success_processor = ProcessIngestionJob(
        store=store,
        handler=success_handler,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=ImmediateRunner(),
    )
    # Reset the setup claim so the concrete processor owns it.
    reset_claim(success_job_id)
    assert isinstance(success_processor.run_once("worker-success"), Succeeded)

    with SessionFactory() as session:
        source_object = session.get(OriginalSourceObjectTable, success_claim.work.source_object_id)
        assert source_object is not None
        assert source_object.object_key == success_metadata.object_key
    assert success_object_store.delete_calls == []

    failure_raw = pdf_raw_bytes(b"terminal-failure")
    failure_workspace_id, failure_job_id, failure_configuration, failure_metadata = submit_pdf_job(
        store,
        raw=failure_raw,
        source_key="support/issue18-retention-failure",
    )
    failure_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-failure",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(failure_claim, ClaimedAttempt)
    failure_object_store = AcceptanceObjectStore(
        metadata=failure_metadata,
        raw=failure_raw,
    )
    failure_handler, _, _ = handler_for_claim(
        failure_claim,
        failure_configuration,
        object_store=failure_object_store,
        extractor=AcceptanceExtractor(
            result=pdf_extraction(),
            failure=PdfExtractionError(
                "PDF_TEXT_INSUFFICIENT",
                reason="INSUFFICIENT_EXTRACTABLE_TEXT",
            ),
        ),
    )
    reset_claim(failure_job_id)
    failure_result = ProcessIngestionJob(
        store=store,
        handler=failure_handler,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=ImmediateRunner(),
    ).run_once("worker-failure")
    assert isinstance(failure_result, FailedTerminal)
    with SessionFactory() as session:
        failure_source = session.get(
            OriginalSourceObjectTable,
            failure_claim.work.source_object_id,
        )
        assert failure_source is not None
        assert failure_source.raw_sha256 == failure_metadata.sha256
    assert failure_object_store.delete_calls == []
