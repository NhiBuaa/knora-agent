"""Core data structures and protocols for cross-encoder reranking providers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RerankingCandidate:
    """An authorized text chunk candidate to be scored by a cross-encoder model."""

    chunk_id: str
    document_version_id: str
    content: str
    content_checksum: str


@dataclass(frozen=True, slots=True)
class ScoredRerankingCandidate:
    """A candidate scored and ranked by the reranking model."""

    candidate: RerankingCandidate
    rerank_score: float
    rerank_rank: int


@dataclass(frozen=True, slots=True)
class RerankingResult:
    """The complete outcome of a cross-encoder reranking operation."""

    model: str
    scored_candidates: tuple[ScoredRerankingCandidate, ...]
    model_revision: str | None = None
    request_id: str | None = None
    duration_ms: float | None = None


class RerankingProvider(Protocol):
    """Protocol for cross-encoder reranking providers."""

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankingCandidate],
    ) -> RerankingResult:
        """Score and rerank candidates against query using cross-encoder inference."""
        ...


class DeterministicRerankingProvider:
    """Offline deterministic provider for unit testing and local contracts."""

    def __init__(self, model: str = "deterministic-reranker-v1") -> None:
        self.model = model

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankingCandidate],
    ) -> RerankingResult:
        if not candidates:
            return RerankingResult(
                model=self.model,
                scored_candidates=(),
                model_revision="v1",
                request_id="det-empty",
                duration_ms=0.0,
            )

        query_terms = set(query.lower().split())
        scored: list[tuple[float, RerankingCandidate]] = []
        for cand in candidates:
            cand_terms = set(cand.content.lower().split())
            overlap = len(query_terms & cand_terms)
            checksum_tie_bias = (
                int(cand.content_checksum[:4], 16) / 65535.0 if cand.content_checksum else 0.0
            )
            score = float(overlap) + 0.001 * checksum_tie_bias
            scored.append((score, cand))

        # Sort descending by score, tie-break by chunk_id ascending
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))

        results = [
            ScoredRerankingCandidate(
                candidate=cand,
                rerank_score=score,
                rerank_rank=rank,
            )
            for rank, (score, cand) in enumerate(scored, start=1)
        ]

        return RerankingResult(
            model=self.model,
            scored_candidates=tuple(results),
            model_revision="v1",
            request_id="det-req-1",
            duration_ms=1.0,
        )
