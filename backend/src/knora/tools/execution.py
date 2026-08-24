from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.dispatch_envelope import DispatchEnvelope, HmacDispatchEnvelopeSigner
from knora.tools.execution_admission import (
    DispatchAdmissionBuilder,
    ExecutionAuthorizer,
    ExecutionResourceAuthorizer,
)
from knora.tools.execution_types import (
    AcquireApplied,
    AcquireDenied,
    AcquireInProgress,
    AcquireRevisionConflict,
    AdmissionApplied,
    AdmissionDenied,
    AuthorizedExecutionBindingSnapshot,
    ExecutionFailed,
    ExecutionFenced,
    ExecutionIndeterminate,
    ExecutionInProgress,
    ExecutionResult,
    ExecutionSucceeded,
    FinalizeApplied,
    ProposalNotExecutable,
    ProviderTerminalFailureCode,
    StoreExecutionFenced,
)
from knora.tools.gateway import (
    ProviderContractInvalid,
    ProviderIdempotencyConflict,
    ProviderScopeDenied,
    ProviderUnavailable,
    ProviderWriteFailed,
    ProviderWriteIndeterminate,
    ProviderWriteSucceeded,
    SupportToolGateway,
)
from knora.tools.proposal_compatibility import CompatibilityCheckerV1
from knora.tools.proposal_store import ToolActionStore, _StoredProposal
from knora.tools.proposal_types import (
    ActorContext,
    CapabilityResolver,
    ExecuteApprovedProposal,
    ResolvedCapabilityContext,
)
from knora.tools.references import AuthorizedExternalResource


class DenyingExecutionResourceAuthorizer:
    def authorize_current(
        self,
        principal: WorkspacePrincipal,
        proposal: _StoredProposal,
        current: ResolvedCapabilityContext,
        *,
        at_time: datetime,
    ) -> AuthorizedExternalResource:
        del principal, proposal, current, at_time
        raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")


class DenyingSupportToolGateway:
    def create_ticket(self, envelope: DispatchEnvelope):
        del envelope
        return ProviderContractInvalid()


class ApprovedProposalExecutor:
    """Hide the generation-1 acquire/admit/dispatch/finalize protocol."""

    def __init__(
        self,
        *,
        resolver: CapabilityResolver,
        store: ToolActionStore,
        execution_authorizer: ExecutionAuthorizer,
        resource_authorizer: ExecutionResourceAuthorizer,
        gateway: SupportToolGateway,
        signer: HmacDispatchEnvelopeSigner,
        compatibility_checker: CompatibilityCheckerV1,
        clock: Callable[[], datetime] | None = None,
        owner_factory: Callable[[], str] | None = None,
        lease_duration: timedelta = timedelta(minutes=2),
    ) -> None:
        if lease_duration <= timedelta(0):
            raise ValueError("execution lease duration must be positive")
        self._resolver = resolver
        self._store = store
        self._execution_authorizer = execution_authorizer
        self._resource_authorizer = resource_authorizer
        self._gateway = gateway
        self._compatibility_checker = compatibility_checker
        self._admission_builder = DispatchAdmissionBuilder(
            resolver=resolver,
            execution_authorizer=execution_authorizer,
            resource_authorizer=resource_authorizer,
            signer=signer,
            compatibility_checker=compatibility_checker,
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._owner_factory = owner_factory or (lambda: str(uuid4()))
        self._lease_duration = lease_duration

    def execute(
        self,
        command: ExecuteApprovedProposal,
        principal: WorkspacePrincipal,
        actor_context: ActorContext,
    ) -> ExecutionResult:
        del actor_context  # actor identity never confers execution authority
        proposal = self._store.read_proposal(principal.workspace_id, command.proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        existing = self._existing_result(proposal)
        if existing is not None:
            return existing
        if proposal.state != "approved":
            raise KnoraError("TOOL_PROPOSAL_NOT_APPROVED")
        if proposal.revision != command.expected_revision:
            raise KnoraError("TOOL_PROPOSAL_REVISION_CONFLICT")
        current = self._resolve_compatible(proposal, persist_stale=True)
        now = self._clock()
        if now >= proposal.expires_at:
            raise KnoraError("TOOL_PROPOSAL_EXPIRED")
        self._resource_authorizer.authorize_current(principal, proposal, current, at_time=now)
        if not self._execution_authorizer.is_authorized(principal, proposal):
            raise KnoraError("TOOL_EXECUTION_NOT_AUTHORIZED")
        owner = self._owner_factory()
        acquired = self._store.acquire_execution(
            principal.workspace_id,
            proposal.proposal_id,
            command.expected_revision,
            owner,
            self._lease_duration,
            AuthorizedExecutionBindingSnapshot.from_context(current),
            now,
        )
        if isinstance(acquired, AcquireInProgress):
            return ExecutionInProgress(proposal.proposal_id, proposal.logical_execution_id)
        if isinstance(acquired, AcquireRevisionConflict):
            raise KnoraError("TOOL_PROPOSAL_REVISION_CONFLICT")
        if isinstance(acquired, AcquireDenied):
            self._raise_acquire_denial(acquired.reason_code)
        assert isinstance(acquired, AcquireApplied)
        try:
            admitted = self._store.authorize_and_admit_dispatch(
                principal.workspace_id,
                proposal.proposal_id,
                owner,
                acquired.execution.generation,
                self._clock(),
                lambda stored, execution, key_epoch, workspace_epoch, database_time: (
                    self._admission_builder.build(
                        principal,
                        stored,
                        execution,
                        key_epoch,
                        workspace_epoch,
                        database_time,
                    )
                ),
            )
        except KnoraError as error:
            if error.code != "PERSISTENCE_OPERATION_FAILED":
                raise
            readback = self._store.read_proposal(principal.workspace_id, proposal.proposal_id)
            if readback is None or readback.admission is None:
                return ExecutionIndeterminate(proposal.proposal_id, proposal.logical_execution_id)
            admitted = AdmissionApplied(readback.admission)
        if isinstance(admitted, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        if isinstance(admitted, AdmissionDenied):
            return ProposalNotExecutable(
                proposal.proposal_id,
                proposal.logical_execution_id,
                admitted.reason_code,
            )
        assert isinstance(admitted, AdmissionApplied)
        try:
            outcome = self._gateway.create_ticket(
                DispatchEnvelope(admitted.admission.envelope_token)
            )
        except (ConnectionError, OSError, TimeoutError):
            outcome = ProviderWriteIndeterminate()
        return self._record_outcome(
            proposal,
            owner,
            acquired.execution.generation,
            outcome,
        )

    def _existing_result(self, proposal: _StoredProposal) -> ExecutionResult | None:
        execution = proposal.execution
        if execution is None:
            return None
        if execution.lifecycle == "succeeded" and execution.external_resource_reference:
            return ExecutionSucceeded(
                proposal.proposal_id,
                proposal.logical_execution_id,
                execution.external_resource_reference,
            )
        if execution.lifecycle == "failed" and execution.rejection_code:
            return ExecutionFailed(
                proposal.proposal_id,
                proposal.logical_execution_id,
                execution.rejection_code,
            )
        return ExecutionInProgress(proposal.proposal_id, proposal.logical_execution_id)

    def _resolve_compatible(
        self, proposal: _StoredProposal, *, persist_stale: bool
    ) -> ResolvedCapabilityContext:
        if proposal.execution_stale_reason is not None:
            raise KnoraError("TOOL_PROPOSAL_STALE")
        try:
            current = self._resolver.resolve_for_proposal(
                proposal.workspace_id, proposal.capability_id
            )
        except (KnoraError, LookupError, ValueError):
            reason = "capability_identity_mismatch"
        else:
            mismatch = self._compatibility_checker.check(proposal, current)
            if mismatch is None:
                return current
            reason = mismatch.value
        if persist_stale:
            self._store.mark_execution_stale(proposal.workspace_id, proposal.proposal_id, reason)
        raise KnoraError("TOOL_PROPOSAL_STALE")

    def _record_outcome(
        self,
        proposal: _StoredProposal,
        owner: str,
        generation: int,
        outcome: object,
    ) -> ExecutionResult:
        now = self._clock()
        if isinstance(outcome, ProviderWriteSucceeded):
            observation_type = "succeeded"
            rejection_code = None
            external_reference = outcome.external_resource_reference
            lifecycle = "succeeded"
        elif isinstance(outcome, ProviderWriteFailed) and str(outcome.rejection_code) in {
            item.value for item in ProviderTerminalFailureCode
        }:
            observation_type = "failed"
            rejection_code = str(outcome.rejection_code)
            external_reference = None
            lifecycle = "failed"
        elif isinstance(outcome, ProviderIdempotencyConflict):
            observed = self._store.record_execution_observation(
                proposal.workspace_id,
                proposal.proposal_id,
                owner,
                generation,
                "provider_idempotency_conflict",
                None,
                None,
                now,
            )
            if isinstance(observed, StoreExecutionFenced):
                return ExecutionFenced(
                    proposal.proposal_id, proposal.logical_execution_id
                )
            return ExecutionInProgress(
                proposal.proposal_id,
                proposal.logical_execution_id,
                reason_code="provider_idempotency_conflict",
            )
        elif isinstance(
            outcome,
            (
                ProviderWriteIndeterminate,
                ProviderUnavailable,
                ProviderContractInvalid,
                ProviderScopeDenied,
            ),
        ):
            observed = self._store.record_execution_observation(
                proposal.workspace_id,
                proposal.proposal_id,
                owner,
                generation,
                "indeterminate_external_outcome",
                None,
                None,
                now,
            )
            if isinstance(observed, StoreExecutionFenced):
                return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
            return ExecutionIndeterminate(proposal.proposal_id, proposal.logical_execution_id)
        else:
            observed = self._store.record_execution_observation(
                proposal.workspace_id,
                proposal.proposal_id,
                owner,
                generation,
                "indeterminate_external_outcome",
                None,
                None,
                now,
            )
            if isinstance(observed, StoreExecutionFenced):
                return ExecutionFenced(
                    proposal.proposal_id, proposal.logical_execution_id
                )
            return ExecutionIndeterminate(
                proposal.proposal_id, proposal.logical_execution_id
            )
        observed = self._store.record_execution_observation(
            proposal.workspace_id,
            proposal.proposal_id,
            owner,
            generation,
            observation_type,
            rejection_code,
            external_reference,
            now,
        )
        if isinstance(observed, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        finalized = self._store.finalize_execution(
            proposal.workspace_id,
            proposal.proposal_id,
            owner,
            generation,
            lifecycle,
            rejection_code,
            external_reference,
            now,
        )
        if isinstance(finalized, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        assert isinstance(finalized, FinalizeApplied)
        if lifecycle == "succeeded":
            assert external_reference is not None
            return ExecutionSucceeded(
                proposal.proposal_id,
                proposal.logical_execution_id,
                external_reference,
            )
        assert rejection_code is not None
        return ExecutionFailed(proposal.proposal_id, proposal.logical_execution_id, rejection_code)

    @staticmethod
    def _raise_acquire_denial(reason_code: str) -> None:
        mapping = {
            "expired": "TOOL_PROPOSAL_EXPIRED",
            "not_approved": "TOOL_PROPOSAL_NOT_APPROVED",
        }
        raise KnoraError(mapping.get(reason_code, "TOOL_PROPOSAL_STALE"))
