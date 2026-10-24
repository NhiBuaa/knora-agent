"""Test for F08: verify corpus statistics do not serve stale cache when membership changes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.ingestion.search_indexing import LexicalProfile


def test_corpus_statistics_not_stale_across_membership_changes() -> None:
    store = PostgresSearchIndexStore(MagicMock())
    profile = LexicalProfile("test", "tiktoken", "cl100k_base", 1.2, 0.75, 256, "b" * 64)

    generations = [SimpleNamespace(chunk_set_id="set1", lexical_profile=profile)]
    store.read_active_generations_in_snapshot = lambda *args: tuple(generations)  # type: ignore[method-assign]

    chunks = [SimpleNamespace(content="alpha")]
    session = SimpleNamespace(
        scalar=lambda stmt: SimpleNamespace(archived=False),
        scalars=lambda stmt: SimpleNamespace(all=lambda: list(chunks)),
    )

    old = store.read_corpus_statistics_in_transaction(session, "workspace", "test")  # type: ignore[arg-type]
    assert old.total_chunks == 1

    # Now change membership: new chunk_set with additional content
    generations[0] = SimpleNamespace(chunk_set_id="set2", lexical_profile=profile)
    chunks.append(SimpleNamespace(content="beta gamma"))

    new = store.read_corpus_statistics_in_transaction(session, "workspace", "test")  # type: ignore[arg-type]
    assert new.total_chunks == 2
    assert new is not old
