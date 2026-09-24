from sqlalchemy import inspect

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.workspace_store import PostgresWorkspaceStore


def test_workspace_store_reads_owner_without_exposing_unowned_workspace() -> None:
    if not inspect(SessionFactory.kw["bind"]).has_table("workspace_identities"):
        return

    store = PostgresWorkspaceStore(SessionFactory)
    assert store.owner_for("workspace-that-does-not-exist") is None
