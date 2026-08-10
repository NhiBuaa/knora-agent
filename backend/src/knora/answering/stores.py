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
    cosine_distance: float
    similarity: float
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
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
    ) -> tuple[RetrievalCandidate, ...]: ...

    def persist_trace(self, trace: QuestionTraceRecord) -> str: ...
