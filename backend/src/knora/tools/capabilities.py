from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.contracts import canonical_digest_v1, require_digest
from knora.tools.references import (
    AuthorizedExternalResource,
    ExternalResourceReference,
    ReferenceVerifier,
)


def _digest(value: object) -> str:
    return canonical_digest_v1(value)


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability_id: str
    version: str
    digest: str
    operation: str
    resource_kind: str

    def __post_init__(self) -> None:
        if not all((self.capability_id, self.version, self.operation, self.resource_kind)):
            raise ValueError("capability descriptor fields are required")
        require_digest(self.digest, "capability digest")
        expected = _digest(
            {
                "capability_id": self.capability_id,
                "operation": self.operation,
                "resource_kind": self.resource_kind,
                "version": self.version,
            }
        )
        if self.digest != expected:
            raise ValueError("capability digest does not match canonical descriptor")


@dataclass(frozen=True, slots=True)
class ExternalScopeBinding:
    workspace_id: str
    binding_id: str
    version: str
    digest: str
    external_scope: str

    def __post_init__(self) -> None:
        if not all((self.workspace_id, self.binding_id, self.version, self.external_scope)):
            raise ValueError("external scope binding fields are required")
        require_digest(self.digest, "binding digest")
        expected = _digest(
            {
                "workspace_id": self.workspace_id,
                "binding_id": self.binding_id,
                "version": self.version,
                "external_scope": self.external_scope,
            }
        )
        if self.digest != expected:
            raise ValueError("binding digest does not match canonical binding")

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

    _ticket_lookup_projection = {
        "capability_id": "ticket_lookup",
        "operation": "read",
        "resource_kind": "ticket",
        "version": "m4.1",
    }
    _descriptors: Mapping[str, CapabilityDescriptor] = {
        "ticket_lookup": CapabilityDescriptor(
            **_ticket_lookup_projection,
            digest=_digest(_ticket_lookup_projection),
        )
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
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
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
        return AuthorizedExternalResource(
            reference_id=verified.reference_id,
            resource_kind=verified.resource_kind,
            provider_routing_handle=verified.provider_routing_handle,
            resource_identity_digest=verified.resource_identity_digest,
            resource_claims_digest=verified.resource_claims_digest,
            external_scope=binding.external_scope,
        )

    authorize = authorize_resource
