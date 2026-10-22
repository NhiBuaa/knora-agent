"""PostgreSQL text/provenance hydration around one projection query."""

from dataclasses import replace
from hashlib import sha256
from unittest.mock import Mock

import pytest
import test_s2_search_index_store as lifecycle
from sqlalchemy import text

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.lexical_retrieval import retrieve_lexical_candidates
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import ChunkTable, DocumentTable
from knora.answering.lexical import validate_bm25_result
from knora.answering.stores import RetrievalConfiguration
from knora.domain.errors import KnoraError
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.search_indexing import LexicalProjectionUnavailable, StageReceipt

lexical_generation = lifecycle.lexical_generation


def _structural_population(generation):
    # These cases isolate PG/query fencing; full measured-population acceptance is separate.
    population = Mock(spec=VerifiedLexicalPopulation)
    population.profile = generation.lexical_profile
    return population


def _ready(generation):
    checksum = sha256("hạn mức 42".encode()).hexdigest()
    generation = replace(
        generation, chunks=(replace(generation.chunks[0], content_checksum=checksum),)
    )
    with SessionFactory.begin() as session:
        session.get(ChunkTable, generation.chunks[0].chunk_id).content_checksum = checksum
    store = PostgresSearchIndexStore(SessionFactory)
    store.request_generation(generation, expected_revision=0)
    store.activate_ready(
        generation, StageReceipt(generation.generation_id, 1, generation.content_digest())
    )
    return store, generation


class Projection:
    def __init__(self, generation, *, changed=None):
        self.generation, self.changed = generation, changed

    def query(self, snapshot, query_text, *, limit):
        assert limit == 200 and query_text == "42"
        assert snapshot.generation_ids == (self.generation.generation_id,)
        if self.changed == "outage":
            raise LexicalProjectionUnavailable("fixture outage")
        if self.changed in {"archive", "checksum"}:
            with SessionFactory.begin() as session:
                session.execute(text("SET LOCAL lock_timeout='1s'"))
                if self.changed == "archive":
                    session.get(DocumentTable, self.generation.document_id).archived = True
                else:
                    session.get(ChunkTable, self.generation.chunks[0].chunk_id).content = "tampered"
        return (
            {
                "chunk_id": self.generation.chunks[0].chunk_id,
                "generation_id": self.generation.generation_id,
                "score": 2.5,
                "rank": 1,
                "score_policy_digest": self.generation.lexical_profile.digest(),
            },
        )


def test_retrieval_loads_text_and_citation_identity_from_postgres(lexical_generation):
    store, generation = _ready(lexical_generation)
    configuration = replace(
        RetrievalConfiguration.bm25_diagnostic_v1(), lexical_policy_id="fixture-only"
    )
    result = retrieve_lexical_candidates(
        SessionFactory,
        generation.workspace_id,
        "42",
        configuration,
        Projection(generation),
        population=_structural_population(generation),
    )
    validate_bm25_result(result, workspace_id=generation.workspace_id, configuration=configuration)
    candidate = result.candidates[0]
    assert (
        candidate.content,
        candidate.source_name,
        candidate.bm25_score,
        candidate.bm25_rank,
    ) == ("hạn mức 42", "isolated.pdf", 2.5, 1)
    assert candidate.embedding_set_id is None


def test_opt_in_answering_facade_retrieves_lexical_without_embedding(lexical_generation):
    _, generation = _ready(lexical_generation)
    configuration = replace(
        RetrievalConfiguration.bm25_diagnostic_v1(), lexical_policy_id="fixture-only"
    )
    store = PostgresAnsweringStore(
        SessionFactory,
        lexical_index=Projection(generation),
        lexical_population=_structural_population(generation),
    )
    store.require_lexical_corpus(generation.workspace_id, "fixture-only")
    result = store.retrieve_candidates(
        workspace_id=generation.workspace_id,
        query_text="42",
        query_vector=None,
        embedding_configuration=None,
        retrieval_configuration=configuration,
    )
    assert [candidate.content for candidate in result.candidates] == ["hạn mức 42"]


@pytest.mark.parametrize("changed", ["archive", "checksum", "outage"])
def test_retrieval_never_turns_invalid_authority_or_outage_into_empty_evidence(
    lexical_generation, changed
):
    store, generation = _ready(lexical_generation)
    configuration = replace(
        RetrievalConfiguration.bm25_diagnostic_v1(), lexical_policy_id="fixture-only"
    )
    with pytest.raises(KnoraError) as caught:
        retrieve_lexical_candidates(
            SessionFactory,
            generation.workspace_id,
            "42",
            configuration,
            Projection(generation, changed=changed),
            population=_structural_population(generation),
        )
    assert caught.value.code == "LEXICAL_RETRIEVAL_UNAVAILABLE"
