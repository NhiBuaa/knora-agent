from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from knora.domain.errors import KnoraError
from knora.tools.contracts import (
    canonical_digest_v1,
    freeze_canonical_value,
    require_digest,
)

REJECT_REASONS = {"not_approved", "incorrect_target", "incorrect_parameters", "other"}
ACTOR_KINDS = {"human", "model", "system"}
SAFE_FAILURE_CODES = frozenset(
    {
        "target_not_found",
        "validation_rejected",
        "policy_rejected",
        "provider_request_rejected",
        "provider_scope_denied",
    }
)


def safe_failure_code(value: str | None) -> str | None:
    """Return only a closed, public-safe execution failure identity."""
    return value if value in SAFE_FAILURE_CODES else None


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
                    "proposal_lifetime_seconds": 3600,
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
            "proposal_lifetime_seconds": 3600,
        }
    )

    def __post_init__(self) -> None:
        if not self.policy_id or not self.policy_version:
            raise ValueError("policy identity and version are required")
        require_digest(self.policy_digest, "policy digest")
        frozen_snapshot = freeze_canonical_value(self.snapshot)
        if not isinstance(frozen_snapshot, Mapping):
            raise ValueError("policy snapshot must be a mapping")
        lifetime = frozen_snapshot.get("proposal_lifetime_seconds")
        if not isinstance(lifetime, int) or isinstance(lifetime, bool) or lifetime <= 0:
            raise ValueError("proposal_lifetime_seconds must be a positive integer")
        expected = canonical_digest_v1(
            {
                "policy_id": self.policy_id,
                "policy_version": self.policy_version,
                "snapshot": frozen_snapshot,
            }
        )
        if self.policy_digest != expected:
            raise ValueError("policy digest does not match canonical policy semantics")
        object.__setattr__(self, "snapshot", frozen_snapshot)

    @classmethod
    def from_semantics(
        cls,
        policy_id: str,
        policy_version: str,
        snapshot: Mapping[str, Any],
    ) -> PolicyProvenance:
        frozen_snapshot = freeze_canonical_value(snapshot)
        if not isinstance(frozen_snapshot, Mapping):
            raise ValueError("policy snapshot must be a mapping")
        projection = {
            "policy_id": policy_id,
            "policy_version": policy_version,
            "snapshot": frozen_snapshot,
        }
        return cls(policy_id, policy_version, canonical_digest_v1(projection), frozen_snapshot)


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

    def __post_init__(self) -> None:
        frozen = freeze_canonical_value(self.payload)
        if not isinstance(frozen, Mapping):
            raise ValueError("audit payload must be a mapping")
        object.__setattr__(self, "payload", frozen)


@dataclass(frozen=True, slots=True)
class ExecutionObservationProjection:
    sequence: int
    observation_type: str
    failure_code: str | None
    external_resource_reference: str | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ExecutionProjection:
    lifecycle: str
    revision: int
    generation: int
    lease_started_at: datetime
    lease_expires_at: datetime
    observations: tuple[ExecutionObservationProjection, ...]
    failure_code: str | None
    external_resource_reference: str | None
    finalized_at: datetime | None


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
    execution: ExecutionProjection | None = None

    def __post_init__(self) -> None:
        frozen = freeze_canonical_value(self.parameters)
        if not isinstance(frozen, Mapping):
            raise ValueError("proposal parameters must be a mapping")
        object.__setattr__(self, "parameters", frozen)
        object.__setattr__(self, "audit", tuple(self.audit))


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
