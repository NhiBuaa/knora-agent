from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Protocol

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
        return self.outcomes.get(
            request.resource.provider_routing_handle, ProviderResourceNotFound()
        )

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


def _valid_provider_text(value: object, *, maximum: int, allow_empty: bool) -> bool:
    return (
        isinstance(value, str)
        and "\x00" not in value
        and len(value) <= maximum
        and (allow_empty or bool(value))
    )
