"""Tests for targeted source verification and finite recovery.

Refs #153 (Retrieval V3 Stage 7 Task 7).
"""

from __future__ import annotations

import pytest

from knora.answering.query_planning import ProtectedSpan, Subquestion
from knora.answering.source_verification import verify_missing_sources
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration, RetrievalResult


def _make_cand(
    chunk_id: str,
    content: str,
    heading_path: tuple[str, ...] = (),
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


class _FakeStore:
    def __init__(self, available_candidates: list[RetrievalCandidate]) -> None:
        self.available_candidates = available_candidates
        self.calls = 0

    def retrieve_candidates(self, **kwargs) -> RetrievalResult:
        self.calls += 1
        query = kwargs.get("query_text", "").casefold()
        matched = [
            c
            for c in self.available_candidates
            if any(
                w in c.content.casefold() or any(w in h.casefold() for h in c.heading_path)
                for w in query.split()
            )
        ]
        return RetrievalResult(tuple(matched))


@pytest.mark.asyncio
async def test_recovery_pass_finds_missing_chapter_in_canonical_source() -> None:
    """Red test: Chapter 5 was missed by initial Top-K but exists in document store."""
    c_ch5 = _make_cand(
        "c_ch5",
        "Chính sách giảm giá vận chuyển áp dụng theo chương 5 của quy chế.",
        heading_path=("Chương 5: Vận chuyển",),
    )
    store = _FakeStore([c_ch5])

    sq = Subquestion(
        id="sq_ch5",
        text="Chương 5 quy định chính sách giảm giá thế nào?",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    retrieval_cfg = RetrievalConfiguration.bm25_top8_v1()

    result = await verify_missing_sources(
        missing_subquestions=[sq],
        store=store,
        workspace_id="ws-1",
        retrieval_configuration=retrieval_cfg,
    )

    assert result.overall_status == "found"
    assert len(result.recovered_candidates) == 1
    assert result.recovered_candidates[0].chunk_id == "c_ch5"
    assert result.outcomes[0].status == "found"
    # Exactly one recovery pass called
    assert store.calls == 1


@pytest.mark.asyncio
async def test_verified_absent_when_section_does_not_exist() -> None:
    """Red test: Document catalog confirms Chapter 5 does not exist."""
    store = _FakeStore([])

    sq = Subquestion(
        id="sq_ch5",
        text="Chương 5 quy định gì?",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    retrieval_cfg = RetrievalConfiguration.bm25_top8_v1()

    result = await verify_missing_sources(
        missing_subquestions=[sq],
        store=store,
        workspace_id="ws-1",
        retrieval_configuration=retrieval_cfg,
        known_section_catalog=["Chương 1", "Chương 2", "Chương 3", "Chương 4"],
    )

    assert result.overall_status == "verified_absent"
    assert len(result.recovered_candidates) == 0
    assert result.outcomes[0].status == "verified_absent"


@pytest.mark.asyncio
async def test_unverified_when_store_unavailable_or_indeterminate() -> None:
    """Red test: Store unavailable or error results in unverified status."""
    sq = Subquestion(
        id="sq_ch5",
        text="Chương 5 quy định gì?",
        protected_spans=(ProtectedSpan("Chương 5", "section", 0, 8),),
        required=True,
    )

    retrieval_cfg = RetrievalConfiguration.bm25_top8_v1()

    # Pass None as store
    result = await verify_missing_sources(
        missing_subquestions=[sq],
        store=None,
        workspace_id="ws-1",
        retrieval_configuration=retrieval_cfg,
    )

    assert result.overall_status == "unverified"
    assert result.outcomes[0].status == "unverified"
