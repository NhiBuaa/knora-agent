"""Public serving must follow the selected strategy and authoritative activation."""

from dataclasses import replace

import pytest
import test_s2_search_index_store as lifecycle
from test_s2_lexical_retrieval import _structural_population

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import LexicalGenerationTable
from knora.answering.stores import RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.search_indexing import StageReceipt

lexical_generation = lifecycle.lexical_generation


def _read(generation):
    return PostgresDocumentReader(
        SessionFactory,
        lexical_population=_structural_population(generation),
        deployed_retrieval_configuration=replace(
            RetrievalConfiguration.bm25_diagnostic_v1(), lexical_policy_id="fixture-only"
        ),
    ).read_document(
        workspace_id=generation.workspace_id,
        document_id=generation.document_id,
        principal=WorkspacePrincipal(generation.workspace_id, "s2-readiness"),
    )


def test_successful_extraction_does_not_mean_lexical_ready(lexical_generation):
    store = PostgresSearchIndexStore(SessionFactory)
    store.request_generation(lexical_generation, expected_revision=0)
    projection = _read(lexical_generation)
    assert projection.lexical_readiness == "not_indexed"
    assert projection.answer_availability == "unavailable"
    assert projection.served_document_version_id is None
    assert projection.embedding_readiness == "not_indexed"


def test_activated_lexical_only_document_is_available_without_embedding(lexical_generation):
    generation = lexical_generation
    store = PostgresSearchIndexStore(SessionFactory)
    store.request_generation(generation, expected_revision=0)
    store.activate_ready(
        generation, StageReceipt(generation.generation_id, 1, generation.content_digest())
    )
    projection = _read(generation)
    assert projection.lexical_readiness == "ready"
    assert projection.answer_availability == "available"
    assert projection.served_document_version_id == generation.document_version_id
    assert projection.serving_state == "current"
    assert projection.embedding_readiness == "not_indexed"


@pytest.mark.parametrize("invalid", ["revoke", "archive", "revision", "receipt"])
def test_invalid_lexical_generation_cannot_be_presented_as_serving(lexical_generation, invalid):
    from knora.adapters.postgres.tables import DocumentTable

    generation = lexical_generation
    store = PostgresSearchIndexStore(SessionFactory)
    store.request_generation(generation, expected_revision=0)
    store.activate_ready(
        generation, StageReceipt(generation.generation_id, 1, generation.content_digest())
    )
    if invalid == "revoke":
        store.revoke(workspace_id=generation.workspace_id, document_id=generation.document_id)
    else:
        with SessionFactory.begin() as session:
            document = session.get(DocumentTable, generation.document_id)
            if invalid == "archive":
                document.archived = True
            elif invalid == "revision":
                document.revision += 1
            else:
                session.get(LexicalGenerationTable, generation.generation_id).acknowledged_count = 0
    projection = _read(generation)
    assert projection.lexical_readiness != "ready"
    assert projection.answer_availability == "unavailable"
    assert projection.served_document_version_id is None
