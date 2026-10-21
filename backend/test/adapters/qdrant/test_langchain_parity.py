"""Parity evaluation and contract tests for native REST vs framework wrappers (Task 6)."""

from __future__ import annotations

import pytest

from knora.adapters.qdrant.search_index import (
    AuthorizedLexicalSnapshot,
    QdrantSearchIndex,
)
from knora.answering import stores
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.search_indexing import LexicalProfile
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.generation import GenerationResult


@pytest.fixture
def sample_profile() -> LexicalProfile:
    return LexicalProfile(
        id="bm25-word-frozen47-population-v1",
        tokenizer="tiktoken",
        tokenizer_version="cl100k_base",
        k1=1.2,
        b=0.75,
        avg_len=128.0,
        statistics_digest="e" * 64,
    )


@pytest.fixture
def sample_embedding_cfg() -> EmbeddingConfiguration:
    return EmbeddingConfiguration.cloudflare_bge_base_en()


@pytest.fixture
def native_index(
    sample_profile: LexicalProfile, sample_embedding_cfg: EmbeddingConfiguration
) -> QdrantSearchIndex:
    return QdrantSearchIndex(
        collection_name="test_knora_parity",
        profile=sample_profile,
        embedding_configuration=sample_embedding_cfg,
        turbo_quant=True,
    )


def test_native_wire_preserves_tenant_keyword_index(native_index: QdrantSearchIndex) -> None:
    """Knora requires canonical tenant keyword index; framework wrappers omit is_tenant."""
    bodies = native_index.payload_index_bodies()
    tenant_index = next((b for b in bodies if b["field_name"] == "workspace_id"), None)
    assert tenant_index is not None
    assert tenant_index["field_schema"] == {"type": "keyword", "is_tenant": True}


def test_native_wire_preserves_turbo_quant_rescore_and_oversampling(
    native_index: QdrantSearchIndex, sample_profile: LexicalProfile
) -> None:
    """Knora enforces TurboQuant bits4 with rescore=True and oversampling=2.0 on wire."""
    snapshot = AuthorizedLexicalSnapshot(
        workspace_id="ws-1",
        generation_ids=("gen-1",),
        profile_id=sample_profile.id,
        profile_digest=sample_profile.digest(),
    )
    query_body = native_index.dense_query_body(snapshot, [0.1] * 768)
    params = query_body["params"]
    assert params["hnsw_ef"] == 256
    assert params["quantization"]["rescore"] is True
    assert params["quantization"]["oversampling"] == 2.0


def test_native_wire_preserves_dbsf_fusion_with_prefetches(
    native_index: QdrantSearchIndex, sample_profile: LexicalProfile
) -> None:
    """Native Qdrant DBSF hybrid requires exact 200+200 prefetch to 100 final limit."""
    snapshot = AuthorizedLexicalSnapshot(
        workspace_id="ws-1",
        generation_ids=("gen-1",),
        profile_id=sample_profile.id,
        profile_digest=sample_profile.digest(),
    )
    hybrid_body = native_index.hybrid_query_body(
        snapshot,
        "query",
        [0.1] * 768,
        dense_limit=200,
        sparse_limit=200,
        final_limit=100,
    )
    assert hybrid_body["query"] == {"fusion": "dbsf"}
    assert hybrid_body["limit"] == 100
    assert len(hybrid_body["prefetch"]) == 2
    assert hybrid_body["prefetch"][0]["limit"] == 200
    assert hybrid_body["prefetch"][1]["limit"] == 200


@pytest.mark.asyncio
async def test_zero_call_bm25_query_invariant(sample_profile: LexicalProfile) -> None:
    """BM25 query retrieval must make exactly 0 embedding calls."""

    class FailOnEmbedProvider:
        def embed(self, *args, **kwargs):
            pytest.fail("Embedding provider called during BM25 retrieval")

        embed_queries = embed
        embed_documents = embed

    class StubGenerator:
        async def generate(self, *args, **kwargs):
            return GenerationResult(
                decision="ANSWER",
                answer="Fact [[E1]]",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="stub",
                model="stub",
                prompt_version="v1",
            )

    class MockBM25Store:
        def require_lexical_corpus(self, *args):
            pass

        def retrieve_candidates(self, **kwargs):
            candidate = stores.RetrievalCandidate(
                document_id="doc-1",
                document_version_id="ver-1",
                source_key="policy.pdf",
                source_name="policy.pdf",
                chunk_set_id="cset-1",
                embedding_set_id=None,
                embedding_configuration_id=None,
                chunk_id="chunk-1",
                chunk_ordinal=0,
                heading_path=(),
                start_line=1,
                end_line=1,
                content="BM25 content",
                content_checksum="c",
                token_count=2,
                cosine_distance=None,
                similarity=None,
                page_start=1,
                page_end=1,
                bm25_score=10.0,
                bm25_rank=1,
                index_generation_id="gen-1",
            )
            obs = stores.BranchObservation(
                branch="bm25",
                status="ELIGIBLE",
                chunk_id="chunk-1",
                branch_rank=1,
                raw_score=10.0,
                score_kind="bm25",
                index_generation_id="gen-1",
                lexical_policy_id=sample_profile.id,
            )
            return stores.RetrievalResult(
                candidates=(candidate,),
                branch_observations=(obs,),
                chunk_set_ids=("cset-1",),
                lexical_generations=(
                    stores.LexicalGeneration(
                        workspace_id="ws-1",
                        document_id="doc-1",
                        document_version_id="ver-1",
                        chunk_set_id="cset-1",
                        index_generation_id="gen-1",
                        lexical_policy_id=sample_profile.id,
                    ),
                ),
            )

        def revalidate_lexical_snapshot(self, *args):
            pass

        def persist_trace(self, trace):
            return "trace-bm25-0call"

    service = AnswerQuestion(
        embedding_provider=FailOnEmbedProvider(),
        embedding_configuration=None,
        generation_provider=StubGenerator(),
        store=MockBM25Store(),
        retrieval_configuration=stores.RetrievalConfiguration.bm25_top8_v1(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="ws-1", question="Query"),
        WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
    )
    assert result.decision == "ANSWER"
