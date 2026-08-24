from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import uuid4

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.contracts import canonical_digest_v1
from knora.tools.dispatch_envelope import HmacDispatchEnvelopeSigner
from knora.tools.execution_types import (
    AdmissionDenied,
    DispatchAdmissionWitness,
    DispatchEnvelopeClaims,
    StoredExecution,
)
from knora.tools.proposal_compatibility import CompatibilityCheckerV1
from knora.tools.proposal_store import _StoredProposal
from knora.tools.proposal_types import CapabilityResolver, ResolvedCapabilityContext
from knora.tools.references import AuthorizedExternalResource


class ExecutionAuthorizer(Protocol):
    def is_authorized(self, principal: WorkspacePrincipal, proposal: _StoredProposal) -> bool: ...


class ExecutionResourceAuthorizer(Protocol):
    def authorize_current(
        self,
        principal: WorkspacePrincipal,
        proposal: _StoredProposal,
        current: ResolvedCapabilityContext,
        *,
        at_time: datetime,
    ) -> AuthorizedExternalResource: ...


class DispatchAdmissionBuilder:
    """Revalidate current authority and seal one immutable dispatch admission."""

    def __init__(
        self,
        *,
        resolver: CapabilityResolver,
        execution_authorizer: ExecutionAuthorizer,
        resource_authorizer: ExecutionResourceAuthorizer,
        signer: HmacDispatchEnvelopeSigner,
        compatibility_checker: CompatibilityCheckerV1,
    ) -> None:
        self._resolver = resolver
        self._execution_authorizer = execution_authorizer
        self._resource_authorizer = resource_authorizer
        self._signer = signer
        self._compatibility_checker = compatibility_checker

    def build(
        self,
        principal: WorkspacePrincipal,
        proposal: _StoredProposal,
        execution: StoredExecution,
        reference_key_epoch: int,
        workspace_dispatch_epoch: int,
        database_time: datetime,
    ) -> DispatchAdmissionWitness | AdmissionDenied:
        if proposal.execution_stale_reason is not None:
            return AdmissionDenied(proposal.execution_stale_reason)
        try:
            current = self._resolver.resolve_for_proposal(
                proposal.workspace_id, proposal.capability_id
            )
        except (KnoraError, LookupError, ValueError):
            return AdmissionDenied("capability_identity_mismatch")
        mismatch = self._compatibility_checker.check(proposal, current)
        if mismatch is not None:
            return AdmissionDenied(mismatch.value)
        if not self._execution_authorizer.is_authorized(principal, proposal):
            return AdmissionDenied("execution_not_authorized")
        try:
            resource = self._resource_authorizer.authorize_current(
                principal, proposal, current, at_time=database_time
            )
        except KnoraError as error:
            return AdmissionDenied(
                "invalid_tool_resource_reference"
                if error.code == "INVALID_TOOL_RESOURCE_REFERENCE"
                else "resource_access_denied"
            )
        return self._seal(
            principal,
            proposal,
            execution,
            resource,
            reference_key_epoch,
            workspace_dispatch_epoch,
            database_time,
        )

    def _seal(
        self,
        principal: WorkspacePrincipal,
        proposal: _StoredProposal,
        execution: StoredExecution,
        resource: AuthorizedExternalResource,
        reference_key_epoch: int,
        workspace_dispatch_epoch: int,
        database_time: datetime,
    ) -> DispatchAdmissionWitness:
        admission_identity = str(uuid4())
        authority_decision_digest = canonical_digest_v1(
            {
                "workspace_id": principal.workspace_id,
                "principal_id": principal.key_id,
                "proposal_id": proposal.proposal_id,
                "authorized": True,
            }
        )
        authority_witness_digest = canonical_digest_v1(
            {
                "authority_decision_digest": authority_decision_digest,
                "reference_key_epoch": reference_key_epoch,
                "workspace_dispatch_epoch": workspace_dispatch_epoch,
            }
        )
        intent = {
            "operation": "create_ticket",
            "title": proposal.parameters["title"],
            "description": proposal.parameters["description"],
            "fingerprint_input": self._fingerprint_input(proposal),
        }
        target_digest = canonical_digest_v1(
            {
                "reference_id": resource.reference_id,
                "resource_kind": resource.resource_kind,
                "resource_identity_digest": resource.resource_identity_digest,
                "resource_claims_digest": resource.resource_claims_digest,
            }
        )
        routing_snapshot_digest = canonical_digest_v1(
            {
                "external_scope": resource.external_scope,
                "provider_routing_handle": resource.provider_routing_handle,
            }
        )
        admission_claims = {
            "purpose": "m4-dispatch-admission-v1",
            "workspace_id": proposal.workspace_id,
            "proposal_id": proposal.proposal_id,
            "logical_execution_id": proposal.logical_execution_id,
            "request_fingerprint": proposal.request_fingerprint,
            "capability": {
                "identity": proposal.capability_id,
                "version": proposal.capability_version,
                "digest": proposal.capability_digest,
            },
            "binding": {
                "identity": proposal.binding_id,
                "version": proposal.binding_version,
                "digest": proposal.binding_digest,
            },
            "policy": {
                "identity": proposal.policy_id,
                "version": proposal.policy_version,
                "digest": proposal.policy_digest,
            },
            "reference_identity": proposal.target_reference_id,
            "reference_digest": proposal.target_reference_digest,
            "reference_claims_digest": proposal.target_resource_claims_digest,
            "resource_identity_digest": proposal.target_resource_identity_digest,
            "canonical_target_digest": target_digest,
            "canonical_parameter_digest": proposal.parameters_digest,
            "complete_intent_digest": proposal.request_fingerprint,
            "reference_key_epoch": reference_key_epoch,
            "workspace_dispatch_epoch": workspace_dispatch_epoch,
            "authority_decision_digest": authority_decision_digest,
            "authority_witness_digest": authority_witness_digest,
            "owner": execution.owner,
            "generation": execution.generation,
            "database_issue_time": database_time,
            "lease_started_at": execution.lease_started_at,
            "lease_deadline": execution.lease_expires_at,
            "routing_snapshot_digest": routing_snapshot_digest,
        }
        admission_claims_digest = canonical_digest_v1(admission_claims)
        envelope = self._signer.sign(
            DispatchEnvelopeClaims(
                admission_identity,
                admission_claims_digest,
                proposal.workspace_id,
                proposal.proposal_id,
                proposal.logical_execution_id,
                proposal.request_fingerprint,
                resource.external_scope,
                resource.provider_routing_handle,
                intent,
            )
        )
        envelope_digest = canonical_digest_v1(envelope.token)
        admission_digest = canonical_digest_v1(
            {
                **admission_claims,
                "admission_identity": admission_identity,
                "admission_claims_digest": admission_claims_digest,
                "envelope_signing_key_identity": self._signer.key_identity,
                "envelope_signing_key_version": self._signer.key_version,
                "canonical_envelope_digest": envelope_digest,
            }
        )
        audit_identity = str(uuid4())
        audit_digest = canonical_digest_v1(
            {
                "event_type": "dispatch_admitted",
                "identity": audit_identity,
                "admission_identity": admission_identity,
                "admission_digest": admission_digest,
            }
        )
        return DispatchAdmissionWitness(
            1,
            admission_identity,
            admission_digest,
            "m4-dispatch-admission-v1",
            proposal.workspace_id,
            proposal.proposal_id,
            proposal.logical_execution_id,
            proposal.request_fingerprint,
            proposal.capability_id,
            proposal.capability_version,
            proposal.capability_digest,
            proposal.binding_id,
            proposal.binding_version,
            proposal.binding_digest,
            proposal.policy_id,
            proposal.policy_version,
            proposal.policy_digest,
            proposal.target_reference_id,
            "m4r1",
            proposal.target_reference_digest,
            proposal.target_resource_claims_digest,
            proposal.target_resource_identity_digest,
            target_digest,
            proposal.parameters_digest,
            proposal.request_fingerprint,
            reference_key_epoch,
            workspace_dispatch_epoch,
            authority_decision_digest,
            authority_witness_digest,
            execution.owner,
            execution.generation,
            database_time,
            execution.lease_started_at,
            execution.lease_expires_at,
            self._signer.key_identity,
            self._signer.key_version,
            routing_snapshot_digest,
            envelope_digest,
            audit_identity,
            audit_digest,
            envelope.token,
        )

    @staticmethod
    def _fingerprint_input(proposal: _StoredProposal) -> dict[str, object]:
        return {
            "operation": "create_ticket",
            "capability": {
                "id": proposal.capability_id,
                "version": proposal.capability_version,
                "digest": proposal.capability_digest,
            },
            "binding": {
                "id": proposal.binding_id,
                "version": proposal.binding_version,
                "digest": proposal.binding_digest,
            },
            "target": {
                "reference_id": proposal.target_reference_id,
                "resource_kind": proposal.resource_kind,
                "resource_identity_digest": proposal.target_resource_identity_digest,
                "resource_claims_digest": proposal.target_resource_claims_digest,
            },
            "parameters": dict(proposal.parameters),
        }
