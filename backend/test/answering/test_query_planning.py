"""Tests for Query Planning, protected span extraction, and fast path execution."""

from __future__ import annotations

import pytest

from knora.answering.query_planning import (
    QueryPlanner,
    build_fast_path_plan,
    extract_protected_spans,
    is_fast_path_eligible,
    validate_protected_spans_preserved,
)
from knora.domain.errors import KnoraError


def test_extract_protected_spans_identifiers_and_numbers():
    query = "Lỗi AUTH_403 xảy ra tại mục 3.1 sau không quá 14 ngày"
    spans = extract_protected_spans(query)

    categories = {s.category: s.text for s in spans}
    assert "identifier" in categories
    assert categories["identifier"] == "AUTH_403"
    assert "section" in categories
    assert categories["section"] == "mục 3.1"
    assert "negation" in categories
    assert categories["negation"] == "không quá"
    assert "number" in categories
    assert categories["number"] == "14"
    assert "unit" in categories
    assert categories["unit"] == "ngày"


def test_validate_protected_spans_preserved_success():
    original_query = "Thời hạn không quá 14 ngày theo AUTH_403"
    original_spans = extract_protected_spans(original_query)

    # Rewritten query preserves all protected components
    rewritten = "Quy định AUTH_403 nêu thời gian xử lý không quá 14 ngày"
    validate_protected_spans_preserved(original_spans, rewritten)


def test_validate_protected_spans_rejects_identifier_mutation():
    original_query = "Kiểm tra mã lỗi AUTH_403"
    original_spans = extract_protected_spans(original_query)

    # Identifier was altered to AUTH_404
    tampered = "Kiểm tra mã lỗi AUTH_404"
    with pytest.raises(KnoraError) as exc_info:
        validate_protected_spans_preserved(original_spans, tampered)

    assert exc_info.value.code == "PROTECTED_SPAN_VIOLATION"


def test_validate_protected_spans_rejects_negation_loss():
    original_query = "Thời hạn không quá 14 ngày"
    original_spans = extract_protected_spans(original_query)

    # Negation 'không quá' was turned into 'khoảng'
    tampered = "Thời hạn khoảng 14 ngày"
    with pytest.raises(KnoraError) as exc_info:
        validate_protected_spans_preserved(original_spans, tampered)

    assert exc_info.value.code == "PROTECTED_SPAN_VIOLATION"


def test_fast_path_eligibility_simple_query():
    simple_query = "Điều kiện hưởng bảo hiểm xã hội một lần là gì?"
    assert is_fast_path_eligible(simple_query) is True


def test_fast_path_eligibility_multi_section_comparison():
    comparison_query = "So sánh quyền lợi giữa chương 2 và chương 5 của báo cáo"
    assert is_fast_path_eligible(comparison_query) is False


def test_build_fast_path_plan_structure():
    query = "Quy định về thời gian thử việc"
    plan = build_fast_path_plan(query, query_id="fast-1")

    assert plan.is_fast_path is True
    assert plan.original_query == query
    assert len(plan.subquestions) == 1
    assert plan.subquestions[0].id == "sub_1"
    assert len(plan.variants) == 1
    assert plan.variants[0].variant_kind == "original"

    obs = plan.to_observation()
    assert obs["is_fast_path"] is True
    assert obs["subquestions_count"] == 1


def test_query_planner_decomposes_multi_section_comparison():
    planner = QueryPlanner()
    query = "So sánh quy định tại chương 2 và chương 5"
    plan = planner.plan(query, query_id="plan-decomp-1")

    assert plan.is_fast_path is False
    assert len(plan.subquestions) >= 2
    assert any("chương 2" in sq.text.lower() for sq in plan.subquestions)
    assert any("chương 5" in sq.text.lower() for sq in plan.subquestions)
    assert len(plan.variants) >= 2


def test_query_decomposition_creates_atomic_subquestions_without_cross_contamination():
    planner = QueryPlanner()
    query = "So sánh quy định về thời hạn tại Chương 2 và giảm giá tại Chương 5"
    plan = planner.plan(query)

    assert not plan.is_fast_path
    assert len(plan.subquestions) == 2
    sq1, sq2 = plan.subquestions

    sq1_sections = [s.text for s in sq1.protected_spans if s.category == "section"]
    sq2_sections = [s.text for s in sq2.protected_spans if s.category == "section"]

    # sq1 must only contain Chapter 2 constraint, not Chapter 5
    assert any("Chương 2" in s for s in sq1_sections)
    assert not any("Chương 5" in s for s in sq1_sections)

    # sq2 must only contain Chapter 5 constraint, not Chapter 2
    assert any("Chương 5" in s for s in sq2_sections)
    assert not any("Chương 2" in s for s in sq2_sections)


def test_query_decomposition_preserves_positional_predicates_and_scoped_facts():
    """F12: Verify positional predicate preservation and isolated group constraints."""
    import hashlib

    from knora.answering.evidence_support import assess_evidence_support
    from knora.answering.stores import RetrievalCandidate

    def _make_cand(cid: str, text: str, heading: tuple[str, ...]) -> RetrievalCandidate:
        return RetrievalCandidate(
            document_id="d",
            document_version_id="v",
            source_key="policy",
            source_name="policy.pdf",
            chunk_set_id="s",
            embedding_set_id=None,
            embedding_configuration_id=None,
            chunk_id=cid,
            chunk_ordinal=0,
            heading_path=heading,
            start_line=1,
            end_line=10,
            content=text,
            content_checksum=hashlib.sha256(text.encode()).hexdigest(),
            token_count=len(text.split()),
            cosine_distance=None,
            similarity=None,
            fusion_score=0.5,
        )

    planner = QueryPlanner()

    # Case 1: Shared predicate before sections, global modifier after
    q1 = "So sánh thời hạn đổi trả Chương 2 và Chương 5, kèm AUTH_403 và AUTH_404"
    plan1 = planner.plan(q1)
    assert len(plan1.subquestions) == 2
    assert all("thời hạn đổi trả" in sq.text for sq in plan1.subquestions)

    # Distractor candidates talking about uniforms must not be falsely supported
    unrelated = [
        _make_cand("2", "Chương 2 quy định về đồng phục nhân viên.", ("Chương 2",)),
        _make_cand("5", "Chương 5 quy định về đồng phục nhân viên.", ("Chương 5",)),
    ]
    eval1 = assess_evidence_support(plan1.subquestions, unrelated)
    assert eval1.all_required_supported is False

    # Case 2: Positional predicate per section (7 days for C2, 20% discount for C5)
    q2 = "So sánh Chương 2 đổi trả trong 7 ngày và Chương 5 giảm giá 20%"
    plan2 = planner.plan(q2)
    assert len(plan2.subquestions) == 2
    sq1, sq2 = plan2.subquestions
    assert "7 ngày" in sq1.text and "20%" not in sq1.text
    assert "20%" in sq2.text and "7 ngày" not in sq2.text

    scoped_sources = [
        _make_cand("a", "Chương 2 đổi trả trong 7 ngày", ("Chương 2",)),
        _make_cand("b", "Chương 5 giảm giá 20%", ("Chương 5",)),
    ]
    eval2 = assess_evidence_support(plan2.subquestions, scoped_sources)
    assert eval2.all_required_supported is True
