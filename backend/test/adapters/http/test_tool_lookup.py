"""HTTP adapter contract tests for the M4.1 ticket-lookup route."""

import base64
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.access.keycloak import KeycloakAuthenticator
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.main import create_app
from knora.tools import (
    AuthorizedReferenceMintingResource,
    ExternalResourceReferenceMinter,
    ExternalScopeBinding,
    FakeSupportToolGateway,
    InMemoryReferenceStore,
    ProviderContractInvalid,
    ProviderResourceNotFound,
    ProviderScopeDenied,
    ProviderUnavailable,
    ReadTool,
    ReferenceKey,
    ReferenceKeyRing,
    ReferenceVerifier,
    TicketLookupResult,
    WorkspaceResourceAuthorizer,
)

NOW = datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
EXPIRES = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)


def _reference_id(value: int) -> str:
    return base64.urlsafe_b64encode(bytes([value]) * 32).decode("ascii").rstrip("=")


def client_with_fixture() -> tuple[TestClient, FakeSupportToolGateway, str, str]:
    binding = ExternalScopeBinding.for_workspace(
        "workspace-a",
        binding_id="binding-a",
        external_scope="scope-a",
    )
    ring = ReferenceKeyRing((ReferenceKey("k1", b"test-only-secret"),))
    minted = ExternalResourceReferenceMinter(
        ring,
        clock=lambda: NOW,
        reference_id_factory=lambda: _reference_id(75),
    ).mint(
        AuthorizedReferenceMintingResource(
            workspace_id="workspace-a",
            capability_id="ticket_lookup",
            capability_version="m4.1",
            binding_id=binding.binding_id,
            binding_version=binding.version,
            binding_digest=binding.digest,
            resource_kind="ticket",
            resource_identity_digest="sha256:" + "1" * 64,
            resource_claims_digest="sha256:" + "2" * 64,
            provider_routing_handle="routing-ticket-75",
        ),
        expires_at=EXPIRES,
    )
    store = InMemoryReferenceStore((minted.record,))
    gateway = FakeSupportToolGateway(
        outcomes={
            minted.record.provider_routing_handle: TicketLookupResult(
                ticket_reference=minted.record.reference_id,
                title="Cannot sign in",
                status="open",
                summary="Customer cannot complete SSO sign-in.",
            )
        }
    )
    tool = ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={"workspace-a": binding},
            reference_verifier=ReferenceVerifier(store, ring, clock=lambda: NOW),
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
    return client, gateway, str(minted.reference), minted.record.provider_routing_handle


def test_ticket_lookup_http_authenticates_and_returns_allowlisted_result() -> None:
    client, gateway, token, _ = client_with_fixture()

    response = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"X-API-Key": "tool-key"},
        json={"ticket_reference": token},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ticket_reference": _reference_id(75),
        "title": "Cannot sign in",
        "status": "open",
        "summary": "Customer cannot complete SSO sign-in.",
    }
    assert gateway.call_count == 1


def test_ticket_lookup_path_workspace_and_schema_denials_precede_gateway() -> None:
    client, gateway, token, _ = client_with_fixture()

    responses = [
        client.post(
            "/v1/workspaces/workspace-a/tools/ticket-lookup",
            json={"ticket_reference": token},
        ),
        client.post(
            "/v1/workspaces/workspace-b/tools/ticket-lookup",
            headers={"X-API-Key": "tool-key"},
            json={"ticket_reference": token},
        ),
        client.post(
            "/v1/workspaces/workspace-a/tools/ticket-lookup",
            headers={"X-API-Key": "tool-key"},
            json={"ticket_reference": token, "provider_id": "spoof"},
        ),
        client.post(
            "/v1/workspaces/workspace-a/tools/ticket-lookup",
            headers={"X-API-Key": "tool-key"},
            json={"ticket_reference": 75},
        ),
    ]

    assert [(response.status_code, response.json()) for response in responses] == [
        (401, {"error": {"code": "UNAUTHENTICATED"}}),
        (403, {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}),
        (422, {"error": {"code": "TOOL_REQUEST_INVALID"}}),
        (422, {"error": {"code": "TOOL_REQUEST_INVALID"}}),
    ]
    assert gateway.call_count == 0


def test_default_tool_composition_disables_route_without_runtime_provider() -> None:
    application = create_app()
    client = TestClient(application)

    response = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        json={"ticket_reference": "m4r1.disabled.route"},
    )

    assert application.state.read_tool is None
    assert response.status_code == 404
    assert not hasattr(application.state, "tool_reference_store")
    assert not hasattr(application.state, "tool_reference_verifier")


def test_authentication_and_workspace_authorization_precede_malformed_json() -> None:
    client, gateway, _, _ = client_with_fixture()

    unauthenticated = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        content="{",
        headers={"Content-Type": "application/json"},
    )
    cross_workspace = client.post(
        "/v1/workspaces/workspace-b/tools/ticket-lookup",
        content="{",
        headers={"Content-Type": "application/json", "X-API-Key": "tool-key"},
    )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert cross_workspace.status_code == 403
    assert cross_workspace.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert gateway.call_count == 0


@pytest.mark.parametrize("workspace_claim", ["workspace-a", None])
def test_bearer_ticket_lookup_uses_persisted_owner_authorization_before_read_tool(
    workspace_claim: str | None,
) -> None:
    class AuthorizerMustDeny:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str | None]] = []

        def authorize(self, identity, workspace_id, capability):
            self.calls.append((identity.subject, workspace_id, capability))
            raise KnoraError("WORKSPACE_ACCESS_DENIED")

    class ReadToolMustNotExecute:
        calls = 0

        def execute(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("read tool executed before workspace authorization")

    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "alice",
            "workspace_id": workspace_claim,
        },
    )
    authorizer = AuthorizerMustDeny()
    read_tool = ReadToolMustNotExecute()
    response = TestClient(
        create_app(
            keycloak_authenticator=authenticator,
            api_key_authenticator=ApiKeyAuthenticator(()),
            workspace_authorizer=authorizer,
            read_tool=read_tool,
        )
    ).post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"Authorization": "Bearer valid-token"},
        json={"ticket_reference": "m4r1.signed-reference"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert authorizer.calls == [("alice", "workspace-a", None)]
    assert read_tool.calls == 0


def test_claimless_bearer_owner_retains_ticket_lookup_read_access() -> None:
    class OwnerAuthorizer:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str | None]] = []

        def authorize(self, identity, workspace_id, capability):
            self.calls.append((identity.subject, workspace_id, capability))
            return WorkspacePrincipal(workspace_id, identity.subject, identity.capabilities)

    class RecordingReadTool:
        calls = 0

        def execute(self, _command, _principal):
            self.calls += 1
            return TicketLookupResult(
                ticket_reference="m4r1.signed-reference",
                title="Cannot sign in",
                status="open",
                summary="Customer cannot complete SSO sign-in.",
            )

    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "alice",
        },
    )
    authorizer = OwnerAuthorizer()
    read_tool = RecordingReadTool()
    response = TestClient(
        create_app(
            keycloak_authenticator=authenticator,
            api_key_authenticator=ApiKeyAuthenticator(()),
            workspace_authorizer=authorizer,
            read_tool=read_tool,
        )
    ).post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"Authorization": "Bearer valid-token"},
        json={"ticket_reference": "m4r1.signed-reference"},
    )

    assert response.status_code == 200
    assert authorizer.calls == [("alice", "workspace-a", None)]
    assert read_tool.calls == 1


def test_http_distinguishes_malformed_reference_from_authorized_not_found() -> None:
    client, gateway, token, routing_handle = client_with_fixture()

    malformed = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"X-API-Key": "tool-key"},
        json={"ticket_reference": "m4r1.%%%.___"},
    )
    gateway.outcomes[routing_handle] = ProviderResourceNotFound()
    absent = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"X-API-Key": "tool-key"},
        json={"ticket_reference": token},
    )

    assert (malformed.status_code, malformed.json()) == (
        400,
        {"error": {"code": "INVALID_TOOL_RESOURCE_REFERENCE"}},
    )
    assert (absent.status_code, absent.json()) == (
        404,
        {"error": {"code": "TOOL_TICKET_NOT_FOUND"}},
    )
    assert gateway.call_count == 1


@pytest.mark.parametrize(
    "outcome,status,code",
    [
        (ProviderScopeDenied(), 403, "TOOL_RESOURCE_ACCESS_DENIED"),
        (ProviderResourceNotFound(), 404, "TOOL_TICKET_NOT_FOUND"),
        (ProviderUnavailable(), 502, "TOOL_PROVIDER_UNAVAILABLE"),
        (ProviderContractInvalid(), 502, "TOOL_PROVIDER_CONTRACT_INVALID"),
        (object(), 502, "TOOL_PROVIDER_CONTRACT_INVALID"),
    ],
)
def test_http_provider_outcomes_use_closed_safe_mapping(outcome, status, code) -> None:
    client, gateway, token, routing_handle = client_with_fixture()
    gateway.outcomes[routing_handle] = outcome

    response = client.post(
        "/v1/workspaces/workspace-a/tools/ticket-lookup",
        headers={"X-API-Key": "tool-key"},
        json={"ticket_reference": token},
    )

    assert response.status_code == status
    assert response.json() == {"error": {"code": code}}
    assert gateway.call_count == 1
