from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.main import create_app
from knora.tools import (
    ActorContext,
    InMemoryToolActionStore,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)
from knora.tools.proposals import PolicyProvenance, ResolvedCapabilityContext


class HttpCapabilityResolver:
    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        del workspace_id
        if capability_id != "create_ticket":
            raise ValueError("unknown capability")
        return ResolvedCapabilityContext(
            capability_id="create_ticket",
            capability_version="m4.2",
            capability_digest="sha256:create-ticket-v1",
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:binding-a",
            policy=PolicyProvenance(),
        )


class HttpTargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        return VerifiedProposalTarget(
            reference=target_reference,
            reference_digest="sha256:verified-target",
            workspace_id=workspace_id,
            capability_id=capability.capability_id,
            capability_version=capability.capability_version,
            binding_id=capability.binding_id,
            binding_version=capability.binding_version,
            binding_digest=capability.binding_digest,
            resource_kind=capability.resource_kind,
        )


def client_with(*, actor_kind: str = "human") -> TestClient:
    workflow = WriteProposalWorkflow(
        capability_resolver=HttpCapabilityResolver(),
        store=InMemoryToolActionStore(),
        target_verifier=HttpTargetVerifier(),
    )
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="proposal-a",
                key_hash=hash_api_key("proposal-key"),
                workspace_id="workspace-a",
                enabled=True,
            ),
        )
    )
    return TestClient(
        create_app(
            write_proposal_workflow=workflow,
            api_key_authenticator=authenticator,
            tool_actor_context=ActorContext("actor-a", actor_kind),
        )
    )


def proposal_payload() -> dict[str, str]:
    return {
        "capability_id": "create_ticket",
        "target_reference": "m4r1.target.opaque",
        "title": "Cannot sign in",
        "description": "Customer cannot complete SSO sign-in.",
    }


def test_proposal_http_routes_are_workspace_scoped_and_typed() -> None:
    client = client_with()

    created = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=proposal_payload(),
    )

    assert created.status_code == 200
    body = created.json()
    assert body["state"] == "proposed"
    assert body["parameters"] == {
        "title": "Cannot sign in",
        "description": "Customer cannot complete SSO sign-in.",
    }
    proposal_id = body["proposal_id"]

    read = client.get(
        f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}",
        headers={"X-API-Key": "proposal-key"},
    )
    assert read.status_code == 200
    assert read.json()["proposal_id"] == proposal_id


def test_proposal_http_denies_cross_workspace_and_extra_actor_fields() -> None:
    client = client_with()

    cross_workspace = client.post(
        "/v1/workspaces/workspace-b/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=proposal_payload(),
    )
    spoofed = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json={**proposal_payload(), "actor_id": "spoof"},
    )
    missing_body = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
    )

    assert cross_workspace.status_code == 403
    assert cross_workspace.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert spoofed.status_code == 422
    assert spoofed.json() == {"error": {"code": "TOOL_REQUEST_INVALID"}}
    assert missing_body.status_code == 422
    assert missing_body.json() == {"error": {"code": "TOOL_REQUEST_INVALID"}}


def test_proposal_http_model_actor_cannot_approve() -> None:
    client = client_with(actor_kind="model")
    created = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=proposal_payload(),
    )
    proposal_id = created.json()["proposal_id"]

    response = client.post(
        f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}/approve",
        headers={"X-API-Key": "proposal-key"},
        json={"expected_revision": 0},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "TOOL_APPROVAL_FORBIDDEN"}}


def test_proposal_http_repeat_decision_returns_persisted_winner() -> None:
    client = client_with()
    created = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=proposal_payload(),
    )
    proposal_id = created.json()["proposal_id"]
    route = f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}/approve"

    first = client.post(
        route, headers={"X-API-Key": "proposal-key"}, json={"expected_revision": 0}
    )
    repeat = client.post(
        route, headers={"X-API-Key": "proposal-key"}, json={"expected_revision": 0}
    )

    assert first.status_code == 200
    assert repeat.status_code == 409
    assert repeat.json()["error"] == {"code": "TOOL_PROPOSAL_ALREADY_DECIDED"}
    assert repeat.json()["proposal"]["state"] == "approved"
    assert repeat.json()["proposal"]["revision"] == 1
