"""Tests for evidence coverage gates before generation.

Refs #153 (Retrieval V3 Stage 7 Task 8).
"""

from __future__ import annotations

from knora.answering.evidence import select_evidence
from knora.answering.query_planning import ProtectedSpan, Subquestion
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


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


def test_evidence_coverage_gate_requires_all_groups_supported() -> None:
    config = RetrievalConfiguration.bm25_top8_v1()

    # Pool only has Chapter 2
    c1 = _make_cand("c1", "Quy định đổi trả hàng chương 2", ("Chương 2",))

    sq1 = Subquestion(
        id="sq1",
        text="Chương 2 quy định đổi trả",
        protected_spans=(ProtectedSpan("Chương 2", "section", 0, 8),),
        required=True,
    )
    sq2 = Subquestion(
        id="sq2",
        text="Chương 5 quy định giảm giá",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    selection = select_evidence([c1], config, subquestions=[sq1, sq2])

    assert selection.support_assessment is not None
    assert selection.support_assessment.all_required_supported is False
    assert "sq2" in selection.support_assessment.missing_group_ids
