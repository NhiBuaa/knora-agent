import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    ActorContext,
    AlreadyDecided,
    ApproveProposal,
    AuthorityProvenance,
    InMemoryToolActionStore,
    PolicyProvenance,
    ProposalApproved,
    ProposeWriteAction,
    RejectProposal,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)


class FakeCapabilityResolver:
    def __init__(self) -> None:
        self.available = True
        self.context = ResolvedCapabilityContext(
            capability_id="create_ticket",
            capability_version="m4.2",
            capability_digest="sha256:" + "a" * 64,
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:" + "b" * 64,
            policy=PolicyProvenance(),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )

    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        del workspace_id
        if not self.available or capability_id != "create_ticket":
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return self.context


class FakeTargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        if target_reference != "m4r1.target.opaque":
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        return VerifiedProposalTarget(
            reference=target_reference,
            reference_digest="sha256:" + "c" * 64,
            reference_id="reference-75",
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


class FakeExecutionAuthorizer:
    def __init__(self, authorized: bool) -> None:
        self.authorized = authorized

    def is_authorized(self, principal, proposal) -> bool:
        del principal, proposal
        return self.authorized


def workflow(*, execution_authorized=True):
    resolver = FakeCapabilityResolver()
    store = InMemoryToolActionStore()
    service = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=store,
        target_verifier=FakeTargetVerifier(),
        execution_authorizer=FakeExecutionAuthorizer(execution_authorized),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    return service, resolver, store


def actor_context(
    actor_id: str,
    actor_kind: str,
    *,
    can_approve: bool = False,
) -> ActorContext:
    return ActorContext(
        actor_id,
        actor_kind,
        authority=AuthorityProvenance.from_semantics(
            f"{actor_kind}-identity-authority", "v1", {"actor_kinds": [actor_kind]}
        ),
        approval_authority=(
            AuthorityProvenance.from_semantics(
                "workspace-approval-authority", "v1", {"workspace_id": "workspace-a"}
            )
            if can_approve
            else None
        ),
    )


def propose(service: WriteProposalWorkflow, actor_kind="model", actor_id="agent-1"):
    return service.handle(
        ProposeWriteAction(
            capability_id="create_ticket",
            target_reference="m4r1.target.opaque",
            title="New ticket",
            description="Line one\r\nLine two",
        ),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context(actor_id, actor_kind),
    )


def test_proposal_is_immutable_and_derives_trusted_provenance() -> None:
    service, _, _ = workflow()

    result = propose(service)
    projection = result.projection

    assert projection.state == "proposed"
    assert projection.parameters == {"title": "New ticket", "description": "Line one\nLine two"}
    assert projection.caller_principal_id == "caller-key"
    assert projection.proposal_actor_id == "agent-1"
    assert projection.proposal_actor_kind == "model"
    assert projection.logical_execution_id
    assert projection.parameters_digest.startswith("sha256:")
    assert projection.audit[0].event_type == "proposed"


def test_only_authorized_human_can_decide_and_same_actor_is_allowed_without_sod() -> None:
    service, _, _ = workflow()
    created = propose(service)
    command = ApproveProposal(created.projection.proposal_id, created.projection.revision)

    with pytest.raises(KnoraError) as forbidden:
        service.handle(
            command,
            WorkspacePrincipal("workspace-a", "caller-key"),
            actor_context("agent-1", "model"),
        )
    assert forbidden.value.code == "TOOL_APPROVAL_FORBIDDEN"

    approved = service.handle(
        command,
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("agent-1", "human", can_approve=True),
    )
    assert isinstance(approved, ProposalApproved)
    assert approved.projection.state == "approved"
    assert approved.projection.approval_actor_kind == "human"


def test_explicit_separation_of_duties_denies_only_same_actor() -> None:
    service, resolver, _ = workflow()
    resolver.context = replace(
        resolver.context,
        policy=PolicyProvenance.from_semantics(
            "m4-human-approval-policy",
            "v1-sod",
            {
                "approval_actor_kinds": ["human"],
                "execution_authority_required": True,
                "separation_of_duties": True,
            },
        ),
    )
    created = propose(service, actor_kind="human", actor_id="human-a")
    command = ApproveProposal(created.projection.proposal_id, 0)

    with pytest.raises(KnoraError) as denied:
        service.handle(
            command,
            WorkspacePrincipal("workspace-a", "caller-key"),
            actor_context("human-a", "human", can_approve=True),
        )
    assert denied.value.code == "TOOL_APPROVAL_FORBIDDEN"

    approved = service.handle(
        command,
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-b", "human", can_approve=True),
    )
    assert approved.projection.state == "approved"


@pytest.mark.parametrize("actor_kind", ["model", "system"])
def test_model_and_system_cannot_reject(actor_kind: str) -> None:
    service, _, _ = workflow()
    created = propose(service)

    with pytest.raises(KnoraError) as denied:
        service.handle(
            RejectProposal(created.projection.proposal_id, 0, "other"),
            WorkspacePrincipal("workspace-a", "caller-key"),
            actor_context(actor_kind, actor_kind),
        )
    assert denied.value.code == "TOOL_APPROVAL_FORBIDDEN"


def test_concurrent_decision_has_one_cas_winner_and_loser_reads_winner() -> None:
    service, _, _ = workflow()
    created = propose(service)
    command = ApproveProposal(created.projection.proposal_id, 0)

    service.handle(
        command,
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )
    loser = service.handle(
        RejectProposal(created.projection.proposal_id, 0, "other"),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-b", "human", can_approve=True),
    )
    assert isinstance(loser, AlreadyDecided)
    assert loser.projection.state == "approved"
    assert loser.projection.revision == 1


def test_wrong_proposed_revision_is_a_revision_conflict() -> None:
    service, _, _ = workflow()
    created = propose(service)

    with pytest.raises(KnoraError) as error:
        service.handle(
            ApproveProposal(created.projection.proposal_id, 9),
            WorkspacePrincipal("workspace-a", "caller-key"),
            actor_context("human-a", "human", can_approve=True),
        )
    assert error.value.code == "TOOL_PROPOSAL_REVISION_CONFLICT"


def test_projection_distinguishes_temporary_execution_denial_and_material_stale() -> None:
    service, resolver, _ = workflow(execution_authorized=False)
    created = propose(service)
    approved = service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )
    assert approved.projection.stale is False
    assert approved.projection.executable is False
    assert approved.projection.non_executable_reason == "execution_not_authorized"

    resolver.context = replace(resolver.context, capability_digest="sha256:" + "d" * 64)
    stale = service.read(
        created.projection.proposal_id, WorkspacePrincipal("workspace-a", "caller-key")
    )
    assert stale.stale is True
    assert stale.executable is False
    assert stale.non_executable_reason == "capability_digest_mismatch"


@pytest.mark.parametrize(
    "reason", ["not_approved", "incorrect_target", "incorrect_parameters", "other"]
)
def test_reject_reason_is_closed_and_persisted(reason: str) -> None:
    service, _, _ = workflow()
    created = propose(service)
    rejected = service.handle(
        RejectProposal(created.projection.proposal_id, 0, reason),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )
    assert rejected.projection.state == "rejected"
    assert rejected.projection.audit[-1].payload["reason_code"] == reason


def test_unknown_reject_reason_is_rejected_before_persistence() -> None:
    service, _, store = workflow()
    created = propose(service)

    with pytest.raises(KnoraError) as error:
        service.handle(
            RejectProposal(created.projection.proposal_id, 0, "spoofed"),
            WorkspacePrincipal("workspace-a", "caller-key"),
            actor_context("human-a", "human", can_approve=True),
        )
    assert error.value.code == "TOOL_REQUEST_INVALID"
    assert store.read_proposal("workspace-a", created.projection.proposal_id).state == "proposed"


def test_human_decision_requires_explicit_current_approval_authority() -> None:
    service, _, _ = workflow()
    created = service.handle(
        ProposeWriteAction(
            "create_ticket",
            "m4r1.target.opaque",
            "New ticket",
            "Line one\nLine two",
        ),
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext(
            "agent-1",
            "model",
            authority=AuthorityProvenance.from_semantics(
                "proposal-model-authority", "v1", {"actor_kinds": ["model"]}
            ),
        ),
    )
    command = ApproveProposal(created.projection.proposal_id, 0)

    with pytest.raises(KnoraError) as unauthorized:
        service.handle(
            command,
            WorkspacePrincipal("workspace-a", "caller-key"),
            ActorContext(
                "human-a",
                "human",
                authority=AuthorityProvenance.from_semantics(
                    "human-identity-authority", "v1", {"actor_kinds": ["human"]}
                ),
            ),
        )
    assert unauthorized.value.code == "TOOL_APPROVAL_FORBIDDEN"

    approved = service.handle(
        command,
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext(
            "human-a",
            "human",
            authority=AuthorityProvenance.from_semantics(
                "human-identity-authority", "v1", {"actor_kinds": ["human"]}
            ),
            approval_authority=AuthorityProvenance.from_semantics(
                "workspace-approval-authority", "v1", {"workspace_id": "workspace-a"}
            ),
        ),
    )

    assert approved.projection.approval_actor_id == "human-a"
    assert approved.projection.approval_authority_id == "workspace-approval-authority"


@pytest.mark.parametrize(
    "title,description",
    [
        (" Leading", "Description"),
        ("Trailing ", "Description"),
        ("Title", " Leading"),
        ("Title", "Trailing "),
    ],
)
def test_proposal_parameters_reject_surrounding_whitespace(
    title: str, description: str
) -> None:
    service, _, _ = workflow()

    with pytest.raises(KnoraError) as error:
        service.handle(
            ProposeWriteAction(
                "create_ticket",
                "m4r1.target.opaque",
                title,
                description,
            ),
            WorkspacePrincipal("workspace-a", "caller-key"),
            actor_context("agent-1", "model"),
        )

    assert error.value.code == "TOOL_REQUEST_INVALID"


def test_description_accepts_10000_scalars_and_rejects_10001() -> None:
    service, _, _ = workflow()
    principal = WorkspacePrincipal("workspace-a", "caller-key")
    actor = actor_context("agent-1", "model")

    accepted = service.handle(
        ProposeWriteAction(
            "create_ticket",
            "m4r1.target.opaque",
            "Title",
            "x" * 10_000,
        ),
        principal,
        actor,
    )
    assert accepted.projection.parameters["description"] == "x" * 10_000

    with pytest.raises(KnoraError) as error:
        service.handle(
            ProposeWriteAction(
                "create_ticket",
                "m4r1.target.opaque",
                "Title",
                "x" * 10_001,
            ),
            principal,
            actor,
        )
    assert error.value.code == "TOOL_REQUEST_INVALID"


@pytest.mark.parametrize(
    "title,description",
    [
        ("Bad\ud800", "Description"),
        ("Bad\udfff", "Description"),
        ("Title", "Bad\ud800"),
        ("Title", "Bad\udfff"),
    ],
)
def test_proposal_parameters_reject_non_scalar_surrogates(
    title: str, description: str
) -> None:
    service, _, _ = workflow()

    with pytest.raises(KnoraError) as error:
        service.handle(
            ProposeWriteAction(
                "create_ticket",
                "m4r1.target.opaque",
                title,
                description,
            ),
            WorkspacePrincipal("workspace-a", "caller-key"),
            actor_context("agent-1", "model"),
        )
    assert error.value.code == "TOOL_REQUEST_INVALID"


def test_provenance_types_reject_noncanonical_digest_placeholders() -> None:
    with pytest.raises(ValueError, match="lowercase sha256"):
        AuthorityProvenance("actor-authority", "v1", "sha256:placeholder")

    with pytest.raises(ValueError, match="lowercase sha256"):
        PolicyProvenance(policy_digest="sha256:placeholder")

    with pytest.raises(ValueError, match="lowercase sha256"):
        ResolvedCapabilityContext(
            capability_id="create_ticket",
            capability_version="m4.2",
            capability_digest="sha256:placeholder",
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:" + "1" * 64,
            policy=PolicyProvenance.from_semantics(
                "m4-human-approval-policy",
                "v1",
                {
                    "approval_actor_kinds": ["human"],
                    "execution_authority_required": True,
                    "separation_of_duties": False,
                },
            ),
        )


def test_parameters_digest_uses_exact_canonical_json_literal() -> None:
    service, _, _ = workflow()
    result = propose(service)
    canonical = b'{"description":"Line one\\nLine two","title":"New ticket"}'

    assert result.projection.parameters_digest == (
        "sha256:" + hashlib.sha256(canonical).hexdigest()
    )


def test_request_fingerprint_binds_complete_provider_target_claims() -> None:
    service, _, store = workflow()
    result = propose(service)
    stored = store.read_proposal("workspace-a", result.projection.proposal_id)
    assert stored is not None
    provider_intent = {
        "binding": {
            "digest": "sha256:" + "b" * 64,
            "id": "binding-a",
            "version": "v1",
        },
        "capability": {
            "digest": "sha256:" + "a" * 64,
            "id": "create_ticket",
            "version": "m4.2",
        },
        "operation": "create_ticket",
        "parameters": {
            "description": "Line one\nLine two",
            "title": "New ticket",
        },
        "target": {
            "reference_id": "reference-75",
            "resource_claims_digest": "sha256:" + "e" * 64,
            "resource_identity_digest": "sha256:" + "d" * 64,
            "resource_kind": "ticket",
        },
    }
    canonical = json.dumps(
        provider_intent,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert stored.target_reference_id == "reference-75"
    assert stored.target_resource_identity_digest == "sha256:" + "d" * 64
    assert stored.target_resource_claims_digest == "sha256:" + "e" * 64
    assert stored.request_fingerprint == "sha256:" + hashlib.sha256(canonical).hexdigest()


def test_default_execution_authorizer_denies_approved_projection() -> None:
    resolver = FakeCapabilityResolver()
    service = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=InMemoryToolActionStore(),
        target_verifier=FakeTargetVerifier(),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    created = propose(service)
    approved = service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )

    assert approved.projection.state == "approved"
    assert approved.projection.stale is False
    assert approved.projection.executable is False
    assert approved.projection.non_executable_reason == "execution_not_authorized"


@pytest.mark.parametrize(
    "mutation,expected_reason",
    [
        ({"capability_id": "create_ticket_v2"}, "capability_identity_mismatch"),
        ({"capability_version": "m4.3"}, "capability_version_mismatch"),
        ({"capability_digest": "sha256:" + "f" * 64}, "capability_digest_mismatch"),
        ({"binding_id": "binding-b"}, "binding_identity_mismatch"),
        ({"binding_version": "v2"}, "binding_version_mismatch"),
        ({"binding_digest": "sha256:" + "f" * 64}, "binding_digest_mismatch"),
    ],
)
def test_projection_reports_exact_capability_and_binding_stale_reason(
    mutation: dict[str, object], expected_reason: str
) -> None:
    service, resolver, _ = workflow(execution_authorized=True)
    created = propose(service)
    service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )
    resolver.context = replace(resolver.context, **mutation)

    stale = service.read(
        created.projection.proposal_id,
        WorkspacePrincipal("workspace-a", "caller-key"),
    )

    assert stale.state == "approved"
    assert stale.stale is True
    assert stale.executable is False
    assert stale.non_executable_reason == expected_reason


@pytest.mark.parametrize(
    "change,expected_reason",
    [
        ("identity", "policy_identity_mismatch"),
        ("version", "policy_version_mismatch"),
        ("digest", "policy_digest_mismatch"),
    ],
)
def test_projection_reports_exact_policy_stale_reason(
    change: str, expected_reason: str
) -> None:
    service, resolver, _ = workflow(execution_authorized=True)
    created = propose(service)
    service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )
    current_policy = resolver.context.policy
    policy_id = "policy-v2" if change == "identity" else current_policy.policy_id
    policy_version = "v2" if change == "version" else current_policy.policy_version
    snapshot = dict(current_policy.snapshot)
    if change == "digest":
        snapshot["execution_authority_required"] = False
    resolver.context = replace(
        resolver.context,
        policy=PolicyProvenance.from_semantics(policy_id, policy_version, snapshot),
    )

    stale = service.read(
        created.projection.proposal_id,
        WorkspacePrincipal("workspace-a", "caller-key"),
    )

    assert stale.stale is True
    assert stale.non_executable_reason == expected_reason


def test_projection_treats_current_resolver_failure_as_stale() -> None:
    service, resolver, _ = workflow(execution_authorized=True)
    created = propose(service)
    service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )
    resolver.available = False

    stale = service.read(
        created.projection.proposal_id,
        WorkspacePrincipal("workspace-a", "caller-key"),
    )

    assert stale.state == "approved"
    assert stale.stale is True
    assert stale.executable is False
    assert stale.non_executable_reason == "capability_identity_mismatch"


def test_expiry_blocks_new_execution_projection_without_changing_approval() -> None:
    current = [datetime(2026, 1, 1, tzinfo=UTC)]
    resolver = FakeCapabilityResolver()
    resolver.context = replace(
        resolver.context,
        expires_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    service = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=InMemoryToolActionStore(),
        target_verifier=FakeTargetVerifier(),
        execution_authorizer=FakeExecutionAuthorizer(True),
        clock=lambda: current[0],
    )
    created = propose(service)
    service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        WorkspacePrincipal("workspace-a", "caller-key"),
        actor_context("human-a", "human", can_approve=True),
    )
    current[0] = datetime(2026, 1, 3, tzinfo=UTC)

    expired = service.read(
        created.projection.proposal_id,
        WorkspacePrincipal("workspace-a", "caller-key"),
    )

    assert expired.state == "approved"
    assert expired.stale is False
    assert expired.executable is False
    assert expired.non_executable_reason == "expired"
