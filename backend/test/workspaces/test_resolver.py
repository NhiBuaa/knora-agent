from datetime import UTC, datetime

import pytest

from knora.access.identity import Identity
from knora.domain.errors import KnoraError
from knora.workspaces.service import WorkspaceService
from knora.workspaces.types import ResolutionState, WorkspaceResolution, WorkspaceView


class Store:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.calls = []

    def resolve(self, identity, hint_id=None):
        active = sorted(
            (w for w in self.items if not w.archived), key=lambda w: (w.created_at, w.id)
        )
        if not self.items:
            created = self.create(identity, "My Workspace", "resolver")
            return WorkspaceResolution(ResolutionState.ACTIVE, created)
        if not active:
            return WorkspaceResolution(ResolutionState.NO_ACTIVE_WORKSPACE, None)
        hinted = next((w for w in active if w.id == hint_id), None)
        return WorkspaceResolution(ResolutionState.ACTIVE, hinted or active[0])

    def create(self, identity, name, idempotency_key):
        self.calls.append((identity.subject, name, idempotency_key))
        existing = next((w for w in self.items if w.name == name and w.id == idempotency_key), None)
        if existing:
            return existing
        value = WorkspaceView(
            id=idempotency_key, name=name, archived=False, revision=0, created_at=datetime.now(UTC)
        )
        self.items.append(value)
        return value

    def get(self, identity, workspace_id):
        value = next((w for w in self.items if w.id == workspace_id), None)
        if value is None:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        return value

    def list(self, identity, archived=None, cursor=None, limit=20):
        return [w for w in self.items if archived is None or w.archived == archived]

    def mutate(self, identity, workspace_id, expected_revision, archived=None, name=None):
        current = self.get(identity, workspace_id)
        if current.revision != expected_revision:
            raise KnoraError("REVISION_CONFLICT")
        if archived is not None and current.archived == archived:
            return current
        value = WorkspaceView(
            current.id,
            name or current.name,
            archived if archived is not None else current.archived,
            current.revision + 1,
            current.created_at,
        )
        self.items[self.items.index(current)] = value
        return value


identity = Identity("https://issuer", "alice", ("documents:read",))


def view(workspace_id, name, *, archived=False, created_at=None):
    return WorkspaceView(workspace_id, name, archived, 0, created_at or datetime.now(UTC))


def test_resolve_when_no_workspaces_creates_default_once():
    store = Store()
    result = WorkspaceService(store).resolve(identity)
    assert result.state == ResolutionState.ACTIVE
    assert result.workspace.name == "My Workspace"
    assert len(store.items) == 1


def test_resolve_when_all_archived_does_not_create_workspace():
    store = Store([view("archived", "Old", archived=True)])
    result = WorkspaceService(store).resolve(identity)
    assert result.state == ResolutionState.NO_ACTIVE_WORKSPACE
    assert result.workspace is None
    assert len(store.items) == 1


def test_resolve_foreign_hint_falls_back_to_stable_first_active():
    first = view("first", "First", created_at=datetime(2024, 1, 1, tzinfo=UTC))
    second = view("second", "Second", created_at=datetime(2024, 1, 2, tzinfo=UTC))
    result = WorkspaceService(Store([second, first])).resolve(identity, "foreign")
    assert result.workspace.id == "first"


def test_archive_and_restore_require_expected_revision():
    store = Store([view("one", "One")])
    service = WorkspaceService(store)
    archived = service.archive(identity, "one", 0)
    assert archived.archived is True
    restored = service.restore(identity, "one", 1)
    assert restored.archived is False
    with pytest.raises(KnoraError, match="REVISION_CONFLICT"):
        service.archive(identity, "one", 0)


def test_create_rejects_blank_or_overlong_name():
    service = WorkspaceService(Store())
    with pytest.raises(KnoraError, match="INVALID_WORKSPACE_NAME"):
        service.create(identity, "  ", "create-1")
    with pytest.raises(KnoraError, match="INVALID_WORKSPACE_NAME"):
        service.create(identity, "x" * 121, "create-2")
