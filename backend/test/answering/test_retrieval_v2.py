import pytest

from knora.answering.retrieval_v2 import normalize_fts_m3_or_v2
from knora.answering.stores import RetrievalConfiguration


def test_fts_m3_or_v2_normalizes_to_safe_sorted_or_lexemes() -> None:
    assert normalize_fts_m3_or_v2("What is the REFUND—period?") == ("period", "refund")
    assert normalize_fts_m3_or_v2("30 days") == ("30", "days")
    assert normalize_fts_m3_or_v2("' OR 1=1; refund refund") == ("1", "refund")
    assert normalize_fts_m3_or_v2("the and what") == ()


def test_retrieval_v2_configs_have_exact_allowed_differences() -> None:
    vector = RetrievalConfiguration.milestone_three_vector_v2(min_similarity=0.42)
    hybrid = RetrievalConfiguration.milestone_three_hybrid_v2(min_similarity=0.42)
    vector_semantics = vector.parity_semantics()
    hybrid_semantics = hybrid.parity_semantics()
    differences = {
        name
        for name in vector_semantics
        if vector_semantics[name] != hybrid_semantics[name]
    }

    assert differences == {
        "strategy",
        "fts_candidate_k",
        "lexical_policy_id",
        "fusion_policy_id",
    }
    assert vector.vector_candidate_k == hybrid.vector_candidate_k == 8
    assert hybrid.fts_candidate_k == 8
    assert vector.id == "retrieval-m3-vector-v2"
    assert hybrid.id == "retrieval-m3-rrf-v2"


def test_retrieval_v2_requires_calibrated_numeric_threshold() -> None:
    with pytest.raises((TypeError, ValueError)):
        RetrievalConfiguration.milestone_three_vector_v2(min_similarity=None)  # type: ignore[arg-type]
