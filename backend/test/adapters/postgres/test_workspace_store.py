from uuid import uuid4

import pytest
from sqlalchemy import inspect

from knora.access.identity import Identity
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.workspace_store import PostgresWorkspaceStore
from knora.domain.errors import KnoraError
from knora.workspaces.service import WorkspaceService


def test_workspace_store_reads_owner_without_exposing_unowned_workspace() -> None:
    if not inspect(SessionFactory.kw["bind"]).has_table("workspace_identities"):
        return

    store = PostgresWorkspaceStore(SessionFactory)
    assert store.owner_for("workspace-that-does-not-exist") is None


def test_workspace_search_filters_before_pagination_and_keeps_owner_and_archive_scope():
    store = PostgresWorkspaceStore(SessionFactory)
    owner = Identity("https://issuer", str(uuid4()))
    other = Identity("https://issuer", str(uuid4()))
    store.create(owner, "Unrelated", "first")
    target = store.create(owner, "Budget 100%_ FINAL", "second")
    archived = store.create(owner, "Budget 100%_ old", "third")
    store.mutate(owner, archived.id, 0, archived=True)
    store.create(other, "Budget 100%_ foreign", "foreign")

    page = store.list(owner, archived=False, limit=1, q="  100%_  ")
    assert [item.id for item in page.items] == [target.id]
    assert page.next_cursor is None
    assert [item.id for item in store.list(owner, archived=True, q="budget").items] == [archived.id]
    assert store.list(owner, q="100%X").items == ()
    assert [item.id for item in store.list(owner, archived=False, q="final").items] == [target.id]


def test_workspace_search_cursor_is_bound_to_normalized_query_and_archive_filter():
    store = PostgresWorkspaceStore(SessionFactory)
    owner = Identity("https://issuer", str(uuid4()))
    first = store.create(owner, "Budget one", "first")
    second = store.create(owner, "Budget two", "second")
    page = store.list(owner, archived=False, limit=1, q=" Budget ")
    assert [item.id for item in page.items] == [first.id]
    assert page.next_cursor is not None
    following = store.list(owner, archived=False, cursor=page.next_cursor, q="budget")
    assert [item.id for item in following.items] == [second.id]
    for query, archived in (("other", False), (None, False), ("budget", True)):
        with pytest.raises(KnoraError, match="INVALID_WORKSPACE_CURSOR"):
            store.list(owner, archived=archived, cursor=page.next_cursor, q=query)


def test_workspace_search_normalizes_blank_query_and_rejects_overlong_query():
    store = PostgresWorkspaceStore(SessionFactory)
    owner = Identity("https://issuer", str(uuid4()))
    workspace = store.create(owner, "One", "one")
    service = WorkspaceService(store)
    assert service.list(owner, q="  ").items == service.list(owner).items
    assert service.list(owner, q=" " + "x" * 200 + " ").items == ()
    assert service.list(owner, q=" " + "\u0130" * 200 + " ").items == ()
    with pytest.raises(KnoraError, match="INVALID_WORKSPACE_QUERY"):
        service.list(owner, q="x" * 201)
    with pytest.raises(KnoraError, match="INVALID_WORKSPACE_QUERY"):
        store.list(owner, q="x" * 201)
    assert service.list(owner).items[0].id == workspace.id


@pytest.mark.parametrize("first_query, next_query", [("İ", "i"), ("i", "İ")])
def test_workspace_unicode_search_uses_postgres_case_semantics_for_matching_and_cursor(
    first_query, next_query
):
    store = PostgresWorkspaceStore(SessionFactory)
    owner = Identity("https://issuer", str(uuid4()))
    first = store.create(owner, "İstanbul one", "first")
    second = store.create(owner, "İstanbul two", "second")
    page = store.list(owner, archived=False, limit=1, q=first_query)
    assert [item.id for item in page.items] == [first.id]
    assert page.next_cursor is not None
    following = store.list(owner, archived=False, cursor=page.next_cursor, q=f" {next_query} ")
    assert [item.id for item in following.items] == [second.id]
