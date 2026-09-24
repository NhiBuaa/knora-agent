from __future__ import annotations

from typing import Protocol

from knora.access.identity import Identity
from knora.workspaces.types import WorkspaceView


class WorkspaceStore(Protocol):
    def owner_for(self, workspace_id: str) -> Identity | None: ...

    def get(self, identity: Identity, workspace_id: str) -> WorkspaceView | None: ...
