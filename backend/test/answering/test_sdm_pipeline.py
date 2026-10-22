"""Pipeline integration tests for Sequential Dependence Model (SDM) reranking."""

from __future__ import annotations

import asyncio
import math
from unittest.mock import Mock

from knora.answering import stores
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.sequential_dependence import CorpusStatistics
from knora.domain.access import WorkspacePrincipal
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration
from knora.providers.generation import GenerationResult


def _make_candidate(
    index: int,
    content: str,
    *,
    fusion_score: float = 0.5,
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
        statistics_digest="a" * 64,
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


def test_sdm_pipeline_stage_order_and_reranking():
    """Verify BM25/Dense -> DBSF candidates -> SDM reranking -> Evidence selection."""
    c1 = _make_candidate(1, "unrelated text without query words", fusion_score=0.90)
    c2 = _make_candidate(2, "exact query phrase sequential dependence", fusion_score=0.70)
    c3 = _make_candidate(3, "dependence sequential words reversed", fusion_score=0.75)

    retrieval_result = _make_retrieval_result((c1, c3, c2))

    store = Mock()
    store.retrieve_candidates.return_value = retrieval_result
    store.require_lexical_corpus.return_value = None
    store.persist_trace.return_value = "trace-123"

    generator = Mock()
    generator.generate = Mock(
        side_effect=lambda **kwargs: asyncio.sleep(
            0,
            result=GenerationResult(
                decision="ANSWER",
                answer="Sample answer text [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="cf",
                model="llama",
                finish_reason="stop",
                usage={"total_tokens": 50},
            ),
        )
    )

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

    config = stores.RetrievalConfiguration.hybrid_sdm_top8_v3()
    answer_question = AnswerQuestion(
        store=store,
        generation_provider=generator,
        embedding_provider=embedding_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=config,
    )

    command = QuestionCommand(
        workspace_id="ws-1",
        question="sequential dependence",
    )
    principal = WorkspacePrincipal(
        workspace_id="ws-1",
        key_id="key-1",
    )

    result = asyncio.run(answer_question.execute(command, principal))
    assert result.decision == "ANSWER"
    assert result.answer == "Sample answer text [[E1]]."

    # Verify trace persisted has SDM status completed
    assert store.persist_trace.called
    trace_arg = store.persist_trace.call_args[0][0]
    metadata = trace_arg.provider_metadata
    assert "sdm" in metadata["retrieval"]
    assert metadata["retrieval"]["sdm"]["status"] == "completed"
    assert metadata["retrieval"]["sdm"]["policy_id"] == "sdm-metzler-croft-2005-v1"

    # Evidence selected: c2 had lower DBSF (0.70) than c1 (0.90),
    # but exact ordered match boosted c2's SDM score so c2 is top-ranked
    assert trace_arg.alias_mapping["E1"] == "chunk-2"
    assert trace_arg.retrieved_chunk_ids[0] == "chunk-2"


def test_sdm_pipeline_unrun_records_not_run():
    """When SDM policy is not configured, trace records sdm status as not_run."""
    c1 = _make_candidate(1, "some text content", fusion_score=0.90)
    retrieval_result = _make_retrieval_result((c1,))

    store = Mock()
    store.retrieve_candidates.return_value = retrieval_result
    store.require_lexical_corpus.return_value = None
    store.persist_trace.return_value = "trace-456"

    generator = Mock()
    generator.generate = Mock(
        side_effect=lambda **kwargs: asyncio.sleep(
            0,
            result=GenerationResult(
                decision="ANSWER",
                answer="Answer [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="cf",
                model="llama",
                finish_reason="stop",
                usage={},
            ),
        )
    )

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

    # Standard hybrid without SDM
    config = stores.RetrievalConfiguration.hybrid_top8_v3()
    answer_question = AnswerQuestion(
        store=store,
        generation_provider=generator,
        embedding_provider=embedding_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=config,
    )

    command = QuestionCommand(workspace_id="ws-1", question="test question")
    principal = WorkspacePrincipal(workspace_id="ws-1", key_id="key-1")

    asyncio.run(answer_question.execute(command, principal))

    trace_arg = store.persist_trace.call_args[0][0]
    metadata = trace_arg.provider_metadata
    assert "sdm" in metadata["retrieval"]
    assert metadata["retrieval"]["sdm"]["status"] == "not_run"


def test_sdm_pipeline_preserves_all_chunk_locators():
    """Verify chunk locators, lines, offsets and heading paths remain intact."""
    c = _make_candidate(1, "exact match", fusion_score=0.8)
    retrieval_result = _make_retrieval_result((c,))

    store = Mock()
    store.retrieve_candidates.return_value = retrieval_result
    store.require_lexical_corpus.return_value = None
    store.persist_trace.return_value = "trace-789"

    generator = Mock()
    generator.generate = Mock(
        side_effect=lambda **kwargs: asyncio.sleep(
            0,
            result=GenerationResult(
                decision="ANSWER",
                answer="Answer [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="cf",
                model="llama",
                finish_reason="stop",
                usage={},
            ),
        )
    )

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

    config = stores.RetrievalConfiguration.hybrid_sdm_top8_v3()
    answer_question = AnswerQuestion(
        store=store,
        generation_provider=generator,
        embedding_provider=embedding_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=config,
    )

    command = QuestionCommand(workspace_id="ws-1", question="exact match")
    principal = WorkspacePrincipal(workspace_id="ws-1", key_id="key-1")

    result = asyncio.run(answer_question.execute(command, principal))
    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.source_key == "policy"
    assert citation.source_name == "policy.pdf"
    assert citation.page_start == 1
    assert citation.page_end == 1

    trace_arg = store.persist_trace.call_args[0][0]
    dec = trace_arg.candidate_decisions[0]
    assert dec["chunk_id"] == "chunk-1"
    assert "sdm_contribution" in dec
    assert dec["sdm_contribution"]["sdm_rank"] == 1


def test_sdm_distractor_invariance_and_statistics_digest_trace():
    """Verify SDM scores for target candidates are invariant to distractor pool changes,
    and actual statistics_digest is bound into trace."""
    c_target = _make_candidate(2, "exact query phrase sequential dependence", fusion_score=0.70)
    c_distractor1 = _make_candidate(1, "completely unrelated sports text", fusion_score=0.90)
    c_distractor2 = _make_candidate(3, "another unrelated financial report", fusion_score=0.85)

    # 1. Pipeline execution with only target candidate
    retrieval_single = _make_retrieval_result((c_target,))
    store_single = Mock()
    store_single.retrieve_candidates.return_value = retrieval_single
    store_single.require_lexical_corpus.return_value = None
    store_single.persist_trace.return_value = "trace-single"
    corpus_stats = CorpusStatistics(
        total_tokens=1000,
        total_chunks=10,
        unigram_frequencies={"exact": 5, "query": 5, "phrase": 5, "sequential": 5, "dependence": 5},
        statistics_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    store_single.read_corpus_statistics.return_value = corpus_stats

    generator = Mock()
    generator.generate = Mock(
        side_effect=lambda **kwargs: asyncio.sleep(
            0,
            result=GenerationResult(
                decision="ANSWER",
                answer="Answer [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="cf",
                model="llama",
                finish_reason="stop",
                usage={},
            ),
        )
    )
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
    config = stores.RetrievalConfiguration.hybrid_sdm_top8_v3()

    aq_single = AnswerQuestion(
        store=store_single,
        generation_provider=generator,
        embedding_provider=embedding_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=config,
    )
    command = QuestionCommand(workspace_id="ws-1", question="sequential dependence")
    principal = WorkspacePrincipal(workspace_id="ws-1", key_id="key-1")

    asyncio.run(aq_single.execute(command, principal))
    trace_single = store_single.persist_trace.call_args[0][0]
    sdm_single_score = trace_single.candidate_decisions[0]["sdm_contribution"]["sdm_score"]

    # Verify trace records the authoritative statistics_digest
    assert (
        trace_single.provider_metadata["retrieval"]["sdm"]["statistics_digest"]
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )

    # 2. Pipeline execution with target candidate + distractors in candidate pool
    retrieval_multi = _make_retrieval_result((c_distractor1, c_distractor2, c_target))
    store_multi = Mock()
    store_multi.retrieve_candidates.return_value = retrieval_multi
    store_multi.require_lexical_corpus.return_value = None
    store_multi.persist_trace.return_value = "trace-multi"
    store_multi.read_corpus_statistics.return_value = corpus_stats

    aq_multi = AnswerQuestion(
        store=store_multi,
        generation_provider=generator,
        embedding_provider=embedding_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=config,
    )
    asyncio.run(aq_multi.execute(command, principal))
    trace_multi = store_multi.persist_trace.call_args[0][0]

    # Find target candidate decision in multi-candidate trace
    target_dec = next(d for d in trace_multi.candidate_decisions if d["chunk_id"] == "chunk-2")
    sdm_multi_score = target_dec["sdm_contribution"]["sdm_score"]

    # Background probabilities are pinned to corpus snapshot, not candidate pool:
    # Target candidate SDM score is IDENTICAL regardless of distractors in pool!
    assert math.isclose(sdm_single_score, sdm_multi_score, rel_tol=1e-9)
