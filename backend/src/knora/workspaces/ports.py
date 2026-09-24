from __future__ import annotations

from typing import Protocol

from knora.access.identity import Identity
from knora.workspaces.types import WorkspacePage, WorkspaceResolution, WorkspaceView


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
