"""Pipeline integration tests for Reranking and Evidence selection."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest

from knora.answering import stores
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.reranking_configuration import (
    DeploymentRerankingConfigurationResolver,
    RerankingConfiguration,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration
from knora.providers.generation import GenerationResult
from knora.providers.reranking import (
    RerankingCandidate,
    RerankingProvider,
    RerankingResult,
    ScoredRerankingCandidate,
)


def _make_candidate(
    index: int,
    content: str,
    *,
    fusion_score: float = 0.5,
    sdm_score: float | None = None,
) -> stores.RetrievalCandidate:
    return stores.RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-1",
        embedding_set_id=None,
        embedding_configuration_id="bge-test",
        chunk_id=f"chunk-{index}",
        chunk_ordinal=index - 1,
        heading_path=("Section 1", "Clause A"),
        start_line=10,
        end_line=20,
        content=content,
        content_checksum=f"chk-{index}",
        token_count=len(content.split()),
        cosine_distance=None,
        similarity=None,
        fusion_score=fusion_score,
        sdm_score=sdm_score,
        page_start=1,
        page_end=1,
        start_offset=0,
        end_offset=len(content),
        index_generation_id="gen-1",
    )


def _make_retrieval_result(
    candidates: tuple[stores.RetrievalCandidate, ...],
) -> stores.RetrievalResult:
    snapshot = stores.LexicalGeneration(
        workspace_id="ws-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cset-1",
        index_generation_id="gen-1",
        lexical_policy_id="bm25-word-frozen47-population-v1",
    )
    obs = tuple(
        stores.BranchObservation(
            branch="fused",
            status="ELIGIBLE",
            chunk_id=c.chunk_id,
            branch_rank=idx,
            raw_score=c.fusion_score,
            score_kind="dbsf",
            index_generation_id="gen-1",
        )
        for idx, c in enumerate(candidates, start=1)
    )
    return stores.RetrievalResult(
        candidates=candidates,
        branch_observations=obs,
        chunk_set_ids=("cset-1",),
        lexical_generations=(snapshot,),
    )


class FakeRerankingProvider:
    def __init__(
        self,
        score_map: dict[str, float] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.score_map = score_map or {}
        self.raises = raises
        self.calls: list[tuple[str, list[RerankingCandidate]]] = []

    def rerank(self, query: str, candidates: list[RerankingCandidate]) -> RerankingResult:
        self.calls.append((query, candidates))
        if self.raises:
            raise self.raises

        scored = []
        for rank, c in enumerate(candidates, start=1):
            score = self.score_map.get(c.chunk_id, 0.5)
            scored.append(
                ScoredRerankingCandidate(candidate=c, rerank_score=score, rerank_rank=rank)
            )
        return RerankingResult(
            scored_candidates=tuple(scored),
            model="@cf/baai/bge-reranker-base",
        )


def _build_answer_question(
    store: Mock,
    generator: Mock,
    reranker: RerankingProvider | None = None,
    rerank_config: RerankingConfiguration | None = None,
) -> AnswerQuestion:
    embedding_config = EmbeddingConfiguration(
        id="bge-test",
        dimensions=768,
        distance_metric="cosine",
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
    )
    embedding_provider = Mock()
    embedding_provider.embed_queries.return_value = EmbeddingBatch(
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
        vectors=((0.1,) * 768,),
    )

    retrieval_config = stores.RetrievalConfiguration.hybrid_rerank_top8_v3()
    resolver = (
        DeploymentRerankingConfigurationResolver(rerank_config)
        if rerank_config is not None
        else None
    )

    return AnswerQuestion(
        store=store,
        generation_provider=generator,
        embedding_provider=embedding_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=retrieval_config,
        reranking_provider=reranker,
        reranking_configuration_resolver=resolver,
    )


def test_stage_order_dbsf_sdm_rerank_mmr_generation():
    """Verify stage order: DBSF -> SDM -> Cross-Encoder rerank -> MMR -> Generation."""
    # c1 had highest initial fusion score (0.90), but lower rerank score (0.2)
    # c2 had lower initial fusion score (0.60), but highest rerank score (0.95)
    c1 = _make_candidate(1, "Text one with general words", fusion_score=0.90, sdm_score=0.90)
    c2 = _make_candidate(
        2, "Text two with specific query relevance", fusion_score=0.60, sdm_score=0.60
    )
    c3 = _make_candidate(3, "Text three with some words", fusion_score=0.70, sdm_score=0.70)

    retrieval_result = _make_retrieval_result((c1, c3, c2))

    store = Mock()
    store.retrieve_candidates.return_value = retrieval_result
    store.require_lexical_corpus.return_value = None
    store.persist_trace.return_value = "trace-s6-1"

    generator = Mock()
    generator.generate = Mock(
        side_effect=lambda **kwargs: asyncio.sleep(
            0,
            result=GenerationResult(
                decision="ANSWER",
                answer="Answer based on top evidence [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="cf",
                model="llama",
                finish_reason="stop",
            ),
        )
    )

    reranker = FakeRerankingProvider(
        score_map={
            "chunk-1": 0.20,
            "chunk-2": 0.95,
            "chunk-3": 0.50,
        }
    )

    config = RerankingConfiguration.cloudflare_bge_reranker_v1()
    answer_question = _build_answer_question(store, generator, reranker, config)

    command = QuestionCommand(workspace_id="ws-1", question="specific query relevance")
    principal = WorkspacePrincipal(workspace_id="ws-1", key_id="key-1")

    result = asyncio.run(answer_question.execute(command, principal))
    assert result.decision == "ANSWER"
    assert result.answer == "Answer based on top evidence [[E1]]."

    # Verify trace persisted
    assert store.persist_trace.called
    trace_arg = store.persist_trace.call_args[0][0]
    metadata = trace_arg.provider_metadata

    # Stage order verification:
    # 1. SDM observation present
    assert metadata["retrieval"]["sdm"]["status"] == "completed"

    # 2. Reranking observation present and completed
    assert "reranking" in metadata["retrieval"]
    rerank_obs = metadata["retrieval"]["reranking"]
    assert rerank_obs["status"] == "completed"
    assert rerank_obs["model"] == "@cf/baai/bge-reranker-base"
    assert rerank_obs["candidates_count"] == 3

    # 3. Candidate decisions contain rerank_contribution with combined_score
    decisions = trace_arg.candidate_decisions
    assert any("rerank_contribution" in d for d in decisions)
    top_dec = decisions[0]
    assert top_dec["chunk_id"] == "chunk-2"
    assert top_dec["rerank_contribution"]["combined_score"] > 0.5

    # 4. Evidence selection: chunk-2 is chosen as E1 due to reranking boost
    assert trace_arg.alias_mapping["E1"] == "chunk-2"
    assert trace_arg.retrieved_chunk_ids[0] == "chunk-2"

    # 5. Revalidation called before model and before generation
    assert store.revalidate_lexical_snapshot.call_count >= 2


def test_reranker_failure_fallback_dbsf_sdm():
    """Verify fallback policy: when reranker raises, pipeline falls back safely to DBSF+SDM."""
    c1 = _make_candidate(1, "Text one high initial score", fusion_score=0.90, sdm_score=0.90)
    c2 = _make_candidate(2, "Text two lower initial score", fusion_score=0.60, sdm_score=0.60)

    retrieval_result = _make_retrieval_result((c1, c2))

    store = Mock()
    store.retrieve_candidates.return_value = retrieval_result
    store.require_lexical_corpus.return_value = None
    store.persist_trace.return_value = "trace-s6-fallback"

    generator = Mock()
    generator.generate = Mock(
        side_effect=lambda **kwargs: asyncio.sleep(
            0,
            result=GenerationResult(
                decision="ANSWER",
                answer="Answer after fallback [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="cf",
                model="llama",
                finish_reason="stop",
            ),
        )
    )

    # Reranker raises 503 / timeout
    reranker = FakeRerankingProvider(raises=RuntimeError("Cloudflare AI Gateway Timeout 504"))

    config = RerankingConfiguration.cloudflare_bge_reranker_v1()
    assert config.fallback_policy == "fallback_dbsf_sdm"

    answer_question = _build_answer_question(store, generator, reranker, config)

    command = QuestionCommand(workspace_id="ws-1", question="some question")
    principal = WorkspacePrincipal(workspace_id="ws-1", key_id="key-1")

    # Pipeline does NOT refuse or crash; it safely falls back to DBSF+SDM
    result = asyncio.run(answer_question.execute(command, principal))
    assert result.decision == "ANSWER"
    assert result.answer == "Answer after fallback [[E1]]."

    # Trace verifies fallback status
    trace_arg = store.persist_trace.call_args[0][0]
    rerank_obs = trace_arg.provider_metadata["retrieval"]["reranking"]
    assert rerank_obs["status"] == "fallback_dbsf_sdm"
    assert "Cloudflare AI Gateway Timeout 504" in rerank_obs["error"]

    # E1 remains chunk-1 because without reranker, c1 had higher initial score
    assert trace_arg.alias_mapping["E1"] == "chunk-1"


def test_postgres_recheck_revocation_fails_closed():
    """Verify PostgreSQL snapshot recheck fails closed if active generation is revoked."""
    c1 = _make_candidate(1, "Text one", fusion_score=0.90)
    retrieval_result = _make_retrieval_result((c1,))

    store = Mock()
    store.retrieve_candidates.return_value = retrieval_result
    store.require_lexical_corpus.return_value = None
    # Simulate race condition: document was archived/revoked right before reranker sees it
    store.revalidate_lexical_snapshot.side_effect = KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    generator = Mock()
    reranker = FakeRerankingProvider(score_map={"chunk-1": 0.99})
    config = RerankingConfiguration.cloudflare_bge_reranker_v1()

    answer_question = _build_answer_question(store, generator, reranker, config)
    command = QuestionCommand(workspace_id="ws-1", question="some question")
    principal = WorkspacePrincipal(workspace_id="ws-1", key_id="key-1")

    with pytest.raises(KnoraError) as exc_info:
        asyncio.run(answer_question.execute(command, principal))

    assert exc_info.value.code == "LEXICAL_RETRIEVAL_UNAVAILABLE"
    # Reranker was NOT called because fail-closed happened before sending source
    assert len(reranker.calls) == 0
    assert not generator.generate.called
