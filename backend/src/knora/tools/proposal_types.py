from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from knora.domain.errors import KnoraError
from knora.tools.proposal_contracts import canonical_digest_v1, require_digest

REJECT_REASONS = {"not_approved", "incorrect_target", "incorrect_parameters", "other"}
ACTOR_KINDS = {"human", "model", "system"}


class ProposalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


def normalize_proposal_text(value: object, maximum: int) -> str:
    if not isinstance(value, str):
        raise KnoraError("TOOL_REQUEST_INVALID")
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    if (
        not normalized
        or normalized != normalized.strip()
        or "\x00" in normalized
        or any(0xD800 <= ord(character) <= 0xDFFF for character in normalized)
        or len(normalized) > maximum
    ):
        raise KnoraError("TOOL_REQUEST_INVALID")
    return normalized


@dataclass(frozen=True, slots=True)
class AuthorityProvenance:
    authority_id: str
    authority_version: str
    authority_digest: str

    def __post_init__(self) -> None:
        if not self.authority_id or not self.authority_version:
            raise ValueError("authority identity and version are required")
        require_digest(self.authority_digest, "authority digest")

    @classmethod
    def from_semantics(
        cls, authority_id: str, authority_version: str, semantics: Mapping[str, Any]
    ) -> AuthorityProvenance:
        return cls(
            authority_id,
            authority_version,
            canonical_digest_v1(
                {
                    "authority_id": authority_id,
                    "authority_version": authority_version,
                    "semantics": semantics,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class ActorContext:
    actor_id: str
    actor_kind: str
    authority: AuthorityProvenance | None = None
    approval_authority: AuthorityProvenance | None = None

    def __post_init__(self) -> None:
        if not self.actor_id or self.actor_kind not in ACTOR_KINDS:
            raise ValueError("invalid trusted actor context")


@dataclass(frozen=True, slots=True)
class ApprovalActor:
    actor_id: str
    actor_kind: str
    authority: AuthorityProvenance


@dataclass(frozen=True, slots=True)
class PolicyProvenance:
    policy_id: str = "m4-human-approval-policy"
    policy_version: str = "v1"
    policy_digest: str = field(
        default_factory=lambda: canonical_digest_v1(
            {
                "policy_id": "m4-human-approval-policy",
                "policy_version": "v1",
                "snapshot": {
                    "approval_actor_kinds": ["human"],
                    "execution_authority_required": True,
                    "separation_of_duties": False,
                },
            }
        )
    )
    snapshot: Mapping[str, Any] = field(
        default_factory=lambda: {
            "approval_actor_kinds": ["human"],
            "separation_of_duties": False,
            "execution_authority_required": True,
        }
    )

    def __post_init__(self) -> None:
        if not self.policy_id or not self.policy_version:
            raise ValueError("policy identity and version are required")
        require_digest(self.policy_digest, "policy digest")
        expected = canonical_digest_v1(
            {
                "policy_id": self.policy_id,
                "policy_version": self.policy_version,
                "snapshot": self.snapshot,
            }
        )
        if self.policy_digest != expected:
            raise ValueError("policy digest does not match canonical policy semantics")

    @classmethod
    def from_semantics(
        cls,
        policy_id: str,
        policy_version: str,
        snapshot: Mapping[str, Any],
    ) -> PolicyProvenance:
        projection = {
            "policy_id": policy_id,
            "policy_version": policy_version,
            "snapshot": snapshot,
        }
        return cls(policy_id, policy_version, canonical_digest_v1(projection), dict(snapshot))


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

    def __post_init__(self) -> None:
        for value in (
            self.capability_id,
            self.capability_version,
            self.resource_kind,
            self.binding_id,
            self.binding_version,
        ):
            if not value:
                raise ValueError("resolved capability fields are required")
        require_digest(self.capability_digest, "capability digest")
        require_digest(self.binding_digest, "binding digest")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("proposal expiry must be timezone-aware")


class CapabilityResolver(Protocol):
    def resolve_for_proposal(
        self, workspace_id: str, capability_id: str
    ) -> ResolvedCapabilityContext: ...


@dataclass(frozen=True, slots=True)
class VerifiedProposalTarget:
    reference: str
    reference_digest: str
    reference_id: str
    workspace_id: str
    capability_id: str
    capability_version: str
    binding_id: str
    binding_version: str
    binding_digest: str
    resource_kind: str
    resource_identity_digest: str
    resource_claims_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.reference,
            self.reference_id,
            self.workspace_id,
            self.capability_id,
            self.capability_version,
            self.binding_id,
            self.binding_version,
            self.resource_kind,
        ):
            if not value:
                raise ValueError("verified target fields are required")
        require_digest(self.reference_digest, "target reference digest")
        require_digest(self.binding_digest, "target binding digest")
        require_digest(self.resource_identity_digest, "target resource identity digest")
        require_digest(self.resource_claims_digest, "target resource claims digest")


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
    """Static resolver whose exact trusted context is supplied by composition."""

    def __init__(self, context: ResolvedCapabilityContext | None = None) -> None:
        if context is None:
            raise ValueError("static proposal resolver requires explicit trusted context")
        self.context = context

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
    proposal_actor_authority_id: str
    proposal_actor_authority_version: str
    proposal_actor_authority_digest: str
    approval_actor_id: str | None
    approval_actor_kind: str | None
    approval_authority_id: str | None
    approval_authority_version: str | None
    approval_authority_digest: str | None
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
    target_reference_id: str
    target_resource_identity_digest: str
    target_resource_claims_digest: str
    logical_execution_id: str
    created_at: datetime
    expires_at: datetime
    decision_at: datetime | None
    executable: bool
    stale: bool
    non_executable_reason: str | None
    audit: tuple[AuditProjection, ...] = ()


ProposalProjection = ToolProposalProjection


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
