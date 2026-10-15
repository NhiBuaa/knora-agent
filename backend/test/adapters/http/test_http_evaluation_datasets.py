from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from knora.adapters.http.evaluation_datasets import get_dataset_service, router
from knora.adapters.http.routes import require_operator_read
from knora.domain.access import WorkspacePrincipal


class RecordingService:
    def create_dataset(self, workspace_id, name, principal):
        assert (workspace_id, name, principal.workspace_id) == ("w1", "Review", "w1")
        return type(
            "Dataset", (), {"id": "d1", "workspace_id": "w1", "name": "Review", "status": "DRAFT"}
        )()

    def get_dataset(self, workspace_id, dataset_id, principal):
        return self.create_dataset(workspace_id, "Review", principal)

    def list_sources(self, workspace_id, dataset_id, principal):
        return ()

    def upload_source(self, workspace_id, dataset_id, filename, media_type, stream, key, principal):
        assert (workspace_id, dataset_id, filename, media_type, key) == (
            "w1",
            "d1",
            "sample.pdf",
            "application/pdf",
            "upload-1",
        )
        assert stream.read() == b"%PDF-test"
        return type(
            "Source",
            (),
            {
                "id": "s1",
                "dataset_id": "d1",
                "document_id": "doc1",
                "document_version_id": "ver1",
                "filename": "sample.pdf",
                "raw_sha256": "a" * 64,
                "byte_size": 9,
                "status": "FAILED",
                "failure_code": "PDF_TEXT_INSUFFICIENT",
                "snapshot_id": None,
            },
        )()


def test_route_upload_returns_source_status_without_storage_key():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_operator_read] = lambda: WorkspacePrincipal(
        "w1", "owner", ("operator:read", "evaluations:write", "documents:write")
    )
    app.dependency_overrides[get_dataset_service] = RecordingService
    client = TestClient(app)
    response = client.post(
        "/v1/workspaces/w1/evaluation/datasets/d1/sources",
        files={"file": ("sample.pdf", b"%PDF-test", "application/pdf")},
        headers={"Idempotency-Key": "upload-1"},
    )
    assert response.status_code == 201
    assert response.json()["failure_code"] == "PDF_TEXT_INSUFFICIENT"
    assert "object_key" not in response.json()
    assert "no-store" in response.headers["cache-control"]


def test_route_create_and_read_draft():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_operator_read] = lambda: WorkspacePrincipal(
        "w1", "owner", ("operator:read", "evaluations:write")
    )
    app.dependency_overrides[get_dataset_service] = RecordingService
    client = TestClient(app)
    created = client.post("/v1/workspaces/w1/evaluation/datasets", json={"name": "Review"})
    assert created.status_code == 201
    assert created.json()["status"] == "DRAFT"
    detail = client.get("/v1/workspaces/w1/evaluation/datasets/d1")
    assert detail.status_code == 200
    assert detail.json()["sources"] == []
