from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Protocol

from knora.domain.errors import KnoraError
from knora.tools.proposal_types import (
    ApprovalActor,
    AuditProjection,
    ProposalDecision,
)


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
    target_reference_id: str
    target_resource_identity_digest: str
    target_resource_claims_digest: str
    resource_kind: str
    parameters: Mapping[str, str]
    parameters_digest: str
    request_fingerprint: str
    caller_principal_id: str
    caller_key_id: str
    proposal_actor_id: str
    proposal_actor_kind: str
    proposal_actor_authority_id: str
    proposal_actor_authority_version: str
    proposal_actor_authority_digest: str
    logical_execution_id: str
    created_at: datetime
    expires_at: datetime
    decision_at: datetime | None = None
    decision_actor_id: str | None = None
    decision_actor_kind: str | None = None
    decision_authority_id: str | None = None
    decision_authority_version: str | None = None
    decision_authority_digest: str | None = None
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
        decision: ProposalDecision,
        actor: ApprovalActor,
        reason_code: str | None,
        decided_at: datetime,
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
                        payload={
                            "caller_principal_id": proposal.caller_principal_id,
                            "authority_id": proposal.proposal_actor_authority_id,
                            "authority_version": proposal.proposal_actor_authority_version,
                            "authority_digest": proposal.proposal_actor_authority_digest,
                        },
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
        decision: ProposalDecision,
        actor: ApprovalActor,
        reason_code: str | None,
        decided_at: datetime,
    ) -> _DecisionResult:
        proposal = self.read_proposal(workspace_id, proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        if proposal.state != "proposed" or proposal.revision != expected_revision:
            return _DecisionResult(False, proposal)
        decided = replace(
            proposal,
            state=decision.value,
            revision=proposal.revision + 1,
            decision_actor_id=actor.actor_id,
            decision_actor_kind=actor.actor_kind,
            decision_authority_id=actor.authority.authority_id,
            decision_authority_version=actor.authority.authority_version,
            decision_authority_digest=actor.authority.authority_digest,
            decision_reason=reason_code,
            decision_at=decided_at,
            audit=proposal.audit
            + (
                AuditProjection(
                    sequence=len(proposal.audit) + 1,
                    event_type=decision.value,
                    actor_id=actor.actor_id,
                    actor_kind=actor.actor_kind,
                    payload={
                        "reason_code": reason_code,
                        "revision": proposal.revision + 1,
                        "authority_id": actor.authority.authority_id,
                        "authority_version": actor.authority.authority_version,
                        "authority_digest": actor.authority.authority_digest,
                    },
                ),
            ),
        )
        self._proposals[proposal_id] = decided
        return _DecisionResult(True, decided)
