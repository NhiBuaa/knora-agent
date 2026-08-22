import pytest
from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.domain.errors import KnoraError
from knora.main import create_app
from knora.tools import (
    ActorContext,
    AuthorityProvenance,
    InMemoryToolActionStore,
    PolicyProvenance,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)


class HttpCapabilityResolver:
    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        del workspace_id
        if capability_id != "create_ticket":
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return ResolvedCapabilityContext(
            capability_id="create_ticket",
            capability_version="m4.2",
            capability_digest="sha256:" + "a" * 64,
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:" + "b" * 64,
            policy=PolicyProvenance(),
        )


class HttpTargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        return VerifiedProposalTarget(
            reference=target_reference,
            reference_digest="sha256:" + "c" * 64,
            reference_id="reference-76-http",
            workspace_id=workspace_id,
            capability_id=capability.capability_id,
            capability_version=capability.capability_version,
            binding_id=capability.binding_id,
            binding_version=capability.binding_version,
            binding_digest=capability.binding_digest,
            resource_kind=capability.resource_kind,
            resource_identity_digest="sha256:" + "d" * 64,
            resource_claims_digest="sha256:" + "e" * 64,
        )


class HttpActorContextProvider:
    def __init__(
        self,
        actor_kind: str,
        *,
        can_approve: bool | None = None,
        actor_id: str = "actor-a",
    ) -> None:
        self.actor_kind = actor_kind
        self.can_approve = actor_kind == "human" if can_approve is None else can_approve
        self.actor_id = actor_id
        self.calls = 0

    def resolve(self, principal) -> ActorContext:
        self.calls += 1
        return ActorContext(
            self.actor_id,
            self.actor_kind,
            authority=AuthorityProvenance.from_semantics(
                f"{self.actor_kind}-identity-authority",
                "v1",
                {"actor_kinds": [self.actor_kind]},
            ),
            approval_authority=(
                AuthorityProvenance.from_semantics(
                    "workspace-approval-authority",
                    "v1",
                    {"workspace_id": principal.workspace_id},
                )
                if self.can_approve
                else None
            ),
        )


def client_with(
    *, actor_kind: str = "human", can_approve: bool | None = None
) -> TestClient:
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
            tool_actor_context_provider=HttpActorContextProvider(
                actor_kind, can_approve=can_approve
            ),
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


def test_default_application_does_not_install_a_global_human_or_proposal_route() -> None:
    application = create_app()
    client = TestClient(application)

    response = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        json=proposal_payload(),
    )

    assert application.state.write_proposal_workflow is None
    assert application.state.tool_actor_context_provider is None
    assert response.status_code == 404


def test_proposal_authentication_and_workspace_authorization_precede_malformed_json() -> None:
    client = client_with()

    unauthenticated = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        content="{",
        headers={"Content-Type": "application/json"},
    )
    cross_workspace = client.post(
        "/v1/workspaces/workspace-b/tool-proposals",
        content="{",
        headers={"Content-Type": "application/json", "X-API-Key": "proposal-key"},
    )

    assert (unauthenticated.status_code, unauthenticated.json()) == (
        401,
        {"error": {"code": "UNAUTHENTICATED"}},
    )
    assert (cross_workspace.status_code, cross_workspace.json()) == (
        403,
        {"error": {"code": "WORKSPACE_ACCESS_DENIED"}},
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capability_id", 1),
        ("target_reference", None),
        ("title", ""),
        ("title", " padded"),
        ("title", "padded "),
        ("title", "x" * 201),
        ("title", "bad\x00title"),
        ("description", ""),
        ("description", " padded"),
        ("description", "padded "),
        ("description", "x" * 10_001),
        ("description", "bad\x00description"),
    ],
)
def test_proposal_http_rejects_invalid_input_before_creation(
    field: str, value: object
) -> None:
    client = client_with()
    payload: dict[str, object] = proposal_payload()
    payload[field] = value

    response = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=payload,
    )

    assert (response.status_code, response.json()) == (
        422,
        {"error": {"code": "TOOL_REQUEST_INVALID"}},
    )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "actor_id",
        "actor_kind",
        "approval_actor_id",
        "caller_principal_id",
        "capability_digest",
        "binding_digest",
        "policy_digest",
        "provider_id",
        "logical_execution_id",
        "request_fingerprint",
    ],
)
def test_proposal_http_rejects_every_forbidden_provenance_field(
    forbidden_field: str,
) -> None:
    client = client_with()

    response = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json={**proposal_payload(), forbidden_field: "spoofed"},
    )

    assert (response.status_code, response.json()) == (
        422,
        {"error": {"code": "TOOL_REQUEST_INVALID"}},
    )


def test_proposal_http_normalizes_canonical_unicode_and_line_endings() -> None:
    client = client_with()
    payload = proposal_payload()
    payload["title"] = "Cafe\u0301 login"
    payload["description"] = "First line\r\nSecond line"

    response = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["parameters"] == {
        "title": "Caf\u00e9 login",
        "description": "First line\nSecond line",
    }


@pytest.mark.parametrize("route", ["approve", "reject"])
@pytest.mark.parametrize(
    ("actor_kind", "can_approve"),
    [("model", False), ("system", False), ("human", False)],
)
def test_proposal_http_only_authorized_humans_can_decide(
    route: str, actor_kind: str, can_approve: bool
) -> None:
    client = client_with(actor_kind=actor_kind, can_approve=can_approve)
    created = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=proposal_payload(),
    )
    proposal_id = created.json()["proposal_id"]
    body = (
        {"expected_revision": 0}
        if route == "approve"
        else {"expected_revision": 0, "reason_code": "not_approved"}
    )

    response = client.post(
        f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}/{route}",
        headers={"X-API-Key": "proposal-key"},
        json=body,
    )

    assert (response.status_code, response.json()) == (
        403,
        {"error": {"code": "TOOL_APPROVAL_FORBIDDEN"}},
    )


@pytest.mark.parametrize(
    ("route", "body"),
    [
        ("approve", {"expected_revision": 0}),
        ("reject", {"expected_revision": 0, "reason_code": "not_approved"}),
    ],
)
def test_proposal_decision_auth_and_absence_matrix(
    route: str, body: dict[str, object]
) -> None:
    client = client_with()
    path = f"/v1/workspaces/workspace-a/tool-proposals/absent/{route}"

    unauthenticated = client.post(path, json=body)
    cross_workspace = client.post(
        path.replace("workspace-a", "workspace-b"),
        headers={"X-API-Key": "proposal-key"},
        json=body,
    )
    absent = client.post(path, headers={"X-API-Key": "proposal-key"}, json=body)

    assert (unauthenticated.status_code, unauthenticated.json()) == (
        401,
        {"error": {"code": "UNAUTHENTICATED"}},
    )
    assert (cross_workspace.status_code, cross_workspace.json()) == (
        403,
        {"error": {"code": "WORKSPACE_ACCESS_DENIED"}},
    )
    assert (absent.status_code, absent.json()) == (
        404,
        {"error": {"code": "TOOL_PROPOSAL_NOT_FOUND"}},
    )


def test_proposal_read_auth_and_absence_matrix() -> None:
    client = client_with()
    path = "/v1/workspaces/workspace-a/tool-proposals/absent"

    unauthenticated = client.get(path)
    cross_workspace = client.get(
        path.replace("workspace-a", "workspace-b"),
        headers={"X-API-Key": "proposal-key"},
    )
    absent = client.get(path, headers={"X-API-Key": "proposal-key"})

    assert (unauthenticated.status_code, unauthenticated.json()) == (
        401,
        {"error": {"code": "UNAUTHENTICATED"}},
    )
    assert (cross_workspace.status_code, cross_workspace.json()) == (
        403,
        {"error": {"code": "WORKSPACE_ACCESS_DENIED"}},
    )
    assert (absent.status_code, absent.json()) == (
        404,
        {"error": {"code": "TOOL_PROPOSAL_NOT_FOUND"}},
    )


def test_proposal_http_rejects_unknown_capability_and_reject_reason() -> None:
    client = client_with()
    unknown_capability = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json={**proposal_payload(), "capability_id": "unknown"},
    )
    created = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "proposal-key"},
        json=proposal_payload(),
    )
    invalid_reason = client.post(
        "/v1/workspaces/workspace-a/tool-proposals/"
        f"{created.json()['proposal_id']}/reject",
        headers={"X-API-Key": "proposal-key"},
        json={"expected_revision": 0, "reason_code": "invented"},
    )

    assert (unknown_capability.status_code, unknown_capability.json()) == (
        403,
        {"error": {"code": "TOOL_CAPABILITY_NOT_FOUND"}},
    )
    assert (invalid_reason.status_code, invalid_reason.json()) == (
        422,
        {"error": {"code": "TOOL_REQUEST_INVALID"}},
    )
