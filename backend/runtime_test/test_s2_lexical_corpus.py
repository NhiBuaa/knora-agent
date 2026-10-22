"""Authoritative lexical corpus reads in the owned PostgreSQL envelope."""

from dataclasses import replace

import pytest
import test_s2_search_index_store as lifecycle

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import DocumentTable
from knora.domain.errors import KnoraError
from knora.ingestion.search_indexing import StageReceipt

lexical_generation = lifecycle.lexical_generation


def _activate(generation):
    store = PostgresSearchIndexStore(SessionFactory)
    store.request_generation(generation, expected_revision=0)
    store.activate_ready(
        generation, StageReceipt(generation.generation_id, 1, generation.content_digest())
    )
    return store


def test_corpus_uses_active_generation_while_desired_rebuild_is_pending(lexical_generation):
    generation = lexical_generation
    store = _activate(generation)
    store.request_generation(
        replace(generation, generation_id="rebuild-" + generation.generation_id[:28], revision=2),
        expected_revision=1,
    )
    assert store.read_active_generations(generation.workspace_id, "fixture-only") == (generation,)


@pytest.mark.parametrize("invalid", ["foreign_workspace", "wrong_profile", "archived", "revision"])
def test_corpus_rejects_unavailable_authority(lexical_generation, invalid):
    generation = lexical_generation
    store = _activate(generation)
    workspace_id, policy = generation.workspace_id, "fixture-only"
    if invalid == "foreign_workspace":
        workspace_id = "foreign"
    elif invalid == "wrong_profile":
        policy = "other-profile"
    else:
        with SessionFactory.begin() as session:
            document = session.get(DocumentTable, generation.document_id)
            if invalid == "archived":
                document.archived = True
            else:
                document.revision += 1
    with pytest.raises(KnoraError) as caught:
        store.read_active_generations(workspace_id, policy)
    assert caught.value.code == "LEXICAL_RETRIEVAL_UNAVAILABLE"
