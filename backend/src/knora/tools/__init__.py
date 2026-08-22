"""Workspace-authorized support tools.

The package intentionally exposes a small, static capability boundary.  Provider adapters and
reference verification live behind typed interfaces so application code never receives provider
SDK objects or raw provider identifiers.
"""

from knora.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityRegistry,
    ExternalScopeBinding,
    WorkspaceResourceAuthorizer,
)
from knora.tools.gateway import (
    FakeSupportToolGateway,
    LookupTicketRequest,
    ProviderContractInvalid,
    ProviderResourceNotFound,
    ProviderScopeDenied,
    ProviderUnavailable,
    SQLiteSupportToolGateway,
    SupportToolGateway,
    TicketLookupResult,
)
from knora.tools.read import ReadTool, ReadToolCommand
from knora.tools.references import (
    ExternalResourceReference,
    InMemoryReferenceStore,
    ReferenceKey,
    ReferenceRecord,
    ReferenceVerifier,
    SQLiteReferenceProvider,
)

__all__ = [
    "CapabilityDescriptor",
    "CapabilityRegistry",
    "ExternalResourceReference",
    "ExternalScopeBinding",
    "FakeSupportToolGateway",
    "InMemoryReferenceStore",
    "LookupTicketRequest",
    "ProviderContractInvalid",
    "ProviderResourceNotFound",
    "ProviderScopeDenied",
    "ProviderUnavailable",
    "ReadTool",
    "ReadToolCommand",
    "ReferenceKey",
    "ReferenceRecord",
    "ReferenceVerifier",
    "SQLiteReferenceProvider",
    "SQLiteSupportToolGateway",
    "SupportToolGateway",
    "TicketLookupResult",
    "WorkspaceResourceAuthorizer",
]
