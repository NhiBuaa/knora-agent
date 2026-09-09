from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    ActorContext,
    ApproveProposal,
    AuthorityProvenance,
    ExecuteApprovedProposal,
    ExecutionFailed,
    ExecutionIndeterminate,
    ExecutionInProgress,
    ExecutionSucceeded,
    HmacDispatchEnvelopeSigner,
    InMemoryToolActionStore,
    PolicyProvenance,
    ProposalNotExecutable,
    ProposeWriteAction,
    ProviderIdempotencyConflict,
    ProviderRequestRejected,
    ProviderScopeDenied,
    ProviderWriteFailed,
    ProviderWriteIndeterminate,
    ProviderWriteSucceeded,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)
from knora.tools.contracts import canonical_digest_v1
from knora.tools.references import AuthorizedExternalResource

NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


class Resolver:
    def __init__(self) -> None:
        self.context = ResolvedCapabilityContext(
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
        if capability_id != "create_ticket":
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return self.context


class ProposalTargetVerifier:
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


class ExecutionResourceAuthorizer:
    def authorize_current(self, principal, proposal, current, *, at_time):
        assert principal.workspace_id == proposal.workspace_id == "workspace-a"
        assert current.capability_id == proposal.capability_id
        assert at_time.tzinfo is not None
        return AuthorizedExternalResource(
            reference_id=proposal.target_reference_id,
            binding_id=current.binding_id,
            binding_version=current.binding_version,
            binding_digest=current.binding_digest,
            resource_kind=proposal.resource_kind,
            provider_routing_handle="routing-target-a",
            resource_identity_digest=proposal.target_resource_identity_digest,
            resource_claims_digest=proposal.target_resource_claims_digest,
            external_scope="scope-a",
        )


class ExecutionAuthorizer:
    def __init__(self, authorized: bool = True) -> None:
        self.authorized = authorized
        self.calls = 0

    def is_authorized(self, principal, proposal) -> bool:
        del principal, proposal
        self.calls += 1
        return self.authorized


class Gateway:
    def __init__(self, outcome=None) -> None:
        self.outcome = outcome or ProviderWriteSucceeded("m4r1.provider-ticket.opaque")
        self.calls = []

    def create_ticket(self, envelope):
        self.calls.append(envelope)
        return self.outcome


class BlockingGateway(Gateway):
    def __init__(self) -> None:
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def create_ticket(self, envelope):
        self.calls.append(envelope)
        self.entered.set()
        assert self.release.wait(timeout=5)
        return self.outcome


def actor(actor_id: str, kind: str, *, can_approve: bool = False) -> ActorContext:
    return ActorContext(
        actor_id,
        kind,
        authority=AuthorityProvenance.from_semantics("actor-authority", "v1", {"actor_kind": kind}),
        approval_authority=(
            AuthorityProvenance.from_semantics(
                "approval-authority", "v1", {"workspace_id": "workspace-a"}
            )
            if can_approve
            else None
        ),
    )


def prepared_workflow(*, gateway=None, execution_authorized: bool = True, store=None):
    resolver = Resolver()
    store = store or InMemoryToolActionStore()
    authorizer = ExecutionAuthorizer(execution_authorized)
    provider = gateway or Gateway()
    workflow = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=store,
        target_verifier=ProposalTargetVerifier(),
        execution_authorizer=authorizer,
        execution_resource_authorizer=ExecutionResourceAuthorizer(),
        gateway=provider,
        dispatch_signer=HmacDispatchEnvelopeSigner(
            key_identity="dispatch-test-key",
            key_version="v1",
            secret=b"dispatch-test-secret",
        ),
        execution_owner_factory=lambda: "worker-a",
        execution_lease_duration=timedelta(minutes=2),
        clock=lambda: NOW,
    )
    principal = WorkspacePrincipal("workspace-a", "key-a")
    created = workflow.handle(
        ProposeWriteAction(
            "create_ticket", "m4r1.target.opaque", "Cannot sign in", "Customer is blocked"
        ),
        principal,
        actor("model-a", "model"),
    )
    approved = workflow.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        actor("human-a", "human", can_approve=True),
    )
    return workflow, resolver, store, authorizer, provider, principal, approved


def test_execute_revalidates_authority_and_finalizes_success() -> None:
    workflow, _, store, authorizer, gateway, principal, approved = prepared_workflow()

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result == ExecutionSucceeded(
        proposal_id=approved.projection.proposal_id,
        logical_execution_id=approved.projection.logical_execution_id,
        external_resource_reference="m4r1.provider-ticket.opaque",
    )
    assert authorizer.calls >= 2  # pre-acquisition and admission-time revalidation
    assert len(gateway.calls) == 1
    assert gateway.calls[0].token.startswith("m4-dispatch-admission-v1.")
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None
    assert stored.execution is not None
    assert stored.execution.lifecycle == "succeeded"
    assert stored.execution.generation == 1
    assert stored.admission is not None


def test_execution_authority_denial_preserves_approved_provenance_and_zero_side_effects() -> None:
    workflow, _, store, _, gateway, principal, approved = prepared_workflow(
        execution_authorized=False
    )
    before = store.read_proposal("workspace-a", approved.projection.proposal_id)

    with pytest.raises(KnoraError) as denied:
        workflow.handle(
            ExecuteApprovedProposal(approved.projection.proposal_id, 1),
            principal,
            actor("executor-a", "system"),
        )

    assert denied.value.code == "TOOL_EXECUTION_NOT_AUTHORIZED"
    assert store.read_proposal("workspace-a", approved.projection.proposal_id) == before
    assert gateway.calls == []


class AdmissionPersistenceFailureStore(InMemoryToolActionStore):
    def authorize_and_admit_dispatch(self, *args, **kwargs):
        raise KnoraError("PERSISTENCE_OPERATION_FAILED")


def test_no_admission_ambiguity_stays_indeterminate_and_is_not_retried() -> None:
    store = AdmissionPersistenceFailureStore()
    workflow, _, _, _, gateway, principal, approved = prepared_workflow(store=store)
    command = ExecuteApprovedProposal(approved.projection.proposal_id, 1)

    first = workflow.handle(command, principal, actor("executor-a", "system"))
    seed = store.read_execution_recovery_seed("workspace-a", approved.projection.proposal_id)
    second = workflow.handle(command, principal, actor("executor-b", "system"))

    assert isinstance(first, ExecutionIndeterminate)
    assert seed is not None and seed.kind == "NoAdmission"
    assert isinstance(second, ExecutionInProgress)
    assert gateway.calls == []


def test_admission_outstanding_seed_is_stable_and_repeated_execute_never_replays() -> None:
    workflow, _, store, _, gateway, principal, approved = prepared_workflow(
        gateway=Gateway(ProviderWriteIndeterminate())
    )
    command = ExecuteApprovedProposal(approved.projection.proposal_id, 1)

    first = workflow.handle(command, principal, actor("executor-a", "system"))
    seed = store.read_execution_recovery_seed("workspace-a", approved.projection.proposal_id)
    second = workflow.handle(command, principal, actor("executor-b", "system"))

    assert isinstance(first, ExecutionIndeterminate)
    assert seed is not None and seed.kind == "AdmissionOutstanding"
    assert isinstance(second, ExecutionInProgress)
    assert len(gateway.calls) == 1


def test_concurrent_execute_has_one_provider_dispatch_and_loser_returns_in_progress() -> None:
    gateway = BlockingGateway()
    workflow, _, _, _, _, principal, approved = prepared_workflow(gateway=gateway)
    command = ExecuteApprovedProposal(approved.projection.proposal_id, 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(workflow.handle, command, principal, actor("executor-a", "system"))
        assert gateway.entered.wait(timeout=5)
        loser = workflow.handle(command, principal, actor("executor-b", "system"))
        gateway.release.set()
        completed = winner.result(timeout=5)

    assert isinstance(completed, ExecutionSucceeded)
    assert loser == ExecutionInProgress(
        proposal_id=approved.projection.proposal_id,
        logical_execution_id=approved.projection.logical_execution_id,
    )
    assert len(gateway.calls) == 1


def test_provider_uncertainty_remains_executing_with_same_identity() -> None:
    workflow, _, store, _, gateway, principal, approved = prepared_workflow(
        gateway=Gateway(ProviderWriteIndeterminate())
    )

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result == ExecutionIndeterminate(
        proposal_id=approved.projection.proposal_id,
        logical_execution_id=approved.projection.logical_execution_id,
    )
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution.lifecycle == "executing"
    assert stored.admission is not None
    assert len(gateway.calls) == 1


def test_post_acquisition_authority_revocation_denies_admission_without_dispatch() -> None:
    workflow, _, store, authorizer, gateway, principal, approved = prepared_workflow()
    original = authorizer.is_authorized
    initial_calls = authorizer.calls

    def revoke_after_first_check(principal, proposal):
        authorized = original(principal, proposal)
        if authorizer.calls == initial_calls + 1:
            authorizer.authorized = False
        return authorized

    authorizer.is_authorized = revoke_after_first_check

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result == ProposalNotExecutable(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        "execution_not_authorized",
    )
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution.lifecycle == "executing"
    assert stored.admission is None
    assert gateway.calls == []


def test_post_acquisition_material_mismatch_is_durably_invalidated() -> None:
    workflow, resolver, store, authorizer, gateway, principal, approved = prepared_workflow()
    original = authorizer.is_authorized
    initial_calls = authorizer.calls

    def mutate_after_first_check(principal, proposal):
        authorized = original(principal, proposal)
        if authorizer.calls == initial_calls + 1:
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
        return authorized

    authorizer.is_authorized = mutate_after_first_check

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result == ProposalNotExecutable(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        "capability_digest_mismatch",
    )
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None
    assert stored.execution_stale_reason == "capability_digest_mismatch"
    assert stored.audit[-1].event_type == "approval_invalidated"
    assert stored.audit[-1].payload["approval_validity"] == "invalidated"
    assert stored.admission is None
    assert gateway.calls == []


COMPATIBILITY_MUTATIONS = (
    ("capability_id", "other", "capability_identity_mismatch"),
    ("capability_version", "m4.3", "capability_version_mismatch"),
    ("capability_digest", "sha256:" + "9" * 64, "capability_digest_mismatch"),
    ("binding_id", "binding-b", "binding_identity_mismatch"),
    ("binding_version", "v2", "binding_version_mismatch"),
    ("binding_digest", "sha256:" + "8" * 64, "binding_digest_mismatch"),
    ("policy_id", "policy-b", "policy_identity_mismatch"),
    ("policy_version", "v2", "policy_version_mismatch"),
    ("policy_digest", "sha256:" + "7" * 64, "policy_digest_mismatch"),
)


def _mutate_context(context, field_name, value):
    if field_name == "policy_id":
        policy = PolicyProvenance.from_semantics(
            value, context.policy.policy_version, context.policy.snapshot
        )
        return replace(context, policy=policy)
    if field_name == "policy_version":
        policy = PolicyProvenance.from_semantics(
            context.policy.policy_id, value, context.policy.snapshot
        )
        return replace(context, policy=policy)
    if field_name == "policy_digest":
        snapshot = dict(context.policy.snapshot)
        snapshot["execution_authority_required"] = False
        policy = PolicyProvenance.from_semantics(
            context.policy.policy_id, context.policy.policy_version, snapshot
        )
        return replace(context, policy=policy)
    return replace(context, **{field_name: value})


@pytest.mark.parametrize(("field_name", "value", "reason"), COMPATIBILITY_MUTATIONS)
def test_pre_acquisition_material_mismatch_is_closed_and_never_acquires(
    field_name, value, reason
) -> None:
    workflow, resolver, store, _, gateway, principal, approved = prepared_workflow()
    resolver.context = _mutate_context(resolver.context, field_name, value)

    with pytest.raises(KnoraError) as error:
        workflow.handle(
            ExecuteApprovedProposal(approved.projection.proposal_id, 1),
            principal,
            actor("executor-a", "system"),
        )

    assert error.value.code == "TOOL_PROPOSAL_STALE"
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None
    assert stored.state == "approved"
    assert stored.execution is None
    assert stored.execution_stale_reason == reason
    assert stored.audit[-1].event_type == "approval_invalidated"
    assert gateway.calls == []


@pytest.mark.parametrize(("field_name", "value", "reason"), COMPATIBILITY_MUTATIONS)
def test_post_acquisition_material_mismatch_matrix_has_no_admission_or_dispatch(
    field_name, value, reason
) -> None:
    workflow, resolver, store, authorizer, gateway, principal, approved = prepared_workflow()
    original = authorizer.is_authorized
    initial_calls = authorizer.calls

    def mutate_after_first_check(current_principal, proposal):
        authorized = original(current_principal, proposal)
        if authorizer.calls == initial_calls + 1:
            resolver.context = _mutate_context(resolver.context, field_name, value)
        return authorized

    authorizer.is_authorized = mutate_after_first_check
    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result == ProposalNotExecutable(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        reason,
    )
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution_stale_reason == reason
    assert stored.admission is None
    assert gateway.calls == []


class SecondCheckResourceDenial(ExecutionResourceAuthorizer):
    def __init__(self, code: str) -> None:
        self.code = code
        self.calls = 0

    def authorize_current(self, principal, proposal, current, *, at_time):
        self.calls += 1
        if self.calls == 2:
            raise KnoraError(self.code)
        return super().authorize_current(principal, proposal, current, at_time=at_time)


@pytest.mark.parametrize(
    ("error_code", "private_reason"),
    [
        ("INVALID_TOOL_RESOURCE_REFERENCE", "invalid_tool_resource_reference"),
        ("TOOL_RESOURCE_ACCESS_DENIED", "resource_access_denied"),
    ],
)
def test_post_acquisition_reference_denial_is_closed_without_invalidating_approval(
    error_code, private_reason
) -> None:
    resource_authorizer = SecondCheckResourceDenial(error_code)
    workflow, _, store, _, gateway, principal, approved = prepared_workflow()
    workflow._executor._resource_authorizer = resource_authorizer
    workflow._executor._admission_builder._resource_authorizer = resource_authorizer

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result.reason_code == private_reason
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution_stale_reason is None
    assert stored.admission is None
    assert stored.audit[-1].event_type == "execution_acquired"
    assert gateway.calls == []


@pytest.mark.parametrize(
    "rejection_code",
    ["target_not_found", "validation_rejected", "policy_rejected"],
)
def test_every_closed_provider_rejection_finalizes_exactly_once(rejection_code) -> None:
    workflow, _, store, _, gateway, principal, approved = prepared_workflow(
        gateway=Gateway(ProviderWriteFailed(rejection_code))
    )

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert result == ExecutionFailed(
        approved.projection.proposal_id,
        approved.projection.logical_execution_id,
        rejection_code,
    )
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution.lifecycle == "failed"
    assert stored.execution.rejection_code == rejection_code
    assert len(gateway.calls) == 1


@pytest.mark.parametrize("outcome, rejection_code", [
    (ProviderRequestRejected(), "provider_request_rejected"),
    (ProviderScopeDenied(), "provider_scope_denied"),
])
def test_definitive_provider_denials_finalize_without_indeterminate_retry_state(
    outcome, rejection_code: str
) -> None:
    workflow, _, store, _, gateway, principal, approved = prepared_workflow(
        gateway=Gateway(outcome)
    )

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert isinstance(result, ExecutionFailed)
    assert result.rejection_code == rejection_code
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution.lifecycle == "failed"
    assert stored.execution.observations[-1].observation_type == rejection_code


def test_admission_binds_server_fingerprint_and_survives_later_authority_mutation() -> None:
    gateway = BlockingGateway()
    workflow, resolver, store, authorizer, _, principal, approved = prepared_workflow(
        gateway=gateway
    )

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            workflow.handle,
            ExecuteApprovedProposal(approved.projection.proposal_id, 1),
            principal,
            actor("executor-a", "system"),
        )
        assert gateway.entered.wait(timeout=5)
        stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
        assert stored is not None and stored.execution is not None and stored.admission is not None
        claims = workflow._executor._admission_builder._signer.verify(gateway.calls[0])
        assert stored.request_fingerprint == stored.execution.acquisition.request_fingerprint
        assert stored.request_fingerprint == stored.admission.request_fingerprint
        assert stored.request_fingerprint == claims["request_fingerprint"]
        authorizer.authorized = False
        resolver.context = replace(resolver.context, capability_digest="sha256:" + "6" * 64)
        gateway.release.set()
        result = pending.result(timeout=5)

    assert isinstance(result, ExecutionSucceeded)
    assert len(gateway.calls) == 1


def test_provider_fingerprint_conflict_stays_non_terminal() -> None:
    workflow, _, store, _, gateway, principal, approved = prepared_workflow(
        gateway=Gateway(ProviderIdempotencyConflict())
    )

    result = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )

    assert isinstance(result, ExecutionInProgress)
    assert result.reason_code == "provider_idempotency_conflict"
    stored = store.read_proposal("workspace-a", approved.projection.proposal_id)
    assert stored is not None and stored.execution is not None
    assert stored.execution.lifecycle == "executing"
    assert stored.execution.observations[-1].observation_type == "provider_idempotency_conflict"
    assert len(gateway.calls) == 1
