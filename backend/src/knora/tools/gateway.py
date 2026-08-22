from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Protocol

from knora.tools.references import AuthorizedExternalResource, SQLiteReferenceProvider


@dataclass(frozen=True, slots=True)
class LookupTicketRequest:
    scope: str
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


@dataclass
class FakeSupportToolGateway:
    outcomes: dict[str, object] = field(default_factory=dict)
    calls: list[LookupTicketRequest] = field(default_factory=list)

    def lookup_ticket(self, request: LookupTicketRequest):
        self.calls.append(request)
        return self.outcomes.get(request.resource.provider_resource_id, ProviderResourceNotFound())

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def reset(self) -> None:
        self.calls.clear()


class SQLiteSupportToolGateway:
    def __init__(self, provider: SQLiteReferenceProvider) -> None:
        self.provider = provider
        self.calls: list[LookupTicketRequest] = []

    def lookup_ticket(self, request: LookupTicketRequest):
        self.calls.append(request)
        if request.scope != request.resource.external_scope:
            return ProviderScopeDenied()
        try:
            result = self.provider.lookup_ticket(
                scope=request.scope, provider_resource_id=request.resource.provider_resource_id
            )
        except sqlite3.Error:
            return ProviderUnavailable()
        if result is None:
            return ProviderResourceNotFound()
        title, status, summary = result
        return TicketLookupResult(
            ticket_reference=request.resource.reference_id,
            title=title,
            status=status,
            summary=summary,
        )
