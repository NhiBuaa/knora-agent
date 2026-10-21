"""Tests for group evidence selection ensuring required subquestions coverage within budget.

Refs #153 (Retrieval V3 Stage 7 Task 6).
"""

from __future__ import annotations

from dataclasses import replace

from knora.answering.evidence import select_evidence
from knora.answering.query_planning import ProtectedSpan, Subquestion
from knora.answering.reranking_configuration import RerankingConfiguration
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


def _make_cand(
    chunk_id: str,
    content: str,
    heading_path: tuple[str, ...] = (),
    token_count: int = 100,
    rerank_score: float = 0.9,
    ordinal: int = 0,
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
        chunk_ordinal=ordinal,
        heading_path=heading_path,
        start_line=1,
        end_line=10,
        content=content,
        content_checksum=f"chk-{chunk_id}",
        token_count=token_count,
        cosine_distance=0.1,
        similarity=rerank_score,
        rerank_score=rerank_score,
    )


def test_red_rank1_to_5_chapter2_rank6_chapter5_both_selected() -> None:
    """Mandatory Red Test: ranks 1-5 only support Chapter 2, rank 6 supports Chapter 5.

    With max_evidence_chunks=5, selector must reserve Chapter 5 evidence rather than
    selecting only Chapter 2 and reporting Chapter 5 as unsupported.
    """
    config = RetrievalConfiguration(
        id="test-config",
        candidate_k=200,
        min_similarity=None,
        max_evidence_chunks=5,
        max_evidence_tokens=3000,
        overlap_policy="adjacent-content-containment-v1",
        strategy="bm25-only",
        lexical_policy_id="bm25-test",
    )

    # Candidates 1 to 5: Chapter 2 (scores 0.95 -> 0.75)
    c1 = _make_cand(
        "c1", "Nội dung quy định thời hạn đổi trả chương 2.", ("Chương 2",), rerank_score=0.95
    )
    c2 = _make_cand(
        "c2", "Thủ tục tiếp nhận khiếu nại khách hàng chương 2.", ("Chương 2",), rerank_score=0.90
    )
    c3 = _make_cand(
        "c3", "Biểu mẫu báo cáo thiệt hại sản phẩm chương 2.", ("Chương 2",), rerank_score=0.85
    )
    c4 = _make_cand(
        "c4", "Quy trình kiểm tra kỹ thuật máy móc chương 2.", ("Chương 2",), rerank_score=0.80
    )
    c5 = _make_cand(
        "c5", "Danh sách các đại lý được ủy quyền chương 2.", ("Chương 2",), rerank_score=0.75
    )
    # Candidate 6: Chapter 5 (score 0.70)
    c6 = _make_cand(
        "c6",
        "Chính sách ưu đãi và giảm giá phí vận chuyển chương 5.",
        ("Chương 5",),
        rerank_score=0.70,
    )

    candidates = [c1, c2, c3, c4, c5, c6]

    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 quy định thời hạn đổi trả thế nào?",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 quy định chính sách giảm giá thế nào?",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    selection = select_evidence(
        candidates,
        config,
        subquestions=[sq1, sq2],
    )

    selected_ids = [d.candidate.chunk_id for d in selection.selected]
    assert len(selected_ids) <= 5
    # Must contain c1 (for sq1) and c6 (for sq2)
    assert "c1" in selected_ids
    assert "c6" in selected_ids

    # Support assessment must confirm both required groups are supported
    assert selection.support_assessment is not None
    assert selection.support_assessment.all_required_supported is True
    assert len(selection.support_assessment.missing_group_ids) == 0


def test_single_chunk_supports_multiple_groups() -> None:
    config = RetrievalConfiguration(
        id="test-config",
        candidate_k=200,
        min_similarity=None,
        max_evidence_chunks=5,
        max_evidence_tokens=3000,
        overlap_policy="adjacent-content-containment-v1",
        strategy="bm25-only",
        lexical_policy_id="bm25-test",
    )

    c_dual = _make_cand(
        "c_dual",
        "Quy định bảo mật thông tin và thời hạn lưu trữ hợp đồng 5 năm.",
        rerank_score=0.9,
    )
    c_other = _make_cand(
        "c_other",
        "Chỉ dẫn về bảo hộ lao động cho công nhân.",
        rerank_score=0.8,
    )

    sq1 = Subquestion(id="sq1", text="bảo mật thông tin", required=True)
    sq2 = Subquestion(id="sq2", text="thời hạn lưu trữ hợp đồng", required=True)

    selection = select_evidence(
        [c_dual, c_other],
        config,
        subquestions=[sq1, sq2],
    )

    selected_ids = [d.candidate.chunk_id for d in selection.selected]
    assert "c_dual" in selected_ids
    assert selection.support_assessment is not None
    assert selection.support_assessment.all_required_supported is True


def test_mmr_selection_with_reserved_groups() -> None:
    config = RetrievalConfiguration(
        id="test-config",
        candidate_k=200,
        min_similarity=None,
        max_evidence_chunks=3,
        max_evidence_tokens=3000,
        overlap_policy="adjacent-content-containment-v1",
        strategy="bm25-only",
        lexical_policy_id="bm25-test",
    )
    rerank_cfg = replace(
        RerankingConfiguration.deterministic_v1(),
        max_evidence_chunks=3,
        mmr_enabled=True,
        mmr_lambda=0.6,
    )

    c1 = _make_cand("c1", "quy định an toàn lao động chương 1", ("Chương 1",), rerank_score=0.95)
    c2 = _make_cand(
        "c2", "hướng dẫn an toàn lao động chương 1 chi tiết", ("Chương 1",), rerank_score=0.90
    )
    c3 = _make_cand(
        "c3", "biện pháp xử lý sự cố an toàn chương 1", ("Chương 1",), rerank_score=0.85
    )
    c4 = _make_cand(
        "c4", "chế độ bồi thường tai nạn lao động chương 4", ("Chương 4",), rerank_score=0.75
    )

    sq1 = Subquestion(
        id="sq1",
        text="Chương 1 an toàn lao động",
        protected_spans=(ProtectedSpan("Chương 1", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 4 bồi thường tai nạn",
        protected_spans=(ProtectedSpan("Chương 4", "section", 0, 8),),
        required=True,
    )

    selection = select_evidence(
        [c1, c2, c3, c4],
        config,
        reranking_configuration=rerank_cfg,
        subquestions=[sq1, sq2],
    )

    selected_ids = [d.candidate.chunk_id for d in selection.selected]
    assert len(selected_ids) <= 3
    assert "c1" in selected_ids
    assert "c4" in selected_ids
    assert selection.support_assessment is not None
    assert selection.support_assessment.all_required_supported is True


def test_legacy_single_query_parity() -> None:
    config = RetrievalConfiguration(
        id="test-config",
        candidate_k=200,
        min_similarity=None,
        max_evidence_chunks=2,
        max_evidence_tokens=3000,
        overlap_policy="adjacent-content-containment-v1",
        strategy="bm25-only",
        lexical_policy_id="bm25-test",
    )
    c1 = _make_cand("c1", "content 1", rerank_score=0.9)
    c2 = _make_cand("c2", "content 2", rerank_score=0.8)
    c3 = _make_cand("c3", "content 3", rerank_score=0.7)

    # Calling select_evidence without subquestions should maintain identical legacy behavior
    selection = select_evidence([c1, c2, c3], config)
    selected_ids = [d.candidate.chunk_id for d in selection.selected]
    assert selected_ids == ["c1", "c2"]
    assert selection.support_assessment is None
