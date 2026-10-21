"""End-to-end integration tests for Retrieval V3 complete pipeline.

Covers:
- Query understanding and protected span extraction
- Multi-query fan-out and fair round-robin candidate merging
- Dense, BM25, and SDM sequential dependence scoring
- Cross-encoder reranking and MMR evidence selection with reserved groups
- Targeted source recovery when required groups are missing
- Answer completeness and citation validation
- Zero local model weights invariant ($0 Cloudflare-only AI)

Refs #153 (Retrieval V3 Stage 8 Task 1).
"""

from __future__ import annotations

import sys

import pytest

from knora.answering.evidence import select_evidence
from knora.answering.generation_validation import validate_generation
from knora.answering.query_correction import generate_typo_hypotheses
from knora.answering.query_planning import (
    ProtectedSpan,
    QueryPlan,
    Subquestion,
    extract_protected_spans,
    validate_protected_spans_preserved,
)
from knora.answering.query_results import merge_cross_query_candidates
from knora.answering.reranking import combine_reranking_scores
from knora.answering.reranking_configuration import RerankingConfiguration
from knora.answering.source_verification import verify_missing_sources
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration, RetrievalResult
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult


def _make_candidate(
    chunk_id: str,
    content: str,
    heading_path: tuple[str, ...] = (),
    sdm_score: float = 0.8,
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
        sdm_score=sdm_score,
        fusion_score=sdm_score,
    )


class _MockRecoveryStore:
    def __init__(self, pool: list[RetrievalCandidate]) -> None:
        self.pool = pool
        self.recovery_calls = 0

    def retrieve_candidates(self, **kwargs) -> RetrievalResult:
        self.recovery_calls += 1
        query = kwargs.get("query_text", "").casefold()
        matched = [
            c
            for c in self.pool
            if any(
                term in " ".join(c.heading_path).casefold() or term in c.content.casefold()
                for term in query.split()
            )
        ]
        return RetrievalResult(tuple(matched))


def test_zero_local_model_weights_in_integrated_runtime() -> None:
    """Verifies that no local deep learning libraries are imported."""
    forbidden = ["torch", "transformers", "fastembed", "onnxruntime", "sentence_transformers"]
    for mod in forbidden:
        assert mod not in sys.modules, f"Forbidden heavy local model library {mod} is loaded!"


def test_retrieval_v3_full_pipeline_multi_intent_with_source_recovery() -> None:
    """Integrated test for complete pipeline from query to validated answer."""
    # Step 1: User asks a multi-intent query with a typo and protected identifier
    raw_query = "So sánh chuong2 về lỗi AUTH_403 và Chương 5 về chính sách giảm giá"

    # Step 2: Protected spans extraction
    spans = extract_protected_spans(raw_query)
    categories = {s.category for s in spans}
    assert "identifier" in categories
    assert "section" in categories

    # Step 3: Typo correction (spacing and normalization)
    typo_res = generate_typo_hypotheses(raw_query)
    assert typo_res.has_typos is True
    # 'chuong2' becomes separated and restored with diacritics
    assert "chương 2" in typo_res.corrected_query.lower()

    # Step 4: Validate protected spans are preserved
    validate_protected_spans_preserved(spans, typo_res.corrected_query)

    # Step 5: Subquestion decomposition
    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 quy định gì về mã lỗi AUTH_403?",
        protected_spans=(
            ProtectedSpan("Chương 2", "section", 0, 8),
            ProtectedSpan("AUTH_403", "identifier", 28, 36),
        ),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 quy định chính sách giảm giá thế nào?",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )
    plan = QueryPlan(
        query_id="plan-1",
        original_query=raw_query,
        is_fast_path=False,
        subquestions=(sq1, sq2),
        variants=(),
        protected_spans=spans,
    )
    assert len(plan.subquestions) == 2

    # Step 6: Initial retrieval returns candidates for sq1 (Chapter 2), but misses Chapter 5
    c_ch2_a = _make_candidate(
        "c_ch2_a", "Chương 2 xử lý mã lỗi AUTH_403 trong 24 giờ", ("Chương 2",), sdm_score=0.95
    )
    c_ch2_b = _make_candidate(
        "c_ch2_b", "Chương 2 hướng dẫn cấu hình tài khoản", ("Chương 2",), sdm_score=0.90
    )

    # Merged candidates from initial search
    merged_pool = merge_cross_query_candidates(
        {
            "sq1": [c_ch2_a, c_ch2_b],
            "sq2": [],  # Initial search missed Chapter 5
        }
    )
    merged_candidates = merged_pool.candidates
    assert len(merged_candidates) == 2

    # Step 7: Reranking & MMR Evidence Selection
    rerank_cfg = RerankingConfiguration.deterministic_v1()
    retrieval_cfg = RetrievalConfiguration.bm25_top8_v1()

    # Cross-encoder scores
    reranked = combine_reranking_scores(
        merged_candidates,
        {"c_ch2_a": 0.96, "c_ch2_b": 0.88},
        rerank_cfg,
    )

    selection_initial = select_evidence(
        reranked,
        retrieval_cfg,
        reranking_configuration=rerank_cfg,
        subquestions=plan.subquestions,
    )
    # Group sq2 is missing
    assert selection_initial.support_assessment is not None
    assert selection_initial.support_assessment.all_required_supported is False
    assert "sq2" in selection_initial.support_assessment.missing_group_ids

    # Step 8: Targeted Source Recovery (exactly 1 pass)
    c_ch5 = _make_candidate(
        "c_ch5",
        "Chương 5 quy định chính sách giảm giá 20% khi thanh toán trực tuyến",
        ("Chương 5",),
    )
    store = _MockRecoveryStore([c_ch5])

    import asyncio

    verification = asyncio.run(
        verify_missing_sources(
            missing_subquestions=[sq2],
            store=store,
            workspace_id="ws-1",
            retrieval_configuration=retrieval_cfg,
            all_known_candidates=merged_candidates,
        )
    )
    assert verification.overall_status == "found"
    assert len(verification.recovered_candidates) == 1
    assert store.recovery_calls == 1

    # Step 9: Re-selection with recovered candidates
    full_pool = list(merged_candidates) + list(verification.recovered_candidates)
    full_reranked = combine_reranking_scores(
        full_pool,
        {"c_ch2_a": 0.96, "c_ch2_b": 0.88, "c_ch5": 0.92},
        rerank_cfg,
    )

    selection_final = select_evidence(
        full_reranked,
        retrieval_cfg,
        reranking_configuration=rerank_cfg,
        subquestions=plan.subquestions,
    )
    # Now both required groups are fully supported!
    assert selection_final.support_assessment is not None
    assert selection_final.support_assessment.all_required_supported is True
    assert len(selection_final.support_assessment.missing_group_ids) == 0

    selected_ids = {d.candidate.chunk_id for d in selection_final.selected}
    assert "c_ch2_a" in selected_ids
    assert "c_ch5" in selected_ids

    # Step 10: Generation & Completeness Validation
    alias_to_cand = {
        f"E{idx}": d.candidate for idx, d in enumerate(selection_final.selected, start=1)
    }
    # Find alias for Chapter 2 and Chapter 5
    alias_ch2 = next(a for a, c in alias_to_cand.items() if c.chunk_id == "c_ch2_a")
    alias_ch5 = next(a for a, c in alias_to_cand.items() if c.chunk_id == "c_ch5")

    # Complete response covering both requirements
    complete_gen = GenerationResult(
        decision="ANSWER",
        answer=(
            f"Theo Chương 2, mã lỗi AUTH_403 được xử lý trong 24 giờ [[{alias_ch2}]]. "
            "Theo Chương 5, chính sách giảm giá 20% áp dụng "
            f"khi thanh toán trực tuyến [[{alias_ch5}]]."
        ),
        cited_evidence_ids=(alias_ch2, alias_ch5),
        refusal_reason=None,
    )

    validated = validate_generation(
        complete_gen,
        available_evidence_ids=tuple(alias_to_cand),
        required_subquestions=plan.subquestions,
        alias_to_candidate=alias_to_cand,
    )
    assert validated.result.decision == "ANSWER"
    assert len(validated.parsed_markers) == 2


def test_retrieval_v3_rejects_incomplete_generation_omitting_subquestion() -> None:
    """Integration test asserting that answer completeness gate blocks partial answers."""
    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 quy định đổi trả",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 quy định giao hàng",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    c1 = _make_candidate("c1", "Chương 2 thời hạn đổi trả 7 ngày", ("Chương 2",))
    c2 = _make_candidate("c2", "Chương 5 miễn phí giao hàng", ("Chương 5",))

    alias_map = {"E1": c1, "E2": c2}

    # Partial answer that only answers Chapter 2 and omits Chapter 5
    partial_gen = GenerationResult(
        decision="ANSWER",
        answer="Theo Chương 2, thời hạn đổi trả là 7 ngày [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )

    with pytest.raises(KnoraError) as exc_info:
        validate_generation(
            partial_gen,
            available_evidence_ids=("E1", "E2"),
            required_subquestions=[sq1, sq2],
            alias_to_candidate=alias_map,
        )
    assert exc_info.value.code == "GENERATION_OUTPUT_INVALID"
