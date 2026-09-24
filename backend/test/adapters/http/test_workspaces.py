import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from knora.access.keycloak import KeycloakAuthenticator
from knora.main import create_app
from knora.workspaces.types import ResolutionState, WorkspaceResolution, WorkspaceView


class WorkspaceServiceFake:
    def __init__(self):
        self.items = {}
        self.owner = None

    def resolve(self, identity, hint_id=None):
        self.owner = identity.subject
        if not self.items:
            value = self.create(identity, "My Workspace", "default")
            return WorkspaceResolution(ResolutionState.ACTIVE, value)
        return WorkspaceResolution(ResolutionState.ACTIVE, next(iter(self.items.values())))

    def create(self, identity, name, idempotency_key):
        self.owner = identity.subject
        value = WorkspaceView(idempotency_key, name.strip(), False, 0, datetime.now(UTC))
        self.items[value.id] = value
        return value

    def read(self, identity, workspace_id):
        return self.items[workspace_id]

    def list(self, identity, archived=None, cursor=None, limit=20):
        from knora.workspaces.types import WorkspacePage

        return WorkspacePage(tuple(self.items.values()), None)

    def archive(self, identity, workspace_id, expected_revision):
        value = self.items[workspace_id]
        updated = WorkspaceView(value.id, value.name, True, expected_revision + 1, value.created_at)
        self.items[workspace_id] = updated
        return updated

    def restore(self, identity, workspace_id, expected_revision):
        value = self.items[workspace_id]
        updated = WorkspaceView(
            value.id, value.name, False, expected_revision + 1, value.created_at
        )
        self.items[workspace_id] = updated
        return updated

    def rename(self, identity, workspace_id, name, expected_revision):
        value = self.items[workspace_id]
        updated = WorkspaceView(
            value.id, name, value.archived, expected_revision + 1, value.created_at
        )
        self.items[workspace_id] = updated
        return updated


def client():
    service = WorkspaceServiceFake()
    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "alice",
            "capabilities": [],
        },
    )
    return TestClient(
        create_app(keycloak_authenticator=authenticator, workspace_service=service)
    ), service


def test_resolve_uses_bearer_identity_without_workspace_claim_and_returns_private_response():
    http, service = client()
    response = http.post("/v1/workspaces/resolve", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["workspace"]["name"] == "My Workspace"
    assert response.headers["Cache-Control"] == "no-store"
    assert service.owner == "alice"


def test_create_requires_idempotency_key_and_uses_no_owner_body_field():
    http, _ = client()
    headers = {"Authorization": "Bearer token"}
    missing = http.post("/v1/workspaces", json={"name": "One"}, headers=headers)
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "MISSING_IDEMPOTENCY_KEY"
    response = http.post(
        "/v1/workspaces",
        json={"name": " One "},
        headers={**headers, "Idempotency-Key": "create-1"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "One"


def test_archive_requires_revision_header_and_restore_keeps_workspace_identity():
    http, _ = client()
    headers = {"Authorization": "Bearer token", "Idempotency-Key": "create-1"}
    created = http.post("/v1/workspaces", json={"name": "One"}, headers=headers).json()
    path = f"/v1/workspaces/{created['id']}"
    missing = http.post(f"{path}/archive", headers=headers)
    assert missing.status_code == 428
    archived = http.post(f"{path}/archive", headers={**headers, "If-Match": "0"})
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    restored = http.post(f"{path}/restore", headers={**headers, "If-Match": "1"})
    assert restored.status_code == 200
    assert restored.json()["id"] == created["id"]


def test_workspace_routes_do_not_accept_api_key_as_identity():
    http, _ = client()
    response = http.post("/v1/workspaces/resolve", headers={"X-API-Key": "legacy"})
    assert response.status_code == 401
