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
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import WorkspaceTable
from knora.ingestion.interface import IngestionResult
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import DocumentProcessor
from knora.main import create_app
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration

RAW_KEY_A = "test-http-key-a"
RAW_KEY_B = "test-http-key-b"


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
) -> TestClient:
    return TestClient(
        create_app(
            ingest_document=service,
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

    assert missing.status_code == 401
    assert missing.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert invalid.status_code == 401
    assert invalid.json() == missing.json()
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
