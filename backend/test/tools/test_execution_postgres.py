from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

from sqlalchemy import select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import (
    ToolActionAuditEventTable,
    ToolDispatchAdmissionTable,
    ToolExecutionObservationTable,
    ToolExecutionTable,
    ToolProposalTable,
    WorkspaceTable,
)
from knora.adapters.postgres.tool_action_store import PostgresToolActionStore
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    ActorContext,
    ApproveProposal,
    AuthorityProvenance,
    ExecuteApprovedProposal,
    ExecutionFenced,
    ExecutionInProgress,
    ExecutionSucceeded,
    HmacDispatchEnvelopeSigner,
    PolicyProvenance,
    ProposeWriteAction,
    ProviderWriteSucceeded,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)
from knora.tools.contracts import canonical_digest_v1
from knora.tools.references import AuthorizedExternalResource

NOW = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


class Resolver:
    def __init__(self, workspace_id: str) -> None:
        self.workspace_id = workspace_id
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
        if workspace_id != self.workspace_id or capability_id != "create_ticket":
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return self.context


class TargetVerifier:
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


class ResourceAuthorizer:
    def authorize_current(self, principal, proposal, current, *, at_time):
        assert at_time.tzinfo is not None
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


class Authorizer:
    def is_authorized(self, principal, proposal):
        return principal.workspace_id == proposal.workspace_id


class Gateway:
    def __init__(self, *, blocking: bool = False) -> None:
        self.calls = []
        self.blocking = blocking
        self.entered = Event()
        self.release = Event()

    def create_ticket(self, envelope):
        self.calls.append(envelope)
        if self.blocking:
            self.entered.set()
            assert self.release.wait(timeout=10)
        return ProviderWriteSucceeded("m4r1.provider-ticket.opaque")


def actor(actor_id: str, kind: str, *, approval: bool = False) -> ActorContext:
    return ActorContext(
        actor_id,
        kind,
        AuthorityProvenance.from_semantics("actor-authority", "v1", {"kind": kind}),
        (
            AuthorityProvenance.from_semantics("approval-authority", "v1", {"role": "approver"})
            if approval
            else None
        ),
    )


def prepared(*, blocking: bool = False, lease_duration: timedelta = timedelta(minutes=5)):
    workspace_id = f"m4-execution-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 execution"))
    store = PostgresToolActionStore(SessionFactory)
    resolver = Resolver(workspace_id)
    authorizer = Authorizer()
    gateway = Gateway(blocking=blocking)
    workflow = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=store,
        target_verifier=TargetVerifier(),
        execution_authorizer=authorizer,
        execution_resource_authorizer=ResourceAuthorizer(),
        gateway=gateway,
        dispatch_signer=HmacDispatchEnvelopeSigner(
            key_identity="dispatch-key", key_version="v1", secret=b"dispatch-secret"
        ),
        execution_owner_factory=lambda: "worker-a",
        execution_lease_duration=lease_duration,
        clock=lambda: NOW,
    )
    principal = WorkspacePrincipal(workspace_id, "key-a")
    created = workflow.handle(
        ProposeWriteAction(
            "create_ticket", "m4r1.target.opaque", "Cannot sign in", "Customer blocked"
        ),
        principal,
        actor("model-a", "model"),
    )
    approved = workflow.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        actor("human-a", "human", approval=True),
    )
    return workflow, resolver, store, authorizer, gateway, principal, approved


def test_postgres_execution_persists_complete_generation_one_and_restarts() -> None:
    workflow, _, _, _, gateway, principal, approved = prepared()

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert isinstance(result, ExecutionSucceeded)
    with SessionFactory() as session:
        execution = session.scalar(
            select(ToolExecutionTable).where(
                ToolExecutionTable.proposal_id == approved.projection.proposal_id
            )
        )
        admission = session.scalar(
            select(ToolDispatchAdmissionTable).where(
                ToolDispatchAdmissionTable.proposal_id == approved.projection.proposal_id
            )
        )
        observations = session.scalars(
            select(ToolExecutionObservationTable).where(
                ToolExecutionObservationTable.proposal_id == approved.projection.proposal_id
            )
        ).all()
    assert execution is not None and execution.generation == 1
    assert execution.lifecycle == "succeeded"
    assert admission is not None and admission.envelope_token == gateway.calls[0].token
    assert admission.admission_digest.startswith("sha256:")
    assert len(observations) == 1

    reloaded = PostgresToolActionStore(SessionFactory).read_proposal(
        principal.workspace_id, approved.projection.proposal_id
    )
    assert reloaded is not None and reloaded.execution is not None
    assert reloaded.execution.lifecycle == "succeeded"
    assert reloaded.admission is not None
    assert reloaded.admission.envelope_token == admission.envelope_token


def test_postgres_concurrent_execute_has_one_dispatch_and_one_durable_admission() -> None:
    workflow, _, _, _, gateway, principal, approved = prepared(blocking=True)
    command = ExecuteApprovedProposal(approved.projection.proposal_id, 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(workflow.handle, command, principal, actor("executor-a", "system"))
        assert gateway.entered.wait(timeout=10)
        loser = workflow.handle(command, principal, actor("executor-b", "system"))
        gateway.release.set()
        assert isinstance(winner.result(timeout=10), ExecutionSucceeded)

    assert isinstance(loser, ExecutionInProgress)
    assert len(gateway.calls) == 1
    with SessionFactory() as session:
        admissions = session.scalars(
            select(ToolDispatchAdmissionTable).where(
                ToolDispatchAdmissionTable.proposal_id == approved.projection.proposal_id
            )
        ).all()
    assert len(admissions) == 1


def test_postgres_fences_observation_after_provider_returns_beyond_lease() -> None:
    workflow, _, _, _, gateway, principal, approved = prepared(
        blocking=True, lease_duration=timedelta(milliseconds=200)
    )
    command = ExecuteApprovedProposal(approved.projection.proposal_id, 1)

    with ThreadPoolExecutor(max_workers=1) as pool:
        execution = pool.submit(
            workflow.handle, command, principal, actor("executor-a", "system")
        )
        assert gateway.entered.wait(timeout=10)
        Event().wait(0.3)
        gateway.release.set()
        result = execution.result(timeout=10)

    assert isinstance(result, ExecutionFenced)
    with SessionFactory() as session:
        stored = session.get(ToolExecutionTable, approved.projection.proposal_id)
        observations = session.scalars(
            select(ToolExecutionObservationTable).where(
                ToolExecutionObservationTable.proposal_id == approved.projection.proposal_id
            )
        ).all()
    assert stored is not None and stored.lifecycle == "executing"
    assert stored.finalized_at is None
    assert observations == []


def test_postgres_material_mismatch_invalidates_approval_without_dispatch() -> None:
    workflow, resolver, _, authorizer, gateway, principal, approved = prepared()
    original = authorizer.is_authorized
    with SessionFactory() as session:
        approved_row = session.get(ToolProposalTable, approved.projection.proposal_id)
        assert approved_row is not None
        approval_provenance = (
            approved_row.decision_actor_id,
            approved_row.decision_authority_id,
            approved_row.decision_authority_version,
            approved_row.decision_authority_digest,
        )
    calls = 0

    def mutate_after_first_check(current_principal, proposal):
        nonlocal calls
        calls += 1
        allowed = original(current_principal, proposal)
        if calls == 1:
            resolver.context = ResolvedCapabilityContext(
                resolver.context.capability_id,
                resolver.context.capability_version,
                "sha256:" + "9" * 64,
                resolver.context.resource_kind,
                resolver.context.binding_id,
                resolver.context.binding_version,
                resolver.context.binding_digest,
                resolver.context.policy,
            )
        return allowed

    authorizer.is_authorized = mutate_after_first_check

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result.reason_code == "capability_digest_mismatch"
    with SessionFactory() as session:
        proposal = session.get(ToolProposalTable, approved.projection.proposal_id)
        admission = session.get(ToolDispatchAdmissionTable, approved.projection.proposal_id)
        audit = session.scalars(
            select(ToolActionAuditEventTable)
            .where(ToolActionAuditEventTable.proposal_id == approved.projection.proposal_id)
            .order_by(ToolActionAuditEventTable.sequence)
        ).all()
    assert proposal is not None
    assert proposal.state == "executing"
    assert proposal.execution_stale_reason == "capability_digest_mismatch"
    assert (
        proposal.decision_actor_id,
        proposal.decision_authority_id,
        proposal.decision_authority_version,
        proposal.decision_authority_digest,
    ) == approval_provenance
    assert audit[-1].event_type == "approval_invalidated"
    assert audit[-1].payload == {
        "reason_code": "capability_digest_mismatch",
        "approval_validity": "invalidated",
    }
    assert admission is None
    assert gateway.calls == []
