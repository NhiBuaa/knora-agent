"""The CLI worker consumes a durable PDF job from a separate process."""

import os
import subprocess
import sys
from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import text

from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import DocumentTable, WorkspaceTable
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.jobs import IngestionJobs, PdfSubmissionCommand, PdfSubmissionConfiguration
from knora.providers.embedding import EmbeddingConfiguration


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
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
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 1 0 0 1 72 720 Tm (Worker evidence.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_cli_worker_claims_pdf_job_and_activates_embedding_set(tmp_path) -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE workspace_admissions, reprocess_audit_records, "
                "idempotency_records, ingestion_job_attempts, ingestion_jobs"
            )
        )
    workspace_id = f"cli-worker-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="CLI worker"))
    object_store = FileSystemObjectStore(tmp_path)
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="test")
    submission = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    ).submit_pdf(
        PdfSubmissionCommand(
            workspace_id=workspace_id,
            source_key="worker-evidence.pdf",
            source_name="worker-evidence.pdf",
            media_type="application/pdf",
            stream=BytesIO(_pdf_bytes()),
            idempotency_key=f"worker-{uuid4()}",
            configuration=PdfSubmissionConfiguration.milestone_two(
                embedding_configuration=EmbeddingConfiguration.milestone_one_local()
            ),
        ),
        principal,
    )

    environment = os.environ.copy()
    environment["KNORA_OBJECT_STORE_ROOT"] = str(tmp_path)
    environment["KNORA_OBJECT_STORE_BACKEND"] = "filesystem"
    environment["KNORA_PROVIDER_MODE"] = "deterministic-local"
    environment.pop("KNORA_EMBEDDING_PROVIDER", None)
    environment.pop("KNORA_GENERATION_PROVIDER", None)
    process = subprocess.run(
        [sys.executable, "-m", "knora.adapters.cli.worker", "--once"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    status = PostgresIngestionJobStore(SessionFactory).get_job_status(
        workspace_id=workspace_id, ingestion_job_id=submission.ingestion_job_id
    )
    assert status is not None
    assert status.status == "succeeded"
    with SessionFactory() as session:
        document = session.get(DocumentTable, submission.document_id)
        assert document is not None
        assert document.active_embedding_set_id is not None
    projection = PostgresDocumentReader(SessionFactory).read_document(
        workspace_id=workspace_id, document_id=submission.document_id, principal=principal
    )
    assert projection.reprocess_supported is True
    reader = PostgresDocumentReader(SessionFactory)
    reader.archive(
        workspace_id=workspace_id,
        document_id=submission.document_id,
        principal=principal,
    )
    assert reader.read_document(
        workspace_id=workspace_id,
        document_id=submission.document_id,
        principal=principal,
    ).reprocess_supported is False


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object preflight")
def test_cli_preflight_proves_pdf_child_memory_limit() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "knora.adapters.cli.worker", "--check-pdf-isolation"],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert process.returncode == 0, process.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object memory limit")
def test_memory_probe_rejects_missing_job_object_limit(monkeypatch) -> None:
    from knora.adapters.cli.worker import prove_windows_pdf_memory_limit
    from knora.adapters.pdf import _pypdf_process

    monkeypatch.setattr(_pypdf_process, "_install_windows_memory_limit", lambda *_args: None)

    assert prove_windows_pdf_memory_limit() is False


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object memory limit")
def test_memory_probe_blocks_a_child_that_exceeds_256_mib() -> None:
    from knora.adapters.cli.worker import prove_windows_pdf_memory_limit

    assert prove_windows_pdf_memory_limit() is True
