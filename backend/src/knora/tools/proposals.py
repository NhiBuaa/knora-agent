from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.contracts import canonical_digest_v1
from knora.tools.dispatch_envelope import HmacDispatchEnvelopeSigner
from knora.tools.execution import (
    ApprovedProposalExecutor,
    ExecutionAuthorizer,
    ExecutionResourceAuthorizer,
    ReconciliationExecutor,
)
from knora.tools.execution_admission import ObservationReferenceResolver
from knora.tools.execution_types import ExecutionResult
from knora.tools.gateway import SupportToolGateway
from knora.tools.proposal_compatibility import (
    CompatibilityCheckerV1,
    CompatibilityReason,
)
from knora.tools.proposal_store import ToolActionStore, _StoredProposal
from knora.tools.proposal_types import (
    REJECT_REASONS,
    ActorContext,
    AlreadyDecided,
    ApprovalActor,
    ApproveProposal,
    CapabilityResolver,
    DenyingProposalTargetVerifier,
    ExecuteApprovedProposal,
    ProposalApproved,
    ProposalCreated,
    ProposalDecision,
    ProposalRejected,
    ProposalTargetVerifier,
    ProposeWriteAction,
    ReconcileExecution,
    RejectProposal,
    ResolvedCapabilityContext,
    ToolProposalProjection,
    TypedWriteCommand,
    VerifiedProposalTarget,
    normalize_proposal_text,
)


class HumanApprovalAuthorizer:
    def authorize_current(self, actor_context: ActorContext) -> ApprovalActor:
        """Validate proposal-independent human authority before resource lookup."""
        if (
            actor_context is None
            or actor_context.actor_kind != "human"
            or actor_context.approval_authority is None
        ):
            raise KnoraError("TOOL_APPROVAL_FORBIDDEN")
        return ApprovalActor(
            actor_context.actor_id,
            actor_context.actor_kind,
            actor_context.approval_authority,
        )

    def authorize_proposal(self, approver: ApprovalActor, proposal: _StoredProposal) -> None:
        """Apply proposal-bound policy only after current authority is established."""
        if (
            bool(proposal.policy_snapshot.get("separation_of_duties"))
            and approver.actor_id == proposal.proposal_actor_id
        ):
            raise KnoraError("TOOL_APPROVAL_FORBIDDEN")

    def authorize(self, actor_context: ActorContext, proposal: _StoredProposal) -> ApprovalActor:
        approver = self.authorize_current(actor_context)
        self.authorize_proposal(approver, proposal)
        return approver


class DenyingExecutionAuthorizer:
    def is_authorized(self, principal: WorkspacePrincipal, proposal: _StoredProposal) -> bool:
        del principal, proposal
        return False


class WriteProposalWorkflow:
    def __init__(
        self,
        *,
        capability_resolver: CapabilityResolver,
        store: ToolActionStore,
        target_verifier: ProposalTargetVerifier | None = None,
        approval_authorizer: HumanApprovalAuthorizer | None = None,
        clock: Callable[[], datetime] | None = None,
        execution_authorizer: ExecutionAuthorizer | None = None,
        compatibility_checker: CompatibilityCheckerV1 | None = None,
        execution_resource_authorizer: ExecutionResourceAuthorizer | None = None,
        observation_reference_resolver: ObservationReferenceResolver | None = None,
        gateway: SupportToolGateway | None = None,
        dispatch_signer: HmacDispatchEnvelopeSigner | None = None,
        execution_owner_factory: Callable[[], str] | None = None,
        execution_lease_duration: timedelta = timedelta(minutes=2),
    ) -> None:
        self._resolver = capability_resolver
        self._store = store
        self._target_verifier = target_verifier or DenyingProposalTargetVerifier()
        self._approval_authorizer = approval_authorizer or HumanApprovalAuthorizer()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._execution_authorizer = execution_authorizer or DenyingExecutionAuthorizer()
        self._compatibility_checker = compatibility_checker or CompatibilityCheckerV1()
        self._executor = None
        self._reconciler = None
        if (
            execution_resource_authorizer is not None
            and gateway is not None
            and dispatch_signer is not None
        ):
            self._executor = ApprovedProposalExecutor(
                resolver=capability_resolver,
                store=store,
                execution_authorizer=self._execution_authorizer,
                resource_authorizer=execution_resource_authorizer,
                gateway=gateway,
                signer=dispatch_signer,
                compatibility_checker=self._compatibility_checker,
                clock=self._clock,
                owner_factory=execution_owner_factory,
                lease_duration=execution_lease_duration,
            )
            if observation_reference_resolver is not None:
                self._reconciler = ReconciliationExecutor(
                    resolver=capability_resolver,
                    store=store,
                    execution_authorizer=self._execution_authorizer,
                    resource_authorizer=execution_resource_authorizer,
                    observation_reference_resolver=observation_reference_resolver,
                    gateway=gateway,
                    signer=dispatch_signer,
                    compatibility_checker=self._compatibility_checker,
                    clock=self._clock,
                    owner_factory=execution_owner_factory,
                    lease_duration=execution_lease_duration,
                )

    def handle(
        self,
        command: TypedWriteCommand,
        principal: WorkspacePrincipal,
        actor_context: ActorContext,
    ) -> (
        ProposalCreated
        | ProposalApproved
        | ProposalRejected
        | AlreadyDecided
        | ToolProposalProjection
        | ExecutionResult
    ):
        if principal is None:
            raise KnoraError("UNAUTHENTICATED")
        if isinstance(command, ProposeWriteAction):
            return self._propose(command, principal, actor_context)
        if isinstance(command, ApproveProposal):
            return self._decide(
                command,
                principal,
                actor_context,
                ProposalDecision.APPROVED,
                None,
            )
        if isinstance(command, RejectProposal):
            if command.reason_code not in REJECT_REASONS:
                raise KnoraError("TOOL_REQUEST_INVALID")
            return self._decide(
                command,
                principal,
                actor_context,
                ProposalDecision.REJECTED,
                command.reason_code,
            )
        if isinstance(command, ExecuteApprovedProposal):
            if self._executor is None:
                raise KnoraError("TOOL_EXECUTION_NOT_AUTHORIZED")
            return self._executor.execute(command, principal, actor_context)
        if isinstance(command, ReconcileExecution):
            if self._reconciler is None:
                raise KnoraError("TOOL_REQUEST_INVALID")
            return self._reconciler.reconcile(command, principal, actor_context)
        raise KnoraError("TOOL_REQUEST_INVALID")

    def _propose(
        self,
        command: ProposeWriteAction,
        principal: WorkspacePrincipal,
        actor: ActorContext,
    ) -> ProposalCreated:
        if actor is None or not actor.actor_id or actor.authority is None:
            raise KnoraError("TOOL_REQUEST_INVALID")
        title = normalize_proposal_text(command.title, 200)
        description = normalize_proposal_text(command.description, 10_000)
        target_reference = normalize_proposal_text(command.target_reference, 4096)
        context = self._resolver.resolve_for_proposal(principal.workspace_id, command.capability_id)
        if context.capability_id != command.capability_id:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        verified_target = self._target_verifier.verify_for_proposal(
            principal.workspace_id, context, target_reference
        )
        self._require_exact_target(principal, context, verified_target)
        now = self._clock()
        lifetime_seconds = context.policy.snapshot["proposal_lifetime_seconds"]
        assert isinstance(lifetime_seconds, int) and not isinstance(lifetime_seconds, bool)
        expires_at = now + timedelta(seconds=lifetime_seconds)
        parameters = {"title": title, "description": description}
        parameters_digest = canonical_digest_v1(parameters)
        request_fingerprint = canonical_digest_v1(
            {
                "operation": "create_ticket",
                "capability": {
                    "id": context.capability_id,
                    "version": context.capability_version,
                    "digest": context.capability_digest,
                },
                "binding": {
                    "id": context.binding_id,
                    "version": context.binding_version,
                    "digest": context.binding_digest,
                },
                "target": {
                    "reference_id": verified_target.reference_id,
                    "resource_kind": verified_target.resource_kind,
                    "resource_identity_digest": verified_target.resource_identity_digest,
                    "resource_claims_digest": verified_target.resource_claims_digest,
                },
                "parameters": parameters,
            }
        )
        proposal = _StoredProposal(
            proposal_id=str(uuid4()),
            workspace_id=principal.workspace_id,
            state="proposed",
            revision=0,
            capability_id=context.capability_id,
            capability_version=context.capability_version,
            capability_digest=context.capability_digest,
            binding_id=context.binding_id,
            binding_version=context.binding_version,
            binding_digest=context.binding_digest,
            policy_id=context.policy.policy_id,
            policy_version=context.policy.policy_version,
            policy_digest=context.policy.policy_digest,
            policy_snapshot=context.policy.snapshot,
            target_reference=verified_target.reference,
            target_reference_digest=verified_target.reference_digest,
            target_reference_id=verified_target.reference_id,
            target_resource_identity_digest=verified_target.resource_identity_digest,
            target_resource_claims_digest=verified_target.resource_claims_digest,
            resource_kind=context.resource_kind,
            parameters=parameters,
            parameters_digest=parameters_digest,
            request_fingerprint=request_fingerprint,
            caller_principal_id=principal.key_id,
            caller_key_id=principal.key_id,
            proposal_actor_id=actor.actor_id,
            proposal_actor_kind=actor.actor_kind,
            proposal_actor_authority_id=actor.authority.authority_id,
            proposal_actor_authority_version=actor.authority.authority_version,
            proposal_actor_authority_digest=actor.authority.authority_digest,
            logical_execution_id=str(uuid4()),
            created_at=now,
            expires_at=expires_at,
        )
        stored = self._store.create_proposal(proposal)
        return ProposalCreated(self._project(stored, principal))

    @staticmethod
    def _require_exact_target(
        principal: WorkspacePrincipal,
        context: ResolvedCapabilityContext,
        target: VerifiedProposalTarget,
    ) -> None:
        if (
            target.workspace_id != principal.workspace_id
            or target.capability_id != context.capability_id
            or target.capability_version != context.capability_version
            or target.binding_id != context.binding_id
            or target.binding_version != context.binding_version
            or target.binding_digest != context.binding_digest
            or target.resource_kind != context.resource_kind
        ):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")

    def _decide(
        self,
        command: ApproveProposal | RejectProposal,
        principal: WorkspacePrincipal,
        actor: ActorContext,
        decision: ProposalDecision,
        reason: str | None,
    ) -> ProposalApproved | ProposalRejected | AlreadyDecided:
        approver = self._approval_authorizer.authorize_current(actor)
        proposal = self._store.read_proposal(principal.workspace_id, command.proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        self._approval_authorizer.authorize_proposal(approver, proposal)
        result = self._store.decide_proposal(
            principal.workspace_id,
            command.proposal_id,
            command.expected_revision,
            decision,
            approver,
            reason,
            self._clock(),
        )
        if not result.applied:
            projection = self._project(result.proposal, principal)
            if result.proposal.state != "proposed":
                return AlreadyDecided(projection)
            raise KnoraError("TOOL_PROPOSAL_REVISION_CONFLICT")
        projection = self._project(result.proposal, principal)
        if decision is ProposalDecision.APPROVED:
            return ProposalApproved(projection)
        return ProposalRejected(projection)

    def read(self, proposal_id: str, principal: WorkspacePrincipal) -> ToolProposalProjection:
        if principal is None:
            raise KnoraError("UNAUTHENTICATED")
        proposal = self._store.read_proposal(principal.workspace_id, proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        return self._project(proposal, principal)

    def _project(
        self, proposal: _StoredProposal, principal: WorkspacePrincipal
    ) -> ToolProposalProjection:
        if proposal.execution_stale_reason is not None:
            compatibility_reason = CompatibilityReason(proposal.execution_stale_reason)
        else:
            try:
                current = self._resolver.resolve_for_proposal(
                    proposal.workspace_id, proposal.capability_id
                )
            except (KnoraError, ValueError, LookupError):
                compatibility_reason = CompatibilityReason.CAPABILITY_IDENTITY_MISMATCH
            else:
                compatibility_reason = self._compatibility_checker.check(proposal, current)
        stale = compatibility_reason is not None
        reason = None
        executable = False
        if proposal.state == "approved" and not stale:
            if proposal.expires_at <= self._clock():
                reason = "expired"
            elif not self._execution_authorizer.is_authorized(principal, proposal):
                reason = "execution_not_authorized"
            else:
                executable = True
        elif stale:
            assert compatibility_reason is not None
            reason = compatibility_reason.value
        elif proposal.state != "approved":
            reason = "not_approved"
        return ToolProposalProjection(
            proposal_id=proposal.proposal_id,
            workspace_id=proposal.workspace_id,
            state=proposal.state,
            revision=proposal.revision,
            action="create_ticket",
            target_reference=proposal.target_reference,
            parameters=dict(proposal.parameters),
            caller_principal_id=proposal.caller_principal_id,
            caller_key_id=proposal.caller_key_id,
            proposal_actor_id=proposal.proposal_actor_id,
            proposal_actor_kind=proposal.proposal_actor_kind,
            proposal_actor_authority_id=proposal.proposal_actor_authority_id,
            proposal_actor_authority_version=proposal.proposal_actor_authority_version,
            proposal_actor_authority_digest=proposal.proposal_actor_authority_digest,
            approval_actor_id=proposal.decision_actor_id,
            approval_actor_kind=proposal.decision_actor_kind,
            approval_authority_id=proposal.decision_authority_id,
            approval_authority_version=proposal.decision_authority_version,
            approval_authority_digest=proposal.decision_authority_digest,
            capability_id=proposal.capability_id,
            capability_version=proposal.capability_version,
            capability_digest=proposal.capability_digest,
            binding_id=proposal.binding_id,
            binding_version=proposal.binding_version,
            binding_digest=proposal.binding_digest,
            policy_id=proposal.policy_id,
            policy_version=proposal.policy_version,
            policy_digest=proposal.policy_digest,
            parameters_digest=proposal.parameters_digest,
            target_reference_digest=proposal.target_reference_digest,
            target_reference_id=proposal.target_reference_id,
            target_resource_identity_digest=proposal.target_resource_identity_digest,
            target_resource_claims_digest=proposal.target_resource_claims_digest,
            logical_execution_id=proposal.logical_execution_id,
            created_at=proposal.created_at,
            expires_at=proposal.expires_at,
            decision_at=proposal.decision_at,
            executable=executable,
            stale=stale,
            non_executable_reason=reason,
            audit=proposal.audit,
        )
