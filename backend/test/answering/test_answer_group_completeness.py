"""Tests for generation answer completeness across required subquestion groups.

Refs #153 (Retrieval V3 Stage 7 Task 8).
"""

from __future__ import annotations

import pytest

from knora.answering.generation_validation import validate_generation
from knora.answering.query_planning import ProtectedSpan, Subquestion
from knora.answering.stores import RetrievalCandidate
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult


def _make_cand(
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
        end_line=10,
        content=content,
        content_checksum=f"chk-{chunk_id}",
        token_count=len(content.split()),
        cosine_distance=0.1,
        similarity=0.9,
    )


def test_answer_completeness_accepts_when_both_groups_covered() -> None:
    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 quy định đổi trả",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 quy định vận chuyển",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    c1 = _make_cand("c1", "Quy định đổi trả theo Chương 2 trong vòng 7 ngày.", ("Chương 2",))
    c2 = _make_cand("c2", "Chính sách miễn phí vận chuyển tại Chương 5.", ("Chương 5",))

    alias_map = {"E1": c1, "E2": c2}

    # Answer covers both Chapter 2 and Chapter 5, and cites both E1 and E2
    result = GenerationResult(
        decision="ANSWER",
        answer=(
            "Theo Chương 2, thời hạn đổi trả là 7 ngày [[E1]]. "
            "Theo Chương 5, vận chuyển được miễn phí [[E2]]."
        ),
        cited_evidence_ids=("E1", "E2"),
        refusal_reason=None,
    )

    validated = validate_generation(
        result,
        available_evidence_ids=("E1", "E2"),
        required_subquestions=[sq1, sq2],
        alias_to_candidate=alias_map,
    )
    assert validated.result.decision == "ANSWER"


def test_answer_completeness_rejects_when_second_chapter_omitted() -> None:
    """Red test: Evidence has Chapter 2 and 5, but answer only covers Chapter 2."""
    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 quy định đổi trả",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 quy định vận chuyển",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    c1 = _make_cand("c1", "Quy định đổi trả theo Chương 2 trong vòng 7 ngày.", ("Chương 2",))
    c2 = _make_cand("c2", "Chính sách miễn phí vận chuyển tại Chương 5.", ("Chương 5",))

    alias_map = {"E1": c1, "E2": c2}

    # Only mentions Chapter 2 and only cites E1
    result = GenerationResult(
        decision="ANSWER",
        answer="Theo Chương 2, thời hạn đổi trả là 7 ngày [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )

    with pytest.raises(KnoraError) as exc_info:
        validate_generation(
            result,
            available_evidence_ids=("E1", "E2"),
            required_subquestions=[sq1, sq2],
            alias_to_candidate=alias_map,
        )
    assert exc_info.value.code == "GENERATION_OUTPUT_INVALID"


def test_answer_completeness_rejects_when_text_omits_section_name() -> None:
    """Red test: Cites E2 but answer text fails to mention Chapter 5."""
    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 đổi trả",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 vận chuyển",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    c1 = _make_cand("c1", "Nội dung Chương 2", ("Chương 2",))
    c2 = _make_cand("c2", "Nội dung Chương 5", ("Chương 5",))

    alias_map = {"E1": c1, "E2": c2}

    # Text repeats Chapter 2 twice instead of addressing Chapter 5
    result = GenerationResult(
        decision="ANSWER",
        answer="Chương 2 nói về đổi trả [[E1]]. Chương 2 cũng bổ sung thêm thông tin [[E2]].",
        cited_evidence_ids=("E1", "E2"),
        refusal_reason=None,
    )

    with pytest.raises(KnoraError) as exc_info:
        validate_generation(
            result,
            available_evidence_ids=("E1", "E2"),
            required_subquestions=[sq1, sq2],
            alias_to_candidate=alias_map,
        )
    assert exc_info.value.code == "GENERATION_OUTPUT_INVALID"
