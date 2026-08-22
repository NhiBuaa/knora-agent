from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError

REJECT_REASONS = {"not_approved", "incorrect_target", "incorrect_parameters", "other"}
ACTOR_KINDS = {"human", "model", "system"}


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _normalize_text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise KnoraError("TOOL_REQUEST_INVALID")
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.strip()
    if not normalized or "\x00" in normalized or len(normalized) > maximum:
        raise KnoraError("TOOL_REQUEST_INVALID")
    return normalized


@dataclass(frozen=True, slots=True)
class ActorContext:
    actor_id: str
    actor_kind: str
    authorized: bool = True
    separation_of_duties: bool = False
    authority_id: str | None = None

    def __post_init__(self) -> None:
        if not self.actor_id or self.actor_kind not in ACTOR_KINDS:
            raise ValueError("invalid trusted actor context")


@dataclass(frozen=True, slots=True)
class PolicyProvenance:
    policy_id: str = "m4-human-approval-policy"
    policy_version: str = "v1"
    policy_digest: str = "sha256:m4-human-approval-policy-v1"
    snapshot: Mapping[str, Any] = field(
        default_factory=lambda: {
            "approval_actor_kinds": ["human"],
            "separation_of_duties": False,
            "execution_authority_required": True,
        }
    )


@dataclass(frozen=True, slots=True)
class ResolvedCapabilityContext:
    capability_id: str
    capability_version: str
    capability_digest: str
    resource_kind: str
    binding_id: str
    binding_version: str
    binding_digest: str
    policy: PolicyProvenance = field(default_factory=PolicyProvenance)
    expires_at: datetime | None = None


class CapabilityResolver(Protocol):
    def resolve_for_proposal(
        self, workspace_id: str, capability_id: str
    ) -> ResolvedCapabilityContext: ...


@dataclass(frozen=True, slots=True)
class VerifiedProposalTarget:
    reference: str
    reference_digest: str
    workspace_id: str
    capability_id: str
    capability_version: str
    binding_id: str
    binding_version: str
    binding_digest: str
    resource_kind: str


class ProposalTargetVerifier(Protocol):
    def verify_for_proposal(
        self,
        workspace_id: str,
        capability: ResolvedCapabilityContext,
        target_reference: str,
    ) -> VerifiedProposalTarget: ...


class DenyingProposalTargetVerifier:
    def verify_for_proposal(
        self,
        workspace_id: str,
        capability: ResolvedCapabilityContext,
        target_reference: str,
    ) -> VerifiedProposalTarget:
        del workspace_id, capability, target_reference
        raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")


class StaticCapabilityResolver:
    """Small default resolver for the statically registered M4.2 write capability."""

    def __init__(self, context: ResolvedCapabilityContext | None = None) -> None:
        self.context = context or ResolvedCapabilityContext(
            capability_id="create_ticket",
            capability_version="m4.2",
            capability_digest="sha256:create-ticket-v1",
            resource_kind="ticket",
            binding_id="binding-default",
            binding_version="v1",
            binding_digest="sha256:binding-default",
        )

    def resolve_for_proposal(
        self, workspace_id: str, capability_id: str
    ) -> ResolvedCapabilityContext:
        del workspace_id
        if capability_id != self.context.capability_id:
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return self.context


@dataclass(frozen=True, slots=True)
class ProposeWriteAction:
    capability_id: str
    target_reference: str
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class ApproveProposal:
    proposal_id: str
    expected_revision: int


@dataclass(frozen=True, slots=True)
class RejectProposal:
    proposal_id: str
    expected_revision: int
    reason_code: str


@dataclass(frozen=True, slots=True)
class ExecuteApprovedProposal:
    proposal_id: str
    expected_revision: int


@dataclass(frozen=True, slots=True)
class ReconcileExecution:
    proposal_id: str
    expected_lease_generation: int


TypedWriteCommand = (
    ProposeWriteAction
    | ApproveProposal
    | RejectProposal
    | ExecuteApprovedProposal
    | ReconcileExecution
)


@dataclass(frozen=True, slots=True)
class AuditProjection:
    sequence: int
    event_type: str
    actor_id: str
    actor_kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolProposalProjection:
    proposal_id: str
    workspace_id: str
    state: str
    revision: int
    action: str
    target_reference: str
    parameters: Mapping[str, str]
    caller_principal_id: str
    caller_key_id: str
    proposal_actor_id: str
    proposal_actor_kind: str
    approval_actor_id: str | None
    approval_actor_kind: str | None
    capability_id: str
    capability_version: str
    capability_digest: str
    binding_id: str
    binding_version: str
    binding_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str
    parameters_digest: str
    target_reference_digest: str
    logical_execution_id: str
    expires_at: datetime
    executable: bool
    stale: bool
    non_executable_reason: str | None
    audit: tuple[AuditProjection, ...] = ()


ProposalProjection = ToolProposalProjection


@dataclass(frozen=True, slots=True)
class _StoredProposal:
    proposal_id: str
    workspace_id: str
    state: str
    revision: int
    capability_id: str
    capability_version: str
    capability_digest: str
    binding_id: str
    binding_version: str
    binding_digest: str
    policy_id: str
    policy_version: str
    policy_digest: str
    policy_snapshot: Mapping[str, Any]
    target_reference: str
    target_reference_digest: str
    resource_kind: str
    parameters: Mapping[str, str]
    parameters_digest: str
    request_fingerprint: str
    caller_principal_id: str
    caller_key_id: str
    proposal_actor_id: str
    proposal_actor_kind: str
    logical_execution_id: str
    expires_at: datetime
    decision_actor_id: str | None = None
    decision_actor_kind: str | None = None
    decision_reason: str | None = None
    audit: tuple[AuditProjection, ...] = ()


@dataclass(frozen=True, slots=True)
class _DecisionResult:
    applied: bool
    proposal: _StoredProposal


class ToolActionStore(Protocol):
    def create_proposal(self, proposal: _StoredProposal) -> _StoredProposal: ...

    def read_proposal(self, workspace_id: str, proposal_id: str) -> _StoredProposal | None: ...

    def decide_proposal(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        decision: str,
        actor: ActorContext,
        reason_code: str | None,
    ) -> _DecisionResult: ...


class InMemoryToolActionStore:
    def __init__(self) -> None:
        self._proposals: dict[str, _StoredProposal] = {}

    def create_proposal(self, proposal: _StoredProposal) -> _StoredProposal:
        if not proposal.audit:
            proposal = replace(
                proposal,
                audit=(
                    AuditProjection(
                        sequence=1,
                        event_type="proposed",
                        actor_id=proposal.proposal_actor_id,
                        actor_kind=proposal.proposal_actor_kind,
                        payload={"caller_principal_id": proposal.caller_principal_id},
                    ),
                ),
            )
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def read_proposal(self, workspace_id: str, proposal_id: str) -> _StoredProposal | None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.workspace_id != workspace_id:
            return None
        return proposal

    def decide_proposal(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        decision: str,
        actor: ActorContext,
        reason_code: str | None,
    ) -> _DecisionResult:
        proposal = self.read_proposal(workspace_id, proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        if proposal.state != "proposed" or proposal.revision != expected_revision:
            return _DecisionResult(False, proposal)
        decided = replace(
            proposal,
            state=decision,
            revision=proposal.revision + 1,
            decision_actor_id=actor.actor_id,
            decision_actor_kind=actor.actor_kind,
            decision_reason=reason_code,
            audit=proposal.audit
            + (
                AuditProjection(
                    sequence=len(proposal.audit) + 1,
                    event_type=decision,
                    actor_id=actor.actor_id,
                    actor_kind=actor.actor_kind,
                    payload={"reason_code": reason_code, "revision": proposal.revision + 1},
                ),
            ),
        )
        self._proposals[proposal_id] = decided
        return _DecisionResult(True, decided)


class HumanApprovalAuthorizer:
    def authorize(self, actor_context: ActorContext, proposal: _StoredProposal) -> ActorContext:
        if (
            not actor_context.authorized
            or actor_context.actor_kind != "human"
            or actor_context.actor_kind not in {"human"}
            or (
                bool(proposal.policy_snapshot.get("separation_of_duties"))
                and actor_context.actor_id == proposal.proposal_actor_id
            )
        ):
            raise KnoraError("TOOL_APPROVAL_FORBIDDEN")
        return actor_context


@dataclass(frozen=True, slots=True)
class ProposalCreated:
    projection: ToolProposalProjection


@dataclass(frozen=True, slots=True)
class ProposalRejected:
    projection: ToolProposalProjection


@dataclass(frozen=True, slots=True)
class ProposalApproved:
    projection: ToolProposalProjection


@dataclass(frozen=True, slots=True)
class AlreadyDecided:
    projection: ToolProposalProjection


class WriteProposalWorkflow:
    def __init__(
        self,
        *,
        capability_resolver: CapabilityResolver,
        store: ToolActionStore,
        target_verifier: ProposalTargetVerifier | None = None,
        approval_authorizer: HumanApprovalAuthorizer | None = None,
        clock: callable | None = None,
        execution_authorizer: callable | None = None,
    ) -> None:
        self._resolver = capability_resolver
        self._store = store
        self._target_verifier = target_verifier or DenyingProposalTargetVerifier()
        self._approval_authorizer = approval_authorizer or HumanApprovalAuthorizer()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._execution_authorizer = execution_authorizer or (lambda _principal, _proposal: True)

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
            return self._decide(command, principal, actor_context, "approved", None)
        if isinstance(command, RejectProposal):
            if command.reason_code not in REJECT_REASONS:
                raise KnoraError("TOOL_REQUEST_INVALID")
            return self._decide(command, principal, actor_context, "rejected", command.reason_code)
        if isinstance(command, (ExecuteApprovedProposal, ReconcileExecution)):
            raise KnoraError("TOOL_REQUEST_INVALID")
        raise KnoraError("TOOL_REQUEST_INVALID")

    def _propose(
        self, command: ProposeWriteAction, principal: WorkspacePrincipal, actor: ActorContext
    ) -> ProposalCreated:
        if actor is None or not actor.actor_id:
            raise KnoraError("TOOL_REQUEST_INVALID")
        title = _normalize_text(command.title, "title", 200)
        description = _normalize_text(command.description, "description", 4000)
        target = _normalize_text(command.target_reference, "target_reference", 4096)
        context = self._resolver.resolve_for_proposal(principal.workspace_id, command.capability_id)
        if context.capability_id != command.capability_id:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        verified_target = self._target_verifier.verify_for_proposal(
            principal.workspace_id, context, target
        )
        if (
            verified_target.workspace_id != principal.workspace_id
            or verified_target.capability_id != context.capability_id
            or verified_target.capability_version != context.capability_version
            or verified_target.binding_id != context.binding_id
            or verified_target.binding_version != context.binding_version
            or verified_target.binding_digest != context.binding_digest
            or verified_target.resource_kind != context.resource_kind
        ):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        now = self._clock()
        expires_at = context.expires_at or now + timedelta(hours=1)
        parameters = {"title": title, "description": description}
        parameters_digest = _digest(parameters)
        target = verified_target.reference
        target_digest = verified_target.reference_digest
        fingerprint = _digest(
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
                "policy": {
                    "id": context.policy.policy_id,
                    "version": context.policy.policy_version,
                    "digest": context.policy.policy_digest,
                },
                "target_reference_digest": target_digest,
                "parameters": parameters,
            }
        )
        proposal = _StoredProposal(
            proposal_id=str(uuid4()), workspace_id=principal.workspace_id, state="proposed",
            revision=0, capability_id=context.capability_id,
            capability_version=context.capability_version,
            capability_digest=context.capability_digest,
            binding_id=context.binding_id, binding_version=context.binding_version,
            binding_digest=context.binding_digest, policy_id=context.policy.policy_id,
            policy_version=context.policy.policy_version,
            policy_digest=context.policy.policy_digest,
            policy_snapshot=dict(context.policy.snapshot), target_reference=target,
            target_reference_digest=target_digest, resource_kind=context.resource_kind,
            parameters=parameters, parameters_digest=parameters_digest,
            request_fingerprint=fingerprint, caller_principal_id=principal.key_id,
            caller_key_id=principal.key_id, proposal_actor_id=actor.actor_id,
            proposal_actor_kind=actor.actor_kind, logical_execution_id=str(uuid4()),
            expires_at=expires_at,
        )
        stored = self._store.create_proposal(proposal)
        return ProposalCreated(self._project(stored, principal))

    def _decide(
        self,
        command: ApproveProposal | RejectProposal,
        principal: WorkspacePrincipal,
        actor: ActorContext,
        decision: str,
        reason: str | None,
    ) -> ProposalApproved | ProposalRejected | AlreadyDecided:
        proposal = self._store.read_proposal(principal.workspace_id, command.proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        approver = self._approval_authorizer.authorize(actor, proposal)
        result = self._store.decide_proposal(
            principal.workspace_id, command.proposal_id, command.expected_revision,
            decision, approver, reason,
        )
        if not result.applied:
            projection = self._project(result.proposal, principal)
            if result.proposal.state != "proposed":
                return AlreadyDecided(projection)
            raise KnoraError("TOOL_PROPOSAL_REVISION_CONFLICT")
        projection = self._project(result.proposal, principal)
        if decision == "approved":
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
        current = self._resolver.resolve_for_proposal(
            proposal.workspace_id, proposal.capability_id
        )
        stale = any(
            (
                current.capability_version != proposal.capability_version,
                current.capability_digest != proposal.capability_digest,
                current.binding_id != proposal.binding_id,
                current.binding_version != proposal.binding_version,
                current.binding_digest != proposal.binding_digest,
                current.policy.policy_id != proposal.policy_id,
                current.policy.policy_version != proposal.policy_version,
                current.policy.policy_digest != proposal.policy_digest,
            )
        )
        reason = None
        executable = False
        if proposal.state == "approved" and not stale:
            if proposal.expires_at <= self._clock():
                reason = "expired"
            elif not self._execution_authorizer(principal, proposal):
                reason = "execution_not_authorized"
            else:
                executable = True
        elif stale:
            reason = "material_compatibility_mismatch"
        elif proposal.state != "approved":
            reason = "not_approved"
        return ToolProposalProjection(
            proposal_id=proposal.proposal_id, workspace_id=proposal.workspace_id,
            state=proposal.state, revision=proposal.revision, action="create_ticket",
            target_reference=proposal.target_reference, parameters=dict(proposal.parameters),
            caller_principal_id=proposal.caller_principal_id, caller_key_id=proposal.caller_key_id,
            proposal_actor_id=proposal.proposal_actor_id,
            proposal_actor_kind=proposal.proposal_actor_kind,
            approval_actor_id=proposal.decision_actor_id,
            approval_actor_kind=proposal.decision_actor_kind,
            capability_id=proposal.capability_id, capability_version=proposal.capability_version,
            capability_digest=proposal.capability_digest, binding_id=proposal.binding_id,
            binding_version=proposal.binding_version, binding_digest=proposal.binding_digest,
            policy_id=proposal.policy_id, policy_version=proposal.policy_version,
            policy_digest=proposal.policy_digest, parameters_digest=proposal.parameters_digest,
            target_reference_digest=proposal.target_reference_digest,
            logical_execution_id=proposal.logical_execution_id, expires_at=proposal.expires_at,
            executable=executable, stale=stale, non_executable_reason=reason, audit=proposal.audit,
        )
