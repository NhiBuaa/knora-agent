"""Q9 offline contract for the bounded native BM25 population."""

from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_bm25_contract import LexicalStore, candidate, execute, observation

from knora.adapters.postgres import lexical_retrieval
from knora.adapters.postgres.tables import ChunkTable, DocumentTable, DocumentVersionTable
from knora.answering import stores
from knora.answering.lexical import validate_bm25_result
from knora.domain.errors import KnoraError
from knora.ingestion.lexical_population import VerifiedLexicalPopulation


@pytest.mark.asyncio
async def test_full_native_top200_ties_keep_primary_top8_and_expose_unknown_boundary():
    ranked = tuple(
        replace(candidate(i, score=2), bm25_rank=rank)
        for rank, i in enumerate(range(200, 0, -1), start=1)
    )
    store = LexicalStore(ranked[:8])
    store.result = replace(
        store.result,
        branch_observations=tuple(
            observation(item)
            if item.bm25_rank <= 8
            else observation(item, status="RANK_LIMIT", reason="RANK_LIMIT")
            for item in ranked
        ),
    )

    await execute(store)

    assert store.traces[0].retrieved_chunk_ids == tuple(item.chunk_id for item in ranked[:8])
    policy = store.traces[0].provider_metadata["retrieval"]["score_policy"]
    assert policy["candidate_limit"] == 8
    assert policy["query_limit"] == 200
    assert policy["tie_order"] == "native"
    assert policy["tie_boundary"] == "unknown"
    assert policy["beyond_limit"] == "unknown"


@pytest.mark.asyncio
async def test_complete_population_traces_canonical_ties_and_no_unseen_rows():
    store = LexicalStore((candidate(1, score=2), candidate(2, score=2)))

    await execute(store)

    policy = store.traces[0].provider_metadata["retrieval"]["score_policy"]
    assert policy["candidate_limit"] == 8
    assert policy["query_limit"] == 200
    assert policy["tie_order"] == "score_desc_chunk_id_asc"
    assert policy["tie_boundary"] == "complete"
    assert policy["beyond_limit"] == "none"


def test_incomplete_population_rejects_uncanonical_ties():
    ranked = (
        replace(candidate(2, score=2), bm25_rank=1),
        replace(candidate(1, score=2), bm25_rank=2),
    )
    store = LexicalStore(ranked)

    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        validate_bm25_result(
            store.result,
            workspace_id="workspace",
            configuration=stores.RetrievalConfiguration.bm25_top8_v1(),
        )


@pytest.mark.parametrize("size", [2, 200, 201])
def test_native_population_rejects_sparse_or_oversized_rank_windows(size):
    ranked = tuple(
        replace(candidate(i, score=1000 - i), bm25_rank=i + 1) for i in range(1, size + 1)
    )
    store = LexicalStore(ranked[:7])
    store.result = replace(
        store.result,
        branch_observations=tuple(
            observation(item)
            if item.bm25_rank <= 8
            else observation(item, status="RANK_LIMIT", reason="RANK_LIMIT")
            for item in ranked
        ),
    )
    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        validate_bm25_result(
            store.result,
            workspace_id="workspace",
            configuration=stores.RetrievalConfiguration.bm25_top8_v1(),
        )


def test_one_top200_query_supplies_primary_top8_without_refill(monkeypatch):
    content = "Fact."
    checksum = sha256(content.encode("utf-8")).hexdigest()
    profile = SimpleNamespace(id="bm25-word-frozen47-population-v1", digest=lambda: "digest")
    generation = SimpleNamespace(
        workspace_id="workspace",
        document_id="doc",
        document_version_id="version",
        chunk_set_id="chunks",
        generation_id="index-1",
        lexical_profile=profile,
        chunks=tuple(
            SimpleNamespace(chunk_id=f"chunk-{i}", ordinal=i, content_checksum=checksum)
            for i in range(1, 10)
        ),
    )

    class Authority:
        def __init__(self, session_factory):
            pass

        def read_active_generations(self, workspace_id, lexical_policy_id):
            return (generation,)

        def revalidate_lexical_snapshot_in_transaction(
            self, session, workspace_id, profile_id, snapshots
        ):
            pass

    # The Q9 case isolates one-query ordering; real population content checks have separate tests.
    population = Mock(spec=VerifiedLexicalPopulation)
    population.profile = profile

    class Session:
        def scalars(self, statement):
            return SimpleNamespace(all=lambda: ["doc"])

        def get(self, model, identity):
            if model is DocumentVersionTable:
                return SimpleNamespace(document_id="doc", raw_sha256="a" * 64)
            if model is DocumentTable:
                return SimpleNamespace(id="doc", source_key="policy", source_name="policy.pdf")
            assert model is ChunkTable
            i = int(identity.split("-")[1])
            return SimpleNamespace(
                id=identity,
                chunk_set_id="chunks",
                ordinal=i,
                content_checksum=checksum,
                content=content,
                heading_path=(),
                start_line=1,
                end_line=1,
                token_count=1,
                page_start=None,
                page_end=None,
                start_offset=None,
                end_offset=None,
            )

    class Factory:
        @contextmanager
        def begin(self):
            yield Session()

    class Projection:
        calls = 0

        def query(self, snapshot, query_text, *, limit):
            self.calls += 1
            assert limit == 200
            return tuple(
                {
                    "generation_id": "index-1",
                    "chunk_id": f"chunk-{i}",
                    "score": 10 - i,
                    "rank": i,
                    "score_policy_digest": "digest",
                }
                for i in range(1, 10)
            )

    monkeypatch.setattr(lexical_retrieval, "PostgresSearchIndexStore", Authority)
    projection = Projection()
    result = lexical_retrieval.retrieve_lexical_candidates(
        Factory(),
        "workspace",
        "Fact?",
        stores.RetrievalConfiguration.bm25_top8_v1(),
        projection,
        population=population,
    )

    assert projection.calls == 1
    assert [candidate.chunk_id for candidate in result.candidates] == [
        f"chunk-{i}" for i in range(1, 9)
    ]
    assert result.branch_observations[-1].status == "RANK_LIMIT"


def test_diagnostic_identity_keeps_top200_and_primary_has_its_own_identity():
    diagnostic = stores.RetrievalConfiguration.bm25_diagnostic_v1()
    primary = stores.RetrievalConfiguration.bm25_top8_v1()
    assert diagnostic.id == "retrieval-bm25-diagnostic-v1"
    assert diagnostic.candidate_k == 200
    assert primary.id == "retrieval-bm25-top8-v1"
    assert primary.candidate_k == 8
    assert (
        replace(
            primary,
            id=diagnostic.id,
            candidate_k=200,
            lexical_policy_id=diagnostic.lexical_policy_id,
        )
        == diagnostic
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("query_limit", 8),
        ("candidate_limit", 200),
        ("tie_order", "native"),
        ("tie_boundary", "unknown"),
        ("beyond_limit", "unknown"),
    ],
)
async def test_reader_rejects_fabricated_primary_window_policy(field, value):
    from test_bm25_contract import generation, projections

    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    store = LexicalStore()
    await execute(store)
    store.traces[0].provider_metadata["retrieval"]["score_policy"][field] = value
    with pytest.raises(LookupError, match="lexical trace provenance"):
        project_bm25_trace(
            trace_id="trace",
            record=store.traces[0],
            candidates=projections(store),
            authorized_generations=(generation(),),
        )


@pytest.mark.asyncio
async def test_reader_accepts_full_window_native_ties_without_refilling_primary():
    from test_bm25_contract import generation, projections

    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    ranked = tuple(
        replace(candidate(i, score=2), bm25_rank=rank)
        for rank, i in enumerate(range(200, 0, -1), 1)
    )
    store = LexicalStore(ranked[:8])
    store.result = replace(
        store.result,
        branch_observations=tuple(
            observation(c)
            if c.bm25_rank <= 8
            else observation(c, status="RANK_LIMIT", reason="RANK_LIMIT")
            for c in ranked
        ),
    )
    await execute(store)
    trace = project_bm25_trace(
        trace_id="trace",
        record=store.traces[0],
        candidates=projections(store),
        authorized_generations=(generation(),),
    )
    assert [c.chunk_id for c in trace.candidates] == [c.chunk_id for c in ranked[:8]]
    assert len(trace.branch_observations) == 200


@pytest.mark.asyncio
async def test_reader_preserves_historical_diagnostic_policy():
    from test_bm25_contract import generation, projections

    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    store = LexicalStore(lexical_policy_id="bm25-unicode-word-v1")
    await execute(store, configuration=stores.RetrievalConfiguration.bm25_diagnostic_v1())
    store.traces[0].provider_metadata["retrieval"]["score_policy"] = {
        "id": "bm25-raw-no-cutoff-v1",
        "score_kind": "bm25",
        "numeric_cutoff": None,
        "cutoff_status": "not_calibrated",
        "candidate_limit": 200,
        "observed_scope": "authorized_top_k",
        "beyond_limit": "unknown",
    }
    trace = project_bm25_trace(
        trace_id="trace",
        record=store.traces[0],
        candidates=projections(store),
        authorized_generations=(replace(generation(), lexical_policy_id="bm25-unicode-word-v1"),),
    )
    assert trace.retrieval_configuration_id == "retrieval-bm25-diagnostic-v1"
    assert len(trace.candidates) == 1


def test_primary_and_upload_fixture_bind_distinct_population_profiles():
    primary = stores.RetrievalConfiguration.bm25_top8_v1()
    fixture = stores.RetrievalConfiguration.bm25_upload_fixture_top8_v1()
    assert primary.lexical_policy_id == "bm25-word-frozen47-population-v1"
    assert fixture.id == "retrieval-bm25-upload-fixture-top8-v1"
    assert fixture.lexical_policy_id == "bm25-word-upload-fixture-population-v1"
    assert replace(fixture, id=primary.id, lexical_policy_id=primary.lexical_policy_id) == primary
    assert (
        stores.RetrievalConfiguration.bm25_diagnostic_v1().lexical_policy_id
        == "bm25-unicode-word-v1"
    )


@pytest.mark.asyncio
async def test_reader_resolves_the_upload_fixture_configuration_without_dense_provenance():
    from test_bm25_contract import generation, projections

    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    config = stores.RetrievalConfiguration.bm25_upload_fixture_top8_v1()
    store = LexicalStore(lexical_policy_id=config.lexical_policy_id)
    await execute(store, configuration=config)
    trace = project_bm25_trace(
        trace_id="trace",
        record=store.traces[0],
        candidates=projections(store),
        authorized_generations=(replace(generation(), lexical_policy_id=config.lexical_policy_id),),
    )
    assert trace.retrieval_configuration_id == config.id
    assert trace.embedding_configuration_id is None
    assert trace.candidates[0].bm25_contribution["raw_score"] == 12.5
