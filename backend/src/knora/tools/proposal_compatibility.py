from __future__ import annotations

from enum import StrEnum

from knora.tools.proposal_store import _StoredProposal
from knora.tools.proposal_types import ResolvedCapabilityContext


class CompatibilityReason(StrEnum):
    CAPABILITY_IDENTITY_MISMATCH = "capability_identity_mismatch"
    CAPABILITY_VERSION_MISMATCH = "capability_version_mismatch"
    CAPABILITY_DIGEST_MISMATCH = "capability_digest_mismatch"
    BINDING_IDENTITY_MISMATCH = "binding_identity_mismatch"
    BINDING_VERSION_MISMATCH = "binding_version_mismatch"
    BINDING_DIGEST_MISMATCH = "binding_digest_mismatch"
    POLICY_IDENTITY_MISMATCH = "policy_identity_mismatch"
    POLICY_VERSION_MISMATCH = "policy_version_mismatch"
    POLICY_DIGEST_MISMATCH = "policy_digest_mismatch"


class CompatibilityCheckerV1:
    def check(
        self,
        approved: _StoredProposal,
        current: ResolvedCapabilityContext,
    ) -> CompatibilityReason | None:
        comparisons = (
            (
                approved.capability_id,
                current.capability_id,
                CompatibilityReason.CAPABILITY_IDENTITY_MISMATCH,
            ),
            (
                approved.capability_version,
                current.capability_version,
                CompatibilityReason.CAPABILITY_VERSION_MISMATCH,
            ),
            (
                approved.capability_digest,
                current.capability_digest,
                CompatibilityReason.CAPABILITY_DIGEST_MISMATCH,
            ),
            (
                approved.binding_id,
                current.binding_id,
                CompatibilityReason.BINDING_IDENTITY_MISMATCH,
            ),
            (
                approved.binding_version,
                current.binding_version,
                CompatibilityReason.BINDING_VERSION_MISMATCH,
            ),
            (
                approved.binding_digest,
                current.binding_digest,
                CompatibilityReason.BINDING_DIGEST_MISMATCH,
            ),
            (
                approved.policy_id,
                current.policy.policy_id,
                CompatibilityReason.POLICY_IDENTITY_MISMATCH,
            ),
            (
                approved.policy_version,
                current.policy.policy_version,
                CompatibilityReason.POLICY_VERSION_MISMATCH,
            ),
            (
                approved.policy_digest,
                current.policy.policy_digest,
                CompatibilityReason.POLICY_DIGEST_MISMATCH,
            ),
        )
        return next(
            (
                reason
                for approved_value, current_value, reason in comparisons
                if approved_value != current_value
            ),
            None,
        )
