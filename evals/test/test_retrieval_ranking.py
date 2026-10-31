"""Tests for pure ranking scorer (nDCG@10, Hit@k, MRR, Recall@k, quantization gate)."""

import math

import pytest
from evals.runners.retrieval_ranking import (
    RankingEvaluationError,
    compute_dcg,
    compute_idcg,
    compute_ndcg,
    macro_average_ranking,
    score_ranking_case,
    verify_quantization_ndcg_gate,
)


def test_hand_calculated_example():
    """Hand-calculated test specified in S4 plan:

    Grades: A=1, B=1, C=0.
    Ranking: [A, C, B].
    DCG = (2^1 - 1)/log2(2) + (2^0 - 1)/log2(3) + (2^1 - 1)/log2(4)
        = 1.0 + 0.0 + 0.5 = 1.5.
    IDCG = (2^1 - 1)/log2(2) + (2^1 - 1)/log2(3) + (2^0 - 1)/log2(4)
         = 1.0 + 1.0 / log2(3).
    """
    judgments = {"A": 1, "B": 1, "C": 0}
    ranking = ["A", "C", "B"]

    result = score_ranking_case("query-hand", ranking, judgments, k=10)

    expected_dcg = 1.0 + 0.0 + 0.5  # 1.5
    expected_idcg = 1.0 + 1.0 / math.log2(3)
    expected_ndcg = expected_dcg / expected_idcg

    assert pytest.approx(result.dcg, rel=1e-9) == expected_dcg
    assert pytest.approx(result.idcg, rel=1e-9) == expected_idcg
    assert pytest.approx(result.ndcg, rel=1e-9) == expected_ndcg
    assert result.status == "observed"


def test_perfect_ranking_yields_one():
    """Ranking all relevant items first yields nDCG = 1.0."""
    judgments = {"A": 1, "B": 1, "C": 0}
    ranking = ["A", "B", "C"]

    result = score_ranking_case("query-perfect", ranking, judgments, k=10)
    assert pytest.approx(result.ndcg, rel=1e-9) == 1.0


def test_lower_ranking_of_relevant_items_decreases_score():
    """Pushing relevant items lower in the rank decreases nDCG."""
    judgments = {"A": 1, "B": 1, "C": 0, "D": 0}
    r_high = score_ranking_case("q", ["A", "B", "C", "D"], judgments, k=10)
    r_mid = score_ranking_case("q", ["A", "C", "B", "D"], judgments, k=10)
    r_low = score_ranking_case("q", ["C", "D", "A", "B"], judgments, k=10)

    assert r_high.ndcg > r_mid.ndcg > r_low.ndcg


def test_tie_policy_among_equal_grades():
    """Equal grades in swapped positions produce identical DCG."""
    grades_1 = [1, 1, 0]
    grades_2 = [1, 1, 0]
    assert compute_dcg(grades_1, k=10) == compute_dcg(grades_2, k=10)


def test_short_and_empty_ranked_lists():
    """Lists shorter than cutoff k are evaluated on observed length; empty list yields 0 DCG."""
    assert compute_dcg([], k=10) == 0.0
    assert compute_idcg([], k=10) == 0.0
    assert compute_ndcg([], [], k=10) is None

    # Short list of 2 items
    judgments = {"A": 1, "B": 1, "C": 1}
    result = score_ranking_case("q-short", ["A", "B"], judgments, k=10)
    # Available has 3 items with grade 1, ranked only has 2
    assert result.dcg < result.idcg
    assert result.ndcg is not None
    assert result.ndcg < 1.0


def test_zero_idcg_handling():
    """When no relevant items exist (all grades 0), IDCG=0, nDCG is None (not applicable)."""
    judgments = {"A": 0, "B": 0, "C": 0}
    result = score_ranking_case("q-zero", ["A", "B", "C"], judgments, k=10)
    assert result.idcg == 0.0
    assert result.ndcg is None
    assert result.status == "not_applicable"
    assert result.hit_at_k is None
    assert result.mrr is None
    assert result.recall_at_k is None


def test_duplicate_ranked_ids_rejected():
    """Duplicate candidate IDs in ranked list must be rejected."""
    judgments = {"A": 1, "B": 1}
    with pytest.raises(RankingEvaluationError, match="duplicate ranked chunk IDs"):
        score_ranking_case("q-dup", ["A", "A", "B"], judgments, k=10)


def test_unjudged_candidate_rejected():
    """Unjudged candidate in top-k must raise error, never silently convert to 0."""
    judgments = {"A": 1, "B": 0}
    with pytest.raises(RankingEvaluationError, match="unjudged candidate at rank 2: C"):
        score_ranking_case("q-unjudged", ["A", "C", "B"], judgments, k=10, require_exhaustive=True)


def test_candidate_outside_authorized_universe_rejected():
    """Candidates outside authorized universe must be rejected."""
    universe = {"A", "B", "C"}
    judgments = {"A": 1, "B": 0, "D": 0}
    with pytest.raises(RankingEvaluationError, match="outside authorized universe"):
        score_ranking_case("q-univ", ["A", "D"], judgments, universe_chunk_ids=universe, k=10)


def test_macro_average_and_denominators():
    """Macro-average tracks evaluable, not_applicable, and missing_or_failed cases."""
    j1 = {"A": 1, "B": 0}
    j2 = {"A": 0, "B": 0}  # IDCG=0 -> N/A
    j3 = {"A": 1, "B": 1}

    c1 = score_ranking_case("q1", ["A", "B"], j1, k=10)  # nDCG = 1.0
    c2 = score_ranking_case("q2", ["A", "B"], j2, k=10)  # N/A
    c3 = score_ranking_case("q3", ["B", "A"], j3, k=10)  # nDCG < 1.0

    macro = macro_average_ranking([c1, c2, c3])

    assert macro.denominators["total"] == 3
    assert macro.denominators["evaluable"] == 2
    assert macro.denominators["not_applicable"] == 1
    assert macro.denominators["missing_or_failed"] == 0

    assert macro.macro_ndcg is not None
    assert macro.macro_ndcg == (c1.ndcg + c3.ndcg) / 2.0


def test_quantization_gate_drop_thresholds():
    """Gate bits4-vs-float32 accepts absolute drop <= 0.01 and rejects > 0.01."""
    # Pass: drop exactly 0.01
    g_exact = verify_quantization_ndcg_gate(0.850, 0.840, max_allowed_drop=0.01)
    assert g_exact.passed is True
    assert pytest.approx(g_exact.drop, abs=1e-9) == 0.01

    # Pass: drop < 0.01
    g_pass = verify_quantization_ndcg_gate(0.850, 0.845, max_allowed_drop=0.01)
    assert g_pass.passed is True
    assert pytest.approx(g_pass.drop, abs=1e-9) == 0.005

    # Fail: drop > 0.01
    g_fail = verify_quantization_ndcg_gate(0.850, 0.838, max_allowed_drop=0.01)
    assert g_fail.passed is False
    assert "EXCESSIVE_DROP" in g_fail.reason

    # Fail: missing metric (None)
    g_none_f32 = verify_quantization_ndcg_gate(None, 0.840, max_allowed_drop=0.01)
    assert g_none_f32.passed is False
    assert "MISSING_METRIC" in g_none_f32.reason

    g_none_b4 = verify_quantization_ndcg_gate(0.850, None, max_allowed_drop=0.01)
    assert g_none_b4.passed is False
    assert "MISSING_METRIC" in g_none_b4.reason


def test_recall_counts_items_not_grade_weight():
    from evals.runners.retrieval_ranking import compute_recall_at_k

    assert compute_recall_at_k([3, 0], total_positive=2, k=2) == 0.5


def test_mrr_cutoff_at_k():
    from evals.runners.retrieval_ranking import compute_mrr

    assert compute_mrr([0] * 10 + [1], total_positive=1, k=10) == 0.0
