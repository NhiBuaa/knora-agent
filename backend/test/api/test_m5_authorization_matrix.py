"""M5 authentication, workspace ownership, and capability denial matrix."""

import time
from dataclasses import dataclass

from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.access.keycloak import KeycloakAuthenticator
from knora.main import create_app


def _bearer_client(*, workspace: str = "workspace-a", capabilities=(), expired=False):
    calls: list[str] = []

    def validate(_token: str):
        if _token == "malformed":
            raise ValueError("invalid bearer")
        return {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() - 1 if expired else time.time() + 60,
            "sub": "subject-a",
            "workspace_id": workspace,
            "capabilities": list(capabilities),
        }

    class LifecycleReader:
        def read_lifecycle(self, *, workspace_id, principal):
            calls.append(workspace_id)
            raise LookupError("opaque proposal not found")

    app = create_app(
        keycloak_authenticator=KeycloakAuthenticator(
            issuer="https://issuer", audience="knora-api", token_validator=validate
        ),
        api_key_authenticator=ApiKeyAuthenticator(()),
        tool_lifecycle_reader=LifecycleReader(),
    )
    return TestClient(app), calls


def test_invalid_and_expired_bearer_tokens_are_rejected_before_opaque_lookup() -> None:
    client, calls = _bearer_client(capabilities=("operator:read",))

    invalid = client.get(
        "/v1/workspaces/workspace-a/operator/tool-lifecycle",
        headers={"Authorization": "Bearer malformed"},
    )
    expired_client, expired_calls = _bearer_client(
        capabilities=("operator:read",), expired=True
    )
    expired = expired_client.get(
        "/v1/workspaces/workspace-a/operator/tool-lifecycle",
        headers={"Authorization": "Bearer expired"},
    )

    assert invalid.status_code == expired.status_code == 401
    assert invalid.json() == expired.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert calls == []
    assert expired_calls == []


def test_missing_operator_capability_denies_before_lookup_without_existence_leakage() -> None:
    client, calls = _bearer_client()

    response = client.get(
        "/v1/workspaces/workspace-a/operator/tool-lifecycle",
        headers={"Authorization": "Bearer valid"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "CAPABILITY_ACCESS_DENIED"}}
    assert calls == []


def test_wrong_workspace_denies_opaque_id_before_lookup() -> None:
    client, calls = _bearer_client(capabilities=("operator:read",))

    response = client.get(
        "/v1/workspaces/workspace-b/operator/tool-lifecycle",
        headers={"Authorization": "Bearer valid"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert calls == []


@dataclass
class _WorkflowMustNotExecute:
    calls: int = 0

    def read(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("M4 workflow lookup bypassed workspace authorization")


def test_m4_tool_proposal_bypass_denies_wrong_workspace_before_opaque_lookup() -> None:
    workflow = _WorkflowMustNotExecute()

    class ActorProvider:
        def resolve(self, _principal):
            raise AssertionError("actor resolution bypassed workspace authorization")

    app = create_app(
        api_key_authenticator=ApiKeyAuthenticator(
            (
                ApiCredential(
                    "workspace-a-key", hash_api_key("key-a"), "workspace-a", True
                ),
            )
        ),
        write_proposal_workflow=workflow,
        tool_actor_context_provider=ActorProvider(),
    )
    response = TestClient(app).get(
        "/v1/workspaces/workspace-b/tool-proposals/proposal-opaque",
        headers={"X-API-Key": "key-a"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert workflow.calls == 0


def test_legacy_x_api_key_remains_workspace_scoped_and_opaque() -> None:
    client, calls = _bearer_client(capabilities=("operator:read",))
    # Replace the bearer-only app with the preserved API-key path.
    app = create_app(
        api_key_authenticator=ApiKeyAuthenticator(
            (ApiCredential("legacy", hash_api_key("legacy-key"), "workspace-a", True),)
        ),
        tool_lifecycle_reader=client.app.state.tool_lifecycle_reader,
    )
    api_client = TestClient(app)
    response = api_client.get(
        "/v1/workspaces/workspace-a/operator/tool-lifecycle",
        headers={"X-API-Key": "legacy-key"},
    )

    assert response.status_code == 503
    assert response.json() == {"error": {"code": "OPERATOR_OBSERVATION_FAILED"}}
    assert calls == ["workspace-a"]
