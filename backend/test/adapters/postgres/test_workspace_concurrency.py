"""Real database contract for Workspace provisioning and lifecycle locking."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from knora.access.identity import Identity
from knora.adapters.postgres.tables import WorkspaceIdentityTable, WorkspaceTable
from knora.adapters.postgres.workspace_admission import PostgresWorkspaceAdmissionStore
from knora.adapters.postgres.workspace_store import PostgresWorkspaceStore
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.workspaces.types import ResolutionState


@pytest.fixture
def workspace_store():
    from knora.infrastructure.settings import settings

    if not settings.database_url.endswith("/knora_issue110_task2"):
        pytest.skip("requires isolated knora_issue110_task2 database")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1 FROM workspace_create_requests LIMIT 1"))
    yield PostgresWorkspaceStore(sessionmaker(bind=engine, expire_on_commit=False))
    engine.dispose()


def identity():
    return Identity("https://issuer", f"task2-{uuid4()}")


def test_parallel_default_resolve_creates_one_workspace(workspace_store):
    owner = identity()
    start = Barrier(2)

    def resolve(_):
        start.wait()
        return workspace_store.resolve(owner)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(resolve, (1, 2)))
    assert first.state == second.state == ResolutionState.ACTIVE
    assert first.workspace.id == second.workspace.id
    assert first.workspace.name == "My Workspace"


def test_explicit_create_racing_resolve_keeps_one_initial_workspace(workspace_store):
    owner = identity()
    start = Barrier(2)

    def create():
        start.wait()
        return workspace_store.create(owner, "Personal", "create-1")

    def resolve():
        start.wait()
        return workspace_store.resolve(owner)

    with ThreadPoolExecutor(max_workers=2) as executor:
        create_future = executor.submit(create)
        resolve_future = executor.submit(resolve)
        created, resolved = create_future.result(), resolve_future.result()
    with workspace_store._session_factory() as session:
        rows = session.scalars(
            select(WorkspaceTable)
            .join(
                WorkspaceIdentityTable,
                WorkspaceTable.owner_identity_id == WorkspaceIdentityTable.id,
            )
            .where(
                WorkspaceIdentityTable.issuer == owner.issuer,
                WorkspaceIdentityTable.subject == owner.subject,
            )
        ).all()
    assert sum(row.name == "Personal" for row in rows) == 1
    assert sum(row.name == "My Workspace" for row in rows) <= 1
    assert len(rows) in {1, 2}
    assert created.id != ""
    assert resolved.workspace is not None


def test_parallel_same_key_create_returns_one_workspace(workspace_store):
    owner = identity()
    start = Barrier(2)

    def create(_):
        start.wait()
        return workspace_store.create(owner, "Shared", "same-key")

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(create, (1, 2)))
    assert first.id == second.id


def test_parallel_same_key_different_payload_has_one_conflict(workspace_store):
    owner = identity()
    start = Barrier(2)

    def create(name):
        start.wait()
        return workspace_store.create(owner, name, "collision")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(create, name)
            for name in ("One", "Two")
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except KnoraError as error:
                outcomes.append(error.code)
    assert len([value for value in outcomes if value == "IDEMPOTENCY_CONFLICT"]) == 1
    assert len([value for value in outcomes if not isinstance(value, str)]) == 1


def test_create_retry_returns_original_even_after_rename_and_rejects_new_payload(workspace_store):
    owner = identity()
    created = workspace_store.create(owner, "Original", "lost-response")
    renamed = workspace_store.mutate(owner, created.id, 0, name="Renamed")
    retry = workspace_store.create(owner, "Original", "lost-response")
    assert retry.id == created.id
    assert retry.name == renamed.name
    with pytest.raises(KnoraError, match="IDEMPOTENCY_CONFLICT"):
        workspace_store.create(owner, "Other", "lost-response")


def test_archive_restore_cas_and_archived_resolver_state(workspace_store):
    owner = identity()
    created = workspace_store.create(owner, "Only", "one")
    archived = workspace_store.mutate(owner, created.id, 0, archived=True)
    assert archived.revision == 1
    assert workspace_store.resolve(owner).state == ResolutionState.NO_ACTIVE_WORKSPACE
    with pytest.raises(KnoraError, match="REVISION_CONFLICT"):
        workspace_store.mutate(owner, created.id, 0, archived=False)
    assert workspace_store.mutate(owner, created.id, 1, archived=False).archived is False


def test_foreign_workspace_cannot_be_read_or_mutated(workspace_store):
    alice, bob = identity(), identity()
    created = workspace_store.create(alice, "Private", "private")
    assert workspace_store.get(bob, created.id) is None
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        workspace_store.mutate(bob, created.id, 0, archived=True)


def test_foreign_hint_and_equal_timestamp_use_owned_id_order(workspace_store):
    alice, bob = identity(), identity()
    first = workspace_store.create(alice, "First", "first")
    second = workspace_store.create(alice, "Second", "second")
    foreign = workspace_store.create(bob, "Foreign", "foreign")
    fixed = datetime(2024, 1, 1, tzinfo=UTC)
    with workspace_store._session_factory.begin() as session:
        for item in (first, second):
            session.get(WorkspaceTable, item.id).created_at = fixed
    expected = min(first.id, second.id)
    assert workspace_store.resolve(alice, foreign.id).workspace.id == expected
    assert workspace_store.resolve(alice, second.id).workspace.id == second.id


def test_pagination_and_archived_filter_are_owner_scoped(workspace_store):
    alice, bob = identity(), identity()
    first = workspace_store.create(alice, "First", "first")
    second = workspace_store.create(alice, "Second", "second")
    workspace_store.create(bob, "Foreign", "foreign")
    page1 = workspace_store.list(alice, limit=1)
    page2 = workspace_store.list(alice, cursor=page1.next_cursor, limit=1)
    assert {page1.items[0].id, page2.items[0].id} == {first.id, second.id}
    assert page2.next_cursor is None
    workspace_store.mutate(alice, first.id, 0, archived=True)
    assert {item.id for item in workspace_store.list(alice, archived=True).items} == {first.id}
    assert {item.id for item in workspace_store.list(alice, archived=False).items} == {second.id}


@pytest.mark.parametrize("cursor", ["a", "e30"])
def test_invalid_cursor_is_rejected_as_validation_error(workspace_store, cursor):
    owner = identity()
    workspace_store.create(owner, "First", "first")
    with pytest.raises(KnoraError, match="INVALID_WORKSPACE_CURSOR"):
        workspace_store.list(owner, cursor=cursor)


def test_archive_and_admit_ordering_is_serialized_for_two_workspaces(workspace_store):
    """A real PostgreSQL barrier race must never admit after an archive commits."""
    owner = identity()
    archived_candidate = workspace_store.create(owner, "Archive race", "archive-race")
    independent = workspace_store.create(owner, "Independent", "independent")
    admission_store = PostgresWorkspaceAdmissionStore(workspace_store._session_factory)
    principal = WorkspacePrincipal(archived_candidate.id, owner.subject)
    start = Barrier(2)

    def archive():
        start.wait()
        return workspace_store.mutate(owner, archived_candidate.id, 0, archived=True)

    def admit():
        start.wait()
        return admission_store.admit(
            principal=principal, operation="ask_question", operation_id="race-1"
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        archive_future = executor.submit(archive)
        admit_future = executor.submit(admit)
        archived = archive_future.result()
        try:
            admitted = admit_future.result()
        except KnoraError as error:
            admitted = error.code

    if admitted == "WORKSPACE_ARCHIVED":
        assert archived.archived is True
    else:
        assert admitted.workspace_id == archived_candidate.id
        assert archived.archived is True

    independent_admission = admission_store.admit(
        principal=WorkspacePrincipal(independent.id, owner.subject),
        operation="ask_question",
        operation_id="independent-1",
    )
    assert independent_admission.workspace_id == independent.id
