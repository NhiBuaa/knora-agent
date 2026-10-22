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
