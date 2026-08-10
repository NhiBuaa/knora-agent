from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import JobStatusProjection, ReprocessResult
from knora.main import create_app

RAW_KEY = "issue-19-http-key"


@dataclass
class FakeJobs:
    projection: JobStatusProjection
    status_calls: int = 0
    reprocess_calls: int = 0

    def get_job_status(self, *, ingestion_job_id: str, principal: WorkspacePrincipal):
        self.status_calls += 1
        return self.projection

    def reprocess_document_version(self, command, principal):
        self.reprocess_calls += 1
        return ReprocessResult(
            ingestion_job_id="job-reprocess",
            document_version_id=command.document_version_id,
            outcome="created",
            status="queued",
            audit_id="audit-1",
        )


def _client(fake: FakeJobs) -> TestClient:
    return TestClient(
        create_app(
            ingestion_jobs=fake,
            api_key_authenticator=ApiKeyAuthenticator(
                (
                    ApiCredential(
                        key_id="issue-19",
                        key_hash=hash_api_key(RAW_KEY),
                        workspace_id="workspace-a",
                        enabled=True,
                    ),
                )
            ),
        )
    )


def _client_for_workspace(fake: FakeJobs, workspace_id: str, raw_key: str) -> TestClient:
    return TestClient(
        create_app(
            ingestion_jobs=fake,
            api_key_authenticator=ApiKeyAuthenticator(
                (
                    ApiCredential(
                        key_id=f"{workspace_id}-key",
                        key_hash=hash_api_key(raw_key),
                        workspace_id=workspace_id,
                        enabled=True,
                    ),
                )
            ),
        )
    )


def _projection() -> JobStatusProjection:
    timestamp = datetime(2026, 8, 10, 5, 0, tzinfo=UTC)
    return JobStatusProjection(
        ingestion_job_id="job-1",
        status="succeeded",
        attempt_count=1,
        max_attempts=4,
        next_attempt_at=None,
        created_at=timestamp,
        started_at=timestamp,
        updated_at=timestamp,
        terminal_at=timestamp,
        target_document_version_id="version-1",
        current_document_version_id="version-1",
        served_document_version_id=None,
        serving_state="unavailable",
        failure_reason=None,
        error_code=None,
        result_document_version_id="version-1",
    )


def test_poll_projects_result_hint_and_no_store_without_internal_fields() -> None:
    fake = FakeJobs(_projection())
    response = _client(fake).get(
        "/v1/workspaces/workspace-a/ingestion-jobs/job-1",
        headers={"X-API-Key": RAW_KEY},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["result"] == {"document_version_id": "version-1"}
    assert body["poll_after_seconds"] == 0
    assert "next_attempt_at" not in body
    assert "worker_id" not in body
    assert "lease_expires_at" not in body


def test_poll_authentication_precedes_lookup() -> None:
    fake = FakeJobs(_projection())
    response = _client(fake).get("/v1/workspaces/workspace-a/ingestion-jobs/job-1")

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert fake.status_calls == 0


def test_reprocess_uses_scoped_idempotency_key_and_no_upload_outcome_field() -> None:
    fake = FakeJobs(_projection())
    response = _client(fake).post(
        "/v1/workspaces/workspace-a/document-versions/version-1/reprocess",
        headers={"X-API-Key": RAW_KEY, "Idempotency-Key": "reprocess-1"},
        json={"config_mode": "current"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "ingestion_job_id": "job-reprocess",
        "document_version_id": "version-1",
        "outcome": "created",
        "status": "queued",
    }
    assert "submission_outcome" not in response.json()
    assert fake.reprocess_calls == 1


def test_poll_and_reprocess_authorization_precede_scoped_resource_lookup() -> None:
    fake = FakeJobs(_projection())
    b_client = _client_for_workspace(fake, "workspace-b", "workspace-b-key")

    poll_forbidden = b_client.get(
        "/v1/workspaces/workspace-a/ingestion-jobs/job-1",
        headers={"X-API-Key": "workspace-b-key"},
    )
    assert poll_forbidden.status_code == 403
    assert fake.status_calls == 0

    reprocess_forbidden = b_client.post(
        "/v1/workspaces/workspace-a/document-versions/version-a/reprocess",
        headers={"X-API-Key": "workspace-b-key", "Idempotency-Key": "reprocess-b"},
        json={"config_mode": "current"},
    )
    assert reprocess_forbidden.status_code == 403
    assert fake.reprocess_calls == 0

    class ScopedMissingJobs(FakeJobs):
        def get_job_status(self, *, ingestion_job_id: str, principal: WorkspacePrincipal):
            self.status_calls += 1
            assert principal.workspace_id == "workspace-b"
            assert ingestion_job_id == "job-from-a"
            raise KnoraError("INGESTION_JOB_NOT_FOUND")

        def reprocess_document_version(self, command, principal):
            self.reprocess_calls += 1
            raise KnoraError("DOCUMENT_VERSION_NOT_FOUND")

    scoped = ScopedMissingJobs(_projection())
    scoped_client = _client_for_workspace(scoped, "workspace-b", "workspace-b-key-2")
    cross_workspace = scoped_client.post(
        "/v1/workspaces/workspace-b/document-versions/version-a/reprocess",
        headers={"X-API-Key": "workspace-b-key-2", "Idempotency-Key": "reprocess-b-2"},
        json={"config_mode": "current"},
    )
    assert cross_workspace.status_code == 404
    assert scoped.reprocess_calls == 1
    scoped_poll = scoped_client.get(
        "/v1/workspaces/workspace-b/ingestion-jobs/job-from-a",
        headers={"X-API-Key": "workspace-b-key-2"},
    )
    assert scoped_poll.status_code == 404
    assert scoped.status_calls == 1


def test_reprocess_invalid_config_mode_is_rejected_without_service_execution() -> None:
    fake = FakeJobs(_projection())
    client = _client(fake)
    missing = client.post(
        "/v1/workspaces/workspace-a/document-versions/version-1/reprocess",
        headers={"X-API-Key": RAW_KEY, "Idempotency-Key": "missing-mode"},
        json={},
    )
    unsupported = client.post(
        "/v1/workspaces/workspace-a/document-versions/version-1/reprocess",
        headers={"X-API-Key": RAW_KEY, "Idempotency-Key": "unsupported-mode"},
        json={"config_mode": "future"},
    )
    assert missing.status_code == 422
    assert unsupported.status_code == 422
    assert fake.reprocess_calls == 0
