import time

from fastapi.testclient import TestClient

from knora.access.api_keys import ApiKeyAuthenticator
from knora.access.keycloak import KeycloakAuthenticator
from knora.main import create_app


def test_capability_is_checked_before_ingest_service_resolution() -> None:
    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "operator-1",
            "workspace_id": "workspace-a",
            "capabilities": [],
        },
    )
    app = create_app(
        keycloak_authenticator=authenticator,
        api_key_authenticator=ApiKeyAuthenticator(()),
    )

    class ServiceMustNotExecute:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("service executed before capability authorization")

    app.state.ingest_document = ServiceMustNotExecute()

    response = TestClient(app).post(
        "/v1/workspaces/workspace-a/documents",
        headers={"Authorization": "Bearer valid-token"},
        data={"source_key": "support/refund-policy"},
        files={"file": ("refund-policy.md", b"# Refunds")},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "CAPABILITY_ACCESS_DENIED"}}


def test_documents_write_capability_is_checked_before_reprocess_lookup() -> None:
    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "operator-1",
            "workspace_id": "workspace-a",
            "capabilities": [],
        },
    )
    app = create_app(
        keycloak_authenticator=authenticator,
        api_key_authenticator=ApiKeyAuthenticator(()),
    )

    class JobsMustNotExecute:
        def reprocess_document_version(self, *_args, **_kwargs):
            raise AssertionError("reprocess lookup executed before capability authorization")

    app.state.ingestion_jobs = JobsMustNotExecute()

    response = TestClient(app).post(
        "/v1/workspaces/workspace-a/document-versions/version-a/reprocess",
        headers={
            "Authorization": "Bearer valid-token",
            "Idempotency-Key": "reprocess-1",
        },
        json={"config_mode": "current"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "CAPABILITY_ACCESS_DENIED"}}


def test_questions_capability_is_checked_before_sync_and_stream_execution() -> None:
    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "operator-1",
            "workspace_id": "workspace-a",
            "capabilities": [],
        },
    )
    app = create_app(
        keycloak_authenticator=authenticator,
        api_key_authenticator=ApiKeyAuthenticator(()),
    )

    class AnswerMustNotExecute:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("sync question executed before capability authorization")

        async def execute_stream(self, *_args, **_kwargs):
            raise AssertionError("stream question executed before capability authorization")

    app.state.answer_question = AnswerMustNotExecute()
    client = TestClient(app)
    headers = {"Authorization": "Bearer valid-token"}
    payload = {"workspace_id": "workspace-a", "question": "Where is the policy?"}

    for path in ("/v1/questions", "/v1/questions/stream"):
        response = client.post(path, headers=headers, json=payload)
        assert response.status_code == 403
        assert response.json() == {"error": {"code": "CAPABILITY_ACCESS_DENIED"}}


def test_documents_read_capability_is_checked_before_ingestion_job_lookup() -> None:
    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "operator-1",
            "workspace_id": "workspace-a",
            "capabilities": [],
        },
    )
    app = create_app(
        keycloak_authenticator=authenticator,
        api_key_authenticator=ApiKeyAuthenticator(()),
    )

    class JobsMustNotExecute:
        def get_job_status(self, *_args, **_kwargs):
            raise AssertionError("job lookup executed before capability authorization")

    app.state.ingestion_jobs = JobsMustNotExecute()
    response = TestClient(app).get(
        "/v1/workspaces/workspace-a/ingestion-jobs/job-a",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "CAPABILITY_ACCESS_DENIED"}}
