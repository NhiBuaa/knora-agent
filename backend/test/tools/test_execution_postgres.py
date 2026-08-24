from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
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
    AcquireApplied,
    ActorContext,
    ApproveProposal,
    AuthorityProvenance,
    ExecuteApprovedProposal,
    ExecutionFenced,
    ExecutionIndeterminate,
    ExecutionInProgress,
    ExecutionSucceeded,
    HmacDispatchEnvelopeSigner,
    PolicyProvenance,
    ProposeWriteAction,
    ProviderOutcomeFound,
    ProviderWriteFailed,
    ProviderWriteIndeterminate,
    ProviderWriteSucceeded,
    ReconciledSucceeded,
    ReconcileExecution,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)
from knora.tools.contracts import canonical_digest_v1
from knora.tools.execution_types import AuthorizedExecutionBindingSnapshot
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
    def __init__(self, *, blocking: bool = False, outcome=None) -> None:
        self.calls = []
        self.blocking = blocking
        self.outcome = outcome or ProviderWriteSucceeded("m4r1.provider-ticket.opaque")
        self.entered = Event()
        self.release = Event()
        self.observations = []

    def create_ticket(self, envelope):
        self.calls.append(envelope)
        if self.blocking:
            self.entered.set()
            assert self.release.wait(timeout=10)
        return self.outcome

    def get_execution_outcome(self, *, scope, logical_execution_id):
        self.observations.append((scope, logical_execution_id))
        return ProviderOutcomeFound(ProviderWriteSucceeded("m4r1.provider-ticket.opaque"))


class ObservationResolver:
    def resolve_started_execution(self, snapshot, principal, proposal, execution):
        assert principal.workspace_id == proposal.workspace_id
        assert snapshot == execution.acquisition.binding_snapshot
        return "scope-a"


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


def prepared(
    *,
    blocking: bool = False,
    lease_duration: timedelta = timedelta(minutes=5),
    outcome=None,
    owner_factory=None,
    store_factory=PostgresToolActionStore,
):
    workspace_id = f"m4-execution-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 execution"))
    store = store_factory(SessionFactory)
    resolver = Resolver(workspace_id)
    authorizer = Authorizer()
    gateway = Gateway(blocking=blocking, outcome=outcome)
    workflow = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=store,
        target_verifier=TargetVerifier(),
        execution_authorizer=authorizer,
        execution_resource_authorizer=ResourceAuthorizer(),
        observation_reference_resolver=ObservationResolver(),
        gateway=gateway,
        dispatch_signer=HmacDispatchEnvelopeSigner(
            key_identity="dispatch-key", key_version="v1", secret=b"dispatch-secret"
        ),
        execution_owner_factory=owner_factory or (lambda: "worker-a"),
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
        audits = session.scalars(
            select(ToolActionAuditEventTable)
            .where(ToolActionAuditEventTable.proposal_id == approved.projection.proposal_id)
            .order_by(ToolActionAuditEventTable.sequence)
        ).all()
    assert execution is not None and execution.generation == 1
    assert execution.lifecycle == "succeeded"
    assert admission is not None and admission.envelope_token == gateway.calls[0].token
    assert admission.admission_digest.startswith("sha256:")
    assert len(observations) == 1
    assert [item.event_type for item in audits] == [
        "proposed",
        "approved",
        "execution_acquired",
        "dispatch_admitted",
        "execution_observed",
        "succeeded",
    ]
    forbidden_audit_keys = {
        "envelope_token",
        "provider_routing_handle",
        "external_scope",
        "secret",
        "credential",
        "mac",
    }
    assert all(not (set(item.payload) & forbidden_audit_keys) for item in audits)

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


class CommitThenLoseAdmissionAckStore(PostgresToolActionStore):
    def __init__(self, session_factory) -> None:
        super().__init__(session_factory)
        self.lost = False

    def authorize_and_admit_dispatch(self, *args, **kwargs):
        result = super().authorize_and_admit_dispatch(*args, **kwargs)
        if not self.lost:
            self.lost = True
            raise KnoraError("PERSISTENCE_OPERATION_FAILED")
        return result


class RollbackAdmissionStore(PostgresToolActionStore):
    def authorize_and_admit_dispatch(self, *args, **kwargs):
        raise KnoraError("PERSISTENCE_OPERATION_FAILED")


def test_postgres_admission_ack_loss_reads_back_without_second_insert() -> None:
    workflow, _, _, _, gateway, principal, approved = prepared(
        store_factory=CommitThenLoseAdmissionAckStore
    )

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert isinstance(result, ExecutionSucceeded)
    assert len(gateway.calls) == 1
    with SessionFactory() as session:
        admissions = session.scalars(
            select(ToolDispatchAdmissionTable).where(
                ToolDispatchAdmissionTable.proposal_id == approved.projection.proposal_id
            )
        ).all()
    assert len(admissions) == 1
    assert admissions[0].envelope_token == gateway.calls[0].token


def test_postgres_absent_admission_after_ambiguous_failure_is_non_terminal() -> None:
    workflow, _, _, _, gateway, principal, approved = prepared(
        store_factory=RollbackAdmissionStore
    )

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert isinstance(result, ExecutionIndeterminate)
    assert gateway.calls == []
    with SessionFactory() as session:
        admission = session.scalar(
            select(ToolDispatchAdmissionTable).where(
                ToolDispatchAdmissionTable.proposal_id == approved.projection.proposal_id
            )
        )
        execution = session.get(ToolExecutionTable, approved.projection.proposal_id)
    assert admission is None
    assert execution is not None and execution.lifecycle == "executing"


@pytest.mark.parametrize(
    "outcome",
    [
        ProviderWriteSucceeded("m4r1.provider-ticket.opaque"),
        ProviderWriteFailed("target_not_found"),
        ProviderWriteFailed("validation_rejected"),
        ProviderWriteFailed("policy_rejected"),
    ],
)
def test_postgres_fences_every_delayed_closed_provider_outcome(outcome) -> None:
    workflow, _, _, _, gateway, principal, approved = prepared(
        blocking=True,
        lease_duration=timedelta(milliseconds=200),
        outcome=outcome,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            workflow.handle,
            ExecuteApprovedProposal(approved.projection.proposal_id, 1),
            principal,
            actor("executor-a", "system"),
        )
        assert gateway.entered.wait(timeout=10)
        Event().wait(0.3)
        gateway.release.set()
        result = pending.result(timeout=10)

    assert isinstance(result, ExecutionFenced)
    with SessionFactory() as session:
        execution = session.get(ToolExecutionTable, approved.projection.proposal_id)
        observations = session.scalars(
            select(ToolExecutionObservationTable).where(
                ToolExecutionObservationTable.proposal_id == approved.projection.proposal_id
            )
        ).all()
    assert execution is not None and execution.lifecycle == "executing"
    assert execution.finalized_at is None
    assert observations == []


def test_postgres_database_time_not_requested_at_controls_acquisition_and_admission() -> None:
    _, _, store, _, _, principal, approved = prepared()
    proposal = store.read_proposal(principal.workspace_id, approved.projection.proposal_id)
    assert proposal is not None
    future_host_time = proposal.expires_at + timedelta(days=1)

    acquired = store.acquire_execution(
        principal.workspace_id,
        proposal.proposal_id,
        proposal.revision,
        "worker-a",
        timedelta(minutes=5),
        AuthorizedExecutionBindingSnapshot.from_context(Resolver(principal.workspace_id).context),
        future_host_time,
    )

    assert isinstance(acquired, AcquireApplied)
    assert acquired.execution.lease_started_at < future_host_time
    assert acquired.execution.lease_started_at < proposal.expires_at


def test_postgres_admission_binds_current_epochs_without_retargeting() -> None:
    workflow, _, store, _, gateway, principal, approved = prepared()
    first_vector = store.advance_dispatch_epochs(
        principal.workspace_id, reference_key=True, workspace=True
    )

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )
    second_vector = store.advance_dispatch_epochs(
        principal.workspace_id, reference_key=True, workspace=True
    )
    reloaded = store.read_proposal(principal.workspace_id, approved.projection.proposal_id)

    assert isinstance(result, ExecutionSucceeded)
    assert reloaded is not None and reloaded.admission is not None
    assert (
        reloaded.admission.reference_key_epoch,
        reloaded.admission.workspace_dispatch_epoch,
    ) == first_vector
    assert second_vector != first_vector
    assert len(gateway.calls) == 1


def test_postgres_reconciliation_takes_over_a_strictly_expired_lease_before_finalizing() -> None:
    owners = iter(("worker-a", "recovery-b"))
    workflow, _, _, _, gateway, principal, approved = prepared(
        lease_duration=timedelta(milliseconds=200),
        outcome=ProviderWriteIndeterminate(),
        owner_factory=lambda: next(owners),
    )
    first = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )
    assert isinstance(first, ExecutionIndeterminate)
    Event().wait(0.3)

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert isinstance(result, ReconciledSucceeded)
    assert gateway.observations == [("scope-a", approved.projection.logical_execution_id)]
    assert len(gateway.calls) == 1
    with SessionFactory() as session:
        execution = session.get(ToolExecutionTable, approved.projection.proposal_id)
        events = session.scalars(
            select(ToolActionAuditEventTable.event_type)
            .where(ToolActionAuditEventTable.proposal_id == approved.projection.proposal_id)
            .order_by(ToolActionAuditEventTable.sequence)
        ).all()
    assert execution is not None
    assert (execution.owner, execution.generation, execution.lifecycle) == (
        "recovery-b",
        2,
        "succeeded",
    )
    assert events[-3:] == ["execution_taken_over", "execution_observed", "succeeded"]
