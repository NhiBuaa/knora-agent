from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.references import (
    AuthorizedExternalResource,
    ExternalResourceReference,
    ReferenceVerifier,
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability_id: str
    version: str
    digest: str
    operation: str
    resource_kind: str


@dataclass(frozen=True, slots=True)
class ExternalScopeBinding:
    workspace_id: str
    binding_id: str
    version: str
    digest: str
    external_scope: str

    @classmethod
    def for_workspace(
        cls,
        workspace_id: str,
        *,
        binding_id: str | None = None,
        version: str = "v1",
        external_scope: str | None = None,
    ) -> ExternalScopeBinding:
        binding_id = binding_id or f"workspace-binding:{workspace_id}"
        external_scope = external_scope or f"external-scope:{workspace_id}"
        digest = _digest(
            {
                "workspace_id": workspace_id,
                "binding_id": binding_id,
                "version": version,
                "external_scope": external_scope,
            }
        )
        return cls(workspace_id, binding_id, version, digest, external_scope)


class CapabilityRegistry:
    """Static, versioned capability registry; it has no dynamic loading path."""

    _descriptors: Mapping[str, CapabilityDescriptor] = {
        "ticket_lookup": CapabilityDescriptor(
            capability_id="ticket_lookup",
            version="m4.1",
            digest="sha256:knora-m4-ticket-lookup-v1",
            operation="read",
            resource_kind="ticket",
        ),
    }

    @classmethod
    def static(cls) -> CapabilityRegistry:
        return cls()

    def resolve(self, capability_id: str) -> CapabilityDescriptor:
        descriptor = self._descriptors.get(capability_id)
        if descriptor is None:
            raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")
        return descriptor

    get = resolve

    def resolve_ticket_lookup(self) -> CapabilityDescriptor:
        return self.resolve("ticket_lookup")

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(self._descriptors)


class WorkspaceResourceAuthorizer:
    """Resolves Workspace bindings and authorizes an opaque reference before gateway use."""

    def __init__(
        self,
        *,
        bindings: Mapping[str, ExternalScopeBinding] | None = None,
        reference_verifier: ReferenceVerifier | None = None,
    ) -> None:
        self._bindings = dict(bindings or {})
        self._reference_verifier = reference_verifier

    def resolve_binding(
        self,
        workspace_id: str,
        descriptor: CapabilityDescriptor | None = None,
    ) -> ExternalScopeBinding:
        del descriptor
        binding = self._bindings.get(workspace_id)
        if binding is None:
            binding = ExternalScopeBinding.for_workspace(workspace_id)
        if binding.workspace_id != workspace_id:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        return binding

    def authorize_resource(
        self,
        principal: WorkspacePrincipal,
        descriptor: CapabilityDescriptor,
        binding: ExternalScopeBinding,
        reference: str | ExternalResourceReference,
    ) -> AuthorizedExternalResource:
        if principal is None:
            raise KnoraError("UNAUTHENTICATED")
        if principal.workspace_id != binding.workspace_id:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        if self._reference_verifier is None:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        try:
            verified = self._reference_verifier.verify(reference)
        except KnoraError as error:
            if error.code == "INVALID_TOOL_RESOURCE_REFERENCE":
                raise
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED") from None
        except (ValueError, TypeError):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED") from None
        if (
            verified.workspace_id != principal.workspace_id
            or verified.capability_id != descriptor.capability_id
            or verified.capability_version != descriptor.version
            or verified.binding_id != binding.binding_id
            or verified.binding_version != binding.version
            or verified.binding_digest != binding.digest
            or verified.resource_kind != descriptor.resource_kind
        ):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        return replace(
            verified.authorized_resource,
            external_scope=binding.external_scope,
        )

    authorize = authorize_resource
