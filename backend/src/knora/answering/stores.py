import re
from dataclasses import dataclass, field, replace
from math import isfinite
from typing import Protocol, overload

from knora.answering.interface import QuestionResult
from knora.providers.embedding import EmbeddingConfiguration

BRANCH_OBSERVATION_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class RetrievalConfiguration:
    id: str
    candidate_k: int
    min_similarity: float | None
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
    sdm_policy_id: str | None = None

    def __post_init__(self) -> None:
        if self.strategy not in {"bm25-only"} and self.min_similarity is None:
            raise ValueError("dense/hybrid retrieval requires its vector threshold")
        if self.strategy == "bm25-only" and (
            self.min_similarity is not None
            or not self.lexical_policy_id
            or self.fusion_policy_id is not None
            or self.fusion_policy_version is not None
        ):
            raise ValueError("BM25 requires a lexical policy and no vector threshold or fusion")
        if self.strategy in {"vector-only", "dense-only"} and (
            self.lexical_policy_id is not None
            or self.fusion_policy_id is not None
            or self.fusion_policy_version is not None
        ):
            raise ValueError("dense-only retrieval requires no lexical policy or fusion policy")
        if self.strategy == "hybrid" and (
            self.lexical_policy_id is not None or self.fusion_policy_id is not None
        ):
            if self.lexical_policy_id is None:
                raise ValueError("hybrid retrieval requires a lexical policy")
            if self.fusion_policy_id is None:
                raise ValueError("hybrid retrieval requires a fusion policy")

    @classmethod
    def bm25_diagnostic_v1(cls) -> "RetrievalConfiguration":
        """Offline composition only; no deployment selector or calibrated acceptance claim."""
        return cls(
            id="retrieval-bm25-diagnostic-v1",
            candidate_k=200,
            min_similarity=None,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-content-containment-v1",
            strategy="bm25-only",
            lexical_policy_id="bm25-unicode-word-v1",
        )

    @classmethod
    def bm25_top8_v1(cls) -> "RetrievalConfiguration":
        """Primary Top8 from one native Top200; no calibrated score cutoff."""
        return replace(
            cls.bm25_diagnostic_v1(),
            id="retrieval-bm25-top8-v1",
            candidate_k=8,
            lexical_policy_id="bm25-word-frozen47-population-v1",
        )

    @classmethod
    def bm25_upload_fixture_top8_v1(cls) -> "RetrievalConfiguration":
        return replace(
            cls.bm25_top8_v1(),
            id="retrieval-bm25-upload-fixture-top8-v1",
            lexical_policy_id="bm25-word-upload-fixture-population-v1",
        )

    @classmethod
    def dense_top8_v3(cls, *, min_similarity: float = 0.65) -> "RetrievalConfiguration":
        """Dense-only Top8 from Qdrant HNSW/TurboQuant; requires calibrated threshold."""
        if not isinstance(min_similarity, (int, float)) or isinstance(min_similarity, bool):
            raise TypeError("calibrated min_similarity must be numeric")
        if not -1.0 <= min_similarity <= 1.0:
            raise ValueError("calibrated min_similarity is outside cosine similarity bounds")
        return cls(
            id="retrieval-dense-top8-v3",
            candidate_k=8,
            min_similarity=float(min_similarity),
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-content-containment-v1",
            strategy="dense-only",
            vector_candidate_k=200,
        )

    @classmethod
    def hybrid_top8_v3(
        cls,
        *,
        min_similarity: float = 0.65,
        lexical_policy_id: str = "bm25-word-frozen47-population-v1",
        fusion_policy_id: str = "dbsf-v1",
        sdm_policy_id: str | None = None,
    ) -> "RetrievalConfiguration":
        """Hybrid Top8 from native DBSF fusion (Top200 dense + Top200 BM25 to Top100 candidates)."""
        if not isinstance(min_similarity, (int, float)) or isinstance(min_similarity, bool):
            raise TypeError("calibrated min_similarity must be numeric")
        if not -1.0 <= min_similarity <= 1.0:
            raise ValueError("calibrated min_similarity is outside cosine similarity bounds")
        return cls(
            id="retrieval-hybrid-top8-v3",
            candidate_k=8,
            min_similarity=float(min_similarity),
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-content-containment-v1",
            strategy="hybrid",
            vector_candidate_k=200,
            fts_candidate_k=200,
            lexical_policy_id=lexical_policy_id,
            fusion_policy_id=fusion_policy_id,
            sdm_policy_id=sdm_policy_id,
        )

    @classmethod
    def hybrid_sdm_top8_v3(
        cls,
        *,
        min_similarity: float = 0.65,
        lexical_policy_id: str = "bm25-word-frozen47-population-v1",
        fusion_policy_id: str = "dbsf-v1",
        sdm_policy_id: str = "sdm-metzler-croft-2005-v1",
    ) -> "RetrievalConfiguration":
        """Hybrid Top8 with Sequential Dependence Model (SDM) reranking after native DBSF."""
        base = cls.hybrid_top8_v3(
            min_similarity=min_similarity,
            lexical_policy_id=lexical_policy_id,
            fusion_policy_id=fusion_policy_id,
            sdm_policy_id=sdm_policy_id,
        )
        return replace(base, id="retrieval-hybrid-sdm-top8-v3")

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
    def evidence_containment_v1(cls) -> "RetrievalConfiguration":
        return replace(
            cls.milestone_one(),
            id="retrieval-evidence-containment-v1",
            overlap_policy="adjacent-content-containment-v1",
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
    def qwen_vietnamese_v1(
        cls, *, min_similarity: float, artifact_sha256: str
    ) -> "RetrievalConfiguration":
        if not isinstance(min_similarity, (int, float)) or isinstance(min_similarity, bool):
            raise TypeError("calibrated min_similarity must be numeric")
        if not -1.0 <= min_similarity <= 1.0:
            raise ValueError("calibrated min_similarity is outside cosine similarity bounds")
        return cls(
            id=f"retrieval-qwen-v1-{artifact_sha256[:24]}",
            candidate_k=16,
            min_similarity=float(min_similarity),
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-token-overlap-v1",
            vector_candidate_k=16,
        )

    @classmethod
    def qwen_containment_candidate_v2(
        cls, *, min_similarity: float, provenance_sha256: str
    ) -> "RetrievalConfiguration":
        """Explicit evaluation composition; not registered as a deployment selector."""
        if (
            not isinstance(min_similarity, (int, float))
            or isinstance(min_similarity, bool)
            or not isfinite(min_similarity)
            or not -1 <= min_similarity <= 1
            or not isinstance(provenance_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", provenance_sha256) is None
        ):
            raise ValueError("invalid Qwen candidate provenance or threshold")
        return replace(
            cls.qwen_vietnamese_v1(
                min_similarity=min_similarity, artifact_sha256=provenance_sha256
            ),
            id=f"retrieval-qwen-containment-candidate-v2-{provenance_sha256[:24]}",
            overlap_policy="adjacent-content-containment-v1",
        )

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
    embedding_set_id: str | None
    embedding_configuration_id: str | None
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
    bm25_score: float | None = None
    bm25_rank: int | None = None
    index_generation_id: str | None = None
    sdm_score: float | None = None
    sdm_rank: int | None = None
    sdm_contribution: dict[str, object] | None = None


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
    raw_score: float | None = None
    score_kind: str | None = None
    index_generation_id: str | None = None
    decision_reason: str | None = None

    def as_mapping(self) -> dict[str, object]:
        mapping = {
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
        if self.branch in {"bm25", "dense", "fused"}:
            mapping.update(
                schema_version=2,
                raw_score=self.raw_score,
                score_kind=self.score_kind,
                index_generation_id=self.index_generation_id,
                decision_reason=self.decision_reason,
            )
        return mapping


@dataclass(frozen=True, slots=True)
class LexicalGeneration:
    """Store-resolved index provenance; readiness/authorization remain store responsibilities."""

    workspace_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    index_generation_id: str
    lexical_policy_id: str


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Candidates plus branch observations from one production retrieval invocation."""

    candidates: tuple[RetrievalCandidate, ...]
    branch_observations: tuple[BranchObservation, ...] = ()
    embedding_set_ids: tuple[str, ...] = ()
    chunk_set_ids: tuple[str, ...] = ()
    lexical_generations: tuple[LexicalGeneration, ...] = ()

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
    embedding_configuration_id: str | None
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
    conversation_turn_id: str | None = None


class AnsweringStore(Protocol):
    def revalidate_lexical_snapshot(
        self,
        workspace_id: str,
        lexical_policy_id: str,
        generations: tuple[LexicalGeneration, ...],
    ) -> None: ...

    def require_lexical_corpus(self, workspace_id: str, lexical_policy_id: str) -> None: ...

    def require_compatible_corpus(
        self, workspace_id: str, embedding_configuration_id: str
    ) -> None: ...

    def retrieve_candidates(
        self,
        *,
        workspace_id: str,
        query_text: str,
        query_vector: tuple[float, ...] | None,
        embedding_configuration: EmbeddingConfiguration | None,
        retrieval_configuration: RetrievalConfiguration,
    ) -> RetrievalResult: ...

    def persist_trace(self, trace: QuestionTraceRecord) -> str: ...

    def read_conversation_result(
        self, workspace_id: str, turn_id: str
    ) -> QuestionResult | None: ...
