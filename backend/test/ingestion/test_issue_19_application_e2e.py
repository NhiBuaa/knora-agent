from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import func, select, text

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import DocumentVersionTable, IngestionJobTable, WorkspaceTable
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    PdfDerivationHandler,
    PdfDerivationProfile,
    ProcessIngestionJob,
    RetryPolicyV1,
    SystemRandomSource,
    UuidOperationIds,
)
from knora.ingestion.jobs import IngestionJobs
from knora.main import create_app
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


def _pdf_with_pages(*pages: str) -> bytes:
    writer = PdfWriter()
    for page_text in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        escaped = page_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands = ["BT /F1 12 Tf", f"1 0 0 1 72 720 Tm ({escaped}) Tj", "ET"]
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_public_upload_worker_poll_and_citation_use_one_job_flow(tmp_path: Path) -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )
    workspace_id = f"issue-19-e2e-{uuid4()}"
    raw_key = f"issue-19-e2e-key-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Issue 19 E2E"))

    embedding_configuration = EmbeddingConfiguration.milestone_one_local()
    object_store = FileSystemObjectStore(tmp_path)
    store = PostgresIngestionJobStore(SessionFactory)
    jobs = IngestionJobs(object_store=object_store, store=store)
    worker = ProcessIngestionJob(
        store=store,
        handler=PdfDerivationHandler(
            object_store=object_store,
            extractor=PypdfTextExtractor(),
            embedding_provider=DeterministicEmbeddingProvider(),
            profile=PdfDerivationProfile.milestone_two(
                embedding_configuration=embedding_configuration
            ),
        ),
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
    )
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="issue-19-e2e-key",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    app = create_app(
        ingestion_jobs=jobs,
        ingestion_worker=worker,
        api_key_authenticator=authenticator,
        embedding_configuration=embedding_configuration,
    )
    pdf = _pdf_with_pages("Introductory page.", "The unique fact is blue umbrellas.")
    with TestClient(app) as client:
        headers = {"X-API-Key": raw_key, "Idempotency-Key": "issue-19-upload"}
        upload = client.post(
            f"/v1/workspaces/{workspace_id}/documents",
            headers=headers,
            data={"source_key": "support/issue-19-e2e"},
            files={"file": ("issue-19-e2e.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 202
        job_id = upload.json()["ingestion_job_id"]

        worker_result = app.state.ingestion_worker.run_once("issue-19-e2e-worker")
        assert worker_result.__class__.__name__ == "Succeeded", worker_result

        poll = client.get(
            f"/v1/workspaces/{workspace_id}/ingestion-jobs/{job_id}",
            headers={"X-API-Key": raw_key},
        )
        assert poll.status_code == 200
        projection = poll.json()
        assert projection["status"] == "succeeded"
        assert projection["result"] == {
            "document_version_id": upload.json()["document_version_id"]
        }
        assert projection["serving_state"] == "current"

        question = client.post(
            "/v1/questions",
            headers={"X-API-Key": raw_key},
            json={
                "workspace_id": workspace_id,
                "question": "The unique fact is blue umbrellas.",
            },
        )
        assert question.status_code == 200
        answer = question.json()
        assert answer["decision"] == "ANSWER"
        assert answer["citations"]
        citation = answer["citations"][0]
        assert citation["document_version_id"] == upload.json()[
            "document_version_id"
        ]
        assert citation["page_start"] == 2
        assert citation["page_end"] == 2
        assert citation["start_offset"] == 0
        assert citation["end_offset"] == len("The unique fact is blue umbrellas.")
        assert citation["excerpt"] == "The unique fact is blue umbrellas."


def test_public_upload_status_and_idempotency_branches_match_durable_job(tmp_path: Path) -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )
    workspace_id = f"issue-19-upload-branches-{uuid4()}"
    raw_key = f"issue-19-upload-key-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Issue 19 upload branches"))

    object_store = FileSystemObjectStore(tmp_path)
    jobs = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    )
    embedding_configuration = EmbeddingConfiguration.milestone_one_local()
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="issue-19-upload-branches-key",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    app = create_app(
        ingestion_jobs=jobs,
        api_key_authenticator=authenticator,
        embedding_configuration=embedding_configuration,
    )
    pdf = b"%PDF-1.7\nstatus branch fixture"

    def upload(key: str, filename: str):
        return client.post(
            f"/v1/workspaces/{workspace_id}/documents",
            headers={"X-API-Key": raw_key, "Idempotency-Key": key},
            data={"source_key": "support/status-branches"},
            files={"file": (filename, pdf, "application/pdf")},
        )

    with TestClient(app) as client:
        created = upload("status-created", "first.pdf")
        replay_non_terminal = upload("status-created", "renamed.pdf")
        dedup_non_terminal = upload("status-dedup", "dedup.pdf")
        assert created.status_code == 202
        assert created.json()["submission_outcome"] == "created"
        assert created.json()["status"] == "queued"
        assert replay_non_terminal.status_code == 202
        assert replay_non_terminal.json()["submission_outcome"] == "idempotency_replay"
        assert replay_non_terminal.json()["status"] == "queued"
        assert dedup_non_terminal.status_code == 202
        assert dedup_non_terminal.json()["submission_outcome"] == "deduplicated"
        assert dedup_non_terminal.json()["status"] == "queued"

        job_id = created.json()["ingestion_job_id"]
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

        replay_terminal = upload("status-created", "terminal-replay.pdf")
        dedup_terminal = upload("status-dedup-terminal", "terminal-dedup.pdf")
        assert replay_terminal.status_code == 200
        assert replay_terminal.json()["submission_outcome"] == "idempotency_replay"
        assert replay_terminal.json()["status"] == "succeeded"
        assert dedup_terminal.status_code == 200
        assert dedup_terminal.json()["submission_outcome"] == "deduplicated"
        assert dedup_terminal.json()["status"] == "succeeded"
        assert {
            created.json()["ingestion_job_id"],
            replay_non_terminal.json()["ingestion_job_id"],
            dedup_non_terminal.json()["ingestion_job_id"],
            replay_terminal.json()["ingestion_job_id"],
            dedup_terminal.json()["ingestion_job_id"],
        } == {job_id}
        with SessionFactory() as session:
            assert session.scalar(
                select(func.count())
                .select_from(IngestionJobTable)
                .where(IngestionJobTable.workspace_id == workspace_id)
            ) == 1
            assert session.scalar(
                select(func.count())
                .select_from(DocumentVersionTable)
                .join(
                    IngestionJobTable,
                    IngestionJobTable.target_document_version_id == DocumentVersionTable.id,
                )
                .where(IngestionJobTable.workspace_id == workspace_id)
            ) == 1
