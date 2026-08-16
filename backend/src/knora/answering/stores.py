from dataclasses import dataclass, field
from typing import Protocol, overload

from knora.providers.embedding import EmbeddingConfiguration

BRANCH_OBSERVATION_SCHEMA_VERSION = 1


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
class BranchObservation:
    """One branch-local retrieval observation, separate from fused candidates."""

    branch: str
    status: str
    chunk_id: str | None = None
    branch_rank: int | None = None
    cosine_distance: float | None = None
    similarity: float | None = None
    native_rank: float | None = None
    lexical_policy_id: str | None = None
    normalized_lexemes: tuple[str, ...] = ()
    omitted_lexemes: tuple[str, ...] = ()

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": BRANCH_OBSERVATION_SCHEMA_VERSION,
            "branch": self.branch,
            "status": self.status,
            "chunk_id": self.chunk_id,
            "branch_rank": self.branch_rank,
            "cosine_distance": self.cosine_distance,
            "similarity": self.similarity,
            "native_rank": self.native_rank,
            "lexical_policy_id": self.lexical_policy_id,
            "normalized_lexemes": list(self.normalized_lexemes),
            "omitted_lexemes": list(self.omitted_lexemes),
        }


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Candidates plus branch observations from one production retrieval invocation."""

    candidates: tuple[RetrievalCandidate, ...]
    branch_observations: tuple[BranchObservation, ...] = ()
    embedding_set_ids: tuple[str, ...] = ()
    chunk_set_ids: tuple[str, ...] = ()

    def __iter__(self):
        return iter(self.candidates)

    def __len__(self) -> int:
        return len(self.candidates)

    @overload
    def __getitem__(self, index: int) -> RetrievalCandidate: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[RetrievalCandidate, ...]: ...

    def __getitem__(
        self, index: int | slice
    ) -> RetrievalCandidate | tuple[RetrievalCandidate, ...]:
        return self.candidates[index]


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
    trace_schema_version: int = 2
    branch_observation_schema_version: int = BRANCH_OBSERVATION_SCHEMA_VERSION
    branch_observations: tuple[dict[str, object], ...] = ()


class AnsweringStore(Protocol):
    def retrieve_candidates(
        self,
        *,
        workspace_id: str,
        query_text: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
    ) -> RetrievalResult: ...

    def persist_trace(self, trace: QuestionTraceRecord) -> str: ...
