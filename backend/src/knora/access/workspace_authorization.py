from __future__ import annotations

from typing import Protocol

from knora.access.identity import Identity
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


class WorkspaceOwnershipStore(Protocol):
    def owner_for(self, workspace_id: str) -> Identity | None: ...


class WorkspaceAuthorizer:
    """Authorizes a validated identity against persisted Workspace ownership."""

    def __init__(self, store: WorkspaceOwnershipStore) -> None:
        self._store = store

    def authorize(
        self,
        identity: Identity,
        workspace_id: str,
        capability: str,
    ) -> WorkspacePrincipal:
        owner = self._store.owner_for(workspace_id)
        if owner is None or owner != Identity(identity.issuer, identity.subject):
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        if capability not in identity.capabilities:
            raise KnoraError("CAPABILITY_ACCESS_DENIED")
        return WorkspacePrincipal(
            workspace_id=workspace_id,
            key_id=identity.subject,
            capabilities=identity.capabilities,
        )
