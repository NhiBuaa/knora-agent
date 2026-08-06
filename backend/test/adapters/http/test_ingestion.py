import asyncio
from dataclasses import dataclass, field, replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from knora.access.api_keys import (
    ApiCredential,
    ApiKeyAuthenticator,
    hash_api_key,
)
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    IngestionJobTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.ingestion.interface import IngestionResult
from knora.ingestion.jobs import IngestionJobs, PdfSubmissionResult
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import DocumentProcessor
from knora.main import create_app
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration

RAW_KEY_A = "test-http-key-a"
RAW_KEY_B = "test-http-key-b"
RAW_KEY_DISABLED = "test-http-key-disabled"


def authenticator() -> ApiKeyAuthenticator:
    return ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="test-a",
                key_hash=hash_api_key(RAW_KEY_A),
                workspace_id="workspace-a",
                enabled=True,
            ),
            ApiCredential(
                key_id="test-b",
                key_hash=hash_api_key(RAW_KEY_B),
                workspace_id="workspace-b",
                enabled=True,
            ),
            ApiCredential(
                key_id="test-disabled",
                key_hash=hash_api_key(RAW_KEY_DISABLED),
                workspace_id="workspace-a",
                enabled=False,
            ),
        )
    )


@dataclass
class RecordingIngestDocument:
    result: IngestionResult
    calls: list[tuple] = field(default_factory=list)

    def execute(self, command, principal):
        self.calls.append((command, principal))
        return self.result


class WorkerThreadIngestDocument(RecordingIngestDocument):
    def execute(self, command, principal):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        return super().execute(command, principal)


@dataclass
class RecordingIngestionJobs:
    result: PdfSubmissionResult
    calls: list[tuple] = field(default_factory=list)
    streamed_bytes: list[bytes] = field(default_factory=list)

    def submit_pdf(self, command, principal):
        self.calls.append((command, principal))
        self.streamed_bytes.append(command.stream.read())
        return self.result


def created_result() -> IngestionResult:
    return IngestionResult(
        outcome="created",
        activation_changed=True,
        document_id="document-1",
        document_version_id="version-1",
        chunk_set_id="chunk-set-1",
        embedding_set_id="embedding-set-1",
        chunking_configuration_id="chunking-m1-v1",
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_count=2,
    )


def client_with(
    service,
    *,
    embedding_configuration: EmbeddingConfiguration | None = None,
    ingestion_jobs=None,
) -> TestClient:
    return TestClient(
        create_app(
            ingest_document=service,
            ingestion_jobs=ingestion_jobs,
            api_key_authenticator=authenticator(),
            embedding_configuration=embedding_configuration,
        )
    )


def valid_upload(client: TestClient, *, key: str | None, workspace_id: str = "workspace-a"):
    headers = {"X-API-Key": key} if key is not None else {}
    return client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        data={"source_key": "support/refund-policy"},
        files={"file": ("refund-policy.md", b"# Refunds\n\nRefunds last 30 days.\n")},
    )


def valid_pdf_upload(
    client: TestClient,
    *,
    key: str | None,
    workspace_id: str = "workspace-a",
    idempotency_key: str = "pdf-request-1",
):
    headers = {"Idempotency-Key": idempotency_key}
    if key is not None:
        headers["X-API-Key"] = key
    return client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        data={"source_key": "support/refund-policy"},
        files={"file": ("refund-policy.pdf", b"%PDF-1.7\nsmall fixture")},
    )


def test_health_is_public_and_minimal() -> None:
    service = RecordingIngestDocument(created_result())
    response = client_with(service).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "knora-agent"}


def test_missing_and_invalid_keys_are_rejected_before_ingestion() -> None:
    service = RecordingIngestDocument(created_result())
    client = client_with(service)

    missing = valid_upload(client, key=None)
    invalid = valid_upload(client, key="unknown-key")
    disabled = valid_upload(client, key=RAW_KEY_DISABLED)

    assert missing.status_code == 401
    assert missing.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert invalid.status_code == 401
    assert invalid.json() == missing.json()
    assert disabled.status_code == 401
    assert disabled.json() == missing.json()
    assert service.calls == []


def test_workspace_mismatch_is_rejected_before_ingestion() -> None:
    service = RecordingIngestDocument(created_result())

    response = valid_upload(client_with(service), key=RAW_KEY_A, workspace_id="workspace-b")

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert service.calls == []


def test_created_and_reused_results_use_distinct_http_statuses() -> None:
    created_service = RecordingIngestDocument(created_result())
    created = valid_upload(client_with(created_service), key=RAW_KEY_A)

    assert created.status_code == 201
    assert created.json() == {
        "outcome": "created",
        "activation_changed": True,
        "document_id": "document-1",
        "document_version_id": "version-1",
        "chunk_set_id": "chunk-set-1",
        "embedding_set_id": "embedding-set-1",
        "chunking_configuration_id": "chunking-m1-v1",
        "embedding_configuration_id": "embedding-local-m1-v2",
        "chunk_count": 2,
    }
    command, principal = created_service.calls[0]
    assert command.workspace_id == "workspace-a"
    assert command.source_key == "support/refund-policy"
    assert command.source_name == "refund-policy.md"
    assert principal.workspace_id == "workspace-a"
    assert principal.key_id == "test-a"

    reused_service = RecordingIngestDocument(
        replace(created_result(), outcome="reused", activation_changed=False)
    )
    reused = valid_upload(client_with(reused_service), key=RAW_KEY_A)

    assert reused.status_code == 200
    assert reused.json()["outcome"] == "reused"
    assert reused.json()["activation_changed"] is False


def test_http_ingestion_uses_the_runtime_embedding_configuration() -> None:
    service = RecordingIngestDocument(created_result())
    configuration = EmbeddingConfiguration.openai_compatible(
        configuration_id="embedding-openai-m1-v1",
        model="text-embedding-3-small",
    )

    response = valid_upload(
        client_with(service, embedding_configuration=configuration),
        key=RAW_KEY_A,
    )

    assert response.status_code == 201
    command, _ = service.calls[0]
    assert command.embedding_configuration == configuration


def test_http_ingestion_does_not_block_the_async_route() -> None:
    response = valid_upload(
        client_with(WorkerThreadIngestDocument(created_result())),
        key=RAW_KEY_A,
    )

    assert response.status_code == 201


def test_pdf_upload_returns_durable_job_response_without_reading_into_application_memory() -> None:
    jobs = RecordingIngestionJobs(
        PdfSubmissionResult(
            ingestion_job_id="job-1",
            submission_outcome="created",
            status="queued",
            document_id="document-1",
            document_version_id="version-1",
            retained_object_key="opaque/source-1",
        )
    )
    client = client_with(RecordingIngestDocument(created_result()), ingestion_jobs=jobs)

    response = valid_pdf_upload(client, key=RAW_KEY_A)

    assert response.status_code == 202
    assert response.json() == {
        "ingestion_job_id": "job-1",
        "submission_outcome": "created",
        "status": "queued",
        "document_id": "document-1",
        "document_version_id": "version-1",
    }
    command, principal = jobs.calls[0]
    assert command.source_name == "refund-policy.pdf"
    assert command.media_type == "application/pdf"
    assert command.idempotency_key == "pdf-request-1"
    assert jobs.streamed_bytes == [b"%PDF-1.7\nsmall fixture"]
    assert principal.workspace_id == "workspace-a"


def test_pdf_upload_authentication_and_workspace_mismatch_precede_job_submission() -> None:
    jobs = RecordingIngestionJobs(
        PdfSubmissionResult(
            ingestion_job_id="job-1",
            submission_outcome="created",
            status="queued",
            document_id="document-1",
            document_version_id="version-1",
            retained_object_key="opaque/source-1",
        )
    )
    client = client_with(RecordingIngestDocument(created_result()), ingestion_jobs=jobs)

    missing = valid_pdf_upload(client, key=None)
    mismatch = valid_pdf_upload(client, key=RAW_KEY_A, workspace_id="workspace-b")

    assert missing.status_code == 401
    assert mismatch.status_code == 403
    assert jobs.calls == []


def test_pdf_upload_uses_terminal_replay_http_status() -> None:
    jobs = RecordingIngestionJobs(
        PdfSubmissionResult(
            ingestion_job_id="job-1",
            submission_outcome="idempotency_replay",
            status="succeeded",
            document_id="document-1",
            document_version_id="version-1",
            retained_object_key="opaque/source-1",
        )
    )

    response = valid_pdf_upload(
        client_with(RecordingIngestDocument(created_result()), ingestion_jobs=jobs),
        key=RAW_KEY_A,
    )

    assert response.status_code == 200
    assert response.json()["submission_outcome"] == "idempotency_replay"
    assert response.json()["status"] == "succeeded"


def test_pdf_upload_rejects_a_mismatched_declared_media_type() -> None:
    jobs = RecordingIngestionJobs(created_result())
    client = client_with(RecordingIngestDocument(created_result()), ingestion_jobs=jobs)

    response = client.post(
        "/v1/workspaces/workspace-a/documents",
        headers={"X-API-Key": RAW_KEY_A, "Idempotency-Key": "pdf-request-1"},
        data={"source_key": "support/refund-policy"},
        files={
            "file": (
                "refund-policy.pdf",
                b"%PDF-1.7\nsmall fixture",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "UNSUPPORTED_DOCUMENT_TYPE"}}
    assert jobs.calls == []


def test_pdf_declared_media_type_cannot_bypass_the_filename_contract() -> None:
    jobs = RecordingIngestionJobs(created_result())
    client = client_with(RecordingIngestDocument(created_result()), ingestion_jobs=jobs)

    response = client.post(
        "/v1/workspaces/workspace-a/documents",
        headers={"X-API-Key": RAW_KEY_A, "Idempotency-Key": "pdf-request-1"},
        data={"source_key": "support/refund-policy"},
        files={
            "file": (
                "refund-policy.txt",
                b"%PDF-1.7\nsmall fixture",
                "application/pdf; charset=binary",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "UNSUPPORTED_DOCUMENT_TYPE"}}
    assert jobs.calls == []


def test_http_pdf_submission_persists_source_object_and_queued_job(tmp_path) -> None:
    workspace_id = f"test-http-pdf-{uuid4()}"
    raw_key = f"key-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="HTTP PDF submission"))
    auth = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="integration",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    object_store = FileSystemObjectStore(tmp_path)
    jobs = IngestionJobs(
        object_store=object_store,
        store=PostgresIngestionJobStore(SessionFactory),
    )
    client = TestClient(
        create_app(api_key_authenticator=auth, ingestion_jobs=jobs)
    )

    response = valid_pdf_upload(client, key=raw_key, workspace_id=workspace_id)

    assert response.status_code == 202
    payload = response.json()
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, payload["ingestion_job_id"])
        source_object = session.get(OriginalSourceObjectTable, job.source_object_id)
        assert job.status == "queued"
        assert job.target_document_version_id == payload["document_version_id"]
        assert source_object.workspace_id == workspace_id
        assert source_object.raw_sha256 == (
            "79c6a101650ef352a7dacc99e21965cc204e80717683d4216a21b7af7798c0d9"
        )
        assert object_store.head(
            workspace_id=workspace_id,
            object_key=source_object.object_key,
        ).byte_size == len(b"%PDF-1.7\nsmall fixture")


@dataclass
class GuardedStore:
    def authorize_workspace(self, *, workspace_id: str) -> None:
        return None

    def read_document_head(self, *, workspace_id: str, source_key: str):
        return None

    def commit_derivation(self, *, prepared, expected_revision):
        raise AssertionError("invalid request must fail before persistence")


@dataclass
class CountingProvider:
    calls: int = 0

    def embed(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        self.calls += 1
        raise AssertionError("invalid request must fail before embedding")


def guarded_client() -> tuple[TestClient, CountingProvider]:
    provider = CountingProvider()
    service = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=provider, store=GuardedStore()
    )
    return client_with(service), provider


def test_invalid_source_type_and_size_fail_before_provider_work() -> None:
    client, provider = guarded_client()

    invalid_source = client.post(
        "/v1/workspaces/workspace-a/documents",
        headers={"X-API-Key": RAW_KEY_A},
        data={"source_key": "/internal/refund-policy"},
        files={"file": ("refund-policy.md", b"valid text")},
    )
    unsupported = client.post(
        "/v1/workspaces/workspace-a/documents",
        headers={"X-API-Key": RAW_KEY_A},
        data={"source_key": "support/refund-policy"},
        files={"file": ("refund-policy.json", b"{}")},
    )
    invalid_encoding = client.post(
        "/v1/workspaces/workspace-a/documents",
        headers={"X-API-Key": RAW_KEY_A},
        data={"source_key": "support/refund-policy"},
        files={"file": ("refund-policy.txt", b"\xff\xfe")},
    )
    oversized = client.post(
        "/v1/workspaces/workspace-a/documents",
        headers={"X-API-Key": RAW_KEY_A},
        data={"source_key": "support/refund-policy"},
        files={"file": ("refund-policy.txt", b"x" * (1024 * 1024 + 1))},
    )

    assert invalid_source.status_code == 400
    assert invalid_source.json() == {"error": {"code": "INVALID_SOURCE_KEY"}}
    assert unsupported.status_code == 400
    assert unsupported.json() == {"error": {"code": "UNSUPPORTED_DOCUMENT_TYPE"}}
    assert invalid_encoding.status_code == 400
    assert invalid_encoding.json() == {"error": {"code": "INVALID_DOCUMENT_ENCODING"}}
    assert oversized.status_code == 413
    assert oversized.json() == {
        "error": {"code": "DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION"}
    }
    assert provider.calls == 0


def test_http_ingestion_creates_then_reuses_postgres_derivation() -> None:
    workspace_id = f"test-http-{uuid4()}"
    raw_key = f"key-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="HTTP ingestion integration"))
    auth = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="integration",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    client = TestClient(create_app(api_key_authenticator=auth))

    created = valid_upload(client, key=raw_key, workspace_id=workspace_id)
    reused = valid_upload(client, key=raw_key, workspace_id=workspace_id)

    assert created.status_code == 201
    assert created.json()["outcome"] == "created"
    assert created.json()["activation_changed"] is True
    assert reused.status_code == 200
    assert reused.json()["outcome"] == "reused"
    assert reused.json()["activation_changed"] is False
    for resource_id in (
        "document_id",
        "document_version_id",
        "chunk_set_id",
        "embedding_set_id",
        "chunking_configuration_id",
        "embedding_configuration_id",
    ):
        assert reused.json()[resource_id] == created.json()[resource_id]


def test_http_persistence_failure_returns_only_a_stable_error_code() -> None:
    workspace_id = f"test-http-{uuid4()}"
    raw_key = f"key-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="HTTP persistence failure"))
    auth = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="integration",
                key_hash=hash_api_key(raw_key),
                workspace_id=workspace_id,
                enabled=True,
            ),
        )
    )
    client = TestClient(create_app(api_key_authenticator=auth))
    canary = "database-canary"

    response = client.post(
        f"/v1/workspaces/{workspace_id}/documents",
        headers={"X-API-Key": raw_key},
        data={"source_key": "support/persistence-failure"},
        files={"file": (f"{canary}-{'x' * 300}.md", b"# Refunds\n\nThirty days.\n")},
    )

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "PERSISTENCE_OPERATION_FAILED"}}
    assert canary not in response.text
