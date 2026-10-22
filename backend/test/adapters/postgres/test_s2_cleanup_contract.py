"""Offline PostgreSQL authority checks for explicit stale projection cleanup."""

from types import SimpleNamespace

import pytest

from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import LexicalGenerationTable, LexicalHeadTable


@pytest.mark.parametrize("pointer", ["active_generation_id", "desired_generation_id"])
def test_cleanup_refuses_active_or_desired_generation_without_projection_call(monkeypatch, pointer):
    store = PostgresSearchIndexStore(None)
    generation = object()
    monkeypatch.setattr(store, "_decode_generation", lambda row: generation)
    row = SimpleNamespace(
        id="generation", workspace_id="workspace", document_id="document", status="requested"
    )
    head = SimpleNamespace(active_generation_id=None, desired_generation_id=None)
    setattr(head, pointer, "generation")

    class Session:
        def get(self, table, identity, **kwargs):
            if table is LexicalGenerationTable:
                if kwargs.get("with_for_update"):
                    assert locked, "lifecycle locks must precede the generation row lock"
                    assert kwargs.get("populate_existing") is True
                return row
            assert table is LexicalHeadTable
            return head

    removed = []
    locked = []
    monkeypatch.setattr(store, "_lock_document", lambda *args, **kwargs: locked.append(args))
    assert (
        store.cleanup_generation_in_transaction(Session(), "generation", removed.append)
        == "retained"
    )
    assert removed == []


@pytest.mark.parametrize("status", ["requested", "revoked", "active"])
def test_cleanup_locks_authority_then_removes_stale_generation(monkeypatch, status):
    store = PostgresSearchIndexStore(None)
    generation = object()
    monkeypatch.setattr(store, "_decode_generation", lambda row: generation)
    row = SimpleNamespace(
        id="generation", workspace_id="workspace", document_id="document", status=status
    )
    head = SimpleNamespace(active_generation_id=None, desired_generation_id=None)

    class Session:
        def get(self, table, identity, **kwargs):
            if table is LexicalGenerationTable:
                if kwargs.get("with_for_update"):
                    assert locked, "lifecycle locks must precede the generation row lock"
                    assert kwargs.get("populate_existing") is True
                return row
            assert table is LexicalHeadTable
            return head

    removed = []
    locked = []
    monkeypatch.setattr(
        store, "_lock_document", lambda *args, **kwargs: locked.append(args) or (None, None)
    )
    assert (
        store.cleanup_generation_in_transaction(Session(), "generation", removed.append)
        == "removed"
    )
    assert removed == [generation]
    assert len(locked) == 1


def test_cleanup_missing_generation_never_calls_projection():
    class Session:
        def get(self, *a, **k):
            return None

    removed = []
    assert (
        PostgresSearchIndexStore(None).cleanup_generation_in_transaction(
            Session(), "missing", removed.append
        )
        == "missing"
    )
    assert removed == []
