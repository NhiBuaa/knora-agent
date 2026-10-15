from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from knora.access.identity import Identity
from knora.adapters.http.evaluation_datasets import get_dataset_service, router
from knora.adapters.http.routes import require_operator_read
from knora.adapters.http.workspaces import require_identity
from knora.domain.access import WorkspacePrincipal
from knora.evaluation.datasets import Dataset


class RecordingService:
    def create_dataset(self, workspace_id, name, principal):
        assert (workspace_id, name, principal.workspace_id) == ("w1", "Review", "w1")
        return Dataset("d1", "w1", "Review", "DRAFT")

    def get_dataset(self, workspace_id, dataset_id, principal):
        return self.create_dataset(workspace_id, "Review", principal)

    def list_sources(self, workspace_id, dataset_id, principal):
        return ()

    def save_case(self, workspace_id, dataset_id, case, expected_revision, principal):
        assert (workspace_id, dataset_id, case.case_id, expected_revision) == (
            "w1",
            "d1",
            "case-1",
            0,
        )
        return type(
            "Dataset",
            (),
            {
                "id": "d1",
                "workspace_id": "w1",
                "name": "Review",
                "status": "DRAFT",
                "revision": 1,
                "cases": (case,),
                "reviews": (),
                "reference": None,
            },
        )()

    def review_case(
        self,
        workspace_id,
        dataset_id,
        case_id,
        decision,
        expected_revision,
        principal,
        *,
        identity,
        note,
    ):
        assert (case_id, decision, expected_revision) == ("case-1", "ACCEPTED", 1)
        return type(
            "Dataset",
            (),
            {
                "id": "d1",
                "workspace_id": "w1",
                "name": "Review",
                "status": "DRAFT",
                "revision": 2,
                "cases": (),
                "reviews": (),
                "reference": None,
            },
        )()

    def freeze_dataset(
        self, workspace_id, dataset_id, expected_revision, principal, *, identity, gold_digest
    ):
        assert identity.issuer == "https://identity.example"
        assert gold_digest == "a" * 64
        return type(
            "Frozen",
            (),
            {"to_json": lambda self: '{"reference":{"version":1},"gold":{"cases":[]}}'},
        )()

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


def test_route_case_edit_review_and_freeze_use_canonical_payloads():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_operator_read] = lambda: WorkspacePrincipal(
        "w1", "owner", ("operator:read", "evaluations:write", "evaluations:approve")
    )
    app.dependency_overrides[get_dataset_service] = RecordingService
    app.dependency_overrides[require_identity] = lambda: Identity(
        "https://identity.example", "owner"
    )
    client = TestClient(app)
    payload = {
        "case_id": "case-1",
        "question": "What?",
        "expected": "ANSWER",
        "reference_answer": "Answer",
        "required_facts": ["Answer"],
        "language": "en",
        "category": "single-hop",
        "evidence_groups": [
            {
                "alternatives": [
                    {
                        "document_version_id": "ver1",
                        "physical_page": 1,
                        "quote": "Answer",
                        "extraction_snapshot_id": None,
                        "extraction_sha256": None,
                        "start_offset": None,
                        "end_offset": None,
                    }
                ]
            }
        ],
        "context_dependencies": [],
        "no_answer_scope": None,
    }
    saved = client.put(
        "/v1/workspaces/w1/evaluation/datasets/d1/cases/case-1",
        json={"case": payload, "expected_revision": 0},
    )
    assert saved.status_code == 200
    reviewed = client.post(
        "/v1/workspaces/w1/evaluation/datasets/d1/cases/case-1/review",
        json={"decision": "ACCEPTED", "expected_revision": 1, "note": "Checked original PDF"},
    )
    assert reviewed.status_code == 200
    frozen = client.post(
        "/v1/workspaces/w1/evaluation/datasets/d1/freeze",
        json={"expected_revision": 2, "gold_digest": "a" * 64},
    )
    assert frozen.status_code == 200
    assert frozen.json()["reference"]["version"] == 1
