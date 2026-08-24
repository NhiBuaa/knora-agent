import importlib.util
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.domain.errors import KnoraError
from knora.main import create_app
from knora.tools import (
    ActorContext,
    AuthorityProvenance,
    ExecutionFenced,
    HmacDispatchEnvelopeSigner,
    InMemoryToolActionStore,
    PolicyProvenance,
    ProposalNotExecutable,
    ProviderIdempotencyConflict,
    ProviderWriteFailed,
    ProviderWriteIndeterminate,
    ProviderWriteSucceeded,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)
from knora.tools.contracts import canonical_digest_v1
from knora.tools.references import AuthorizedExternalResource


def test_ticket_lookup_router_is_owned_by_http_adapter() -> None:
    from knora.adapters.http import tools

    assert tools.router is not None
    assert importlib.util.find_spec("knora.tools.http") is None


NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


class HttpResolver:
    def __init__(self) -> None:
        self.context = ResolvedCapabilityContext(
            "create_ticket",
            "m4.2",
            "sha256:" + "a" * 64,
            "ticket",
            "binding-a",
            "v1",
            "sha256:" + "b" * 64,
            PolicyProvenance(),
        )

    def resolve_for_proposal(self, workspace_id, capability_id):
        if workspace_id != "workspace-a" or capability_id != "create_ticket":
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return self.context


class HttpTargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        return VerifiedProposalTarget(
            target_reference,
            canonical_digest_v1(target_reference),
            "A" * 43,
            workspace_id,
            capability.capability_id,
            capability.capability_version,
            capability.binding_id,
            capability.binding_version,
            capability.binding_digest,
            capability.resource_kind,
            "sha256:" + "c" * 64,
            "sha256:" + "d" * 64,
        )


class HttpResourceAuthorizer:
    def authorize_current(self, principal, proposal, current, *, at_time):
        return AuthorizedExternalResource(
            proposal.target_reference_id,
            current.binding_id,
            current.binding_version,
            current.binding_digest,
            proposal.resource_kind,
            "routing-a",
            proposal.target_resource_identity_digest,
            proposal.target_resource_claims_digest,
            "scope-a",
        )


class HttpExecutionAuthorizer:
    def is_authorized(self, principal, proposal):
        return principal.workspace_id == proposal.workspace_id


class HttpGateway:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = []

    def create_ticket(self, envelope):
        self.calls.append(envelope)
        return self.outcome


class HttpActorProvider:
    def resolve(self, principal):
        return ActorContext(
            principal.key_id,
            "human",
            AuthorityProvenance.from_semantics("actor-authority", "v1", {"kind": "human"}),
            AuthorityProvenance.from_semantics("approval-authority", "v1", {"role": "approver"}),
        )


def execution_client(outcome):
    gateway = HttpGateway(outcome)
    workflow = WriteProposalWorkflow(
        capability_resolver=HttpResolver(),
        store=InMemoryToolActionStore(),
        target_verifier=HttpTargetVerifier(),
        execution_authorizer=HttpExecutionAuthorizer(),
        execution_resource_authorizer=HttpResourceAuthorizer(),
        gateway=gateway,
        dispatch_signer=HmacDispatchEnvelopeSigner(
            key_identity="dispatch-key", key_version="v1", secret=b"dispatch-secret"
        ),
        execution_owner_factory=lambda: "worker-a",
        execution_lease_duration=timedelta(minutes=5),
        clock=lambda: NOW,
    )
    authenticator = ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="key-a",
                key_hash=hash_api_key("secret-a"),
                workspace_id="workspace-a",
                enabled=True,
            ),
        )
    )
    client = TestClient(
        create_app(
            write_proposal_workflow=workflow,
            tool_actor_context_provider=HttpActorProvider(),
            api_key_authenticator=authenticator,
        )
    )
    created = client.post(
        "/v1/workspaces/workspace-a/tool-proposals",
        headers={"X-API-Key": "secret-a"},
        json={
            "capability_id": "create_ticket",
            "target_reference": "m4r1.target.opaque",
            "title": "Cannot sign in",
            "description": "Customer blocked",
        },
    )
    proposal_id = created.json()["proposal_id"]
    approved = client.post(
        f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}/approve",
        headers={"X-API-Key": "secret-a"},
        json={"expected_revision": 0},
    )
    assert approved.status_code == 200
    return client, gateway, proposal_id, approved.json()["logical_execution_id"]


@pytest.mark.parametrize(
    ("outcome", "status", "outcome_type", "variant_field", "variant_value"),
    [
        (
            ProviderWriteSucceeded("m4r1.provider-ticket.opaque"),
            200,
            "execution_succeeded",
            "external_resource_reference",
            "m4r1.provider-ticket.opaque",
        ),
        (
            ProviderWriteFailed("target_not_found"),
            502,
            "execution_failed",
            "rejection_code",
            "target_not_found",
        ),
        (
            ProviderWriteFailed("validation_rejected"),
            502,
            "execution_failed",
            "rejection_code",
            "validation_rejected",
        ),
        (
            ProviderWriteFailed("policy_rejected"),
            502,
            "execution_failed",
            "rejection_code",
            "policy_rejected",
        ),
        (
            ProviderWriteIndeterminate(),
            202,
            "execution_indeterminate",
            "reason_code",
            "indeterminate_external_outcome",
        ),
        (
            ProviderIdempotencyConflict(),
            409,
            "execution_in_progress",
            "reason_code",
            "provider_idempotency_conflict",
        ),
    ],
)
def test_execute_http_uses_closed_sanitized_result_matrix(
    outcome, status, outcome_type, variant_field, variant_value
) -> None:
    client, gateway, proposal_id, logical_id = execution_client(outcome)

    response = client.post(
        f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}/execute",
        headers={"X-API-Key": "secret-a"},
        json={"expected_revision": 1},
    )

    assert response.status_code == status
    assert response.json() == {
        "proposal_id": proposal_id,
        "logical_execution_id": logical_id,
        "lifecycle": {
            "execution_succeeded": "succeeded",
            "execution_failed": "failed",
            "execution_indeterminate": "executing",
            "execution_in_progress": "executing",
        }[outcome_type],
        "outcome_type": outcome_type,
        variant_field: variant_value,
    }
    assert len(gateway.calls) == 1


def test_execute_http_auth_workspace_and_schema_fail_before_workflow() -> None:
    client, gateway, proposal_id, _ = execution_client(
        ProviderWriteSucceeded("m4r1.provider-ticket.opaque")
    )
    path = f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}/execute"

    unauthenticated = client.post(path, json={"expected_revision": 1})
    cross_workspace = client.post(
        path.replace("workspace-a", "workspace-b"),
        headers={"X-API-Key": "secret-a"},
        content="{",
    )
    injected = client.post(
        path,
        headers={"X-API-Key": "secret-a"},
        json={"expected_revision": 1, "logical_execution_id": "spoof"},
    )

    assert unauthenticated.status_code == 401
    assert cross_workspace.status_code == 403
    assert injected.status_code == 422
    assert gateway.calls == []


@pytest.mark.parametrize(
    ("reason", "status", "code"),
    [
        ("workspace_access_denied", 403, "WORKSPACE_ACCESS_DENIED"),
        ("resource_access_denied", 403, "TOOL_RESOURCE_ACCESS_DENIED"),
        ("execution_not_authorized", 403, "TOOL_EXECUTION_NOT_AUTHORIZED"),
        ("invalid_tool_resource_reference", 400, "INVALID_TOOL_RESOURCE_REFERENCE"),
        ("capability_identity_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("capability_version_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("capability_digest_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("binding_identity_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("binding_version_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("binding_digest_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("policy_identity_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("policy_version_mismatch", 409, "TOOL_PROPOSAL_STALE"),
        ("policy_digest_mismatch", 409, "TOOL_PROPOSAL_STALE"),
    ],
)
def test_execute_http_post_acquisition_denial_matrix_is_exact(reason, status, code) -> None:
    from knora.tools.proposal_http import _execution_response

    response = _execution_response(ProposalNotExecutable("proposal", "logical", reason))

    assert isinstance(response, JSONResponse)
    assert response.status_code == status
    assert json.loads(response.body) == {"error": {"code": code}}


def test_execute_http_fenced_projection_has_exact_allowlist() -> None:
    from knora.tools.proposal_http import _execution_response

    response = _execution_response(ExecutionFenced("proposal", "logical"))

    assert response.status_code == 409
    assert json.loads(response.body) == {
        "proposal_id": "proposal",
        "logical_execution_id": "logical",
        "lifecycle": "executing",
        "outcome_type": "execution_fenced",
        "reason_code": "execution_fenced",
    }


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "[]",
        "{}",
        '{"expected_revision":true}',
        '{"expected_revision":"1"}',
        '{"expected_revision":1,"request_fingerprint":"spoof"}',
    ],
)
def test_execute_http_validation_matrix_precedes_workflow(content) -> None:
    client, gateway, proposal_id, _ = execution_client(
        ProviderWriteSucceeded("m4r1.provider-ticket.opaque")
    )

    response = client.post(
        f"/v1/workspaces/workspace-a/tool-proposals/{proposal_id}/execute",
        headers={"X-API-Key": "secret-a", "Content-Type": "application/json"},
        content=content,
    )

    assert response.status_code == 422
    assert response.json() == {"error": {"code": "TOOL_REQUEST_INVALID"}}
    assert gateway.calls == []
