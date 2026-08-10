from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    DocumentTable,
    IngestionJobTable,
    ReprocessAuditTable,
    WorkspaceTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.job_processing import AttemptTimingV1, ClaimOperationId
from knora.ingestion.jobs import (
    IngestionJobs,
    PdfSubmissionCommand,
    PdfSubmissionConfiguration,
    ReprocessDocumentVersionCommand,
)
from knora.providers.embedding import EmbeddingConfiguration


def _configuration() -> PdfSubmissionConfiguration:
    return PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )


def _workspace(name: str) -> str:
    workspace_id = f"issue-19-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name=name))
    return workspace_id


def _submit(workspace_id: str, object_store: FileSystemObjectStore):
    service = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="key-a")
    return service.submit_pdf(
        PdfSubmissionCommand(
            workspace_id=workspace_id,
            source_key="support/issue-19.pdf",
            source_name="issue-19.pdf",
            media_type="application/pdf",
            stream=BytesIO(b"%PDF-1.7\nissue-19 source"),
            idempotency_key="upload-1",
            configuration=_configuration(),
        ),
        principal,
    )


def test_queued_job_has_public_projection_and_workspace_scoped_status(tmp_path) -> None:
    workspace_id = _workspace("queued projection")
    result = _submit(workspace_id, FileSystemObjectStore(tmp_path))
    projection = PostgresIngestionJobStore(SessionFactory).get_job_status(
        workspace_id=workspace_id,
        ingestion_job_id=result.ingestion_job_id,
    )

    assert projection is not None
    assert projection.status == "queued"
    assert projection.attempt_count == 0
    assert projection.max_attempts == 4
    assert projection.next_attempt_at is None
    assert projection.created_at.tzinfo is not None
    assert projection.updated_at.tzinfo is not None
    assert projection.started_at is None
    assert projection.terminal_at is None
    assert projection.target_document_version_id == result.document_version_id
    assert projection.current_document_version_id == result.document_version_id
    assert projection.served_document_version_id is None
    assert projection.serving_state == "unavailable"


def test_first_claim_projects_processing_and_immutable_started_at(tmp_path) -> None:
    workspace_id = _workspace("processing projection")
    _submit(workspace_id, FileSystemObjectStore(tmp_path))
    store = PostgresIngestionJobStore(SessionFactory)
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(str(uuid4())),
        worker_id="issue-19-worker",
        timing=AttemptTimingV1.standard(),
    )
    after = store.get_job_status(
        workspace_id=claim.work.workspace_id,
        ingestion_job_id=claim.token.job_id,
    )

    assert after is not None
    assert after.status == "processing"
    assert after.attempt_count == 1
    assert after.max_attempts == 4
    assert after.next_attempt_at is None
    assert after.started_at is not None
    assert after.started_at == after.updated_at


def test_reprocess_creates_one_audit_and_replays_same_binding(tmp_path) -> None:
    workspace_id = _workspace("reprocess audit")
    object_store = FileSystemObjectStore(tmp_path)
    upload = _submit(workspace_id, object_store)
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, upload.ingestion_job_id)
        document = session.get(DocumentTable, upload.document_id)
        assert job is not None and document is not None
        job.status = "succeeded"
        job.attempt_count = 1
        job.started_at = now
        job.terminal_at = now
        job.updated_at = now
        job.terminal_outcome_code = "succeeded"

    service = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    )
    command = ReprocessDocumentVersionCommand(
        workspace_id=workspace_id,
        document_version_id=upload.document_version_id,
        config_mode="current",
        config_source_job_id=None,
        idempotency_key="reprocess-1",
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="key-a")
    first = service.reprocess_document_version(command, principal)
    second = service.reprocess_document_version(command, principal)

    assert first.outcome == "reused"
    assert second.outcome == "idempotency_replay"
    assert first.ingestion_job_id == upload.ingestion_job_id
    assert second.ingestion_job_id == first.ingestion_job_id
    assert first.audit_id is not None
    audit = PostgresIngestionJobStore(SessionFactory).read_reprocess_audit(
        workspace_id=workspace_id,
        audit_event_id=first.audit_id,
    )
    assert audit is not None
    assert audit.workspace_id == workspace_id
    assert audit.actor_key_id == "key-a"
    assert audit.action == "document_version.reprocess"
    assert audit.target_document_version_id == upload.document_version_id
    assert audit.requested_config_mode == "current"
    assert audit.resolved_config_mode == "current"
    assert audit.ingestion_job_id == upload.ingestion_job_id
    assert audit.outcome == "reused"
    assert audit.created_at.tzinfo is not None
    with SessionFactory() as session:
        assert session.scalar(
            select(text("count(*)"))
            .select_from(ReprocessAuditTable)
            .where(ReprocessAuditTable.workspace_id == workspace_id)
        ) == 1


def test_reprocess_conflict_is_detected_before_selector_lookup(tmp_path) -> None:
    workspace_id = _workspace("reprocess conflict")
    object_store = FileSystemObjectStore(tmp_path)
    upload = _submit(workspace_id, object_store)
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, upload.ingestion_job_id)
        assert job is not None
        now = datetime.now(UTC)
        job.status = "succeeded"
        job.attempt_count = 1
        job.started_at = now
        job.terminal_at = now
        job.updated_at = now
        job.terminal_outcome_code = "succeeded"
    service = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="key-a")
    service.reprocess_document_version(
        ReprocessDocumentVersionCommand(
            workspace_id=workspace_id,
            document_version_id=upload.document_version_id,
            config_mode="current",
            config_source_job_id=None,
            idempotency_key="reprocess-conflict",
        ),
        principal,
    )

    with pytest.raises(KnoraError, match="IDEMPOTENCY_KEY_CONFLICT"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                workspace_id=workspace_id,
                document_version_id=upload.document_version_id,
                config_mode="same_as_job",
                config_source_job_id="does-not-exist",
                idempotency_key="reprocess-conflict",
            ),
            principal,
        )


def test_same_as_job_explicit_selector_links_fresh_generation_and_resets_budget(tmp_path) -> None:
    workspace_id = _workspace("same as job")
    object_store = FileSystemObjectStore(tmp_path)
    upload = _submit(workspace_id, object_store)
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        prior = session.get(IngestionJobTable, upload.ingestion_job_id)
        assert prior is not None
        prior.status = "failed"
        prior.attempt_count = 4
        prior.started_at = now
        prior.terminal_at = now
        prior.updated_at = now
        prior.failure_reason = "retry_exhausted"
        prior.safe_failure_code = "retry_exhausted"

    service = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    )
    result = service.reprocess_document_version(
        ReprocessDocumentVersionCommand(
            workspace_id=workspace_id,
            document_version_id=upload.document_version_id,
            config_mode="same_as_job",
            config_source_job_id=upload.ingestion_job_id,
            idempotency_key="same-as-job-1",
        ),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="key-a"),
    )

    assert result.outcome == "created"
    with SessionFactory() as session:
        fresh = session.get(IngestionJobTable, result.ingestion_job_id)
        prior = session.get(IngestionJobTable, upload.ingestion_job_id)
        assert fresh is not None and prior is not None
        assert fresh.id != prior.id
        assert fresh.reprocess_of_job_id == prior.id
        assert fresh.attempt_count == 0
        assert fresh.max_attempts == 4
        assert fresh.status == "queued"
        assert prior.status == "failed"
        assert prior.attempt_count == 4


def test_reprocess_source_selector_validation_precedes_generation_creation(tmp_path) -> None:
    workspace_id = _workspace("selector validation")
    object_store = FileSystemObjectStore(tmp_path)
    upload = _submit(workspace_id, object_store)
    service = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="key-a")
    with SessionFactory() as session:
        before = session.scalar(
            select(text("count(*)")).select_from(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id
            )
        )

    with pytest.raises(KnoraError, match="CONFIG_SOURCE_JOB_REQUIRED"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                workspace_id=workspace_id,
                document_version_id=upload.document_version_id,
                config_mode="same_as_job",
                config_source_job_id=None,
                idempotency_key="selector-missing",
            ),
            principal,
        )
    with pytest.raises(KnoraError, match="CONFIG_SOURCE_JOB_INVALID"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                workspace_id=workspace_id,
                document_version_id=upload.document_version_id,
                config_mode="same_as_job",
                config_source_job_id="not-a-source-job",
                idempotency_key="selector-invalid",
            ),
            principal,
        )
    with pytest.raises(KnoraError, match="CONFIG_SOURCE_JOB_NOT_ALLOWED"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                workspace_id=workspace_id,
                document_version_id=upload.document_version_id,
                config_mode="current",
                config_source_job_id=upload.ingestion_job_id,
                idempotency_key="selector-current-with-source",
            ),
            principal,
        )
    with SessionFactory() as session:
        assert session.scalar(
            select(text("count(*)")).select_from(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id
            )
        ) == before
