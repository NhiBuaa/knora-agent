"""Comprehensive test contracts for dense and hybrid retrieval (Task 5)."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from knora.adapters.postgres import lexical_retrieval
from knora.adapters.qdrant.search_index import (
    AuthorizedLexicalSnapshot,
    ProjectionResponseError,
    QdrantSearchIndex,
)
from knora.answering import stores
from knora.answering.interface import QuestionCommand
from knora.answering.lexical import validate_dense_result, validate_hybrid_result
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalProfile,
    lexical_point_id,
)
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration
from knora.providers.generation import GenerationResult


@pytest.fixture
def test_profile() -> LexicalProfile:
    return LexicalProfile(
        id="bm25-word-frozen47-population-v1",
        tokenizer="tiktoken",
        tokenizer_version="cl100k_base",
        k1=1.2,
        b=0.75,
        avg_len=128.0,
        statistics_digest="d" * 64,
    )


@pytest.fixture
def test_embedding_config() -> EmbeddingConfiguration:
    return EmbeddingConfiguration(
        id="cloudflare-bge-base-en-v1.5",
        dimensions=768,
        distance_metric="cosine",
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
    )


@pytest.fixture
def authorized_snapshot(test_profile: LexicalProfile) -> AuthorizedLexicalSnapshot:
    return AuthorizedLexicalSnapshot(
        workspace_id="ws-tenant-1",
        generation_ids=("gen-1",),
        profile_id=test_profile.id,
        profile_digest=test_profile.digest(),
    )


@pytest.fixture
def qdrant_index(
    test_profile: LexicalProfile, test_embedding_config: EmbeddingConfiguration
) -> QdrantSearchIndex:
    return QdrantSearchIndex(
        collection_name="test_collection",
        profile=test_profile,
        embedding_configuration=test_embedding_config,
        turbo_quant=True,
    )


def test_dense_query_body_prefetches_with_scope_filter_and_turbo_params(
    qdrant_index: QdrantSearchIndex, authorized_snapshot: AuthorizedLexicalSnapshot
) -> None:
    query_vector = [0.1] * 768
    body = qdrant_index.dense_query_body(authorized_snapshot, query_vector, limit=200)

    assert body["using"] == "dense"
    assert body["limit"] == 200
    assert body["with_payload"] is True
    assert body["params"]["hnsw_ef"] == 256
    assert body["params"]["quantization"]["rescore"] is True
    assert body["params"]["quantization"]["oversampling"] == 2.0

    scope = body["filter"]["must"]
    assert {"key": "workspace_id", "match": {"value": "ws-tenant-1"}} in scope
    assert {"key": "generation_id", "match": {"any": ["gen-1"]}} in scope
    assert {
        "key": "profile_digest",
        "match": {"value": authorized_snapshot.profile_digest},
    } in scope


def test_hybrid_query_body_has_both_prefetches_and_dbsf_fusion(
    qdrant_index: QdrantSearchIndex, authorized_snapshot: AuthorizedLexicalSnapshot
) -> None:
    query_vector = [0.1] * 768
    body = qdrant_index.hybrid_query_body(
        authorized_snapshot,
        "test query text",
        query_vector,
        dense_limit=200,
        sparse_limit=200,
        final_limit=100,
    )

    assert body["limit"] == 100
    assert body["with_payload"] is True
    assert body["query"] == {"fusion": "dbsf"}

    prefetches = body["prefetch"]
    assert len(prefetches) == 2

    sparse_pf = next(p for p in prefetches if p["using"] == "bm25")
    assert sparse_pf["limit"] == 200
    assert "filter" in sparse_pf
    assert sparse_pf["params"]["idf"]["corpus"] == sparse_pf["filter"]

    dense_pf = next(p for p in prefetches if p["using"] == "dense")
    assert dense_pf["limit"] == 200
    assert dense_pf["params"]["hnsw_ef"] == 256
    assert dense_pf["params"]["quantization"]["rescore"] is True
    assert dense_pf["params"]["quantization"]["oversampling"] == 2.0
    assert "filter" in dense_pf


def test_parse_response_rejects_foreign_and_malformed_points(
    qdrant_index: QdrantSearchIndex, authorized_snapshot: AuthorizedLexicalSnapshot
) -> None:
    valid_pt_id = lexical_point_id("gen-1", "chunk-1")

    # Foreign workspace
    with pytest.raises(ProjectionResponseError, match="stale, foreign or incomplete"):
        qdrant_index.parse_response(
            authorized_snapshot,
            {
                "points": [
                    {
                        "id": valid_pt_id,
                        "score": 0.9,
                        "payload": {
                            "workspace_id": "foreign-ws",
                            "generation_id": "gen-1",
                            "chunk_id": "chunk-1",
                            "profile_digest": authorized_snapshot.profile_digest,
                        },
                    }
                ]
            },
        )

    # Foreign generation
    with pytest.raises(ProjectionResponseError, match="stale, foreign or incomplete"):
        qdrant_index.parse_response(
            authorized_snapshot,
            {
                "points": [
                    {
                        "id": lexical_point_id("gen-unauthorized", "chunk-1"),
                        "score": 0.9,
                        "payload": {
                            "workspace_id": "ws-tenant-1",
                            "generation_id": "gen-unauthorized",
                            "chunk_id": "chunk-1",
                            "profile_digest": authorized_snapshot.profile_digest,
                        },
                    }
                ]
            },
        )

    # Inverted score monotonicity
    with pytest.raises(ProjectionResponseError, match="identity, uniqueness or rank is invalid"):
        qdrant_index.parse_response(
            authorized_snapshot,
            {
                "points": [
                    {
                        "id": lexical_point_id("gen-1", "chunk-1"),
                        "score": 0.5,
                        "payload": {
                            "workspace_id": "ws-tenant-1",
                            "generation_id": "gen-1",
                            "chunk_id": "chunk-1",
                            "profile_digest": authorized_snapshot.profile_digest,
                        },
                    },
                    {
                        "id": lexical_point_id("gen-1", "chunk-2"),
                        "score": 0.8,  # Higher score after lower score
                        "payload": {
                            "workspace_id": "ws-tenant-1",
                            "generation_id": "gen-1",
                            "chunk_id": "chunk-2",
                            "profile_digest": authorized_snapshot.profile_digest,
                        },
                    },
                ]
            },
        )


def test_parse_response_canonical_tie_break_on_equal_scores(
    qdrant_index: QdrantSearchIndex, authorized_snapshot: AuthorizedLexicalSnapshot
) -> None:
    # 2 points with equal scores (len < 200) must be ordered deterministically by chunk_id
    response = {
        "points": [
            {
                "id": lexical_point_id("gen-1", "chunk-b"),
                "score": 0.75,
                "payload": {
                    "workspace_id": "ws-tenant-1",
                    "generation_id": "gen-1",
                    "chunk_id": "chunk-b",
                    "profile_digest": authorized_snapshot.profile_digest,
                },
            },
            {
                "id": lexical_point_id("gen-1", "chunk-a"),
                "score": 0.75,
                "payload": {
                    "workspace_id": "ws-tenant-1",
                    "generation_id": "gen-1",
                    "chunk_id": "chunk-a",
                    "profile_digest": authorized_snapshot.profile_digest,
                },
            },
        ]
    }
    parsed = qdrant_index.parse_response(authorized_snapshot, response, limit=200)
    assert len(parsed) == 2
    assert parsed[0]["chunk_id"] == "chunk-a"
    assert parsed[0]["rank"] == 1
    assert parsed[1]["chunk_id"] == "chunk-b"
    assert parsed[1]["rank"] == 2


class StubEmbeddingProvider:
    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions
        self.calls = 0

    def embed_queries(
        self, queries: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        self.calls += 1
        return EmbeddingBatch(
            vectors=tuple([0.05] * self.dimensions for _ in queries),
            provider=configuration.provider,
            model=configuration.model,
            usage={"prompt_tokens": 5, "total_tokens": 5},
            cost=0.0,
            provider_request_id="stub-req-1",
        )

    embed = embed_queries


class StubGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, question: str, evidence: tuple) -> GenerationResult:
        self.calls += 1
        return GenerationResult(
            decision="ANSWER",
            answer="Answer based on [[E1]].",
            cited_evidence_ids=("E1",),
            refusal_reason=None,
            provider="stub-gen",
            model="stub-model",
            prompt_version="v1",
        )


def _sample_generation(profile: LexicalProfile) -> LexicalGeneration:
    content = "Sample chunk content 1"
    content_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return LexicalGeneration(
        generation_id="gen-test-1",
        workspace_id="ws-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cset-1",
        lexical_profile=profile,
        revision=1,
        chunks=(LexicalChunk(chunk_id="chunk-1", ordinal=0, content_checksum=content_checksum),),
    )


@pytest.mark.asyncio
async def test_dense_only_e2e_answer_and_trace(
    test_profile: LexicalProfile, test_embedding_config: EmbeddingConfiguration
) -> None:
    content = "Sample chunk content 1"
    content_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    gen = _sample_generation(test_profile)

    class MockStore:
        def __init__(self) -> None:
            self.traces = []
            self.ready_checks = []

        def require_lexical_corpus(self, workspace_id, lexical_policy_id):
            self.ready_checks.append((workspace_id, lexical_policy_id))

        def retrieve_candidates(self, **kwargs):
            candidate = stores.RetrievalCandidate(
                document_id=gen.document_id,
                document_version_id=gen.document_version_id,
                source_key="policy.pdf",
                source_name="policy.pdf",
                chunk_set_id=gen.chunk_set_id,
                embedding_set_id=None,
                embedding_configuration_id=test_embedding_config.id,
                chunk_id="chunk-1",
                chunk_ordinal=0,
                heading_path=(),
                start_line=1,
                end_line=1,
                content=content,
                content_checksum=content_checksum,
                token_count=5,
                cosine_distance=0.15,
                similarity=0.85,
                page_start=1,
                page_end=1,
                index_generation_id=gen.generation_id,
            )
            obs = stores.BranchObservation(
                branch="dense",
                status="ELIGIBLE",
                chunk_id="chunk-1",
                branch_rank=1,
                cosine_distance=0.15,
                similarity=0.85,
                raw_score=0.85,
                score_kind="cosine_similarity",
                index_generation_id=gen.generation_id,
            )
            return stores.RetrievalResult(
                candidates=(candidate,),
                branch_observations=(obs,),
                chunk_set_ids=(gen.chunk_set_id,),
                lexical_generations=(
                    stores.LexicalGeneration(
                        workspace_id=gen.workspace_id,
                        document_id=gen.document_id,
                        document_version_id=gen.document_version_id,
                        chunk_set_id=gen.chunk_set_id,
                        index_generation_id=gen.generation_id,
                        lexical_policy_id=test_profile.id,
                    ),
                ),
            )

        def revalidate_lexical_snapshot(self, workspace_id, lexical_policy_id, generations):
            assert workspace_id == "ws-1"
            assert generations[0].index_generation_id == gen.generation_id

        def persist_trace(self, trace):
            self.traces.append(trace)
            return "trace-dense-1"

    store = MockStore()
    embedding_provider = StubEmbeddingProvider()
    generator = StubGenerator()
    retrieval_cfg = stores.RetrievalConfiguration.dense_top8_v3(min_similarity=0.65)

    service = AnswerQuestion(
        embedding_provider=embedding_provider,
        embedding_configuration=test_embedding_config,
        generation_provider=generator,
        store=store,
        retrieval_configuration=retrieval_cfg,
    )

    result = await service.execute(
        QuestionCommand(workspace_id="ws-1", question="What is policy?"),
        WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
    )

    assert result.decision == "ANSWER"
    assert result.answer == "Answer based on [[E1]]."
    assert len(result.citations) == 1
    assert result.citations[0].source_key == "policy.pdf"
    assert embedding_provider.calls == 1
    assert generator.calls == 1

    # Check trace
    assert len(store.traces) == 1
    trace = store.traces[0]
    retrieval_meta = trace.provider_metadata["retrieval"]
    assert retrieval_meta["mode"] == "dense-only"
    assert retrieval_meta["score_policy"]["score_kind"] == "cosine_similarity"
    assert retrieval_meta["score_policy"]["numeric_cutoff"] == 0.65
    assert retrieval_meta["score_policy"]["cutoff_status"] == "calibrated"


@pytest.mark.asyncio
async def test_hybrid_e2e_answer_and_trace_no_cosine_cutoff_on_dbsf(
    test_profile: LexicalProfile, test_embedding_config: EmbeddingConfiguration
) -> None:
    content = "Sample chunk content 1"
    content_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    gen = _sample_generation(test_profile)

    class MockHybridStore:
        def __init__(self) -> None:
            self.traces = []

        def require_lexical_corpus(self, workspace_id, lexical_policy_id):
            assert workspace_id == "ws-1"

        def retrieve_candidates(self, **kwargs):
            candidate = stores.RetrievalCandidate(
                document_id=gen.document_id,
                document_version_id=gen.document_version_id,
                source_key="policy.pdf",
                source_name="policy.pdf",
                chunk_set_id=gen.chunk_set_id,
                embedding_set_id=None,
                embedding_configuration_id=test_embedding_config.id,
                chunk_id="chunk-1",
                chunk_ordinal=0,
                heading_path=(),
                start_line=1,
                end_line=1,
                content=content,
                content_checksum=content_checksum,
                token_count=5,
                cosine_distance=None,
                similarity=None,
                fusion_score=0.52,  # DBSF score
                page_start=1,
                page_end=1,
                index_generation_id=gen.generation_id,
            )
            obs = stores.BranchObservation(
                branch="fused",
                status="ELIGIBLE",
                chunk_id="chunk-1",
                branch_rank=1,
                raw_score=0.52,
                score_kind="dbsf",
                index_generation_id=gen.generation_id,
            )
            return stores.RetrievalResult(
                candidates=(candidate,),
                branch_observations=(obs,),
                chunk_set_ids=(gen.chunk_set_id,),
                lexical_generations=(
                    stores.LexicalGeneration(
                        workspace_id=gen.workspace_id,
                        document_id=gen.document_id,
                        document_version_id=gen.document_version_id,
                        chunk_set_id=gen.chunk_set_id,
                        index_generation_id=gen.generation_id,
                        lexical_policy_id=test_profile.id,
                    ),
                ),
            )

        def revalidate_lexical_snapshot(self, workspace_id, lexical_policy_id, generations):
            pass

        def persist_trace(self, trace):
            self.traces.append(trace)
            return "trace-hybrid-1"

    store = MockHybridStore()
    embedding_provider = StubEmbeddingProvider()
    generator = StubGenerator()
    retrieval_cfg = stores.RetrievalConfiguration.hybrid_top8_v3()

    service = AnswerQuestion(
        embedding_provider=embedding_provider,
        embedding_configuration=test_embedding_config,
        generation_provider=generator,
        store=store,
        retrieval_configuration=retrieval_cfg,
    )

    result = await service.execute(
        QuestionCommand(workspace_id="ws-1", question="What is policy?"),
        WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
    )

    assert result.decision == "ANSWER"
    assert len(store.traces) == 1
    trace = store.traces[0]
    retrieval_meta = trace.provider_metadata["retrieval"]
    assert retrieval_meta["mode"] == "hybrid"
    assert retrieval_meta["score_policy"]["score_kind"] == "dbsf"
    # Essential requirement: DBSF score must not have silent cosine cutoff
    assert retrieval_meta["score_policy"]["numeric_cutoff"] is None
    assert retrieval_meta["score_policy"]["query_limit"] == 100


def test_validate_dense_result_rejects_below_similarity_threshold(
    test_profile: LexicalProfile,
) -> None:
    gen = _sample_generation(test_profile)
    snapshot = stores.LexicalGeneration(
        workspace_id=gen.workspace_id,
        document_id=gen.document_id,
        document_version_id=gen.document_version_id,
        chunk_set_id=gen.chunk_set_id,
        index_generation_id=gen.generation_id,
        lexical_policy_id=test_profile.id,
    )
    # If candidate similarity is below min_similarity (0.65), validation rejects ELIGIBLE
    obs = stores.BranchObservation(
        branch="dense",
        status="ELIGIBLE",  # Invalid because raw_score 0.5 < 0.65
        chunk_id="chunk-1",
        branch_rank=1,
        raw_score=0.5,
        score_kind="cosine_similarity",
        index_generation_id=gen.generation_id,
    )
    cand = stores.RetrievalCandidate(
        document_id=gen.document_id,
        document_version_id=gen.document_version_id,
        source_key="doc.pdf",
        source_name="doc.pdf",
        chunk_set_id=gen.chunk_set_id,
        embedding_set_id=None,
        embedding_configuration_id=None,
        chunk_id="chunk-1",
        chunk_ordinal=0,
        heading_path=(),
        start_line=1,
        end_line=1,
        content="Fact",
        content_checksum="c",
        token_count=1,
        cosine_distance=0.5,
        similarity=0.5,
        index_generation_id=gen.generation_id,
    )
    result = stores.RetrievalResult(
        candidates=(cand,),
        branch_observations=(obs,),
        chunk_set_ids=(gen.chunk_set_id,),
        lexical_generations=(snapshot,),
    )
    cfg = stores.RetrievalConfiguration.dense_top8_v3(min_similarity=0.65)
    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        validate_dense_result(result, workspace_id="ws-1", configuration=cfg)


def test_validate_hybrid_result_rejects_sparse_observations_or_wrong_kind(
    test_profile: LexicalProfile,
) -> None:
    gen = _sample_generation(test_profile)
    snapshot = stores.LexicalGeneration(
        workspace_id=gen.workspace_id,
        document_id=gen.document_id,
        document_version_id=gen.document_version_id,
        chunk_set_id=gen.chunk_set_id,
        index_generation_id=gen.generation_id,
        lexical_policy_id=test_profile.id,
    )
    obs = stores.BranchObservation(
        branch="bm25",  # Should be 'fused'
        status="ELIGIBLE",
        chunk_id="chunk-1",
        branch_rank=1,
        raw_score=0.8,
        score_kind="bm25",
        index_generation_id=gen.generation_id,
    )
    result = stores.RetrievalResult(
        candidates=(),
        branch_observations=(obs,),
        chunk_set_ids=(gen.chunk_set_id,),
        lexical_generations=(snapshot,),
    )
    cfg = stores.RetrievalConfiguration.hybrid_top8_v3()
    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        validate_hybrid_result(result, workspace_id="ws-1", configuration=cfg)


@pytest.mark.asyncio
async def test_snapshot_fence_fails_safely_on_archive_before_generation(
    test_profile: LexicalProfile, test_embedding_config: EmbeddingConfiguration
) -> None:
    gen = _sample_generation(test_profile)

    class ArchiveFencingStore:
        archived = False

        def require_lexical_corpus(self, workspace_id, lexical_policy_id):
            pass

        def retrieve_candidates(self, **kwargs):
            candidate = stores.RetrievalCandidate(
                document_id=gen.document_id,
                document_version_id=gen.document_version_id,
                source_key="policy.pdf",
                source_name="policy.pdf",
                chunk_set_id=gen.chunk_set_id,
                embedding_set_id=None,
                embedding_configuration_id=test_embedding_config.id,
                chunk_id="chunk-1",
                chunk_ordinal=0,
                heading_path=(),
                start_line=1,
                end_line=1,
                content="Sample content",
                content_checksum=gen.chunks[0].content_checksum,
                token_count=5,
                cosine_distance=0.1,
                similarity=0.9,
                index_generation_id=gen.generation_id,
            )
            obs = stores.BranchObservation(
                branch="dense",
                status="ELIGIBLE",
                chunk_id="chunk-1",
                branch_rank=1,
                cosine_distance=0.1,
                similarity=0.9,
                raw_score=0.9,
                score_kind="cosine_similarity",
                index_generation_id=gen.generation_id,
            )
            return stores.RetrievalResult(
                candidates=(candidate,),
                branch_observations=(obs,),
                chunk_set_ids=(gen.chunk_set_id,),
                lexical_generations=(
                    stores.LexicalGeneration(
                        workspace_id=gen.workspace_id,
                        document_id=gen.document_id,
                        document_version_id=gen.document_version_id,
                        chunk_set_id=gen.chunk_set_id,
                        index_generation_id=gen.generation_id,
                        lexical_policy_id=test_profile.id,
                    ),
                ),
            )

        def revalidate_lexical_snapshot(self, workspace_id, lexical_policy_id, generations):
            if self.archived:
                raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

        def persist_trace(self, trace):
            pytest.fail("Trace must not be persisted on fenced failure")

    store = ArchiveFencingStore()
    embedding_provider = StubEmbeddingProvider()
    generator = StubGenerator()
    service = AnswerQuestion(
        embedding_provider=embedding_provider,
        embedding_configuration=test_embedding_config,
        generation_provider=generator,
        store=store,
        retrieval_configuration=stores.RetrievalConfiguration.dense_top8_v3(min_similarity=0.65),
    )

    def trigger_archive(stage: str) -> None:
        if stage == "generating":
            store.archived = True

    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        await service.execute(
            QuestionCommand(workspace_id="ws-1", question="Query"),
            WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
            stage_callback=trigger_archive,
        )

    assert generator.calls == 0


def test_postgres_hydration_rejects_unauthorized_high_scoring_decoy(
    test_profile: LexicalProfile, test_embedding_config: EmbeddingConfiguration, monkeypatch
) -> None:
    gen = _sample_generation(test_profile)

    # Decoy point from a foreign generation with a very high score (0.99)
    decoy_hit = {
        "id": lexical_point_id("gen-decoy-unauthorized", "chunk-decoy"),
        "score": 0.99,
        "rank": 1,
        "generation_id": "gen-decoy-unauthorized",
        "chunk_id": "chunk-decoy",
        "score_policy_digest": test_profile.digest(),
    }

    class MockProjection:
        def __init__(self, profile: LexicalProfile) -> None:
            self.index = SimpleNamespace(profile=profile)

        def query_dense(self, *args, **kwargs):
            return (decoy_hit,)

    authority = Mock()
    authority.read_active_generations.return_value = (gen,)
    monkeypatch.setattr(lexical_retrieval, "PostgresSearchIndexStore", lambda _: authority)

    class MockSession:
        def get(self, model, ident):
            return None

        def scalars(self, *args, **kwargs):
            return Mock(all=Mock(return_value=["doc-1"]))

    class MockSessionFactory:
        def begin(self):
            class Scope:
                def __enter__(self):
                    return MockSession()

                def __exit__(self, *args):
                    pass

            return Scope()

    # Hydration must reject the decoy with KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")
    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        lexical_retrieval.retrieve_dense_candidates(
            MockSessionFactory(),
            workspace_id="ws-1",
            query_vector=tuple([0.1] * 768),
            configuration=stores.RetrievalConfiguration.dense_top8_v3(min_similarity=0.65),
            projection=MockProjection(test_profile),
            embedding_configuration=test_embedding_config,
        )
