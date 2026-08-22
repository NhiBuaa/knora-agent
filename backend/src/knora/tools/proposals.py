from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.proposal_compatibility import (
    CompatibilityCheckerV1,
    CompatibilityReason,
)
from knora.tools.proposal_contracts import canonical_digest_v1
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
    def authorize(self, actor_context: ActorContext, proposal: _StoredProposal) -> ApprovalActor:
        if (
            actor_context.actor_kind != "human"
            or actor_context.approval_authority is None
            or (
                bool(proposal.policy_snapshot.get("separation_of_duties"))
                and actor_context.actor_id == proposal.proposal_actor_id
            )
        ):
            raise KnoraError("TOOL_APPROVAL_FORBIDDEN")
        return ApprovalActor(
            actor_context.actor_id,
            actor_context.actor_kind,
            actor_context.approval_authority,
        )


class ExecutionAuthorizer(Protocol):
    def is_authorized(
        self, principal: WorkspacePrincipal, proposal: _StoredProposal
    ) -> bool: ...


class DenyingExecutionAuthorizer:
    def is_authorized(
        self, principal: WorkspacePrincipal, proposal: _StoredProposal
    ) -> bool:
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
    ) -> None:
        self._resolver = capability_resolver
        self._store = store
        self._target_verifier = target_verifier or DenyingProposalTargetVerifier()
        self._approval_authorizer = approval_authorizer or HumanApprovalAuthorizer()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._execution_authorizer = execution_authorizer or DenyingExecutionAuthorizer()
        self._compatibility_checker = compatibility_checker or CompatibilityCheckerV1()

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
        if isinstance(command, (ExecuteApprovedProposal, ReconcileExecution)):
            raise KnoraError("TOOL_REQUEST_INVALID")
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
        context = self._resolver.resolve_for_proposal(
            principal.workspace_id, command.capability_id
        )
        if context.capability_id != command.capability_id:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        verified_target = self._target_verifier.verify_for_proposal(
            principal.workspace_id, context, target_reference
        )
        self._require_exact_target(principal, context, verified_target)
        now = self._clock()
        expires_at = context.expires_at or now + timedelta(hours=1)
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
            policy_snapshot=dict(context.policy.snapshot),
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
        proposal = self._store.read_proposal(principal.workspace_id, command.proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        approver = self._approval_authorizer.authorize(actor, proposal)
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
