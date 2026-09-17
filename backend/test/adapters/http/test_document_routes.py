from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.ingestion.documents import (
    DocumentDeletionRequestProjection,
    DocumentLifecycleService,
    DocumentListProjection,
    DocumentProjection,
)
from knora.main import create_app


class FakeReader:
    def list_documents(self, *, workspace_id, principal):
        return DocumentListProjection(
            (DocumentProjection("d1", workspace_id, "support/refunds", "refunds.md", False, 0),)
        )

    def read_document(self, *, workspace_id, document_id, principal):
        return DocumentProjection(
            document_id, workspace_id, "support/refunds", "refunds.md", False, 0
        )


class FakeLifecycle:
    def archive(self, **kwargs):
        return DocumentProjection(
            kwargs["document_id"], kwargs["workspace_id"], "support/refunds", "refunds.md", True, 1
        )

    def unarchive(self, **kwargs):
        return DocumentProjection(
            kwargs["document_id"], kwargs["workspace_id"], "support/refunds", "refunds.md", False, 2
        )

    def request_deletion(self, **kwargs):
        return DocumentDeletionRequestProjection("r1", kwargs["document_id"], "requested")


def test_deletion_projection_has_async_state():
    p = DocumentDeletionRequestProjection(request_id="r", document_id="d", state="requested")
    assert p.state == "requested"


def test_document_list_and_archive_routes_are_workspace_scoped():
    raw_key = "document-route-key"
    auth = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="route-key",
                key_hash=hash_api_key(raw_key),
                workspace_id="workspace-a",
                enabled=True,
            ),
        )
    )
    app = create_app(
        api_key_authenticator=auth,
        document_reader=FakeReader(),
        document_lifecycle=DocumentLifecycleService(FakeLifecycle()),
    )
    client = TestClient(app)

    listed = client.get("/v1/workspaces/workspace-a/documents", headers={"X-API-Key": raw_key})
    assert listed.status_code == 200
    assert listed.json()["documents"][0]["archived"] is False

    archived = client.post(
        "/v1/workspaces/workspace-a/documents/d1/archive",
        headers={"X-API-Key": raw_key},
    )
    assert archived.status_code == 200
    assert archived.json()["archived"] is True

    denied = client.get("/v1/workspaces/workspace-b/documents", headers={"X-API-Key": raw_key})
    assert denied.status_code == 403
    assert denied.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
