from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    ActorContext,
    ApproveProposal,
    AuthorityProvenance,
    ExecuteApprovedProposal,
    HmacDispatchEnvelopeSigner,
    InMemoryToolActionStore,
    PolicyProvenance,
    ProposeWriteAction,
    ProviderObservationMalformed,
    ProviderObservationTimeout,
    ProviderObservationUnavailable,
    ProviderOutcomeFound,
    ProviderOutcomeNotFound,
    ProviderWriteFailed,
    ProviderWriteIndeterminate,
    ProviderWriteSucceeded,
    ReconciledFailed,
    ReconciledSucceeded,
    ReconcileExecution,
    ReconciliationIndeterminate,
    ReconciliationOutcomeNotFound,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)
from knora.tools.contracts import canonical_digest_v1
from knora.tools.references import AuthorizedExternalResource

NOW = datetime(2026, 8, 24, 12, 30, tzinfo=UTC)


class Resolver:
    context = ResolvedCapabilityContext(
        capability_id="create_ticket",
        capability_version="m4.2",
        capability_digest="sha256:" + "a" * 64,
        resource_kind="ticket",
        binding_id="binding-a",
        binding_version="v1",
        binding_digest="sha256:" + "b" * 64,
        policy=PolicyProvenance(),
    )

    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        assert workspace_id == "workspace-a"
        assert capability_id == "create_ticket"
        return self.context


class TargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        return VerifiedProposalTarget(
            reference=target_reference,
            reference_digest=canonical_digest_v1(target_reference),
            reference_id="A" * 43,
            workspace_id=workspace_id,
            capability_id=capability.capability_id,
            capability_version=capability.capability_version,
            binding_id=capability.binding_id,
            binding_version=capability.binding_version,
            binding_digest=capability.binding_digest,
            resource_kind=capability.resource_kind,
            resource_identity_digest="sha256:" + "c" * 64,
            resource_claims_digest="sha256:" + "d" * 64,
        )


class ResourceAuthorizer:
    def authorize_current(self, principal, proposal, current, *, at_time):
        assert principal.workspace_id == proposal.workspace_id == "workspace-a"
        assert at_time.tzinfo is not None
        return AuthorizedExternalResource(
            reference_id=proposal.target_reference_id,
            binding_id=current.binding_id,
            binding_version=current.binding_version,
            binding_digest=current.binding_digest,
            resource_kind=proposal.resource_kind,
            provider_routing_handle="routing-a",
            resource_identity_digest=proposal.target_resource_identity_digest,
            resource_claims_digest=proposal.target_resource_claims_digest,
            external_scope="scope-a",
        )


class CountingResourceAuthorizer(ResourceAuthorizer):
    def __init__(self) -> None:
        self.calls = 0
        self.allowed = True

    def authorize_current(self, principal, proposal, current, *, at_time):
        self.calls += 1
        if not self.allowed:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        return super().authorize_current(principal, proposal, current, at_time=at_time)


class ExecutionAuthorizer:
    def is_authorized(self, principal, proposal) -> bool:
        return principal.workspace_id == proposal.workspace_id


class ToggleExecutionAuthorizer(ExecutionAuthorizer):
    def __init__(self) -> None:
        self.calls = 0
        self.allowed = True

    def is_authorized(self, principal, proposal) -> bool:
        self.calls += 1
        return self.allowed and super().is_authorized(principal, proposal)


class ObservationResolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_started_execution(self, snapshot, principal, proposal, execution):
        self.calls += 1
        assert principal.workspace_id == proposal.workspace_id
        assert snapshot == execution.acquisition.binding_snapshot
        return "scope-a"


class DeniedObservationResolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_started_execution(self, snapshot, principal, proposal, execution):
        self.calls += 1
        return None


class MutableClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self):
        return self.now


class Gateway:
    def __init__(self, *, observed=None) -> None:
        self.write_calls = []
        self.observation_calls = []
        self.observed = observed or ProviderOutcomeFound(
            ProviderWriteSucceeded("m4r1.provider-ticket.opaque")
        )

    def create_ticket(self, envelope):
        self.write_calls.append(envelope)
        return ProviderWriteIndeterminate()

    def get_execution_outcome(self, *, scope, logical_execution_id):
        self.observation_calls.append((scope, logical_execution_id))
        return self.observed


def actor(actor_id: str, kind: str, *, can_approve: bool = False) -> ActorContext:
    return ActorContext(
        actor_id,
        kind,
        authority=AuthorityProvenance.from_semantics("actor", "v1", {"kind": kind}),
        approval_authority=(
            AuthorityProvenance.from_semantics("approval", "v1", {"workspace": "workspace-a"})
            if can_approve
            else None
        ),
    )


def test_reconcile_observes_provider_truth_before_terminalizing_an_indeterminate_execution(
) -> None:
    store = InMemoryToolActionStore()
    gateway = Gateway()
    observation_resolver = ObservationResolver()
    workflow = WriteProposalWorkflow(
        capability_resolver=Resolver(),
        store=store,
        target_verifier=TargetVerifier(),
        execution_authorizer=ExecutionAuthorizer(),
        execution_resource_authorizer=ResourceAuthorizer(),
        observation_reference_resolver=observation_resolver,
        gateway=gateway,
        dispatch_signer=HmacDispatchEnvelopeSigner(
            key_identity="dispatch-key", key_version="v1", secret=b"dispatch-secret"
        ),
        execution_owner_factory=lambda: "worker-a",
        execution_lease_duration=timedelta(minutes=2),
        clock=lambda: NOW,
    )
    principal = WorkspacePrincipal("workspace-a", "key-a")
    created = workflow.handle(
        ProposeWriteAction("create_ticket", "m4r1.target.opaque", "Login", "Customer blocked"),
        principal,
        actor("model-a", "model"),
    )
    approved = workflow.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        actor("human-a", "human", can_approve=True),
    )
    first = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )
    assert first.outcome_type == "execution_indeterminate"

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert result == ReconciledSucceeded(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        "m4r1.provider-ticket.opaque",
    )
    assert observation_resolver.calls == 1
    assert gateway.observation_calls == [("scope-a", approved.projection.logical_execution_id)]
    assert len(gateway.write_calls) == 1
    stored = store.read_proposal(principal.workspace_id, approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution.lifecycle == "succeeded"


def test_reconcile_preserves_closed_provider_rejection_without_another_write() -> None:
    workflow, gateway, principal, approved = _prepared_reconciliation_workflow(
        observed=ProviderOutcomeFound(ProviderWriteFailed("validation_rejected"))
    )
    workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert result == ReconciledFailed(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        "validation_rejected",
    )
    assert len(gateway.write_calls) == 1


def test_reconcile_not_found_stays_nonterminal_while_the_lease_is_current() -> None:
    workflow, gateway, principal, approved = _prepared_reconciliation_workflow(
        observed=ProviderOutcomeNotFound()
    )
    workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert result == ReconciliationOutcomeNotFound(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
    )
    assert len(gateway.observation_calls) == 1
    assert len(gateway.write_calls) == 1


@pytest.mark.parametrize(
    ("provider_outcome", "reason_code"),
    [
        (ProviderObservationUnavailable(), "provider_observation_unavailable"),
        (ProviderObservationTimeout(), "provider_observation_timeout"),
        (ProviderObservationMalformed(), "provider_observation_malformed"),
    ],
)
def test_reconcile_keeps_each_ambiguous_provider_observation_nonterminal(
    provider_outcome, reason_code
) -> None:
    workflow, gateway, principal, approved = _prepared_reconciliation_workflow(
        observed=provider_outcome
    )
    workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert result == ReconciliationIndeterminate(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        reason_code,
    )
    assert len(gateway.observation_calls) == 1
    assert len(gateway.write_calls) == 1


def test_terminal_reconciliation_survives_expiry_and_current_write_revocation() -> None:
    clock = MutableClock()
    resource_authorizer = CountingResourceAuthorizer()
    execution_authorizer = ToggleExecutionAuthorizer()
    observation_resolver = ObservationResolver()
    workflow, gateway, principal, approved = _prepared_reconciliation_workflow(
        clock=clock,
        resource_authorizer=resource_authorizer,
        execution_authorizer=execution_authorizer,
        observation_resolver=observation_resolver,
    )
    workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )
    write_authorization_counts = (resource_authorizer.calls, execution_authorizer.calls)
    clock.now += timedelta(days=1)
    resource_authorizer.allowed = execution_authorizer.allowed = False

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert isinstance(result, ReconciledSucceeded)
    assert observation_resolver.calls == 1
    assert (resource_authorizer.calls, execution_authorizer.calls) == write_authorization_counts
    assert len(gateway.write_calls) == 1


def test_observation_routing_denial_precedes_provider_observation_and_retry() -> None:
    resolver = DeniedObservationResolver()
    workflow, gateway, principal, approved = _prepared_reconciliation_workflow(
        observation_resolver=resolver
    )
    workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert result == ReconciliationIndeterminate(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        "observation_routing_unavailable",
    )
    assert resolver.calls == 1
    assert gateway.observation_calls == []
    assert len(gateway.write_calls) == 1


def test_not_found_retry_denial_observes_once_without_another_provider_write() -> None:
    clock = MutableClock()
    resource_authorizer = CountingResourceAuthorizer()
    execution_authorizer = ToggleExecutionAuthorizer()
    owners = iter(("worker-a", "recovery-b"))
    workflow, gateway, principal, approved = _prepared_reconciliation_workflow(
        observed=ProviderOutcomeNotFound(),
        clock=clock,
        resource_authorizer=resource_authorizer,
        execution_authorizer=execution_authorizer,
        owner_factory=lambda: next(owners),
        lease_duration=timedelta(seconds=1),
    )
    workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )
    prior_resource_calls = resource_authorizer.calls
    clock.now += timedelta(seconds=2)
    execution_authorizer.allowed = False

    with pytest.raises(KnoraError) as error:
        workflow.handle(
            ReconcileExecution(approved.projection.proposal_id, 1),
            principal,
            actor("recovery-a", "system"),
        )

    assert error.value.code == "TOOL_EXECUTION_NOT_AUTHORIZED"
    assert gateway.observation_calls == [("scope-a", approved.projection.logical_execution_id)]
    assert resource_authorizer.calls == prior_resource_calls + 1
    assert len(gateway.write_calls) == 1


def _prepared_reconciliation_workflow(
    *,
    observed=None,
    clock=None,
    resource_authorizer=None,
    execution_authorizer=None,
    observation_resolver=None,
    owner_factory=None,
    lease_duration=timedelta(minutes=2),
):
    gateway = Gateway(observed=observed)
    workflow = WriteProposalWorkflow(
        capability_resolver=Resolver(),
        store=InMemoryToolActionStore(),
        target_verifier=TargetVerifier(),
        execution_authorizer=execution_authorizer or ExecutionAuthorizer(),
        execution_resource_authorizer=resource_authorizer or ResourceAuthorizer(),
        observation_reference_resolver=observation_resolver or ObservationResolver(),
        gateway=gateway,
        dispatch_signer=HmacDispatchEnvelopeSigner(
            key_identity="dispatch-key", key_version="v1", secret=b"dispatch-secret"
        ),
        execution_owner_factory=owner_factory or (lambda: "worker-a"),
        execution_lease_duration=lease_duration,
        clock=clock or (lambda: NOW),
    )
    principal = WorkspacePrincipal("workspace-a", "key-a")
    created = workflow.handle(
        ProposeWriteAction("create_ticket", "m4r1.target.opaque", "Login", "Customer blocked"),
        principal,
        actor("model-a", "model"),
    )
    approved = workflow.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        actor("human-a", "human", can_approve=True),
    )
    return workflow, gateway, principal, approved
