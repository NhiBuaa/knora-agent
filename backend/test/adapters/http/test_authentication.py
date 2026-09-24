import time

from fastapi.testclient import TestClient

from knora.access.api_keys import ApiKeyAuthenticator
from knora.access.keycloak import KeycloakAuthenticator
from knora.answering.interface import QuestionEvent, QuestionResult
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestionResult
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


def test_bearer_workspace_claims_are_untrusted_before_document_service_resolution() -> None:
    class AuthorizerMustDeny:
        def __init__(self):
            self.calls = []

        def authorize(self, identity, workspace_id, capability):
            self.calls.append((identity.subject, workspace_id, capability))
            raise KnoraError("WORKSPACE_ACCESS_DENIED")

    class RecordingService:
        calls = 0

        def execute(self, *_args):
            self.calls += 1
            return IngestionResult(
                outcome="created",
                activation_changed=True,
                document_id="document-1",
                document_version_id="version-1",
                chunk_set_id="chunk-set-1",
                embedding_set_id="embedding-set-1",
                chunking_configuration_id="chunking-m1-v1",
                embedding_configuration_id="embedding-local-m1-v2",
                chunk_count=1,
            )

    for workspace_claim in ("workspace-a", None):
        authenticator = KeycloakAuthenticator(
            issuer="https://issuer",
            audience="knora-api",
            token_validator=lambda _token, workspace_claim=workspace_claim: {
                "iss": "https://issuer",
                "aud": "knora-api",
                "exp": time.time() + 60,
                "sub": "alice",
                "workspace_id": workspace_claim,
                "capabilities": ["documents:write"],
            },
        )
        authorizer = AuthorizerMustDeny()
        service = RecordingService()
        response = TestClient(
            create_app(
                keycloak_authenticator=authenticator,
                api_key_authenticator=ApiKeyAuthenticator(()),
                ingest_document=service,
                workspace_authorizer=authorizer,
            )
        ).post(
            "/v1/workspaces/workspace-a/documents",
            headers={"Authorization": "Bearer valid-token"},
            data={"source_key": "support/refund-policy"},
            files={"file": ("refund-policy.md", b"# Refunds")},
        )

        assert response.status_code == 403
        assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
        assert authorizer.calls == [("alice", "workspace-a", "documents:write")]
        assert service.calls == 0


def test_claimless_bearer_question_uses_database_workspace_authorization() -> None:
    class Authorizer:
        def __init__(self) -> None:
            self.calls = []

        def authorize(self, identity, workspace_id, capability):
            self.calls.append((identity.subject, workspace_id, capability))
            return WorkspacePrincipal(workspace_id, identity.subject, identity.capabilities)

    class Answer:
        calls = 0

        async def execute(self, command, principal):
            self.calls += 1
            return QuestionResult(
                workspace_id=command.workspace_id,
                decision="REFUSAL",
                answer=None,
                citations=(),
                refusal_reason="INSUFFICIENT_EVIDENCE",
                trace_id="trace-1",
            )

        async def execute_stream(self, command, principal):
            self.calls += 1
            yield QuestionEvent(stage="refusal", payload={}, terminal=True)

    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "alice",
            "capabilities": ["questions:ask"],
        },
    )
    authorizer = Authorizer()
    answer = Answer()
    response = TestClient(
        create_app(
            keycloak_authenticator=authenticator,
            api_key_authenticator=ApiKeyAuthenticator(()),
            workspace_authorizer=authorizer,
            answer_question=answer,
        )
    ).post(
        "/v1/questions",
        headers={"Authorization": "Bearer valid-token"},
        json={"workspace_id": "workspace-a", "question": "Where?"},
    )

    assert response.status_code == 200
    assert authorizer.calls == [("alice", "workspace-a", "questions:ask")]
    assert answer.calls == 1

    stream = TestClient(
        create_app(
            keycloak_authenticator=authenticator,
            api_key_authenticator=ApiKeyAuthenticator(()),
            workspace_authorizer=authorizer,
            answer_question=answer,
        )
    ).post(
        "/v1/questions/stream",
        headers={"Authorization": "Bearer valid-token"},
        json={"workspace_id": "workspace-a", "question": "Where?"},
    )
    assert stream.status_code == 200
    assert authorizer.calls[-1] == ("alice", "workspace-a", "questions:ask")
    assert answer.calls == 2
