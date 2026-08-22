from __future__ import annotations

from dataclasses import dataclass

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.capabilities import CapabilityRegistry, WorkspaceResourceAuthorizer
from knora.tools.gateway import (
    LookupTicketRequest,
    ProviderContractInvalid,
    ProviderResourceNotFound,
    ProviderScopeDenied,
    ProviderUnavailable,
    SupportToolGateway,
    TicketLookupResult,
)


@dataclass(frozen=True, slots=True)
class ReadToolCommand:
    ticket_reference: str


class ReadTool:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry | None = None,
        resource_authorizer: WorkspaceResourceAuthorizer | None = None,
        gateway: SupportToolGateway | None = None,
    ) -> None:
        self.registry = registry or CapabilityRegistry.static()
        self.resource_authorizer = resource_authorizer
        self.gateway = gateway

    def execute(
        self, command: ReadToolCommand, principal: WorkspacePrincipal
    ) -> TicketLookupResult:
        if principal is None:
            raise KnoraError("UNAUTHENTICATED")
        if not isinstance(command, ReadToolCommand) or not isinstance(
            command.ticket_reference, str
        ):
            raise KnoraError("TOOL_REQUEST_INVALID")
        if not command.ticket_reference.strip():
            raise KnoraError("TOOL_REQUEST_INVALID")
        descriptor = self.registry.resolve_ticket_lookup()
        if self.resource_authorizer is None or self.gateway is None:
            raise KnoraError("TOOL_PROVIDER_UNAVAILABLE")
        binding = self.resource_authorizer.resolve_binding(principal.workspace_id, descriptor)
        authorized_resource = self.resource_authorizer.authorize_resource(
            principal, descriptor, binding, command.ticket_reference
        )
        outcome = self.gateway.lookup_ticket(
            LookupTicketRequest(
                scope=binding.external_scope,
                binding_id=binding.binding_id,
                binding_version=binding.version,
                binding_digest=binding.digest,
                resource=authorized_resource,
            )
        )
        if isinstance(outcome, TicketLookupResult):
            return outcome
        if isinstance(outcome, ProviderScopeDenied):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        if isinstance(outcome, ProviderResourceNotFound):
            raise KnoraError("TOOL_TICKET_NOT_FOUND")
        if isinstance(outcome, ProviderUnavailable):
            raise KnoraError("TOOL_PROVIDER_UNAVAILABLE")
        if isinstance(outcome, ProviderContractInvalid):
            raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID")
        raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID")
