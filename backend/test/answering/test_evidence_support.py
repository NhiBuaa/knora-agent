"""Tests for deterministic evidence support assessment.

Verifies that factual support against subquestions and constraints
(section, identifier, numbers, negations, keywords) is rigorously checked.
Refs #153 (Retrieval V3 Stage 7 Task 5).
"""

from __future__ import annotations

from knora.answering.evidence_support import assess_evidence_support
from knora.answering.query_planning import ProtectedSpan, Subquestion
from knora.answering.stores import RetrievalCandidate


def _make_candidate(
    chunk_id: str,
    content: str,
    heading_path: tuple[str, ...] = (),
    page_number: int = 1,
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
        end_line=10,
        content=content,
        content_checksum=f"chk-{chunk_id}",
        token_count=len(content.split()),
        cosine_distance=0.1,
        similarity=0.9,
        page_start=page_number,
        page_end=page_number,
    )


def test_correct_section_and_facts_supported() -> None:
    sq = Subquestion(
        id="sq1",
        text="Chương 2 quy định gì về thời hạn bảo hành 12 tháng?",
        protected_spans=(
            ProtectedSpan("Chương 2", "section", 0, 8),
            ProtectedSpan("12", "number", 43, 45),
        ),
        required=True,
    )
    cand = _make_candidate(
        "c1",
        "Nội dung quy định thời hạn bảo hành sản phẩm là 12 tháng kể từ ngày giao hàng.",
        heading_path=("Chương 2: Chính sách bảo hành",),
    )

    assessment = assess_evidence_support([sq], [cand], purpose="final_support")
    assert assessment.all_required_supported is True
    assert len(assessment.missing_group_ids) == 0
    assert assessment.group_assessments[0].status == "supported"
    assert assessment.group_assessments[0].supporting_chunk_ids == ("c1",)


def test_correct_section_but_missing_facts_unsupported() -> None:
    sq = Subquestion(
        id="sq1",
        text="Chương 2 quy định gì về thời hạn bảo hành?",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    # Correct section heading, but content is about office equipment
    cand = _make_candidate(
        "c1",
        "Danh mục các thiết bị văn phòng được trang bị cho nhân sự mới.",
        heading_path=("Chương 2: Thiết bị văn phòng",),
    )

    assessment = assess_evidence_support([sq], [cand])
    assert assessment.all_required_supported is False
    assert assessment.missing_group_ids == ("sq1",)
    assert assessment.group_assessments[0].status == "unsupported"
    assert assessment.group_assessments[0].supporting_chunk_ids == ()


def test_distractor_wrong_section_unsupported() -> None:
    sq = Subquestion(
        id="sq1",
        text="Chương 2 chính sách đổi trả hàng hóa",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    # Has matching keywords but belongs to Chương 5
    cand = _make_candidate(
        "c1",
        "Chính sách đổi trả hàng hóa đối với các đơn hàng trực tuyến.",
        heading_path=("Chương 5: Mua sắm trực tuyến",),
    )

    assessment = assess_evidence_support([sq], [cand])
    assert assessment.all_required_supported is False
    assert assessment.group_assessments[0].status == "unsupported"


def test_missing_number_or_negation_constraint_unsupported() -> None:
    sq = Subquestion(
        id="sq1",
        text="Quy định không được tự ý sửa chữa máy trong 30 ngày",
        protected_spans=(
            ProtectedSpan("không được", "negation", 9, 19),
            ProtectedSpan("30", "number", 44, 46),
        ),
        required=True,
    )
    # Content has '30' but lacks negation 'không được' (or says allowed)
    cand_missing_negation = _make_candidate(
        "c1",
        "Khách hàng tự ý sửa chữa máy trong vòng 30 ngày kể từ ngày mua.",
    )
    res1 = assess_evidence_support([sq], [cand_missing_negation])
    assert res1.group_assessments[0].status == "unsupported"

    # Content has 'không được' but missing '30'
    cand_missing_number = _make_candidate(
        "c2",
        "Khách hàng không được tự ý sửa chữa máy khi chưa có kỹ thuật viên.",
    )
    res2 = assess_evidence_support([sq], [cand_missing_number])
    assert res2.group_assessments[0].status == "unsupported"


def test_multiple_subquestions_partial_support() -> None:
    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 quy định gì?",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 quy định gì?",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )
    # Only candidate for Chương 2 exists in pool
    c1 = _make_candidate("c1", "Nội dung quy định chi tiết.", heading_path=("Chương 2",))

    assessment = assess_evidence_support([sq1, sq2], [c1])
    assert assessment.all_required_supported is False
    assert assessment.missing_group_ids == ("sq2",)

    by_group = {ga.group_id: ga for ga in assessment.group_assessments}
    assert by_group["sq1"].status == "supported"
    assert by_group["sq1"].supporting_chunk_ids == ("c1",)
    assert by_group["sq2"].status == "unsupported"
    assert by_group["sq2"].supporting_chunk_ids == ()


def test_supporting_chunk_ids_strictly_subset_of_candidates() -> None:
    sq = Subquestion(id="sq1", text="bảo mật thông tin", required=True)
    c1 = _make_candidate("c1", "tiêu chuẩn bảo mật thông tin nội bộ")
    c2 = _make_candidate("c2", "hướng dẫn bảo mật thông tin khách hàng")
    c3 = _make_candidate("c3", "thực đơn nhà ăn trưa")

    assessment = assess_evidence_support([sq], [c1, c2, c3])
    assert assessment.group_assessments[0].status == "supported"
    supporting = set(assessment.group_assessments[0].supporting_chunk_ids)
    assert supporting.issubset({"c1", "c2", "c3"})
    assert "c3" not in supporting


def test_deterministic_digest_and_observation() -> None:
    sq = Subquestion(id="sq1", text="thời hạn hợp đồng", required=True)
    c1 = _make_candidate("c1", "thời hạn hợp đồng là hai năm")

    res_a = assess_evidence_support([sq], [c1], purpose="candidate_support")
    res_b = assess_evidence_support([sq], [c1], purpose="candidate_support")
    res_final = assess_evidence_support([sq], [c1], purpose="final_support")

    assert res_a.assessment_digest == res_b.assessment_digest
    assert res_a.assessment_digest != res_final.assessment_digest

    obs = res_a.to_observation()
    assert obs["purpose"] == "candidate_support"
    assert obs["all_required_supported"] is True
    assert isinstance(obs["group_assessments"], list)


def test_exact_boundary_prevents_false_support_for_partial_prefix():
    # C2 must not match C20
    sq_c2 = Subquestion(
        id="sq_c2",
        text="Quy định tại Chương 2",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    cand_c20 = _make_candidate("c20", "Nội dung quy định chi tiết.", heading_path=("Chương 20",))
    res_sec = assess_evidence_support([sq_c2], [cand_c20])
    assert res_sec.all_required_supported is False
    assert res_sec.group_assessments[0].status == "unsupported"

    # 14 must not match 140
    sq_num = Subquestion(
        id="sq_num",
        text="Thời hạn 14 ngày",
        protected_spans=(ProtectedSpan("14", "number", 9, 11),),
        required=True,
    )
    cand_num140 = _make_candidate("c140", "Thời hạn giải quyết là 140 ngày làm việc.")
    res_num = assess_evidence_support([sq_num], [cand_num140])
    assert res_num.all_required_supported is False

    # AUTH_403 must not match AUTH_404
    sq_auth = Subquestion(
        id="sq_auth",
        text="Xử lý lỗi AUTH_403",
        protected_spans=(ProtectedSpan("AUTH_403", "identifier", 11, 19),),
        required=True,
    )
    cand_auth404 = _make_candidate("c404", "Hướng dẫn xử lý lỗi AUTH_404 hệ thống.")
    res_auth = assess_evidence_support([sq_auth], [cand_auth404])
    assert res_auth.all_required_supported is False
