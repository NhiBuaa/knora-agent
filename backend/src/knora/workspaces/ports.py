from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from knora.access.identity import Identity
from knora.domain.access import WorkspacePrincipal
from knora.workspaces.types import WorkspacePage, WorkspaceResolution, WorkspaceView


@dataclass(frozen=True, slots=True)
class WorkspaceAdmission:
    id: str
    workspace_id: str
    operation: str
    operation_id: str
    admitted_at: datetime


class WorkspaceAdmissionStore(Protocol):
    """Durably admits a user-originated mutation before its first side effect."""

    def admit(
        self,
        *,
        principal: WorkspacePrincipal,
        operation: str,
        operation_id: str,
    ) -> WorkspaceAdmission: ...


class WorkspaceStore(Protocol):
    def owner_for(self, workspace_id: str) -> Identity | None: ...

    def get(self, identity: Identity, workspace_id: str) -> WorkspaceView | None: ...

    def resolve(self, identity: Identity, hint_id: str | None = None) -> WorkspaceResolution: ...

    def create(self, identity: Identity, name: str, idempotency_key: str) -> WorkspaceView: ...

    def list(
        self,
        identity: Identity,
        archived: bool | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> WorkspacePage: ...

    def mutate(
        self,
        identity: Identity,
        workspace_id: str,
        expected_revision: int,
        *,
        archived: bool | None = None,
        name: str | None = None,
    ) -> WorkspaceView: ...
