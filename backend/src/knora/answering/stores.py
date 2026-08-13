from dataclasses import dataclass, field
from typing import Protocol

from knora.providers.embedding import EmbeddingConfiguration


@dataclass(frozen=True, slots=True)
class RetrievalConfiguration:
    id: str
    candidate_k: int
    min_similarity: float
    max_evidence_chunks: int
    max_evidence_tokens: int
    overlap_policy: str
    strategy: str = "vector-only"
    fusion_policy_version: str | None = None
    fts_policy_version: str | None = None
    vector_candidate_k: int | None = None
    fts_candidate_k: int | None = None
    lexical_policy_id: str | None = None
    fusion_policy_id: str | None = None

    def parity_semantics(self) -> dict[str, object]:
        """Project strategy semantics for vector/hybrid parity review, excluding identity."""

        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name not in {"id", "fusion_policy_version", "fts_policy_version"}
        }

    @classmethod
    def milestone_one(cls) -> "RetrievalConfiguration":
        return cls(
            id="retrieval-m1-v1",
            candidate_k=8,
            min_similarity=0.65,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-token-overlap-v1",
        )

    @classmethod
    def milestone_three_hybrid(cls) -> "RetrievalConfiguration":
        return cls(
            id="retrieval-m3-rrf-v1",
            candidate_k=8,
            min_similarity=0.65,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-token-overlap-v1",
            strategy="hybrid",
            fusion_policy_version="rrf-v1",
            fts_policy_version="fts-v1",
        )

    @classmethod
    def milestone_three_vector_v2(cls, *, min_similarity: float) -> "RetrievalConfiguration":
        return cls._milestone_three_v2(strategy="vector-only", min_similarity=min_similarity)

    @classmethod
    def milestone_three_hybrid_v2(cls, *, min_similarity: float) -> "RetrievalConfiguration":
        return cls._milestone_three_v2(strategy="hybrid", min_similarity=min_similarity)

    @classmethod
    def _milestone_three_v2(
        cls, *, strategy: str, min_similarity: float
    ) -> "RetrievalConfiguration":
        if not isinstance(min_similarity, (int, float)):
            raise TypeError("calibrated min_similarity must be numeric")
        if not -1.0 <= min_similarity <= 1.0:
            raise ValueError("calibrated min_similarity is outside cosine similarity bounds")
        hybrid = strategy == "hybrid"
        return cls(
            id="retrieval-m3-rrf-v2" if hybrid else "retrieval-m3-vector-v2",
            candidate_k=8,
            min_similarity=float(min_similarity),
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-token-overlap-v1",
            strategy=strategy,
            vector_candidate_k=8,
            fts_candidate_k=8 if hybrid else None,
            lexical_policy_id="fts-m3-or-v2" if hybrid else None,
            fusion_policy_id="rrf-v2" if hybrid else None,
        )


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    document_id: str
    document_version_id: str
    source_key: str
    source_name: str
    chunk_set_id: str
    embedding_set_id: str
    embedding_configuration_id: str
    chunk_id: str
    chunk_ordinal: int
    heading_path: tuple[str, ...]
    start_line: int
    end_line: int
    content: str
    content_checksum: str
    token_count: int
    cosine_distance: float | None
    similarity: float | None
    fusion_score: float = 0.0
    vector_contribution: dict[str, object] | None = None
    fts_contribution: dict[str, object] | None = None
    page_start: int | None = None
    page_end: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(frozen=True, slots=True)
class QuestionTraceRecord:
    workspace_id: str
    question: str
    retrieval_configuration_id: str
    embedding_configuration_id: str
    candidate_decisions: tuple[dict[str, object], ...]
    retrieved_chunk_ids: tuple[str, ...]
    embedding_set_ids: tuple[str, ...]
    chunk_set_ids: tuple[str, ...]
    decision: str
    answer: str | None
    refusal_reason: str | None
    generation_status: str
    fusion_policy_version: str | None = None
    alias_mapping: dict[str, str] = field(default_factory=dict)
    parsed_markers: tuple[str, ...] = ()
    validation_outcome: str = "not_applicable"
    provider_metadata: dict[str, object] = field(default_factory=dict)
    latency_ms: float = 0.0


class AnsweringStore(Protocol):
    def retrieve_candidates(
        self,
        *,
        workspace_id: str,
        query_text: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
    ) -> tuple[RetrievalCandidate, ...]: ...

    def persist_trace(self, trace: QuestionTraceRecord) -> str: ...
