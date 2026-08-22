from dataclasses import replace
from datetime import UTC, datetime

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    ActorContext,
    AlreadyDecided,
    ApproveProposal,
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
        self.context = ResolvedCapabilityContext(
            capability_id="create_ticket",
            capability_version="m4.2",
            capability_digest="sha256:create-ticket-v1",
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:binding-a",
            policy=PolicyProvenance(),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )

    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        del workspace_id
        if capability_id != self.context.capability_id:
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return self.context


class FakeTargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        if target_reference != "m4r1.target.opaque":
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
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


def workflow(*, execution_authorized=True):
    resolver = FakeCapabilityResolver()
    store = InMemoryToolActionStore()
    service = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=store,
        target_verifier=FakeTargetVerifier(),
        execution_authorizer=lambda _principal, _proposal: execution_authorized,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    return service, resolver, store


def propose(service: WriteProposalWorkflow, actor_kind="model", actor_id="agent-1"):
    return service.handle(
        ProposeWriteAction(
            capability_id="create_ticket",
            target_reference="m4r1.target.opaque",
            title="  New ticket  ",
            description="Line one\r\nLine two",
        ),
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext(actor_id=actor_id, actor_kind=actor_kind),
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
            ActorContext("agent-1", "model"),
        )
    assert forbidden.value.code == "TOOL_APPROVAL_FORBIDDEN"

    approved = service.handle(
        command,
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext("agent-1", "human"),
    )
    assert isinstance(approved, ProposalApproved)
    assert approved.projection.state == "approved"
    assert approved.projection.approval_actor_kind == "human"


def test_concurrent_decision_has_one_cas_winner_and_loser_reads_winner() -> None:
    service, _, _ = workflow()
    created = propose(service)
    command = ApproveProposal(created.projection.proposal_id, 0)

    service.handle(
        command,
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext("human-a", "human"),
    )
    loser = service.handle(
        RejectProposal(created.projection.proposal_id, 0, "other"),
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext("human-b", "human"),
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
            ActorContext("human-a", "human"),
        )
    assert error.value.code == "TOOL_PROPOSAL_REVISION_CONFLICT"


def test_projection_distinguishes_temporary_execution_denial_and_material_stale() -> None:
    service, resolver, _ = workflow(execution_authorized=False)
    created = propose(service)
    approved = service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext("human-a", "human"),
    )
    assert approved.projection.stale is False
    assert approved.projection.executable is False
    assert approved.projection.non_executable_reason == "execution_not_authorized"

    resolver.context = replace(resolver.context, capability_digest="sha256:new-version")
    stale = service.read(
        created.projection.proposal_id, WorkspacePrincipal("workspace-a", "caller-key")
    )
    assert stale.stale is True
    assert stale.executable is False
    assert stale.non_executable_reason == "material_compatibility_mismatch"


@pytest.mark.parametrize(
    "reason", ["not_approved", "incorrect_target", "incorrect_parameters", "other"]
)
def test_reject_reason_is_closed_and_persisted(reason: str) -> None:
    service, _, _ = workflow()
    created = propose(service)
    rejected = service.handle(
        RejectProposal(created.projection.proposal_id, 0, reason),
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext("human-a", "human"),
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
            ActorContext("human-a", "human"),
        )
    assert error.value.code == "TOOL_REQUEST_INVALID"
    assert store.read_proposal("workspace-a", created.projection.proposal_id).state == "proposed"
