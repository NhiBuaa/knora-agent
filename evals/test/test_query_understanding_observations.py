"""Tests for Query Understanding trace observations and ablation comparisons.

Verifies QueryPlan, EvidenceSupportAssessment, and SourceVerification observation
structures, false-correction bounds, and protected span preservation.
Refs #153 (Retrieval V3 Stage 7 Task 9).
"""

from __future__ import annotations

import pytest

from knora.answering.evidence_support import assess_evidence_support
from knora.answering.query_correction import generate_typo_hypotheses
from knora.answering.query_planning import (
    ProtectedSpan,
    QueryPlan,
    QueryVariant,
    Subquestion,
    extract_protected_spans,
    validate_protected_spans_preserved,
)
from knora.answering.source_verification import (
    GroupVerificationOutcome,
    SourceVerificationResult,
)
from knora.answering.stores import RetrievalCandidate
from knora.domain.errors import KnoraError


def _make_candidate(
    chunk_id: str, content: str, heading_path: tuple[str, ...] = ()
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
        heading_path=heading_path,
        start_line=1,
        end_line=1,
        content=content,
        content_checksum=f"chk-{chunk_id}",
        token_count=len(content.split()),
        cosine_distance=None,
        similarity=0.9,
    )


def test_query_plan_observation_structure() -> None:
    sq = Subquestion(
        id="sq1",
        text="Chương 2 quy định gì về AUTH_403?",
        protected_spans=(
            ProtectedSpan("Chương 2", "section", 0, 8),
            ProtectedSpan("AUTH_403", "identifier", 24, 32),
        ),
        required=True,
    )
    variant = QueryVariant(
        query="Chương 2 mã lỗi AUTH_403",
        reason="rewrite",
        variant_kind="rewrite",
    )
    plan = QueryPlan(
        query_id="q1",
        original_query="Chương 2 quy định gì về AUTH_403?",
        is_fast_path=False,
        subquestions=(sq,),
        variants=(variant,),
        protected_spans=sq.protected_spans,
    )

    obs = plan.to_observation()
    assert obs["query_id"] == "q1"
    assert obs["is_fast_path"] is False
    assert obs["subquestions_count"] == 1
    assert obs["subquestion_ids"] == ["sq1"]
    assert obs["variants_count"] == 1
    assert obs["protected_spans_count"] == 2
    assert obs["protected_spans"][0]["text"] == "Chương 2"
    assert obs["protected_spans"][1]["text"] == "AUTH_403"


def test_evidence_support_observation_structure() -> None:
    sq = Subquestion(id="sq1", text="bảo mật hệ thống", required=True)
    cand = _make_candidate("c1", "quy định bảo mật hệ thống thông tin")

    assessment = assess_evidence_support([sq], [cand], purpose="final_support")
    obs = assessment.to_observation()

    assert obs["purpose"] == "final_support"
    assert obs["all_required_supported"] is True
    assert obs["missing_group_ids"] == []
    assert len(obs["group_assessments"]) == 1
    assert obs["group_assessments"][0]["group_id"] == "sq1"
    assert obs["group_assessments"][0]["status"] == "supported"


def test_source_verification_observation_structure() -> None:
    outcome = GroupVerificationOutcome(
        group_id="sq_ch5",
        status="found",
        recovered_chunk_ids=("c5",),
        reason="Recovered from section lookup",
        checked_sections=("Chương 5",),
    )
    c5 = _make_candidate("c5", "Chương 5 chính sách vận chuyển", ("Chương 5",))

    result = SourceVerificationResult(
        outcomes=(outcome,),
        recovered_candidates=(c5,),
        overall_status="found",
        verification_digest="digest123",
    )

    obs = result.to_observation()
    assert obs["overall_status"] == "found"
    assert obs["verification_digest"] == "digest123"
    assert obs["recovered_candidates_count"] == 1
    assert obs["recovered_chunk_ids"] == ["c5"]
    assert len(obs["outcomes"]) == 1
    assert obs["outcomes"][0]["status"] == "found"


def test_false_correction_rate_zero_on_correct_queries() -> None:
    """Verifies that completely correct queries are preserved without alterations."""
    correct_queries = [
        "Chính sách bảo hành sản phẩm năm 2026",
        "Quy trình xử lý lỗi AUTH_403 cho người dùng",
        "Chương 2 quy định về thời hạn hợp đồng lao động",
        "Điều 15 tiêu chuẩn an toàn bảo mật ISO 27001",
    ]

    for q in correct_queries:
        res = generate_typo_hypotheses(q)
        assert res.has_typos is False
        assert res.corrected_query is None


def test_protected_spans_guard_rejects_altered_identifiers() -> None:
    original = "Lỗi AUTH_403 trong Chương 2 không quá 14 ngày"
    spans = extract_protected_spans(original)

    # Valid rewrite preserving all spans
    valid_rewrite = "Trong Chương 2 lỗi AUTH_403 không quá 14 ngày được xử lý"
    validate_protected_spans_preserved(spans, valid_rewrite)

    # Invalid rewrite changing AUTH_403 to AUTH_404
    invalid_ident = "Trong Chương 2 lỗi AUTH_404 không quá 14 ngày được xử lý"
    with pytest.raises(KnoraError) as exc_info1:
        validate_protected_spans_preserved(spans, invalid_ident)
    assert exc_info1.value.code == "PROTECTED_SPAN_VIOLATION"

    # Invalid rewrite omitting section
    invalid_sec = "Lỗi AUTH_403 không quá 14 ngày được xử lý"
    with pytest.raises(KnoraError) as exc_info2:
        validate_protected_spans_preserved(spans, invalid_sec)
    assert exc_info2.value.code == "PROTECTED_SPAN_VIOLATION"
