from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.main import create_app
from knora.tools import (
    CapabilityRegistry,
    ExternalResourceReference,
    ExternalScopeBinding,
    FakeSupportToolGateway,
    InMemoryReferenceStore,
    ReadTool,
    ReferenceKey,
    ReferenceRecord,
    ReferenceVerifier,
    TicketLookupResult,
    WorkspaceResourceAuthorizer,
)


def client_with_fixture() -> tuple[TestClient, FakeSupportToolGateway, str]:
    record = ReferenceRecord(
        reference_id="ticket-fixture-75",
        workspace_id="workspace-a",
        capability_id="ticket_lookup",
        capability_version="m4.1",
        binding_id="binding-a",
        binding_version="v1",
        binding_digest="sha256:binding-a",
        resource_kind="ticket",
        resource_claims={"scope": "support"},
        provider_resource_id="provider-ticket-75",
        expires_at=4_000_000_000,
        key_version="k1",
    )
    key = ReferenceKey("k1", b"test-only-secret")
    store = InMemoryReferenceStore((record,))
    token = ExternalResourceReference.mint(record, key)
    verifier = ReferenceVerifier(store, {"k1": key}, clock=lambda: 1_700_000_000)
    gateway = FakeSupportToolGateway(
        outcomes={
            record.provider_resource_id: TicketLookupResult(
                ticket_reference=record.reference_id,
                title="Cannot sign in",
                status="open",
                summary="Customer cannot complete SSO sign-in.",
            )
        }
    )
    tool = ReadTool(
        registry=CapabilityRegistry.static(),
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={
                "workspace-a": ExternalScopeBinding(
                    "workspace-a", "binding-a", "v1", "sha256:binding-a", "scope-a"
                )
            },
            reference_verifier=verifier,
        ),
        gateway=gateway,
    )
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="tool-a",
                key_hash=hash_api_key("tool-key"),
                workspace_id="workspace-a",
                enabled=True,
            ),
        )
    )
    client = TestClient(create_app(read_tool=tool, api_key_authenticator=authenticator))
    return client, gateway, str(token)


def test_ticket_lookup_http_authenticates_and_returns_allowlisted_result() -> None:
    client, gateway, token = client_with_fixture()

    response = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"X-API-Key": "tool-key"},
        json={"ticket_reference": token},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ticket_reference": "ticket-fixture-75",
        "title": "Cannot sign in",
        "status": "open",
        "summary": "Customer cannot complete SSO sign-in.",
    }
    assert gateway.call_count == 1


def test_ticket_lookup_path_workspace_and_schema_denials_precede_gateway() -> None:
    client, gateway, token = client_with_fixture()

    missing_auth = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        json={"ticket_reference": token},
    )
    cross_workspace = client.post(
        "/v1/workspaces/workspace-b/tools/ticket-lookup",
        headers={"X-API-Key": "tool-key"},
        json={"ticket_reference": token},
    )
    extra_field = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"X-API-Key": "tool-key"},
        json={"ticket_reference": token, "provider_id": "spoof"},
    )

    assert missing_auth.status_code == 401
    assert missing_auth.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert cross_workspace.status_code == 403
    assert cross_workspace.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert extra_field.status_code == 422
    assert extra_field.json() == {"error": {"code": "TOOL_REQUEST_INVALID"}}
    assert gateway.call_count == 0
