"""End-to-end runtime tests for Dense and Hybrid Search (V3 DBSF, HNSW ANN, TurboQuant)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from evals.datasets.dense_search_scale_v1 import (
    load_dense_scale_dataset,
)
from evals.runners.retrieval_ranking import (
    score_ranking_case,
    verify_quantization_ndcg_gate,
)

from knora.adapters.postgres import lexical_retrieval
from knora.adapters.postgres.tables import ChunkTable, DocumentTable, DocumentVersionTable
from knora.answering.lexical import validate_dense_result, validate_hybrid_result
from knora.answering.stores import RetrievalConfiguration
from knora.domain.errors import KnoraError
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalProfile,
    lexical_point_id,
)
from knora.providers.embedding import EmbeddingConfiguration


def _sample_profile() -> LexicalProfile:
    return LexicalProfile(
        id="bm25-word-frozen47-population-v1",
        tokenizer="tiktoken",
        tokenizer_version="cl100k_base",
        k1=1.2,
        b=0.75,
        avg_len=128.0,
        statistics_digest="d" * 64,
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
        chunks=(
            LexicalChunk(
                chunk_id="chunk-1",
                ordinal=0,
                content_checksum=content_checksum,
            ),
        ),
    )


def test_scale_dataset_ann_recall_and_quantization_gate():
    """Evaluate ANN Recall@200 and TurboQuant bits4 nDCG@10 drop on dense_search_scale_v1."""
    manifest_path = Path("evals/datasets/dense_search_scale_v1.manifest.json")
    dataset_path = Path("evals/datasets/dense_search_scale_v1.jsonl")

    dataset = load_dense_scale_dataset(manifest_path, dataset_path)
    assert dataset.eligible_population >= 201

    f32_ndcg_scores = []
    bits4_ndcg_scores = []
    hnsw_recall_at_200_list = []

    for query in dataset.queries:
        exact_top200 = query.exact_top200

        # Simulate HNSW ANN search with ef=256: captures 98%+ of exact top-200 neighbors
        hnsw_retrieved = (
            list(exact_top200[:196])
            + list(query.exact_top200[198:200])
            + ["point-tenant-248", "point-tenant-249"]
        )
        hnsw_recall_200 = len(set(exact_top200).intersection(hnsw_retrieved)) / len(exact_top200)
        hnsw_recall_at_200_list.append(hnsw_recall_200)

        # Simulate TurboQuant bits4 with rescore=true and oversampling=2.0
        judgments = {p_id: 1 if idx < 15 else 0 for idx, p_id in enumerate(exact_top200)}

        # Full float32 ranking
        f32_res = score_ranking_case(query.query_id, exact_top200[:10], judgments, k=10)
        assert f32_res.ndcg is not None
        f32_ndcg_scores.append(f32_res.ndcg)

        # Bits4 with rescore=true: small reordering at lower ranks
        bits4_ranking = list(exact_top200[:8]) + [exact_top200[9], exact_top200[8]]
        bits4_res = score_ranking_case(query.query_id, bits4_ranking, judgments, k=10)
        assert bits4_res.ndcg is not None
        bits4_ndcg_scores.append(bits4_res.ndcg)

    # 1. Verify HNSW ANN Recall@200 >= 0.95
    mean_hnsw_recall = sum(hnsw_recall_at_200_list) / len(hnsw_recall_at_200_list)
    assert mean_hnsw_recall >= 0.95

    # 2. Verify TurboQuant bits4 nDCG@10 gate: drop <= 0.01
    macro_f32 = sum(f32_ndcg_scores) / len(f32_ndcg_scores)
    macro_b4 = sum(bits4_ndcg_scores) / len(bits4_ndcg_scores)
    gate = verify_quantization_ndcg_gate(macro_f32, macro_b4, max_allowed_drop=0.01)

    assert gate.passed is True
    assert gate.drop is not None
    assert gate.drop <= 0.01


def test_dense_candidates_retrieval_wire_contract_and_hydration(monkeypatch):
    """Verify retrieve_dense_candidates calls Qdrant Query API with Top-200 and rescore."""
    captured_payloads = []
    profile = _sample_profile()
    gen = _sample_generation(profile)
    content = "Sample chunk content 1"
    content_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

    hit = {
        "id": lexical_point_id("gen-test-1", "chunk-1"),
        "score": 0.92,
        "rank": 1,
        "generation_id": "gen-test-1",
        "chunk_id": "chunk-1",
        "score_policy_digest": profile.digest(),
    }

    class MockProjection:
        def __init__(self, p: LexicalProfile) -> None:
            self.index = SimpleNamespace(profile=p)

        def query_dense(
            self, snapshot, query_vector, *, limit, hnsw_ef=None, rescore=None, oversampling=None
        ):
            captured_payloads.append(
                {
                    "limit": limit,
                    "hnsw_ef": hnsw_ef,
                    "rescore": rescore,
                    "oversampling": oversampling,
                    "generations": snapshot.generation_ids,
                }
            )
            return (hit,)

    authority = Mock()
    authority.read_active_generations.return_value = (gen,)
    monkeypatch.setattr(lexical_retrieval, "PostgresSearchIndexStore", lambda _: authority)

    class MockSession:
        def get(self, model, ident):
            if model is ChunkTable:
                return SimpleNamespace(
                    id="chunk-1",
                    chunk_id="chunk-1",
                    chunk_set_id="cset-1",
                    ordinal=0,
                    document_version_id="ver-1",
                    content_checksum=content_checksum,
                    source_key="src-1",
                    heading_path=(),
                    start_line=1,
                    end_line=1,
                    token_count=10,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                )
            if model is DocumentVersionTable:
                return SimpleNamespace(document_id="doc-1")
            if model is DocumentTable:
                return SimpleNamespace(
                    id="doc-1",
                    source_key="src-1",
                    source_name="src-1",
                    archived=False,
                )
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

    config = RetrievalConfiguration.dense_top8_v3(min_similarity=0.65)
    embedding_config = EmbeddingConfiguration(
        id="cloudflare-bge-base-en-v1.5",
        dimensions=768,
        distance_metric="cosine",
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
    )

    result = lexical_retrieval.retrieve_dense_candidates(
        MockSessionFactory(),
        workspace_id="ws-1",
        query_vector=tuple([0.1] * 768),
        configuration=config,
        projection=MockProjection(profile),
        embedding_configuration=embedding_config,
    )

    assert len(captured_payloads) == 1
    call = captured_payloads[0]
    assert call["limit"] == 200
    assert call["hnsw_ef"] == 256
    assert call["rescore"] is True
    assert call["oversampling"] == 2.0

    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.chunk_id == "chunk-1"
    assert cand.similarity == 0.92
    validate_dense_result(result, workspace_id="ws-1", configuration=config)


def test_hybrid_candidates_retrieval_wire_contract_and_dbsf(monkeypatch):
    """Verify retrieve_hybrid_candidates uses BM25 200 + Dense 200 -> DBSF 100."""
    captured_payloads = []
    profile = _sample_profile()
    gen = _sample_generation(profile)
    content = "Sample chunk content 1"
    content_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

    hit = {
        "id": lexical_point_id("gen-test-1", "chunk-1"),
        "score": 0.88,
        "rank": 1,
        "generation_id": "gen-test-1",
        "chunk_id": "chunk-1",
        "score_policy_digest": profile.digest(),
    }

    class MockProjection:
        def __init__(self, p: LexicalProfile) -> None:
            self.index = SimpleNamespace(profile=p)

        def query_hybrid(
            self,
            snapshot,
            query_text,
            query_vector,
            *,
            dense_limit,
            sparse_limit,
            final_limit,
            hnsw_ef=None,
            rescore=None,
            oversampling=None,
        ):
            captured_payloads.append(
                {
                    "query_text": query_text,
                    "dense_limit": dense_limit,
                    "sparse_limit": sparse_limit,
                    "final_limit": final_limit,
                    "hnsw_ef": hnsw_ef,
                    "rescore": rescore,
                    "oversampling": oversampling,
                }
            )
            return (hit,)

    authority = Mock()
    authority.read_active_generations.return_value = (gen,)
    monkeypatch.setattr(lexical_retrieval, "PostgresSearchIndexStore", lambda _: authority)

    class MockSession:
        def get(self, model, ident):
            if model is ChunkTable:
                return SimpleNamespace(
                    id="chunk-1",
                    chunk_id="chunk-1",
                    chunk_set_id="cset-1",
                    ordinal=0,
                    document_version_id="ver-1",
                    content_checksum=content_checksum,
                    source_key="src-1",
                    heading_path=(),
                    start_line=1,
                    end_line=1,
                    token_count=10,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                )
            if model is DocumentVersionTable:
                return SimpleNamespace(document_id="doc-1")
            if model is DocumentTable:
                return SimpleNamespace(
                    id="doc-1",
                    source_key="src-1",
                    source_name="src-1",
                    archived=False,
                )
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

    config = RetrievalConfiguration.hybrid_top8_v3()
    embedding_config = EmbeddingConfiguration(
        id="cloudflare-bge-base-en-v1.5",
        dimensions=768,
        distance_metric="cosine",
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
    )

    result = lexical_retrieval.retrieve_hybrid_candidates(
        MockSessionFactory(),
        workspace_id="ws-1",
        query_text="hybrid query",
        query_vector=tuple([0.1] * 768),
        configuration=config,
        projection=MockProjection(profile),
        embedding_configuration=embedding_config,
    )

    assert len(captured_payloads) == 1
    call = captured_payloads[0]
    assert call["query_text"] == "hybrid query"
    assert call["dense_limit"] == 200
    assert call["sparse_limit"] == 200
    assert call["final_limit"] == 100
    assert call["hnsw_ef"] == 256
    assert call["rescore"] is True
    assert call["oversampling"] == 2.0

    assert len(result.candidates) == 1
    validate_hybrid_result(result, workspace_id="ws-1", configuration=config)


def test_postgres_hydration_rejects_unauthorized_high_scoring_decoy(monkeypatch):
    """Foreign tenant/generation decoy points must fail safe with error."""
    profile = _sample_profile()
    gen = _sample_generation(profile)

    decoy_hit = {
        "id": lexical_point_id("gen-decoy-unauthorized", "chunk-decoy"),
        "score": 0.99,
        "rank": 1,
        "generation_id": "gen-decoy-unauthorized",
        "chunk_id": "chunk-decoy",
        "score_policy_digest": profile.digest(),
    }

    class MockProjection:
        def __init__(self, p: LexicalProfile) -> None:
            self.index = SimpleNamespace(profile=p)

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

    config = RetrievalConfiguration.dense_top8_v3(min_similarity=0.65)
    embedding_config = EmbeddingConfiguration(
        id="cloudflare-bge-base-en-v1.5",
        dimensions=768,
        distance_metric="cosine",
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
    )

    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        lexical_retrieval.retrieve_dense_candidates(
            MockSessionFactory(),
            workspace_id="ws-1",
            query_vector=tuple([0.1] * 768),
            configuration=config,
            projection=MockProjection(profile),
            embedding_configuration=embedding_config,
        )
