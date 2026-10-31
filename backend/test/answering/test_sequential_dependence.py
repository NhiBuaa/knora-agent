"""Unit tests and hand-computed reference fixtures for Sequential Dependence Model (SDM).

References:
    Metzler, D. and Croft, W.B., "A Markov Random Field Model for Term Dependencies",
    SIGIR 2005. https://lintool.github.io/Ivory/docs/publications/Metzler_Croft_SIGIR2005.pdf
"""

from __future__ import annotations

import math

import pytest

from knora.answering.sequential_dependence import (
    CorpusStatistics,
    SequentialDependenceConfig,
    SequentialDependenceScorer,
    tokenize_lexical_text,
)
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


def _make_candidate(
    chunk_id: str,
    content: str,
    *,
    fusion_score: float = 0.5,
    token_count: int | None = None,
) -> RetrievalCandidate:
    tokens = tokenize_lexical_text(content)
    actual_count = token_count if token_count is not None else len(tokens)
    return RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="src-1",
        source_name="src-1.pdf",
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
        token_count=actual_count,
        cosine_distance=None,
        similarity=None,
        fusion_score=fusion_score,
    )


def test_tokenize_lexical_text_special_cases():
    """Verify NFKC lowercase, AUTH_403, 3.1, Vietnamese diacritics, numbers and negation."""
    text = "AUTH_403: phiên bản 3.1 không tìm thấy lỗi 404 (Việt-Anh)"
    tokens = tokenize_lexical_text(text)
    assert tokens == (
        "auth_403",
        "phiên",
        "bản",
        "3.1",
        "không",
        "tìm",
        "thấy",
        "lỗi",
        "404",
        "việt",
        "anh",
    )


def test_hand_computed_numerical_components():
    """Verify exact hand-calculated log-probabilities for each SDM component."""
    # Setup miniature collection stats:
    # |C| = 100, mu = 10.0, lambda_t = 0.80, lambda_o = 0.15, lambda_u = 0.05
    corpus = CorpusStatistics(
        total_tokens=100,
        total_chunks=10,
        unigram_frequencies={"cat": 10, "dog": 5},
    )
    config = SequentialDependenceConfig(
        lambda_t=0.80,
        lambda_o=0.15,
        lambda_u=0.05,
        mu=10.0,
        window_size=8,
        blend_alpha=0.30,
    )
    scorer = SequentialDependenceScorer(config=config, corpus_stats=corpus)

    # Document: "cat dog" -> length = 2
    # c_T("cat")=1, c_T("dog")=1, c_O=1, c_U=1
    # P("cat"|C) = 10/100 = 0.10, P("dog"|C) = 5/100 = 0.05
    # P_O = 0.10 * 0.05 = 0.005
    # P_U = min(1.0, 8 * 0.005) = 0.04
    # Denom = 2 + 10 = 12
    # f_T("cat") = ln((1 + 10*0.10)/12) = ln(2/12) = ln(1/6)
    # f_T("dog") = ln((1 + 10*0.05)/12) = ln(1.5/12) = ln(0.125)
    # S_T = ln(1/6) + ln(0.125)
    expected_f_t_cat = math.log(2.0 / 12.0)
    expected_f_t_dog = math.log(1.5 / 12.0)
    expected_s_t = expected_f_t_cat + expected_f_t_dog

    # f_O = ln((1 + 10*0.005)/12) = ln(1.05/12) = ln(0.0875)
    expected_s_o = math.log(1.05 / 12.0)

    # f_U = ln((1 + 10*0.04)/12) = ln(1.4/12)
    expected_s_u = math.log(1.4 / 12.0)

    expected_s_raw = 0.80 * expected_s_t + 0.15 * expected_s_o + 0.05 * expected_s_u

    candidate = _make_candidate("doc-mini", "cat dog")
    results = scorer.score_candidates("cat dog", [candidate])
    assert len(results) == 1
    res = results[0]

    assert pytest.approx(res.unigram_score, rel=1e-5) == expected_s_t
    assert pytest.approx(res.ordered_score, rel=1e-5) == expected_s_o
    assert pytest.approx(res.unordered_score, rel=1e-5) == expected_s_u
    assert pytest.approx(res.raw_sdm_score, rel=1e-5) == expected_s_raw


def test_same_unigrams_different_order_and_window_distances():
    """Same unigram counts but different order and distances produce distinct scores."""
    corpus = CorpusStatistics(
        total_tokens=1000,
        total_chunks=100,
        unigram_frequencies={"quick": 20, "brown": 20},
    )
    config = SequentialDependenceConfig(
        lambda_t=0.70,
        lambda_o=0.20,
        lambda_u=0.10,
        mu=10.0,
        window_size=3,
    )
    scorer = SequentialDependenceScorer(config=config, corpus_stats=corpus)

    # All three documents have identical length (6 tokens) and identical words:
    # Doc 1: "the quick brown fox one two" -> ordered & unordered match (dist 1 <= 2)
    c1 = _make_candidate("c1", "the quick brown fox one two")
    # Doc 2: "the brown quick fox one two" -> reversed: ordered=0, unordered=1 (dist 1 <= 2)
    c2 = _make_candidate("c2", "the brown quick fox one two")
    # Doc 3: "the quick one two brown fox" -> dist 3 > 2: ordered=0, unordered=0 (outside window)
    c3 = _make_candidate("c3", "the quick one two brown fox")

    scored = scorer.score_candidates("quick brown", [c1, c2, c3])
    by_id = {r.candidate.chunk_id: r for r in scored}

    # All have identical unigram counts and document lengths -> identical unigram_score
    assert pytest.approx(by_id["c1"].unigram_score, rel=1e-4) == by_id["c2"].unigram_score
    assert pytest.approx(by_id["c2"].unigram_score, rel=1e-4) == by_id["c3"].unigram_score

    # Ordered score: c1 > c2 == c3
    assert by_id["c1"].ordered_score > by_id["c2"].ordered_score
    assert pytest.approx(by_id["c2"].ordered_score, rel=1e-4) == by_id["c3"].ordered_score

    # Unordered score: c1 == c2 > c3
    assert pytest.approx(by_id["c1"].unordered_score, rel=1e-4) == by_id["c2"].unordered_score
    assert by_id["c2"].unordered_score > by_id["c3"].unordered_score

    # Final ranking order: c1 first, then c2, c3 last
    assert scored[0].candidate.chunk_id == "c1"
    assert scored[1].candidate.chunk_id == "c2"
    assert scored[2].candidate.chunk_id == "c3"


def test_repeated_terms_in_query():
    """Handling repeated terms in query correctly."""
    corpus = CorpusStatistics(
        total_tokens=500,
        total_chunks=50,
        unigram_frequencies={"error": 30},
    )
    scorer = SequentialDependenceScorer(corpus_stats=corpus)

    c_adj = _make_candidate("c_adj", "system error error log")
    c_sep = _make_candidate("c_sep", "system error fatal error log")

    scored = scorer.score_candidates("error error", [c_adj, c_sep])
    assert scored[0].candidate.chunk_id == "c_adj"
    assert scored[0].ordered_score > scored[1].ordered_score


def test_exact_window_edge():
    """Tokens at window edge (distance == window-1 vs window) correctly partitioned."""
    corpus = CorpusStatistics(
        total_tokens=1000,
        total_chunks=50,
        unigram_frequencies={"start": 10, "finish": 10},
    )
    # Window size = 8
    config = SequentialDependenceConfig(window_size=8, mu=10.0)
    scorer = SequentialDependenceScorer(config=config, corpus_stats=corpus)

    # Span = 8 tokens (start at 0, finish at 7) -> inside window
    c_inside = _make_candidate("c_in", "start a b c d e f finish")
    # Span = 9 tokens (start at 0, finish at 8) -> outside window
    c_outside = _make_candidate("c_out", "start a b c d e f g finish")

    scored = scorer.score_candidates("start finish", [c_inside, c_outside])
    by_id = {r.candidate.chunk_id: r for r in scored}

    assert by_id["c_in"].unordered_score > by_id["c_out"].unordered_score


def test_dense_only_candidates_preserved_without_nan():
    """Candidates with 0 lexical matches receive finite score and retain DBSF contribution."""
    corpus = CorpusStatistics(
        total_tokens=1000,
        total_chunks=100,
        unigram_frequencies={"neural": 25, "network": 25},
    )
    config = SequentialDependenceConfig(blend_alpha=0.30)
    scorer = SequentialDependenceScorer(config=config, corpus_stats=corpus)

    # Lexical match candidate with low DBSF score
    c_lex = _make_candidate("c_lex", "neural network deep architecture", fusion_score=0.40)
    # Dense-only candidate with high DBSF score but completely different words
    c_dense = _make_candidate(
        "c_dense", "artificial intelligence model parameters", fusion_score=0.95
    )

    scored = scorer.score_candidates("neural network", [c_lex, c_dense])
    by_id = {r.candidate.chunk_id: r for r in scored}

    assert math.isfinite(by_id["c_dense"].raw_sdm_score)
    assert math.isfinite(by_id["c_dense"].combined_score)
    assert by_id["c_dense"].combined_score > 0.0
    # Dense candidate's high DBSF keeps it competitive
    assert by_id["c_dense"].candidate.fusion_score == 0.95


def test_deterministic_tie_break_and_permutation_invariance():
    """Candidate permutation produces identical ranking and deterministic tie-breaking."""
    corpus = CorpusStatistics(
        total_tokens=500,
        total_chunks=50,
        unigram_frequencies={"alpha": 10, "beta": 10},
    )
    scorer = SequentialDependenceScorer(corpus_stats=corpus)

    c_b = _make_candidate("chunk-b", "alpha beta", fusion_score=0.8)
    c_a = _make_candidate("chunk-a", "alpha beta", fusion_score=0.8)

    # Order 1: c_b then c_a
    res1 = scorer.score_candidates("alpha beta", [c_b, c_a])
    # Order 2: c_a then c_b
    res2 = scorer.score_candidates("alpha beta", [c_a, c_b])

    # Identical score, tie-break by chunk_id ascending ("chunk-a" before "chunk-b")
    assert [r.candidate.chunk_id for r in res1] == ["chunk-a", "chunk-b"]
    assert [r.candidate.chunk_id for r in res2] == ["chunk-a", "chunk-b"]


def test_invalid_configurations_rejected():
    """Verify invalid weights, window size, smoothing or corpus stats raise ValueError."""
    with pytest.raises(ValueError, match="weights must be non-negative"):
        SequentialDependenceConfig(lambda_t=-0.1)

    with pytest.raises(ValueError, match="sum of weights must be positive"):
        SequentialDependenceConfig(lambda_t=0.0, lambda_o=0.0, lambda_u=0.0)

    with pytest.raises(ValueError, match="window_size must be at least 2"):
        SequentialDependenceConfig(window_size=1)

    with pytest.raises(ValueError, match="mu must be positive"):
        SequentialDependenceConfig(mu=0.0)

    with pytest.raises(ValueError, match="blend_alpha must be between 0 and 1"):
        SequentialDependenceConfig(blend_alpha=1.5)

    with pytest.raises(ValueError, match="total_tokens must be positive"):
        CorpusStatistics(total_tokens=0, total_chunks=10)


def test_empty_or_single_token_query():
    """Empty query or single token query handled safely."""
    corpus = CorpusStatistics(
        total_tokens=500,
        total_chunks=50,
        unigram_frequencies={"search": 15},
    )
    scorer = SequentialDependenceScorer(corpus_stats=corpus)

    c1 = _make_candidate("c1", "search engine indexing", fusion_score=0.7)
    c2 = _make_candidate("c2", "database query optimization", fusion_score=0.6)

    # Empty query: returns candidates preserved with original rank
    empty_res = scorer.score_candidates("", [c1, c2])
    assert len(empty_res) == 2
    assert empty_res[0].candidate.chunk_id == "c1"

    # Single token query: ordered and unordered are not applicable, only unigram scores
    single_res = scorer.score_candidates("search", [c1, c2])
    assert len(single_res) == 2
    assert single_res[0].ordered_score == 0.0
    assert single_res[0].unordered_score == 0.0
    assert single_res[0].unigram_score > single_res[1].unigram_score


def test_retrieval_configuration_hybrid_sdm_top8_v3():
    """Verify RetrievalConfiguration profile and resolver for hybrid_sdm_top8_v3."""
    config = RetrievalConfiguration.hybrid_sdm_top8_v3()
    assert config.id == "retrieval-hybrid-sdm-top8-v3"
    assert config.strategy == "hybrid"
    assert config.sdm_policy_id == "sdm-metzler-croft-2005-v1"
    assert config.fusion_policy_id == "dbsf-v1"
    assert config.candidate_k == 100
