from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    IdempotencyRecordTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    ReprocessAuditTable,
    WorkspaceTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimOperationId,
    FailureCauseV1,
    RetryExhausted,
    ScheduleRetry,
    TransitionOperationId,
    WorkSuperseded,
)
from knora.ingestion.jobs import (
    IngestionJobs,
    PdfSubmissionCommand,
    PdfSubmissionConfiguration,
    ReprocessDocumentVersionCommand,
)
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.main import create_app
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


def _configuration() -> PdfSubmissionConfiguration:
    return PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )


def _workspace(name: str) -> str:
    workspace_id = f"issue-19-acceptance-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name=name))
    return workspace_id


def _service(tmp_path) -> tuple[IngestionJobs, FileSystemObjectStore]:
    object_store = FileSystemObjectStore(tmp_path)
    return (
        IngestionJobs(
            object_store=object_store,
            store=PostgresIngestionJobStore(SessionFactory),
        ),
        object_store,
    )


def _upload(
    service: IngestionJobs,
    workspace_id: str,
    *,
    source_key: str,
    source_name: str,
    raw: bytes,
    idempotency_key: str,
):
    return service.submit_pdf(
        PdfSubmissionCommand(
            workspace_id=workspace_id,
            source_key=source_key,
            source_name=source_name,
            media_type="application/pdf",
            stream=BytesIO(raw),
            idempotency_key=idempotency_key,
            configuration=_configuration(),
        ),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="acceptance-key"),
    )


def _mark_succeeded(job_id: str) -> None:
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, job_id)
        assert job is not None
        job.status = "succeeded"
        job.attempt_count = 1
        job.started_at = now
        job.updated_at = now
        job.terminal_at = now
        job.terminal_outcome_code = "succeeded"


def _job_count(workspace_id: str) -> int:
    with SessionFactory() as session:
        return session.scalar(
            select(func.count())
            .select_from(IngestionJobTable)
            .where(IngestionJobTable.workspace_id == workspace_id)
        )


def test_upload_idempotency_binding_filename_scope_and_operation_isolation(tmp_path) -> None:
    service, _ = _service(tmp_path)
    workspace_a = _workspace("upload scope A")
    workspace_b = _workspace("upload scope B")
    raw = b"%PDF-1.7\nfilename-exclusion-fixture"

    first = _upload(
        service,
        workspace_a,
        source_key="support/filename-exclusion",
        source_name="first-client-name.pdf",
        raw=raw,
        idempotency_key="literal-shared-key",
    )
    filename_replay = _upload(
        service,
        workspace_a,
        source_key="support/filename-exclusion",
        source_name="different-client-name.pdf",
        raw=raw,
        idempotency_key="literal-shared-key",
    )
    filename_dedup = _upload(
        service,
        workspace_a,
        source_key="support/filename-exclusion",
        source_name="third-client-name.pdf",
        raw=raw,
        idempotency_key="different-key",
    )

    assert filename_replay.ingestion_job_id == first.ingestion_job_id
    assert filename_replay.submission_outcome == "idempotency_replay"
    assert filename_dedup.ingestion_job_id == first.ingestion_job_id
    assert filename_dedup.submission_outcome == "deduplicated"
    assert _job_count(workspace_a) == 1

    workspace_b_result = _upload(
        service,
        workspace_b,
        source_key="support/filename-exclusion",
        source_name="workspace-b.pdf",
        raw=raw,
        idempotency_key="literal-shared-key",
    )
    assert workspace_b_result.submission_outcome == "created"
    assert workspace_b_result.ingestion_job_id != first.ingestion_job_id
    assert _job_count(workspace_b) == 1

    operation_key_result = _upload(
        service,
        workspace_a,
        source_key="support/operation-scope",
        source_name="operation.pdf",
        raw=b"%PDF-1.7\noperation-scope-fixture",
        idempotency_key="same-literal-operation-key",
    )
    _mark_succeeded(operation_key_result.ingestion_job_id)
    reprocess = service.reprocess_document_version(
        ReprocessDocumentVersionCommand(
            workspace_id=workspace_a,
            document_version_id=operation_key_result.document_version_id,
            config_mode="current",
            config_source_job_id=None,
            idempotency_key="same-literal-operation-key",
        ),
        WorkspacePrincipal(workspace_id=workspace_a, key_id="acceptance-key"),
    )
    assert reprocess.outcome == "reused"
    assert reprocess.ingestion_job_id == operation_key_result.ingestion_job_id
    with SessionFactory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordTable)
            .where(
                IdempotencyRecordTable.workspace_id == workspace_a,
                IdempotencyRecordTable.key == "same-literal-operation-key",
            )
        ) == 2


def test_upload_conflict_preserves_original_binding_and_fingerprint_race_is_one_winner(
    tmp_path,
) -> None:
    service, _ = _service(tmp_path)
    workspace_id = _workspace("upload conflict binding")
    source_key = "support/conflict-binding"
    first = _upload(
        service,
        workspace_id,
        source_key=source_key,
        source_name="first.pdf",
        raw=b"%PDF-1.7\nfingerprint-one",
        idempotency_key="binding-key",
    )
    baseline_jobs = _job_count(workspace_id)
    with pytest.raises(KnoraError, match="IDEMPOTENCY_KEY_CONFLICT"):
        _upload(
            service,
            workspace_id,
            source_key=source_key,
            source_name="conflicting.pdf",
            raw=b"%PDF-1.7\nfingerprint-two",
            idempotency_key="binding-key",
        )
    replay = _upload(
        service,
        workspace_id,
        source_key=source_key,
        source_name="original-name-again.pdf",
        raw=b"%PDF-1.7\nfingerprint-one",
        idempotency_key="binding-key",
    )
    assert replay.submission_outcome == "idempotency_replay"
    assert replay.ingestion_job_id == first.ingestion_job_id
    assert _job_count(workspace_id) == baseline_jobs

    race_key = "conflicting-race-key"
    race_inputs = (b"%PDF-1.7\nrace-one", b"%PDF-1.7\nrace-two")

    def submit_race(raw: bytes):
        try:
            return _upload(
                service,
                workspace_id,
                source_key="support/conflicting-race",
                source_name="race.pdf",
                raw=raw,
                idempotency_key=race_key,
            )
        except KnoraError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(submit_race, race_inputs))
    successes = [outcome for outcome in outcomes if not isinstance(outcome, KnoraError)]
    conflicts = [outcome for outcome in outcomes if isinstance(outcome, KnoraError)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].code == "IDEMPOTENCY_KEY_CONFLICT"
    with SessionFactory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(IngestionJobTable)
            .where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.source_object_id.is_not(None),
            )
        ) == baseline_jobs + 1
        assert session.scalar(
            select(func.count())
            .select_from(DocumentVersionTable)
            .join(
                IngestionJobTable,
                IngestionJobTable.target_document_version_id == DocumentVersionTable.id,
            )
            .where(IngestionJobTable.workspace_id == workspace_id)
        ) == baseline_jobs + 1


def test_reprocess_conflicting_fingerprints_have_one_binding_and_no_extra_generation(
    tmp_path,
) -> None:
    service, _ = _service(tmp_path)
    workspace_id = _workspace("reprocess conflict race")
    upload = _upload(
        service,
        workspace_id,
        source_key="support/reprocess-race",
        source_name="reprocess-race.pdf",
        raw=b"%PDF-1.7\nreprocess-race",
        idempotency_key="upload-race-base",
    )
    _mark_succeeded(upload.ingestion_job_id)
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="acceptance-key")
    commands = (
        ReprocessDocumentVersionCommand(
            workspace_id=workspace_id,
            document_version_id=upload.document_version_id,
            config_mode="current",
            config_source_job_id=None,
            idempotency_key="reprocess-conflicting-race",
        ),
        ReprocessDocumentVersionCommand(
            workspace_id=workspace_id,
            document_version_id=upload.document_version_id,
            config_mode="same_as_job",
            config_source_job_id=upload.ingestion_job_id,
            idempotency_key="reprocess-conflicting-race",
        ),
    )

    def run(command):
        try:
            return service.reprocess_document_version(command, principal)
        except KnoraError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(run, commands))
    successes = [outcome for outcome in outcomes if not isinstance(outcome, KnoraError)]
    conflicts = [outcome for outcome in outcomes if isinstance(outcome, KnoraError)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].code == "IDEMPOTENCY_KEY_CONFLICT"
    assert successes[0].ingestion_job_id == upload.ingestion_job_id
    with SessionFactory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(IngestionJobTable)
            .where(IngestionJobTable.workspace_id == workspace_id)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(ReprocessAuditTable)
            .where(ReprocessAuditTable.workspace_id == workspace_id)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordTable)
            .where(
                IdempotencyRecordTable.workspace_id == workspace_id,
                IdempotencyRecordTable.operation == "reprocess_document_version",
            )
        ) == 1


def _poll_client(service: IngestionJobs, workspace_id: str) -> tuple[TestClient, str]:
    raw_key = f"poll-key-{uuid4()}"
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="poll-key-id",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    return (
        TestClient(
            create_app(
                ingestion_jobs=service,
                api_key_authenticator=authenticator,
            )
        ),
        raw_key,
    )


def _poll(client: TestClient, workspace_id: str, job_id: str, raw_key: str) -> dict:
    response = client.get(
        f"/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert "poll_after_seconds" in payload
    return payload


def test_public_poll_projects_all_six_states_exact_retry_and_terminal_metadata(tmp_path) -> None:
    service, _ = _service(tmp_path)
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )
    workspace_id = _workspace("public six states")
    store = PostgresIngestionJobStore(SessionFactory)
    client, raw_key = _poll_client(service, workspace_id)

    processing = _upload(
        service,
        workspace_id,
        source_key="support/state-processing",
        source_name="processing.pdf",
        raw=b"%PDF-1.7\nprocessing",
        idempotency_key="state-processing",
    )
    processing_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="state-processing-worker",
        timing=AttemptTimingV1.standard(),
    )
    assert processing_claim.token.job_id == processing.ingestion_job_id

    retry = _upload(
        service,
        workspace_id,
        source_key="support/state-retry",
        source_name="retry.pdf",
        raw=b"%PDF-1.7\nretry",
        idempotency_key="state-retry",
    )
    retry_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="state-retry-worker",
        timing=AttemptTimingV1.standard(),
    )
    retry_result = store.schedule_retry(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=retry_claim,
        failure=CanonicalFailureV1(
            cause=FailureCauseV1.PROVIDER_TRANSIENT,
            safe_code="provider_transient",
            failure_reason=None,
            cause_version="failure-causes-v1",
            mapping_version="cause-mapping-v1",
        ),
        decision=ScheduleRetry(
            delay_microseconds=5_000_000,
            window_upper_bound_microseconds=5_000_000,
        ),
    )
    assert retry_result.next_attempt_at is not None

    succeeded = _upload(
        service,
        workspace_id,
        source_key="support/state-succeeded",
        source_name="succeeded.pdf",
        raw=b"%PDF-1.7\nsucceeded",
        idempotency_key="state-succeeded",
    )
    _mark_succeeded(succeeded.ingestion_job_id)
    failed = _upload(
        service,
        workspace_id,
        source_key="support/state-failed",
        source_name="failed.pdf",
        raw=b"%PDF-1.7\nfailed",
        idempotency_key="state-failed",
    )
    failed_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="state-failed-worker",
        timing=AttemptTimingV1.standard(),
    )
    store.finalize_terminal_failure(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=failed_claim,
        failure=CanonicalFailureV1(
            cause=FailureCauseV1.INVALID_INPUT,
            safe_code="invalid_input",
            failure_reason="terminal_input",
            cause_version="failure-causes-v1",
            mapping_version="cause-mapping-v1",
        ),
    )

    exhausted = _upload(
        service,
        workspace_id,
        source_key="support/state-exhausted",
        source_name="exhausted.pdf",
        raw=b"%PDF-1.7\nexhausted",
        idempotency_key="state-exhausted",
    )
    exhausted_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="state-exhausted-worker",
        timing=AttemptTimingV1.standard(),
    )
    retry_failure = CanonicalFailureV1(
        cause=FailureCauseV1.PROVIDER_TRANSIENT,
        safe_code="provider_transient",
        failure_reason=None,
        cause_version="failure-causes-v1",
        mapping_version="cause-mapping-v1",
    )
    for _ in range(3):
        store.schedule_retry(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=exhausted_claim,
            failure=retry_failure,
            decision=ScheduleRetry(delay_microseconds=0, window_upper_bound_microseconds=0),
        )
        exhausted_claim = store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id="state-exhausted-worker",
            timing=AttemptTimingV1.standard(),
        )
    store.finalize_terminal_failure(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=exhausted_claim,
        failure=CanonicalFailureV1(
            cause=retry_failure.cause,
            safe_code=retry_failure.safe_code,
            failure_reason="retry_exhausted",
            cause_version=retry_failure.cause_version,
            mapping_version=retry_failure.mapping_version,
        ),
        decision=RetryExhausted(),
    )

    superseded_a = _upload(
        service,
        workspace_id,
        source_key="support/state-superseded",
        source_name="superseded-a.pdf",
        raw=b"%PDF-1.7\nsuperseded-a",
        idempotency_key="state-superseded-a",
    )
    superseded_claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="state-superseded-worker",
        timing=AttemptTimingV1.standard(),
    )
    superseded_b = _upload(
        service,
        workspace_id,
        source_key="support/state-superseded",
        source_name="superseded-b.pdf",
        raw=b"%PDF-1.7\nsuperseded-b",
        idempotency_key="state-superseded-b",
    )
    store.finalize_superseded(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=superseded_claim,
        outcome=WorkSuperseded(
            replacement_document_version_id=superseded_b.document_version_id,
            replacement_ingestion_job_id=superseded_b.ingestion_job_id,
        ),
    )
    queued = _upload(
        service,
        workspace_id,
        source_key="support/state-queued",
        source_name="queued.pdf",
        raw=b"%PDF-1.7\nqueued",
        idempotency_key="state-queued",
    )

    with client:
        queued_payload = _poll(client, workspace_id, queued.ingestion_job_id, raw_key)
        assert queued_payload["status"] == "queued"
        assert queued_payload["attempt_count"] == 0
        assert queued_payload["max_attempts"] == 4
        assert "next_attempt_at" not in queued_payload
        assert queued_payload["failure_reason"] is None
        assert queued_payload["terminal_at"] is None
        assert queued_payload["serving_state"] == "unavailable"
        assert queued_payload["served_document_version_id"] is None

        processing_payload = _poll(client, workspace_id, processing.ingestion_job_id, raw_key)
        assert processing_payload["status"] == "processing"
        assert processing_payload["attempt_count"] == 1
        assert processing_payload["max_attempts"] == 4
        assert "next_attempt_at" not in processing_payload
        assert processing_payload["started_at"] is not None
        assert processing_payload["terminal_at"] is None

        retry_payload = _poll(client, workspace_id, retry.ingestion_job_id, raw_key)
        assert retry_payload["status"] == "retry_scheduled"
        assert retry_payload["attempt_count"] == 1
        assert retry_payload["max_attempts"] == 4
        assert (
            datetime.fromisoformat(retry_payload["next_attempt_at"])
            == retry_result.next_attempt_at
        )
        assert retry_payload["failure_reason"] is None
        assert retry_payload["terminal_at"] is None

        succeeded_payload = _poll(client, workspace_id, succeeded.ingestion_job_id, raw_key)
        assert succeeded_payload["status"] == "succeeded"
        assert succeeded_payload["attempt_count"] == 1
        assert succeeded_payload["max_attempts"] == 4
        assert "next_attempt_at" not in succeeded_payload
        assert succeeded_payload["failure_reason"] is None
        assert succeeded_payload["error_code"] is None
        assert succeeded_payload["result"] == {
            "document_version_id": succeeded.document_version_id
        }

        failed_payload = _poll(client, workspace_id, failed.ingestion_job_id, raw_key)
        assert failed_payload["status"] == "failed"
        assert failed_payload["attempt_count"] == 1
        assert failed_payload["max_attempts"] == 4
        assert failed_payload["failure_reason"] == "terminal_input"
        assert failed_payload["error_code"] == "invalid_input"
        assert "next_attempt_at" not in failed_payload
        assert "result" not in failed_payload

        exhausted_payload = _poll(client, workspace_id, exhausted.ingestion_job_id, raw_key)
        assert exhausted_payload["status"] == "failed"
        assert exhausted_payload["attempt_count"] == 4
        assert exhausted_payload["max_attempts"] == 4
        assert exhausted_payload["failure_reason"] == "retry_exhausted"
        assert exhausted_payload["error_code"] == "provider_transient"
        assert "next_attempt_at" not in exhausted_payload
        assert "result" not in exhausted_payload

        superseded_payload = _poll(
            client, workspace_id, superseded_a.ingestion_job_id, raw_key
        )
        assert superseded_payload["status"] == "superseded"
        assert superseded_payload["attempt_count"] == 1
        assert superseded_payload["max_attempts"] == 4
        assert superseded_payload["failure_reason"] is None
        assert superseded_payload["error_code"] is None
        assert "next_attempt_at" not in superseded_payload
        assert "result" not in superseded_payload
        assert (
            superseded_payload["replacement_document_version_id"]
            == superseded_b.document_version_id
        )


def test_processing_and_failed_poll_keep_previous_serving_tuple(tmp_path) -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )
    workspace_id = _workspace("previous serving poll")
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="acceptance-key")
    IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key="support/previous-serving",
            source_name="a.md",
            media_type="text/markdown",
            raw_content=b"# A\n\nHistorical active content.",
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        principal,
    )
    service, _ = _service(tmp_path)
    b_upload = _upload(
        service,
        workspace_id,
        source_key="support/previous-serving",
        source_name="b.pdf",
        raw=b"%PDF-1.7\nnew current content",
        idempotency_key="previous-serving-b",
    )
    store = PostgresIngestionJobStore(SessionFactory)
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="previous-serving-worker",
        timing=AttemptTimingV1.standard(),
    )
    assert claim.token.job_id == b_upload.ingestion_job_id
    client, raw_key = _poll_client(service, workspace_id)
    with client:
        processing = _poll(client, workspace_id, b_upload.ingestion_job_id, raw_key)
        assert processing["status"] == "processing"
        assert processing["target_document_version_id"] == b_upload.document_version_id
        assert processing["current_document_version_id"] == b_upload.document_version_id
        assert processing["served_document_version_id"] is not None
        assert processing["serving_state"] == "previous"
        served_a = processing["served_document_version_id"]

        store.finalize_terminal_failure(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim,
            failure=CanonicalFailureV1(
                cause=FailureCauseV1.INVALID_INPUT,
                safe_code="invalid_input",
                failure_reason="terminal_input",
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
        )
        failed = _poll(client, workspace_id, b_upload.ingestion_job_id, raw_key)
        assert failed["status"] == "failed"
        assert failed["target_document_version_id"] == b_upload.document_version_id
        assert failed["current_document_version_id"] == b_upload.document_version_id
        assert failed["served_document_version_id"] == served_a
        assert failed["serving_state"] == "previous"


def test_public_timestamp_sequence_keeps_first_started_at_across_retry(tmp_path) -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )
    service, _ = _service(tmp_path)
    workspace_id = _workspace("public timestamp sequence")
    job = _upload(
        service,
        workspace_id,
        source_key="support/timestamp-sequence",
        source_name="timestamps.pdf",
        raw=b"%PDF-1.7\ntimestamps",
        idempotency_key="timestamp-sequence",
    )
    store = PostgresIngestionJobStore(SessionFactory)
    client, raw_key = _poll_client(service, workspace_id)
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="timestamp-worker",
        timing=AttemptTimingV1.standard(),
    )
    with client:
        processing = _poll(client, workspace_id, job.ingestion_job_id, raw_key)
        started_at = processing["started_at"]
        updated_at = processing["updated_at"]
        assert processing["attempt_count"] == 1
        assert processing["terminal_at"] is None

        retry = store.schedule_retry(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim,
            failure=CanonicalFailureV1(
                cause=FailureCauseV1.PROVIDER_TRANSIENT,
                safe_code="provider_transient",
                failure_reason=None,
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
            decision=ScheduleRetry(delay_microseconds=0, window_upper_bound_microseconds=0),
        )
        retry_poll = _poll(client, workspace_id, job.ingestion_job_id, raw_key)
        assert retry_poll["status"] == "retry_scheduled"
        assert retry_poll["started_at"] == started_at
        assert retry_poll["updated_at"] != updated_at
        assert datetime.fromisoformat(retry_poll["next_attempt_at"]) == retry.next_attempt_at

        second_claim = store.claim_next_attempt(
            operation_id=ClaimOperationId(uuid4().hex),
            worker_id="timestamp-worker",
            timing=AttemptTimingV1.standard(),
        )
        second_poll = _poll(client, workspace_id, job.ingestion_job_id, raw_key)
        assert second_poll["status"] == "processing"
        assert second_poll["attempt_count"] == 2
        assert second_poll["started_at"] == started_at
        assert second_poll["updated_at"] != retry_poll["updated_at"]

        store.finalize_terminal_failure(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=second_claim,
            failure=CanonicalFailureV1(
                cause=FailureCauseV1.INVALID_INPUT,
                safe_code="invalid_input",
                failure_reason="terminal_input",
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
        )
        terminal = _poll(client, workspace_id, job.ingestion_job_id, raw_key)
        assert terminal["status"] == "failed"
        assert terminal["started_at"] == started_at
        assert terminal["terminal_at"] is not None
        assert terminal["updated_at"] != second_poll["updated_at"]


def test_historical_reprocess_rejection_is_side_effect_free(tmp_path) -> None:
    service, _ = _service(tmp_path)
    workspace_id = _workspace("historical reprocess rejection")
    first = _upload(
        service,
        workspace_id,
        source_key="support/historical-reject",
        source_name="a.pdf",
        raw=b"%PDF-1.7\nhistorical-a",
        idempotency_key="historical-a",
    )
    second = _upload(
        service,
        workspace_id,
        source_key="support/historical-reject",
        source_name="b.pdf",
        raw=b"%PDF-1.7\ncurrent-b",
        idempotency_key="historical-b",
    )
    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        assert document is not None
        current_before = document.current_document_version_id
        jobs_before = session.scalar(
            select(func.count())
            .select_from(IngestionJobTable)
            .where(IngestionJobTable.workspace_id == workspace_id)
        )
        audits_before = session.scalar(
            select(func.count())
            .select_from(ReprocessAuditTable)
            .where(ReprocessAuditTable.workspace_id == workspace_id)
        )
    assert current_before == second.document_version_id

    with pytest.raises(KnoraError, match="DOCUMENT_VERSION_NOT_CURRENT"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                workspace_id=workspace_id,
                document_version_id=first.document_version_id,
                config_mode="current",
                config_source_job_id=None,
                idempotency_key="historical-reject-key",
            ),
            WorkspacePrincipal(workspace_id=workspace_id, key_id="acceptance-key"),
        )

    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        assert document is not None
        assert document.current_document_version_id == current_before
        assert session.scalar(
            select(func.count())
            .select_from(IngestionJobTable)
            .where(IngestionJobTable.workspace_id == workspace_id)
        ) == jobs_before
        assert session.scalar(
            select(func.count())
            .select_from(ReprocessAuditTable)
            .where(ReprocessAuditTable.workspace_id == workspace_id)
        ) == audits_before


def test_reprocess_missing_key_and_unavailable_source_create_no_generation(tmp_path) -> None:
    service, object_store = _service(tmp_path)
    workspace_id = _workspace("reprocess unavailable source")
    upload = _upload(
        service,
        workspace_id,
        source_key="support/unavailable-source",
        source_name="source.pdf",
        raw=b"%PDF-1.7\nunavailable-source",
        idempotency_key="unavailable-upload",
    )
    _mark_succeeded(upload.ingestion_job_id)
    before = _job_count(workspace_id)
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="acceptance-key")
    with pytest.raises(KnoraError, match="MISSING_IDEMPOTENCY_KEY"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                workspace_id=workspace_id,
                document_version_id=upload.document_version_id,
                config_mode="current",
                config_source_job_id=None,
                idempotency_key="",
            ),
            principal,
        )
    with SessionFactory() as session:
        source_object = session.scalar(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.document_version_id == upload.document_version_id
            )
        )
    assert source_object is not None
    object_store.delete(
        workspace_id=workspace_id,
        object_key=source_object.object_key,
    )
    with pytest.raises(KnoraError, match="SOURCE_OBJECT_NOT_AVAILABLE"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                workspace_id=workspace_id,
                document_version_id=upload.document_version_id,
                config_mode="current",
                config_source_job_id=None,
                idempotency_key="unavailable-reprocess",
            ),
            principal,
        )
    assert _job_count(workspace_id) == before
