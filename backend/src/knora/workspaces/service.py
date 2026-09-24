from __future__ import annotations

from knora.access.identity import Identity
from knora.domain.errors import KnoraError
from knora.workspaces.ports import WorkspaceStore
from knora.workspaces.types import WorkspaceResolution, WorkspaceView


class WorkspaceService:
    """Own Workspace lifecycle and resolver policy; adapters own transactions."""

    def __init__(self, store: WorkspaceStore) -> None:
        self._store = store

    def resolve(self, identity: Identity, hint_id: str | None = None) -> WorkspaceResolution:
        return self._store.resolve(identity, hint_id)

    def create(self, identity: Identity, name: str, idempotency_key: str) -> WorkspaceView:
        normalized = name.strip()
        if not normalized or len(normalized) > 120:
            raise KnoraError("INVALID_WORKSPACE_NAME")
        if not idempotency_key or len(idempotency_key) > 255:
            raise KnoraError("INVALID_IDEMPOTENCY_KEY")
        return self._store.create(identity, normalized, idempotency_key)

    def list(
        self,
        identity: Identity,
        archived: bool | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ):
        if limit < 1 or limit > 100:
            raise KnoraError("INVALID_WORKSPACE_LIMIT")
        return self._store.list(identity, archived, cursor, limit)

    def read(self, identity: Identity, workspace_id: str) -> WorkspaceView:
        workspace = self._store.get(identity, workspace_id)
        if workspace is None:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        return workspace

    def rename(self, identity: Identity, workspace_id: str, name: str, expected_revision: int):
        normalized = name.strip()
        if not normalized or len(normalized) > 120:
            raise KnoraError("INVALID_WORKSPACE_NAME")
        return self._store.mutate(identity, workspace_id, expected_revision, name=normalized)

    def archive(self, identity: Identity, workspace_id: str, expected_revision: int):
        return self._store.mutate(identity, workspace_id, expected_revision, archived=True)

    def restore(self, identity: Identity, workspace_id: str, expected_revision: int):
        return self._store.mutate(identity, workspace_id, expected_revision, archived=False)
