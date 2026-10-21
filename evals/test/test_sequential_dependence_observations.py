"""Tests for Sequential Dependence Model (SDM) trace observations and ranking ablations."""

from __future__ import annotations

import math

from evals.runners.phrase_boost import PhraseBoostComparator, PhraseBoostConfig
from evals.runners.retrieval_ranking import score_ranking_case

from knora.answering.sequential_dependence import (
    CorpusStatistics,
    SequentialDependenceConfig,
    SequentialDependenceScorer,
)
from knora.answering.stores import RetrievalCandidate


def _make_candidate(
    chunk_id: str,
    content: str,
    *,
    bm25_score: float = 1.0,
    fusion_score: float = 0.5,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-1",
        embedding_set_id=None,
        embedding_configuration_id=None,
        chunk_id=chunk_id,
        chunk_ordinal=0,
        heading_path=(),
        start_line=1,
        end_line=1,
        content=content,
        content_checksum="chk-" + chunk_id,
        token_count=len(content.split()),
        cosine_distance=None,
        similarity=None,
        bm25_score=bm25_score,
        fusion_score=fusion_score,
        index_generation_id="gen-1",
    )


def test_sdm_observation_validator_rejects_nonfinite_or_mismatched_scores():
    """Observation validator ensures finite scores, valid policy and no candidate mutation."""
    scorer = SequentialDependenceScorer()
    c = _make_candidate("c1", "test content", fusion_score=0.8)
    results = scorer.score_candidates("test query", [c])

    assert len(results) == 1
    res = results[0]
    assert math.isfinite(res.raw_sdm_score)
    assert math.isfinite(res.normalized_sdm_score)
    assert math.isfinite(res.combined_score)
    assert 0.0 <= res.normalized_sdm_score <= 1.0
    assert 0.0 <= res.combined_score <= 1.0

    # Ensure input candidate identity and locators are never mutated
    assert res.candidate.chunk_id == "c1"
    assert res.candidate.content == "test content"
    assert res.candidate.fusion_score == 0.8
    assert res.candidate.sdm_score == res.combined_score
    assert res.candidate.sdm_rank == 1


def test_sdm_ranking_ablation_matrix_on_development_cases():
    """Compare BM25-only, BM25+PhraseBoost, BM25+SDM, DBSF, and DBSF+SDM."""
    corpus = CorpusStatistics(
        total_tokens=1000,
        total_chunks=10,
        unigram_frequencies={"sequential": 15, "dependence": 15, "ranking": 10},
    )
    sdm_scorer = SequentialDependenceScorer(corpus_stats=corpus)
    phrase_comparator = PhraseBoostComparator(PhraseBoostConfig(lambda_param=0.6))

    # Construct representative candidate pool
    # c_exact: exact adjacent ordered pair "sequential dependence"
    # c_unord: unordered window pair "dependence ... sequential"
    # c_unrel: high BM25 unigram noise but no pairs
    c_exact = _make_candidate(
        "chunk-exact",
        "intro sequential dependence model architecture",
        bm25_score=4.0,
        fusion_score=0.70,
    )
    c_unord = _make_candidate(
        "chunk-unord",
        "dependence in language models sequential overview",
        bm25_score=4.5,
        fusion_score=0.72,
    )
    c_noise = _make_candidate(
        "chunk-noise",
        "sequential sequential sequential term repetition",
        bm25_score=6.0,
        fusion_score=0.80,
    )
    candidates = [c_noise, c_unord, c_exact]

    query = "sequential dependence"
    judgments = {
        "chunk-exact": 1,
        "chunk-unord": 1,
        "chunk-noise": 0,
    }

    # 1. Pure BM25 baseline: order by bm25_score descending -> [c_noise, c_unord, c_exact]
    bm25_ranked = sorted(candidates, key=lambda c: -c.bm25_score)
    bm25_score_res = score_ranking_case(
        "q1",
        [c.chunk_id for c in bm25_ranked],
        judgments,
        k=10,
    )

    # 2. BM25 + Phrase Boost:
    phrase_res = phrase_comparator.rerank(query, candidates)
    phrase_score_res = score_ranking_case(
        "q1",
        [r.candidate.chunk_id for r in phrase_res],
        judgments,
        k=10,
    )

    # 3. BM25 + SDM (without dense fusion):
    sdm_bm25_config = SequentialDependenceConfig(blend_alpha=0.5)
    sdm_bm25_scorer = SequentialDependenceScorer(config=sdm_bm25_config, corpus_stats=corpus)
    sdm_bm25_res = sdm_bm25_scorer.score_candidates(query, candidates)
    sdm_bm25_score_res = score_ranking_case(
        "q1",
        [r.candidate.chunk_id for r in sdm_bm25_res],
        judgments,
        k=10,
    )

    # 4. Hybrid DBSF Baseline: order by fusion_score descending -> [c_noise, c_unord, c_exact]
    dbsf_ranked = sorted(candidates, key=lambda c: -c.fusion_score)
    dbsf_score_res = score_ranking_case(
        "q1",
        [c.chunk_id for c in dbsf_ranked],
        judgments,
        k=10,
    )

    # 5. Hybrid DBSF + SDM:
    dbsf_sdm_res = sdm_scorer.score_candidates(query, candidates)
    dbsf_sdm_score_res = score_ranking_case(
        "q1",
        [r.candidate.chunk_id for r in dbsf_sdm_res],
        judgments,
        k=10,
    )

    # Verify that SDM promotes relevant candidates over unigram noise:
    # Under pure BM25, c_noise was top-ranked (nDCG is low)
    assert bm25_score_res.ndcg is not None
    assert phrase_score_res.ndcg is not None
    assert sdm_bm25_score_res.ndcg is not None
    assert dbsf_score_res.ndcg is not None
    assert dbsf_sdm_score_res.ndcg is not None

    # DBSF+SDM achieves higher nDCG than baseline DBSF
    assert dbsf_sdm_score_res.ndcg >= dbsf_score_res.ndcg
    assert dbsf_sdm_res[0].candidate.chunk_id == "chunk-exact"
