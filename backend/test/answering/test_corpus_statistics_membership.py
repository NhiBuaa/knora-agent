"""Test for F08: verify corpus statistics do not serve stale cache when membership changes."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.domain.errors import KnoraError
from knora.ingestion.search_indexing import LexicalProfile


def test_corpus_statistics_not_stale_across_membership_changes() -> None:
    store = PostgresSearchIndexStore(MagicMock())
    profile = LexicalProfile("test", "tiktoken", "cl100k_base", 1.2, 0.75, 256, "b" * 64)

    generations = [
        SimpleNamespace(
            chunk_set_id="set1",
            document_version_id="ver1",
            lexical_profile=profile,
        )
    ]
    store.read_active_generations_in_snapshot = lambda *args: tuple(generations)  # type: ignore[method-assign]

    chunks = [
        SimpleNamespace(content="alpha", content_checksum=hashlib.sha256(b"alpha").hexdigest())
    ]
    session = SimpleNamespace(
        scalar=lambda stmt: SimpleNamespace(archived=False),
        scalars=lambda stmt: SimpleNamespace(all=lambda: list(chunks)),
    )

    stats_a = store.read_corpus_statistics_in_transaction(session, "workspace", "test")  # type: ignore[arg-type]
    assert stats_a.total_chunks == 1

    # Now change membership: new chunk_set with additional content
    generations[0] = SimpleNamespace(
        chunk_set_id="set2",
        document_version_id="ver2",
        lexical_profile=profile,
    )
    chunks.append(
        SimpleNamespace(
            content="beta gamma", content_checksum=hashlib.sha256(b"beta gamma").hexdigest()
        )
    )

    stats_b = store.read_corpus_statistics_in_transaction(session, "workspace", "test")  # type: ignore[arg-type]
    assert stats_b.total_chunks == 2
    assert stats_b is not stats_a
    assert stats_a.snapshot_id != stats_b.snapshot_id
    assert stats_a.statistics_digest != stats_b.statistics_digest

    # Cache reuse still revalidates authoritative chunk bytes before serving statistics.
    chunk_reads = MagicMock(side_effect=session.scalars)
    cached_session = SimpleNamespace(
        scalar=lambda stmt: SimpleNamespace(archived=False),
        scalars=chunk_reads,
    )
    cached = store.read_corpus_statistics_in_transaction(cached_session, "workspace", "test")  # type: ignore[arg-type]
    assert cached is stats_b
    assert chunk_reads.call_count == 1

    chunks[0].content = "corrupted"
    with pytest.raises(KnoraError) as rejected:
        store.read_corpus_statistics_in_transaction(cached_session, "workspace", "test")  # type: ignore[arg-type]
    assert rejected.value.code == "LEXICAL_RETRIEVAL_UNAVAILABLE"
