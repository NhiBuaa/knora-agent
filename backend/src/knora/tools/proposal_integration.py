"""Composition adapters joining accepted M4.1 seams to the proposal workflow."""

from __future__ import annotations

from collections.abc import Mapping

from knora.domain.errors import KnoraError
from knora.tools.capabilities import (
    CapabilityRegistry,
    ExternalScopeBinding,
    WorkspaceResourceAuthorizer,
)
from knora.tools.contracts import canonical_digest_v1
from knora.tools.proposal_types import (
    PolicyProvenance,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
)
from knora.tools.references import ReferenceVerifier


class RegistryCapabilityResolver:
    """Resolve proposal capability and binding from the static typed registry."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        bindings: Mapping[str, ExternalScopeBinding],
        policy: PolicyProvenance,
    ) -> None:
        self._registry = registry
        self._binding_authorizer = WorkspaceResourceAuthorizer(bindings=bindings)
        self._policy = policy

    def resolve_for_proposal(
        self, workspace_id: str, capability_id: str
    ) -> ResolvedCapabilityContext:
        descriptor = self._registry.resolve(capability_id)
        if descriptor.operation != "write":
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        binding = self._binding_authorizer.resolve_binding(workspace_id, descriptor)
        return ResolvedCapabilityContext(
            capability_id=descriptor.capability_id,
            capability_version=descriptor.version,
            capability_digest=descriptor.digest,
            resource_kind=descriptor.resource_kind,
            binding_id=binding.binding_id,
            binding_version=binding.version,
            binding_digest=binding.digest,
            policy=self._policy,
        )


class ReferenceProposalTargetVerifier:
    """Adapt integrity-protected M4.1 references to proposal target claims."""

    def __init__(self, verifier: ReferenceVerifier) -> None:
        self._verifier = verifier

    def verify_for_proposal(
        self,
        workspace_id: str,
        capability: ResolvedCapabilityContext,
        target_reference: str,
    ) -> VerifiedProposalTarget:
        del workspace_id, capability
        try:
            verified = self._verifier.verify(target_reference)
        except KnoraError as error:
            if error.code == "INVALID_TOOL_RESOURCE_REFERENCE":
                raise
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED") from None
        except (TypeError, ValueError):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED") from None
        return VerifiedProposalTarget(
            reference=target_reference,
            reference_digest=canonical_digest_v1(target_reference),
            reference_id=verified.reference_id,
            workspace_id=verified.workspace_id,
            capability_id=verified.capability_id,
            capability_version=verified.capability_version,
            binding_id=verified.binding_id,
            binding_version=verified.binding_version,
            binding_digest=verified.binding_digest,
            resource_kind=verified.resource_kind,
            resource_identity_digest=verified.resource_identity_digest,
            resource_claims_digest=verified.resource_claims_digest,
        )
