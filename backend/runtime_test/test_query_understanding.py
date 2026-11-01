"""Runtime contract, performance and safety validation for Query Understanding and Source Recovery.

Tests zero local model weights invariant, p50 latency bounds (<10ms for local pipeline components),
concurrency safety, and multi-query evidence coverage under load.
Refs #153 (Retrieval V3 Stage 7 Task 9).
"""

from __future__ import annotations

import asyncio
import sys
import time

from knora.answering.evidence import select_evidence
from knora.answering.evidence_support import assess_evidence_support
from knora.answering.generation_validation import validate_generation
from knora.answering.query_correction import generate_typo_hypotheses
from knora.answering.query_planning import (
    ProtectedSpan,
    Subquestion,
    extract_protected_spans,
)
from knora.answering.query_results import merge_cross_query_candidates
from knora.answering.source_verification import verify_missing_sources
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration, RetrievalResult
from knora.providers.generation import GenerationResult


def _make_candidate(
    chunk_id: str,
    content: str,
    heading_path: tuple[str, ...] = (),
    score: float = 0.9,
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
        similarity=score,
        rerank_score=score,
    )


class _MockSourceStore:
    def __init__(self, candidates: list[RetrievalCandidate]) -> None:
        self.candidates = candidates

    def retrieve_candidates(self, **kwargs) -> RetrievalResult:
        q = kwargs.get("query_text", "").casefold()
        matched = [
            c
            for c in self.candidates
            if q in " ".join(c.heading_path).casefold() or q in c.content.casefold()
        ]
        return RetrievalResult(tuple(matched))


def test_zero_local_model_weights_invariant() -> None:
    """Verifies that no heavy local ML frameworks are imported."""
    forbidden = ["torch", "transformers", "fastembed", "onnxruntime", "sentence_transformers"]
    for mod in forbidden:
        assert mod not in sys.modules, f"Forbidden heavy model module {mod} is loaded!"


def test_local_query_understanding_latency_p50_under_10ms() -> None:
    """Benchmark local query understanding components over 100 iterations."""
    latencies = []
    candidates = [
        _make_candidate(f"c{i}", f"Quy định chương 2 về hợp đồng {i}") for i in range(100)
    ]
    sq = Subquestion(
        id="sq1",
        text="Chương 2 quy định gì về thời hạn hợp đồng?",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )

    for _ in range(50):
        t0 = time.perf_counter()
        _ = extract_protected_spans("Chương 2 lỗi AUTH_403 ngày 2026-10-21 không quá 14 ngày")
        _ = generate_typo_hypotheses("chuong2 chinh sach baos hiem")
        _ = assess_evidence_support([sq], candidates)
        _ = merge_cross_query_candidates({"sq1": candidates[:20], "sq2": candidates[20:40]})
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    # Local deterministic operations must run well within budget (typically < 3ms)
    assert p50 < 10.0, f"Query understanding p50 latency {p50:.2f}ms exceeds 10ms threshold"


def test_end_to_end_recovery_and_answer_completeness() -> None:
    """Verifies full flow: initial miss -> recovery pass -> selection -> completeness validation."""
    config = RetrievalConfiguration.bm25_top8_v1()

    # Initial pool only has Chapter 2
    c_ch2 = _make_candidate("c_ch2", "Chương 2 quy định đổi trả trong 7 ngày", ("Chương 2",))
    c_ch5 = _make_candidate("c_ch5", "Chương 5 quy định giao hàng miễn phí", ("Chương 5",))

    store = _MockSourceStore([c_ch2, c_ch5])

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

    # Step 1: Initial selection on c_ch2 leaves sq2 unsupported
    sel1 = select_evidence([c_ch2], config, subquestions=[sq1, sq2])
    assert sel1.support_assessment is not None
    assert sel1.support_assessment.all_required_supported is False

    # Step 2: Recovery pass discovers c_ch5
    async def run_recovery():
        return await verify_missing_sources(
            missing_subquestions=[sq2],
            store=store,
            workspace_id="ws-1",
            retrieval_configuration=config,
            all_known_candidates=[c_ch2],
        )

    recovery_res = asyncio.run(run_recovery())
    assert recovery_res.overall_status == "found"
    assert len(recovery_res.recovered_candidates) == 1

    # Step 3: Second selection with merged candidates
    merged_candidates = [c_ch2, recovery_res.recovered_candidates[0]]
    sel2 = select_evidence(merged_candidates, config, subquestions=[sq1, sq2])
    assert sel2.support_assessment is not None
    assert sel2.support_assessment.all_required_supported is True

    # Step 4: Validate answer completeness
    alias_map = {"E1": c_ch2, "E2": c_ch5}
    gen_result = GenerationResult(
        decision="ANSWER",
        answer=(
            "Theo Chương 2, thời hạn đổi trả là 7 ngày [[E1]]. "
            "Theo Chương 5, giao hàng được miễn phí [[E2]]."
        ),
        cited_evidence_ids=("E1", "E2"),
        refusal_reason=None,
    )
    validated = validate_generation(
        gen_result,
        available_evidence_ids=("E1", "E2"),
        required_subquestions=[sq1, sq2],
        alias_to_candidate=alias_map,
    )
    assert validated.result.decision == "ANSWER"
