from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Protocol

from knora.tools.dispatch_envelope import DispatchEnvelope, HmacDispatchEnvelopeSigner
from knora.tools.execution_types import ProviderTerminalFailureCode
from knora.tools.references import AuthorizedExternalResource
from knora.tools.sqlite_provider import SQLiteReferenceProvider


@dataclass(frozen=True, slots=True)
class LookupTicketRequest:
    scope: str
    binding_id: str
    binding_version: str
    binding_digest: str
    resource: AuthorizedExternalResource


@dataclass(frozen=True, slots=True)
class TicketLookupResult:
    ticket_reference: str
    title: str
    status: str
    summary: str

    @property
    def reference(self) -> str:
        return self.ticket_reference


@dataclass(frozen=True, slots=True)
class ProviderScopeDenied:
    code: str = "provider_scope_denied"


@dataclass(frozen=True, slots=True)
class ProviderResourceNotFound:
    code: str = "provider_resource_not_found"


@dataclass(frozen=True, slots=True)
class ProviderUnavailable:
    code: str = "provider_unavailable"


@dataclass(frozen=True, slots=True)
class ProviderContractInvalid:
    code: str = "provider_contract_invalid"


@dataclass(frozen=True, slots=True)
class ProviderWriteSucceeded:
    external_resource_reference: str
    code: str = "succeeded"


@dataclass(frozen=True, slots=True)
class ProviderWriteFailed:
    rejection_code: ProviderTerminalFailureCode | str
    code: str = "failed"


@dataclass(frozen=True, slots=True)
class ProviderWriteIndeterminate:
    code: str = "provider_outcome_indeterminate"


@dataclass(frozen=True, slots=True)
class ProviderIdempotencyConflict:
    code: str = "provider_idempotency_conflict"


@dataclass(frozen=True, slots=True)
class ProviderOutcomeNotFound:
    code: str = "provider_outcome_not_found"


@dataclass(frozen=True, slots=True)
class ProviderOutcomeFound:
    outcome: ProviderWriteSucceeded | ProviderWriteFailed
    code: str = "found"


@dataclass(frozen=True, slots=True)
class ProviderObservationUnavailable:
    code: str = "provider_observation_unavailable"


@dataclass(frozen=True, slots=True)
class ProviderObservationTimeout:
    code: str = "provider_observation_timeout"


@dataclass(frozen=True, slots=True)
class ProviderObservationMalformed:
    code: str = "provider_observation_malformed"


class SupportToolGateway(Protocol):
    def lookup_ticket(
        self, request: LookupTicketRequest
    ) -> (
        TicketLookupResult
        | ProviderScopeDenied
        | ProviderResourceNotFound
        | ProviderUnavailable
        | ProviderContractInvalid
    ): ...

    def create_ticket(
        self, envelope: DispatchEnvelope
    ) -> (
        ProviderWriteSucceeded
        | ProviderWriteFailed
        | ProviderWriteIndeterminate
        | ProviderIdempotencyConflict
        | ProviderScopeDenied
        | ProviderUnavailable
        | ProviderContractInvalid
    ): ...

    def get_execution_outcome(
        self, *, scope: str, logical_execution_id: str
    ) -> (
        ProviderOutcomeFound
        | ProviderOutcomeNotFound
        | ProviderObservationUnavailable
        | ProviderObservationTimeout
        | ProviderObservationMalformed
    ): ...


@dataclass
class FakeSupportToolGateway:
    outcomes: dict[str, object] = field(default_factory=dict)
    calls: list[LookupTicketRequest] = field(default_factory=list)
    write_outcomes: dict[str, object] = field(default_factory=dict)
    write_calls: list[DispatchEnvelope] = field(default_factory=list)
    observation_outcomes: dict[str, object] = field(default_factory=dict)
    observation_calls: list[tuple[str, str]] = field(default_factory=list)

    def lookup_ticket(self, request: LookupTicketRequest):
        self.calls.append(request)
        return self.outcomes.get(
            request.resource.provider_routing_handle, ProviderResourceNotFound()
        )

    def create_ticket(self, envelope: DispatchEnvelope):
        self.write_calls.append(envelope)
        return self.write_outcomes.get(envelope.token, ProviderWriteIndeterminate())

    def get_execution_outcome(self, *, scope: str, logical_execution_id: str):
        self.observation_calls.append((scope, logical_execution_id))
        return self.observation_outcomes.get(logical_execution_id, ProviderOutcomeNotFound())

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def reset(self) -> None:
        self.calls.clear()


class SQLiteSupportToolGateway:
    def __init__(
        self,
        provider: SQLiteReferenceProvider,
        *,
        dispatch_verifier: HmacDispatchEnvelopeSigner | None = None,
        forced_rejection: ProviderTerminalFailureCode | None = None,
        indeterminate_after_commit: bool = False,
    ) -> None:
        self.provider = provider
        self.calls: list[LookupTicketRequest] = []
        self.write_calls: list[DispatchEnvelope] = []
        self._dispatch_verifier = dispatch_verifier
        self._forced_rejection = forced_rejection
        self._indeterminate_after_commit = indeterminate_after_commit

    def lookup_ticket(self, request: LookupTicketRequest):
        self.calls.append(request)
        if (
            request.scope != request.resource.external_scope
            or request.binding_id != request.resource.binding_id
            or request.binding_version != request.resource.binding_version
            or request.binding_digest != request.resource.binding_digest
        ):
            return ProviderScopeDenied()
        try:
            result = self.provider.lookup_ticket(
                scope=request.scope,
                provider_routing_handle=request.resource.provider_routing_handle,
            )
        except sqlite3.Error:
            return ProviderUnavailable()
        except Exception:
            return ProviderContractInvalid()
        if result is None:
            return ProviderResourceNotFound()
        if not isinstance(result, tuple) or len(result) != 3:
            return ProviderContractInvalid()
        title, status, summary = result
        if (
            not _valid_provider_text(title, maximum=200, allow_empty=False)
            or not _valid_provider_text(status, maximum=100, allow_empty=False)
            or not _valid_provider_text(summary, maximum=10_000, allow_empty=True)
        ):
            return ProviderContractInvalid()
        return TicketLookupResult(
            ticket_reference=request.resource.reference_id,
            title=title,
            status=status,
            summary=summary,
        )

    def create_ticket(self, envelope: DispatchEnvelope):
        self.write_calls.append(envelope)
        if self._dispatch_verifier is None:
            return ProviderContractInvalid()
        try:
            claims = self._dispatch_verifier.verify(envelope)
            intent = claims.get("intent")
            if not isinstance(intent, dict):
                return ProviderContractInvalid()
            expected_fingerprint = _provider_intent_fingerprint(intent)
            if expected_fingerprint != claims.get("request_fingerprint"):
                return ProviderContractInvalid()
            target_authorization = self.provider.authorize_write_target(
                scope=_required_text(claims, "external_scope"),
                provider_routing_handle=_required_text(claims, "provider_routing_handle"),
            )
            if target_authorization == "scope_denied":
                return ProviderScopeDenied()
            result = self.provider.create_ticket(
                scope=_required_text(claims, "external_scope"),
                provider_routing_handle=_required_text(claims, "provider_routing_handle"),
                logical_execution_id=_required_text(claims, "logical_execution_id"),
                request_fingerprint=expected_fingerprint,
                admission_digest=_required_text(claims, "admission_claims_digest"),
                title=_required_text(intent, "title"),
                description=_required_text(intent, "description"),
                external_resource_reference=self._dispatch_verifier.mint_external_resource_reference(
                    _required_text(claims, "logical_execution_id")
                ),
                forced_rejection=(
                    None if self._forced_rejection is None else self._forced_rejection.value
                ),
            )
        except sqlite3.Error:
            return ProviderUnavailable()
        except (KeyError, TypeError, ValueError):
            return ProviderContractInvalid()
        if result[0] == "conflict":
            return ProviderIdempotencyConflict()
        if result[0] == "failed":
            outcome = ProviderWriteFailed(result[1])
        else:
            outcome = ProviderWriteSucceeded(result[1])
        if self._indeterminate_after_commit:
            return ProviderWriteIndeterminate()
        return outcome

    def get_execution_outcome(self, *, scope: str, logical_execution_id: str):
        try:
            result = self.provider.get_execution_outcome(
                scope=scope, logical_execution_id=logical_execution_id
            )
        except sqlite3.Error:
            return ProviderObservationUnavailable()
        if result is None:
            return ProviderOutcomeNotFound()
        outcome_type, value = result
        if outcome_type == "succeeded":
            return ProviderOutcomeFound(ProviderWriteSucceeded(value))
        if outcome_type == "failed" and value in {
            item.value for item in ProviderTerminalFailureCode
        }:
            return ProviderOutcomeFound(ProviderWriteFailed(value))
        return ProviderObservationMalformed()


def _valid_provider_text(value: object, *, maximum: int, allow_empty: bool) -> bool:
    return (
        isinstance(value, str)
        and "\x00" not in value
        and len(value) <= maximum
        and (allow_empty or bool(value))
    )


def _provider_intent_fingerprint(intent: dict[str, object]) -> str:
    from knora.tools.contracts import canonical_digest_v1

    fingerprint_input = intent.get("fingerprint_input")
    if not isinstance(fingerprint_input, dict):
        raise ValueError("fingerprint input is required")
    return canonical_digest_v1(fingerprint_input)


def _required_text(values: dict[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} is required")
    return value
