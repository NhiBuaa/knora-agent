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
    ObservationReferenceResolver,
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
    ExecutionNotStale,
    ExecutionResult,
    ExecutionSucceeded,
    FinalizeApplied,
    ProposalNotExecutable,
    ProviderTerminalFailureCode,
    ReconciledFailed,
    ReconciledSucceeded,
    ReconciliationIndeterminate,
    ReconciliationOutcomeNotFound,
    StoreExecutionFenced,
    StoreExecutionFinalized,
    TakeoverApplied,
)
from knora.tools.gateway import (
    ProviderContractInvalid,
    ProviderIdempotencyConflict,
    ProviderObservationMalformed,
    ProviderObservationTimeout,
    ProviderObservationUnavailable,
    ProviderOutcomeFound,
    ProviderOutcomeNotFound,
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
    ReconcileExecution,
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
        resource = self._resource_authorizer.authorize_current(
            principal, proposal, current, at_time=now
        )
        if not self._execution_authorizer.is_authorized(principal, proposal):
            raise KnoraError("TOOL_EXECUTION_NOT_AUTHORIZED")
        owner = self._owner_factory()
        acquired = self._store.acquire_execution(
            principal.workspace_id,
            proposal.proposal_id,
            command.expected_revision,
            owner,
            self._lease_duration,
            AuthorizedExecutionBindingSnapshot.from_context(
                current,
                workspace_id=principal.workspace_id,
                resource=resource,
            ),
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


class ReconciliationExecutor:
    """Observe provider truth before any stale-lease recovery or same-key retry."""

    def __init__(
        self,
        *,
        resolver: CapabilityResolver,
        store: ToolActionStore,
        execution_authorizer: ExecutionAuthorizer,
        resource_authorizer: ExecutionResourceAuthorizer,
        observation_reference_resolver: ObservationReferenceResolver,
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
        self._observation_reference_resolver = observation_reference_resolver
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

    def reconcile(
        self,
        command: ReconcileExecution,
        principal: WorkspacePrincipal,
        actor_context: ActorContext,
    ) -> ExecutionResult:
        del actor_context
        proposal = self._store.read_proposal(principal.workspace_id, command.proposal_id)
        if proposal is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
        execution = proposal.execution
        if execution is None:
            raise KnoraError("TOOL_PROPOSAL_NOT_APPROVED")
        existing = self._terminal_result(proposal)
        if existing is not None:
            return existing
        if command.expected_lease_generation != execution.generation:
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        scope = self._observation_reference_resolver.resolve_started_execution(
            execution.acquisition.binding_snapshot,
            principal,
            proposal,
            execution,
        )
        if scope is None:
            return ReconciliationIndeterminate(
                proposal.proposal_id,
                proposal.logical_execution_id,
                "observation_routing_unavailable",
            )
        try:
            outcome = self._gateway.get_execution_outcome(
                scope=scope,
                logical_execution_id=proposal.logical_execution_id,
            )
        except TimeoutError:
            outcome = ProviderObservationTimeout()
        except (ConnectionError, OSError):
            outcome = ProviderObservationUnavailable()
        if isinstance(outcome, ProviderOutcomeFound):
            return self._reconcile_terminal(
                proposal,
                execution,
                command.expected_lease_generation,
                outcome.outcome,
            )
        if isinstance(outcome, ProviderOutcomeNotFound):
            return self._reconcile_not_found(
                proposal,
                execution,
                command.expected_lease_generation,
                principal,
            )
        reason_code = (
            "provider_observation_timeout"
            if isinstance(outcome, ProviderObservationTimeout)
            else (
                "provider_observation_malformed"
                if isinstance(outcome, ProviderObservationMalformed)
                else "provider_observation_unavailable"
            )
        )
        return self._record_indeterminate(proposal, execution, reason_code)

    def _reconcile_terminal(
        self,
        proposal: _StoredProposal,
        execution,
        expected_generation: int,
        outcome: ProviderWriteSucceeded | ProviderWriteFailed,
    ) -> ExecutionResult:
        owner = self._owner_factory()
        current = execution
        if current.owner != owner:
            takeover = self._store.takeover_stale_execution(
                proposal.workspace_id,
                proposal.proposal_id,
                expected_generation,
                owner,
                self._lease_duration,
                self._clock(),
            )
            if isinstance(takeover, TakeoverApplied):
                current = takeover.execution
            elif isinstance(takeover, StoreExecutionFinalized):
                return self._terminal_result_from_execution(proposal, takeover.execution)
            elif isinstance(takeover, StoreExecutionFenced):
                return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
            else:
                return ExecutionInProgress(proposal.proposal_id, proposal.logical_execution_id)
        result = self._record_terminal(proposal, current, outcome)
        if not isinstance(result, ExecutionFenced):
            return result
        takeover = self._store.takeover_stale_execution(
            proposal.workspace_id,
            proposal.proposal_id,
            expected_generation,
            owner,
            self._lease_duration,
            self._clock(),
        )
        if isinstance(takeover, TakeoverApplied):
            return self._record_terminal(proposal, takeover.execution, outcome)
        if isinstance(takeover, StoreExecutionFinalized):
            return self._terminal_result_from_execution(proposal, takeover.execution)
        if isinstance(takeover, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        return ExecutionInProgress(proposal.proposal_id, proposal.logical_execution_id)

    def _record_terminal(self, proposal: _StoredProposal, execution, outcome) -> ExecutionResult:
        if isinstance(outcome, ProviderWriteSucceeded):
            observation_type = "reconciled_succeeded"
            lifecycle = "succeeded"
            rejection_code = None
            external_reference = outcome.external_resource_reference
        elif isinstance(outcome, ProviderWriteFailed) and str(outcome.rejection_code) in {
            item.value for item in ProviderTerminalFailureCode
        }:
            observation_type = "reconciled_failed"
            lifecycle = "failed"
            rejection_code = str(outcome.rejection_code)
            external_reference = None
        else:
            return ReconciliationIndeterminate(
                proposal.proposal_id,
                proposal.logical_execution_id,
                "provider_observation_malformed",
            )
        observed = self._store.record_execution_observation(
            proposal.workspace_id,
            proposal.proposal_id,
            execution.owner,
            execution.generation,
            observation_type,
            rejection_code,
            external_reference,
            self._clock(),
        )
        if isinstance(observed, StoreExecutionFinalized):
            return self._terminal_result_from_execution(proposal, observed.execution)
        if isinstance(observed, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        finalized = self._store.finalize_execution(
            proposal.workspace_id,
            proposal.proposal_id,
            execution.owner,
            execution.generation,
            lifecycle,
            rejection_code,
            external_reference,
            self._clock(),
        )
        if isinstance(finalized, StoreExecutionFinalized):
            return self._terminal_result_from_execution(proposal, finalized.execution)
        if isinstance(finalized, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        if lifecycle == "succeeded":
            assert external_reference is not None
            return ReconciledSucceeded(
                proposal.proposal_id, proposal.logical_execution_id, external_reference
            )
        assert rejection_code is not None
        return ReconciledFailed(proposal.proposal_id, proposal.logical_execution_id, rejection_code)

    def _reconcile_not_found(
        self,
        proposal: _StoredProposal,
        execution,
        expected_generation: int,
        principal: WorkspacePrincipal,
    ) -> ExecutionResult:
        owner = self._owner_factory()
        takeover = self._store.takeover_stale_execution(
            proposal.workspace_id,
            proposal.proposal_id,
            expected_generation,
            owner,
            self._lease_duration,
            self._clock(),
        )
        if isinstance(takeover, StoreExecutionFinalized):
            return self._terminal_result_from_execution(proposal, takeover.execution)
        if isinstance(takeover, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        if isinstance(takeover, ExecutionNotStale):
            if takeover.execution.owner == owner:
                self._record_nonterminal(proposal, takeover.execution, "provider_outcome_not_found")
            return ReconciliationOutcomeNotFound(
                proposal.proposal_id, proposal.logical_execution_id
            )
        assert isinstance(takeover, TakeoverApplied)
        record = self._record_nonterminal(
            proposal, takeover.execution, "provider_outcome_not_found"
        )
        if isinstance(record, (ExecutionFenced, ReconciliationIndeterminate)):
            return record
        return self._retry_after_not_found(proposal, takeover.execution, principal)

    def _retry_after_not_found(
        self, proposal: _StoredProposal, execution, principal: WorkspacePrincipal
    ) -> ExecutionResult:
        self._revalidate_retry(proposal, principal)
        if proposal.admission is None:
            admitted = self._store.authorize_and_admit_dispatch(
                proposal.workspace_id,
                proposal.proposal_id,
                execution.owner,
                execution.generation,
                self._clock(),
                lambda stored, current_execution, key_epoch, workspace_epoch, database_time: (
                    self._admission_builder.build(
                        principal,
                        stored,
                        current_execution,
                        key_epoch,
                        workspace_epoch,
                        database_time,
                    )
                ),
            )
            if isinstance(admitted, StoreExecutionFenced):
                return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
            if isinstance(admitted, AdmissionDenied):
                return ProposalNotExecutable(
                    proposal.proposal_id, proposal.logical_execution_id, admitted.reason_code
                )
            assert isinstance(admitted, AdmissionApplied)
            admission = admitted.admission
        else:
            admission = proposal.admission
        try:
            outcome = self._gateway.create_ticket(DispatchEnvelope(admission.envelope_token))
        except (ConnectionError, OSError, TimeoutError):
            outcome = ProviderWriteIndeterminate()
        if isinstance(outcome, (ProviderWriteSucceeded, ProviderWriteFailed)):
            return self._record_terminal(proposal, execution, outcome)
        return self._record_indeterminate(proposal, execution, "indeterminate_external_outcome")

    def _revalidate_retry(
        self, proposal: _StoredProposal, principal: WorkspacePrincipal
    ) -> None:
        if proposal.execution_stale_reason is not None:
            raise KnoraError("TOOL_PROPOSAL_STALE")
        try:
            current = self._resolver.resolve_for_proposal(
                proposal.workspace_id, proposal.capability_id
            )
        except (KnoraError, LookupError, ValueError):
            self._store.mark_execution_stale(
                proposal.workspace_id, proposal.proposal_id, "capability_identity_mismatch"
            )
            raise KnoraError("TOOL_PROPOSAL_STALE") from None
        mismatch = self._compatibility_checker.check(proposal, current)
        if mismatch is not None:
            self._store.mark_execution_stale(
                proposal.workspace_id, proposal.proposal_id, mismatch.value
            )
            raise KnoraError("TOOL_PROPOSAL_STALE")
        now = self._clock()
        if now >= proposal.expires_at:
            raise KnoraError("TOOL_PROPOSAL_EXPIRED")
        self._resource_authorizer.authorize_current(principal, proposal, current, at_time=now)
        if not self._execution_authorizer.is_authorized(principal, proposal):
            raise KnoraError("TOOL_EXECUTION_NOT_AUTHORIZED")

    def _record_nonterminal(self, proposal: _StoredProposal, execution, observation_type: str):
        observed = self._store.record_execution_observation(
            proposal.workspace_id,
            proposal.proposal_id,
            execution.owner,
            execution.generation,
            observation_type,
            None,
            None,
            self._clock(),
        )
        if isinstance(observed, StoreExecutionFenced):
            return ExecutionFenced(proposal.proposal_id, proposal.logical_execution_id)
        if isinstance(observed, StoreExecutionFinalized):
            return self._terminal_result_from_execution(proposal, observed.execution)
        return None

    def _record_indeterminate(
        self, proposal: _StoredProposal, execution, reason_code: str
    ) -> ExecutionResult:
        owner = self._owner_factory()
        if execution.owner == owner:
            result = self._record_nonterminal(proposal, execution, reason_code)
            if result is not None:
                return result
        return ReconciliationIndeterminate(
            proposal.proposal_id, proposal.logical_execution_id, reason_code
        )

    @staticmethod
    def _terminal_result_from_execution(proposal: _StoredProposal, execution) -> ExecutionResult:
        if execution.lifecycle == "succeeded" and execution.external_resource_reference:
            return ReconciledSucceeded(
                proposal.proposal_id,
                proposal.logical_execution_id,
                execution.external_resource_reference,
            )
        if execution.lifecycle == "failed" and execution.rejection_code:
            return ReconciledFailed(
                proposal.proposal_id,
                proposal.logical_execution_id,
                execution.rejection_code,
            )
        return ExecutionInProgress(proposal.proposal_id, proposal.logical_execution_id)

    def _terminal_result(self, proposal: _StoredProposal) -> ExecutionResult | None:
        if proposal.execution is None or proposal.execution.lifecycle == "executing":
            return None
        return self._terminal_result_from_execution(proposal, proposal.execution)
