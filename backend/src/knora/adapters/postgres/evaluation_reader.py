from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from math import isfinite

from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.lexical_retrieval import validate_population_in_transaction
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    QuestionTraceTable,
)
from knora.answering.evidence import select_evidence
from knora.answering.generation_validation import MARKER_PATTERN, validate_generation
from knora.answering.lexical import validate_bm25_result
from knora.answering.retrieval_configuration import (
    CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
    resolve_retrieval_configuration,
)
from knora.answering.retrieval_v2 import normalize_fts_m3_or_v2_details
from knora.answering.stores import (
    BranchObservation,
    LexicalGeneration,
    QuestionTraceRecord,
    RetrievalCandidate,
    RetrievalConfiguration,
    RetrievalResult,
)
from knora.domain.errors import KnoraError
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.providers.generation import GenerationResult

_VALID_FINAL_DECISIONS = {
    "SELECTED",
    "REDUNDANT_OVERLAP",
    "BUDGET_EXCEEDED",
    "ELIGIBLE_NOT_SELECTED",
}
_VALID_DECISION_REASONS = {"TOKEN_BUDGET", "CHUNK_COUNT_LIMIT"}
_VALID_LEXICAL_POLICIES = {"fts-v1", "fts-m3-or-v2"}
_VALID_BRANCH_STATUSES = {
    "vector": {"ELIGIBLE", "BELOW_THRESHOLD", "NO_CONTRIBUTION"},
    "fts": {"ELIGIBLE", "INELIGIBLE", "NO_CONTRIBUTION"},
}
_RETRIEVAL_PROVENANCE = {
    "retrieval-evidence-containment-v1": (None, None, {"vector"}),
    "retrieval-m1-v1": (None, None, {"vector"}),
    "retrieval-m3-vector-v2": (None, None, {"vector"}),
    "retrieval-m3-rrf-v1": ("rrf-v1", "fts-v1", {"vector", "fts"}),
    "retrieval-m3-rrf-v2": ("rrf-v2", "fts-m3-or-v2", {"vector", "fts"}),
}


def _validate_embedding_provenance(
    *,
    embedding_set_ids: list[str],
    chunk_set_ids: list[str],
    embedding_configuration_id: str,
    rows: Iterable[tuple[str, str, str]],
) -> None:
    materialized = list(rows)
    if (
        len(materialized) != len(embedding_set_ids)
        or {row[0] for row in materialized} != set(embedding_set_ids)
        or {row[1] for row in materialized} != set(chunk_set_ids)
        or any(row[2] != embedding_configuration_id for row in materialized)
    ):
        raise LookupError("evaluation trace provenance is invalid")


@dataclass(frozen=True, slots=True)
class EvaluationCandidateProjection:
    chunk_id: str
    document_version_id: str
    chunk_set_id: str
    source_key: str
    chunk_ordinal: int
    workspace_id: str
    content: str
    start_line: int
    end_line: int
    final_rank: int
    fusion_score: float | None
    final_decision: str
    decision_reason: str | None
    vector_contribution: dict[str, object] | None
    fts_contribution: dict[str, object] | None
    raw_sha256: str | None = None
    parser_configuration_id: str | None = None
    normalizer_configuration_id: str | None = None
    chunking_configuration_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    content_checksum: str | None = None
    document_id: str | None = None
    token_count: int | None = None
    bm25_contribution: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PdfChunkProjection:
    workspace_id: str
    source_key: str
    chunk_id: str
    document_version_id: str
    chunk_set_id: str
    raw_sha256: str
    parser_configuration_id: str
    normalizer_configuration_id: str
    chunking_configuration_id: str
    page_start: int
    page_end: int
    start_offset: int
    end_offset: int
    content_checksum: str
    content: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class EvaluationTraceProjection:
    trace_id: str
    workspace_id: str
    retrieval_configuration_id: str
    embedding_configuration_id: str | None
    candidates: tuple[EvaluationCandidateProjection, ...]
    alias_mapping: dict[str, str]
    provider_metadata: dict[str, object]
    retrieval_latency_ms: float
    trace_schema_version: int
    branch_observation_schema_version: int
    fusion_policy_version: str | None
    embedding_set_ids: tuple[str, ...]
    chunk_set_ids: tuple[str, ...]
    candidate_decisions: tuple[dict[str, object], ...]
    branch_observations: tuple[dict[str, object], ...]
    decision: str
    answer: str | None
    refusal_reason: str | None
    parsed_markers: tuple[str, ...]
    validation_outcome: str


def project_bm25_trace(
    *,
    trace_id: str,
    record: QuestionTraceRecord,
    candidates: tuple[EvaluationCandidateProjection, ...],
    authorized_generations: tuple[LexicalGeneration, ...],
    include_invalid_generation: bool = False,
) -> EvaluationTraceProjection:
    """Project a trusted lexical snapshot offline; does not establish database readiness.

    S2.2 must resolve generations and chunks from PostgreSQL in one authorized snapshot.
    Never pass trace self-assertions as the authoritative snapshot.
    """
    try:
        configs = (
            RetrievalConfiguration.bm25_diagnostic_v1(),
            RetrievalConfiguration.bm25_top8_v1(),
            RetrievalConfiguration.bm25_upload_fixture_top8_v1(),
        )
        config = next(c for c in configs if c.id == record.retrieval_configuration_id)
        metadata = record.provider_metadata["retrieval"]
        native_full_window = len(record.branch_observations) == 200
        expected_policy = {
            "id": "bm25-raw-no-cutoff-v1",
            "score_kind": "bm25",
            "numeric_cutoff": None,
            "cutoff_status": "not_calibrated",
            "candidate_limit": config.candidate_k,
            "query_limit": 200,
            "observed_scope": "authorized_top_200",
            "tie_order": "native" if native_full_window else "score_desc_chunk_id_asc",
            "tie_boundary": "unknown" if native_full_window else "complete",
            "beyond_limit": "unknown" if native_full_window else "none",
        }
        legacy_policy = {
            "id": "bm25-raw-no-cutoff-v1",
            "score_kind": "bm25",
            "numeric_cutoff": None,
            "cutoff_status": "not_calibrated",
            "candidate_limit": 200,
            "observed_scope": "authorized_top_k",
            "beyond_limit": "unknown",
        }
        policy_valid = metadata["score_policy"] == expected_policy or (
            config.id == "retrieval-bm25-diagnostic-v1"
            and metadata["score_policy"] == legacy_policy
        )
        if (
            not trace_id
            or record.trace_schema_version != 3
            or record.branch_observation_schema_version != 2
            or record.retrieval_configuration_id != config.id
            or record.embedding_configuration_id is not None
            or record.embedding_set_ids
            or record.fusion_policy_version is not None
            or metadata["mode"] != "bm25-only"
            or not policy_valid
            or metadata["lexical_generations"] != [asdict(g) for g in authorized_generations]
            or record.provider_metadata["embedding"] != {"status": "not_run"}
            or record.provider_metadata["timing"]["phases"]["query_embedding"].get("status")
            != "not_run"
            or tuple(c.chunk_id for c in candidates) != record.retrieved_chunk_ids
            or len(record.candidate_decisions) != len(candidates)
        ):
            raise ValueError("lexical trace metadata mismatch")
        resolved = []
        for rank, (c, d) in enumerate(zip(candidates, record.candidate_decisions, strict=True), 1):
            if (
                c.workspace_id != record.workspace_id
                or c.chunk_id != d["chunk_id"]
                or c.final_rank != rank
                or d["final_rank"] != rank
                or c.final_decision != d["final_decision"]
                or c.decision_reason != d["decision_reason"]
                or c.fusion_score is not None
                or d["fusion_score"] is not None
                or c.vector_contribution is not None
                or c.fts_contribution is not None
                or d["vector_contribution"] is not None
                or d["fts_contribution"] is not None
                or c.bm25_contribution != d["bm25_contribution"]
                or type(c.token_count) is not int
                or c.token_count < 1
            ):
                raise ValueError("lexical candidate mismatch")
            bm25 = c.bm25_contribution
            resolved.append(
                RetrievalCandidate(
                    document_id=c.document_id,
                    document_version_id=c.document_version_id,
                    source_key=c.source_key,
                    source_name=c.source_key,
                    chunk_set_id=c.chunk_set_id,
                    embedding_set_id=None,
                    embedding_configuration_id=None,
                    chunk_id=c.chunk_id,
                    chunk_ordinal=c.chunk_ordinal,
                    heading_path=(),
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    content_checksum=c.content_checksum,
                    token_count=c.token_count,
                    cosine_distance=None,
                    similarity=None,
                    bm25_score=bm25["raw_score"],
                    bm25_rank=bm25["branch_rank"],
                    index_generation_id=bm25["index_generation_id"],
                )
            )
        observations = []
        for item in record.branch_observations:
            if item["schema_version"] != 2:
                raise ValueError("lexical observation version mismatch")
            observations.append(
                BranchObservation(**{k: v for k, v in item.items() if k != "schema_version"})
            )
        result = RetrievalResult(
            candidates=tuple(resolved),
            branch_observations=tuple(observations),
            chunk_set_ids=record.chunk_set_ids,
            lexical_generations=authorized_generations,
        )
        validate_bm25_result(result, workspace_id=record.workspace_id, configuration=config)
        selection = select_evidence(result.candidates, config)
        for actual, expected in zip(record.candidate_decisions, selection.decisions, strict=True):
            outcome = expected.outcome
            reason = None
            if outcome in {"TOKEN_BUDGET_EXCEEDED", "CHUNK_COUNT_LIMIT"}:
                reason = "TOKEN_BUDGET" if outcome == "TOKEN_BUDGET_EXCEEDED" else outcome
                outcome = "BUDGET_EXCEEDED"
            if (actual["final_decision"], actual["decision_reason"], actual["budget_evidence"]) != (
                outcome,
                reason,
                expected.budget_evidence,
            ):
                raise ValueError("lexical selection mismatch")
        aliases = {f"E{i}": d.candidate.chunk_id for i, d in enumerate(selection.selected, 1)}
        if record.alias_mapping != aliases or record.decision not in {"ANSWER", "REFUSAL"}:
            raise ValueError("lexical alias mismatch")
        invalid_generation = include_invalid_generation and record.validation_outcome == "invalid"
        if aliases:
            if record.generation_status != "completed" or (
                record.validation_outcome != "valid" and not invalid_generation
            ):
                raise ValueError("lexical generation state mismatch")
        elif (record.decision, record.generation_status, record.validation_outcome) != (
            "REFUSAL",
            "not_called",
            "not_applicable",
        ):
            raise ValueError("lexical empty-selection state mismatch")
        if invalid_generation:
            # Operator diagnostics retain the stored failure; evaluation stays strict by default.
            markers = (
                tuple(MARKER_PATTERN.findall(record.answer))
                if isinstance(record.answer, str)
                else ()
            )
            if markers != record.parsed_markers:
                raise ValueError("lexical invalid-generation markers mismatch")
        else:
            validated = validate_generation(
                GenerationResult(
                    decision=record.decision,
                    answer=record.answer,
                    refusal_reason=record.refusal_reason,
                    cited_evidence_ids=record.parsed_markers,
                ),
                available_evidence_ids=tuple(aliases),
            )
            if validated.parsed_markers != record.parsed_markers:
                raise ValueError("lexical markers mismatch")
        latency = _retrieval_latency(record.provider_metadata)
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        StopIteration,
        KnoraError,
        LookupError,
    ) as error:
        raise LookupError("evaluation lexical trace provenance is invalid") from error
    return EvaluationTraceProjection(
        trace_id=trace_id,
        workspace_id=record.workspace_id,
        retrieval_configuration_id=record.retrieval_configuration_id,
        embedding_configuration_id=None,
        candidates=candidates,
        alias_mapping=record.alias_mapping,
        provider_metadata=record.provider_metadata,
        retrieval_latency_ms=latency,
        trace_schema_version=3,
        branch_observation_schema_version=2,
        fusion_policy_version=None,
        embedding_set_ids=(),
        chunk_set_ids=record.chunk_set_ids,
        candidate_decisions=record.candidate_decisions,
        branch_observations=record.branch_observations,
        decision=record.decision,
        answer=record.answer,
        refusal_reason=record.refusal_reason,
        parsed_markers=record.parsed_markers,
        validation_outcome=record.validation_outcome,
    )


@dataclass(frozen=True, slots=True)
class ActiveCorpusDocumentProjection:
    source_key: str
    document_version_id: str
    chunk_set_id: str
    normalized_content_checksum: str
    chunking_configuration_id: str
    embedding_configuration_id: str
    chunk_references: tuple[str, ...]
    raw_sha256: str | None = None
    embedding_set_id: str | None = None
    chunk_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActiveCorpusProjection:
    workspace_id: str
    documents: tuple[ActiveCorpusDocumentProjection, ...]


class PostgresEvaluationReader:
    """Read-only, trace-scoped projections for the local evaluation runner."""

    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        lexical_population: VerifiedLexicalPopulation | None = None,
        include_invalid_generation: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._lexical_population = lexical_population
        self._include_invalid_generation = include_invalid_generation

    @staticmethod
    def _begin_lexical_snapshot(session) -> None:
        bind = session.get_bind()
        if isinstance(bind, Connection) and bind.in_transaction():
            if bind.get_isolation_level() not in {"REPEATABLE READ", "SERIALIZABLE"}:
                raise ValueError("Lexical projections require a consistent read snapshot")
        else:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})

    def _read_bm25_trace(self, session, trace, workspace_id) -> EvaluationTraceProjection:
        try:
            if self._lexical_population is None or trace.workspace_id != workspace_id:
                raise ValueError("verified lexical population is required")
            configurations = (
                RetrievalConfiguration.bm25_top8_v1(),
                RetrievalConfiguration.bm25_upload_fixture_top8_v1(),
            )
            config = next(c for c in configurations if c.id == trace.retrieval_configuration_id)
            generations = PostgresSearchIndexStore(
                self._session_factory
            ).read_active_generations_in_snapshot(session, workspace_id, config.lexical_policy_id)
            validate_population_in_transaction(
                session, workspace_id, generations, self._lexical_population
            )
            snapshots = tuple(
                LexicalGeneration(
                    workspace_id,
                    g.document_id,
                    g.document_version_id,
                    g.chunk_set_id,
                    g.generation_id,
                    g.lexical_profile.id,
                )
                for g in generations
            )
            chunk_generations = {
                (g.generation_id, c.chunk_id): g for g in generations for c in g.chunks
            }
            decisions = trace.candidate_decisions
            chunk_ids = [d["chunk_id"] for d in decisions]
            observed_ids = []
            for observation in trace.branch_observations:
                chunk_id = observation.get("chunk_id")
                if chunk_id is not None:
                    if (observation.get("index_generation_id"), chunk_id) not in chunk_generations:
                        raise ValueError("foreign lexical branch chunk")
                    observed_ids.append(chunk_id)
            required_ids = set((*chunk_ids, *observed_ids))
            rows = session.execute(
                select(ChunkTable, DocumentTable, DocumentVersionTable, ChunkSetTable)
                .join(ChunkSetTable, ChunkSetTable.id == ChunkTable.chunk_set_id)
                .join(
                    DocumentVersionTable,
                    DocumentVersionTable.id == ChunkSetTable.document_version_id,
                )
                .join(DocumentTable, DocumentTable.id == DocumentVersionTable.document_id)
                .where(ChunkTable.id.in_(required_ids), DocumentTable.workspace_id == workspace_id)
            ).all()
            by_chunk = {
                chunk.id: (chunk, document, version, cs) for chunk, document, version, cs in rows
            }
            if len(rows) != len(required_ids) or set(by_chunk) != required_ids:
                raise ValueError("lexical candidate not found")
            for observation in trace.branch_observations:
                if observation.get("chunk_id") is None:
                    continue
                g = chunk_generations[observation["index_generation_id"], observation["chunk_id"]]
                chunk, document, version, cs = by_chunk[observation["chunk_id"]]
                if (document.id, document.workspace_id, version.id, cs.id, chunk.chunk_set_id) != (
                    g.document_id,
                    workspace_id,
                    g.document_version_id,
                    g.chunk_set_id,
                    g.chunk_set_id,
                ):
                    raise ValueError("lexical candidate provenance mismatch")
            candidates = tuple(
                EvaluationCandidateProjection(
                    chunk_id=chunk_id,
                    document_version_id=by_chunk[chunk_id][2].id,
                    chunk_set_id=by_chunk[chunk_id][3].id,
                    source_key=by_chunk[chunk_id][1].source_key,
                    chunk_ordinal=by_chunk[chunk_id][0].ordinal,
                    workspace_id=by_chunk[chunk_id][1].workspace_id,
                    content=by_chunk[chunk_id][0].content,
                    start_line=by_chunk[chunk_id][0].start_line,
                    end_line=by_chunk[chunk_id][0].end_line,
                    final_rank=decision["final_rank"],
                    fusion_score=decision["fusion_score"],
                    final_decision=decision["final_decision"],
                    decision_reason=decision.get("decision_reason"),
                    vector_contribution=decision.get("vector_contribution"),
                    fts_contribution=decision.get("fts_contribution"),
                    raw_sha256=by_chunk[chunk_id][2].raw_sha256,
                    parser_configuration_id=by_chunk[chunk_id][3].parser_configuration_id,
                    normalizer_configuration_id=by_chunk[chunk_id][3].normalizer_configuration_id,
                    chunking_configuration_id=by_chunk[chunk_id][3].chunking_configuration_id,
                    page_start=by_chunk[chunk_id][0].page_start,
                    page_end=by_chunk[chunk_id][0].page_end,
                    start_offset=by_chunk[chunk_id][0].start_offset,
                    end_offset=by_chunk[chunk_id][0].end_offset,
                    content_checksum=by_chunk[chunk_id][0].content_checksum,
                    document_id=by_chunk[chunk_id][1].id,
                    token_count=by_chunk[chunk_id][0].token_count,
                    bm25_contribution=decision.get("bm25_contribution"),
                )
                for chunk_id, decision in zip(chunk_ids, decisions, strict=True)
            )
            values = {f.name: getattr(trace, f.name) for f in fields(QuestionTraceRecord)}
            for key in (
                "candidate_decisions",
                "retrieved_chunk_ids",
                "embedding_set_ids",
                "chunk_set_ids",
                "parsed_markers",
                "branch_observations",
            ):
                values[key] = tuple(values[key])
            return project_bm25_trace(
                trace_id=trace.id,
                record=QuestionTraceRecord(**values),
                candidates=candidates,
                authorized_generations=snapshots,
                include_invalid_generation=self._include_invalid_generation,
            )
        except (KnoraError, ValueError, TypeError, KeyError, AttributeError, StopIteration) as exc:
            raise LookupError("evaluation lexical trace provenance is invalid") from exc

    def read_trace(self, *, trace_id: str, workspace_id: str) -> EvaluationTraceProjection:
        with self._session_factory() as session:
            if self._lexical_population is not None:
                self._begin_lexical_snapshot(session)
            trace = session.scalar(
                select(QuestionTraceTable).where(
                    QuestionTraceTable.id == trace_id,
                    QuestionTraceTable.workspace_id == workspace_id,
                )
            )
            if trace is None:
                raise LookupError("evaluation trace not found")
            if trace.trace_schema_version == 3:
                return self._read_bm25_trace(session, trace, workspace_id)
            _validate_trace_metadata(trace)
            decisions = [dict(item) for item in trace.candidate_decisions]
            chunk_ids = _ordered_candidate_ids(
                decisions, fusion_policy_version=trace.fusion_policy_version
            )
            branch_chunk_ids = list(
                dict.fromkeys(
                    str(observation["chunk_id"])
                    for observation in trace.branch_observations
                    if observation.get("chunk_id") is not None
                )
            )
            resolved_chunk_ids = list(dict.fromkeys((*chunk_ids, *branch_chunk_ids)))
            embedding_rows = session.execute(
                select(
                    EmbeddingSetTable.id,
                    EmbeddingSetTable.chunk_set_id,
                    EmbeddingSetTable.embedding_configuration_id,
                )
                .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
                .join(
                    DocumentVersionTable,
                    DocumentVersionTable.id == ChunkSetTable.document_version_id,
                )
                .join(DocumentTable, DocumentTable.id == DocumentVersionTable.document_id)
                .where(
                    EmbeddingSetTable.id.in_(trace.embedding_set_ids),
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.active_embedding_set_id == EmbeddingSetTable.id,
                    EmbeddingSetTable.status == "completed",
                )
            ).all()
            _validate_embedding_provenance(
                embedding_set_ids=trace.embedding_set_ids,
                chunk_set_ids=trace.chunk_set_ids,
                embedding_configuration_id=trace.embedding_configuration_id,
                rows=embedding_rows,
            )
            rows = session.execute(
                select(ChunkTable, DocumentTable, DocumentVersionTable, ChunkSetTable)
                .join(ChunkSetTable, ChunkSetTable.id == ChunkTable.chunk_set_id)
                .join(
                    DocumentVersionTable,
                    DocumentVersionTable.id == ChunkSetTable.document_version_id,
                )
                .join(DocumentTable, DocumentTable.id == DocumentVersionTable.document_id)
                .join(
                    EmbeddingSetTable,
                    EmbeddingSetTable.id == DocumentTable.active_embedding_set_id,
                )
                .where(
                    ChunkTable.id.in_(resolved_chunk_ids),
                    DocumentTable.workspace_id == workspace_id,
                    ChunkSetTable.id.in_(trace.chunk_set_ids),
                    EmbeddingSetTable.id.in_(trace.embedding_set_ids),
                    EmbeddingSetTable.chunk_set_id == ChunkSetTable.id,
                    EmbeddingSetTable.embedding_configuration_id
                    == trace.embedding_configuration_id,
                    EmbeddingSetTable.status == "completed",
                )
            ).all()
        by_chunk = {chunk.id: (chunk, document, version) for chunk, document, version, _ in rows}
        chunk_sets = {chunk.id: chunk_set for chunk, _, _, chunk_set in rows}
        missing_chunk_ids = [chunk_id for chunk_id in chunk_ids if chunk_id not in by_chunk]
        if missing_chunk_ids:
            raise LookupError("evaluation candidate not found")
        missing_branch_chunk_ids = [
            chunk_id for chunk_id in branch_chunk_ids if chunk_id not in by_chunk
        ]
        if missing_branch_chunk_ids:
            raise LookupError("evaluation branch candidate not found")
        trace_embedding_set_ids = set(str(item) for item in trace.embedding_set_ids)
        trace_chunk_set_ids = set(str(item) for item in trace.chunk_set_ids)
        if any(
            chunk.chunk_set_id not in trace_chunk_set_ids
            or document.active_embedding_set_id not in trace_embedding_set_ids
            for chunk, document, _ in by_chunk.values()
        ):
            raise LookupError("evaluation candidate provenance mismatch")
        retrieval_configuration = _resolve_retrieval_configuration(trace.retrieval_configuration_id)
        _validate_candidate_budget_evidence(
            decisions,
            by_chunk,
            retrieval_configuration=retrieval_configuration,
        )
        candidates = tuple(
            EvaluationCandidateProjection(
                chunk_id=chunk_id,
                chunk_set_id=by_chunk[chunk_id][0].chunk_set_id,
                document_version_id=by_chunk[chunk_id][2].id,
                source_key=by_chunk[chunk_id][1].source_key,
                chunk_ordinal=by_chunk[chunk_id][0].ordinal,
                workspace_id=by_chunk[chunk_id][1].workspace_id,
                content=by_chunk[chunk_id][0].content,
                start_line=by_chunk[chunk_id][0].start_line,
                end_line=by_chunk[chunk_id][0].end_line,
                final_rank=int(decision["final_rank"]),
                fusion_score=float(decision["fusion_score"]),
                final_decision=str(decision["final_decision"]),
                decision_reason=decision.get("decision_reason"),
                vector_contribution=decision.get("vector_contribution"),
                fts_contribution=decision.get("fts_contribution"),
                raw_sha256=by_chunk[chunk_id][2].raw_sha256,
                parser_configuration_id=chunk_sets[chunk_id].parser_configuration_id,
                normalizer_configuration_id=chunk_sets[chunk_id].normalizer_configuration_id,
                chunking_configuration_id=chunk_sets[chunk_id].chunking_configuration_id,
                page_start=by_chunk[chunk_id][0].page_start,
                page_end=by_chunk[chunk_id][0].page_end,
                start_offset=by_chunk[chunk_id][0].start_offset,
                end_offset=by_chunk[chunk_id][0].end_offset,
                content_checksum=by_chunk[chunk_id][0].content_checksum,
            )
            for chunk_id, decision in zip(chunk_ids, decisions, strict=True)
        )
        latency = _retrieval_latency(trace.provider_metadata)
        return EvaluationTraceProjection(
            trace_id=trace.id,
            workspace_id=trace.workspace_id,
            retrieval_configuration_id=trace.retrieval_configuration_id or "",
            embedding_configuration_id=trace.embedding_configuration_id or "",
            candidates=candidates,
            alias_mapping=dict(trace.alias_mapping),
            provider_metadata=dict(trace.provider_metadata),
            retrieval_latency_ms=latency,
            trace_schema_version=trace.trace_schema_version,
            branch_observation_schema_version=trace.branch_observation_schema_version,
            fusion_policy_version=trace.fusion_policy_version,
            embedding_set_ids=tuple(str(item) for item in trace.embedding_set_ids),
            chunk_set_ids=tuple(str(item) for item in trace.chunk_set_ids),
            candidate_decisions=tuple(decisions),
            branch_observations=tuple(dict(item) for item in trace.branch_observations),
            decision=trace.decision,
            answer=trace.answer,
            refusal_reason=trace.refusal_reason,
            parsed_markers=tuple(str(item) for item in trace.parsed_markers),
            validation_outcome=trace.validation_outcome,
        )

    def _read_lexical_pdf_chunks(self, *, workspace_id: str) -> tuple[PdfChunkProjection, ...]:
        try:
            with self._session_factory() as session:
                self._begin_lexical_snapshot(session)
                generations = PostgresSearchIndexStore(
                    self._session_factory
                ).read_active_generations_in_snapshot(
                    session, workspace_id, self._lexical_population.profile.id
                )
                validate_population_in_transaction(
                    session, workspace_id, generations, self._lexical_population
                )
                expected = {c.chunk_id: g for g in generations for c in g.chunks}
                rows = session.execute(
                    select(ChunkTable, DocumentTable, DocumentVersionTable, ChunkSetTable)
                    .join(ChunkSetTable, ChunkSetTable.id == ChunkTable.chunk_set_id)
                    .join(
                        DocumentVersionTable,
                        DocumentVersionTable.id == ChunkSetTable.document_version_id,
                    )
                    .join(DocumentTable, DocumentTable.id == DocumentVersionTable.document_id)
                    .where(
                        ChunkTable.id.in_(expected),
                        DocumentTable.workspace_id == workspace_id,
                        DocumentVersionTable.media_type == "application/pdf",
                    )
                    .order_by(DocumentTable.source_key, ChunkTable.ordinal)
                ).all()
                if len(rows) != len(expected) or {r[0].id for r in rows} != set(expected):
                    raise ValueError("lexical PDF population is incomplete")
                for chunk, document, version, chunk_set in rows:
                    g = expected[chunk.id]
                    if (document.workspace_id, document.id, version.id, chunk_set.id) != (
                        workspace_id,
                        g.document_id,
                        g.document_version_id,
                        g.chunk_set_id,
                    ):
                        raise ValueError("lexical PDF provenance mismatch")
                return tuple(
                    PdfChunkProjection(
                        workspace_id=document.workspace_id,
                        source_key=document.source_key,
                        chunk_id=chunk.id,
                        document_version_id=version.id,
                        chunk_set_id=chunk_set.id,
                        raw_sha256=version.raw_sha256,
                        parser_configuration_id=chunk_set.parser_configuration_id,
                        normalizer_configuration_id=chunk_set.normalizer_configuration_id,
                        chunking_configuration_id=chunk_set.chunking_configuration_id,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        start_offset=chunk.start_offset,
                        end_offset=chunk.end_offset,
                        content_checksum=chunk.content_checksum,
                        content=chunk.content,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                    )
                    for chunk, document, version, chunk_set in rows
                )
        except (KnoraError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise LookupError("evaluation lexical PDF provenance is invalid") from exc

    def read_pdf_chunks(self, *, workspace_id: str) -> tuple[PdfChunkProjection, ...]:
        """Project only current, active PDF derivations inside the requested workspace."""
        if self._lexical_population is not None:
            return self._read_lexical_pdf_chunks(workspace_id=workspace_id)
        with self._session_factory() as session:
            rows = session.execute(
                select(ChunkTable, DocumentTable, DocumentVersionTable, ChunkSetTable)
                .join(ChunkSetTable, ChunkSetTable.id == ChunkTable.chunk_set_id)
                .join(
                    DocumentVersionTable,
                    DocumentVersionTable.id == ChunkSetTable.document_version_id,
                )
                .join(DocumentTable, DocumentTable.id == DocumentVersionTable.document_id)
                .join(
                    EmbeddingSetTable, EmbeddingSetTable.id == DocumentTable.active_embedding_set_id
                )
                .where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.archived.is_(False),
                    DocumentTable.current_document_version_id == DocumentVersionTable.id,
                    DocumentVersionTable.media_type == "application/pdf",
                    EmbeddingSetTable.chunk_set_id == ChunkSetTable.id,
                    EmbeddingSetTable.status == "completed",
                    ChunkSetTable.status == "completed",
                )
                .order_by(DocumentTable.source_key, ChunkTable.ordinal)
            ).all()
        return tuple(
            PdfChunkProjection(
                workspace_id=document.workspace_id,
                source_key=document.source_key,
                chunk_id=chunk.id,
                document_version_id=version.id,
                chunk_set_id=chunk_set.id,
                raw_sha256=version.raw_sha256,
                parser_configuration_id=chunk_set.parser_configuration_id,
                normalizer_configuration_id=chunk_set.normalizer_configuration_id,
                chunking_configuration_id=chunk_set.chunking_configuration_id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                content_checksum=chunk.content_checksum,
                content=chunk.content,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
            for chunk, document, version, chunk_set in rows
        )

    def read_active_corpus(self, *, workspace_id: str) -> ActiveCorpusProjection:
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    DocumentTable,
                    DocumentVersionTable,
                    ChunkSetTable,
                    EmbeddingSetTable,
                    ChunkTable,
                )
                .join(
                    EmbeddingSetTable,
                    EmbeddingSetTable.id == DocumentTable.active_embedding_set_id,
                )
                .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
                .join(
                    DocumentVersionTable,
                    DocumentVersionTable.id == ChunkSetTable.document_version_id,
                )
                .join(ChunkTable, ChunkTable.chunk_set_id == ChunkSetTable.id)
                .where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.archived.is_(False),
                    EmbeddingSetTable.status == "completed",
                )
                .order_by(DocumentTable.source_key, ChunkTable.ordinal)
            ).all()
        grouped: dict[str, list] = {}
        chunk_id_groups: dict[str, list[str]] = {}
        identities: dict[str, tuple] = {}
        for document, version, chunk_set, embedding_set, chunk in rows:
            grouped.setdefault(document.source_key, []).append(
                f"{document.source_key}#{chunk.ordinal}"
            )
            chunk_id_groups.setdefault(document.source_key, []).append(chunk.id)
            identities[document.source_key] = (version, chunk_set, embedding_set)
        documents = tuple(
            ActiveCorpusDocumentProjection(
                source_key=source_key,
                document_version_id=identities[source_key][0].id,
                chunk_set_id=identities[source_key][1].id,
                normalized_content_checksum=identities[source_key][0].normalized_content_checksum,
                chunking_configuration_id=identities[source_key][1].chunking_configuration_id,
                embedding_configuration_id=identities[source_key][2].embedding_configuration_id,
                chunk_references=tuple(grouped[source_key]),
                raw_sha256=identities[source_key][0].raw_sha256,
                embedding_set_id=identities[source_key][2].id,
                chunk_ids=tuple(chunk_id_groups[source_key]),
            )
            for source_key in sorted(grouped)
        )
        return ActiveCorpusProjection(workspace_id=workspace_id, documents=documents)


def _validate_candidate_budget_evidence(
    decisions: list[dict[str, object]],
    by_chunk: dict[str, tuple[object, object, object]],
    *,
    retrieval_configuration: object,
) -> None:
    """Bind budget evidence to selected chunks and immutable configuration limits."""
    max_chunks = getattr(retrieval_configuration, "max_evidence_chunks", None)
    max_tokens = getattr(retrieval_configuration, "max_evidence_tokens", None)
    if (
        type(max_chunks) is not int
        or type(max_tokens) is not int
        or max_chunks < 1
        or max_tokens < 1
    ):
        raise LookupError("evaluation candidate budget evidence is invalid")

    selected_chunk_ids: list[str] = []
    selected_tokens = 0
    for decision in decisions:
        evidence = decision.get("budget_evidence")
        chunk_id = decision.get("chunk_id")
        resolved = by_chunk.get(chunk_id) if isinstance(chunk_id, str) else None
        chunk = resolved[0] if resolved is not None else None
        candidate_tokens = getattr(chunk, "token_count", None)
        if evidence is not None and (
            not isinstance(evidence, dict)
            or type(candidate_tokens) is not int
            or evidence.get("candidate_token_count") != candidate_tokens
            or evidence.get("max_evidence_chunks") != max_chunks
            or evidence.get("max_evidence_tokens") != max_tokens
            or evidence.get("selected_chunk_count") != len(selected_chunk_ids)
            or evidence.get("selected_token_count") != selected_tokens
            or evidence.get("token_total") != selected_tokens + candidate_tokens
            or not _valid_budget_evidence(str(decision.get("decision_reason")), evidence)
        ):
            raise LookupError("evaluation candidate budget evidence is invalid")
        if decision.get("final_decision") == "SELECTED":
            if type(candidate_tokens) is not int or not isinstance(chunk_id, str):
                raise LookupError("evaluation candidate budget evidence is invalid")
            selected_chunk_ids.append(chunk_id)
            selected_tokens += candidate_tokens


def _resolve_retrieval_configuration(configuration_id: str) -> object:
    """Resolve persisted trace limits through the application configuration seam."""
    try:
        if configuration_id in {"retrieval-m3-vector-v2", "retrieval-m3-rrf-v2"}:
            return resolve_retrieval_configuration(
                configuration_id,
                vector_min_similarity=CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
            )
        return resolve_retrieval_configuration(
            configuration_id,
            vector_min_similarity=None,
        )
    except (TypeError, ValueError) as error:
        raise LookupError("evaluation trace retrieval configuration is invalid") from error


def _ordered_candidate_ids(
    decisions: list[dict[str, object]], *, fusion_policy_version: str | None = None
) -> list[str]:
    """Validate persisted fused ordering before it becomes evaluation provenance."""
    chunk_ids: list[str] = []
    for expected_rank, decision in enumerate(decisions, start=1):
        chunk_id = decision.get("chunk_id")
        if (
            type(decision.get("final_rank")) is not int
            or decision.get("final_rank") != expected_rank
            or not isinstance(chunk_id, str)
            or not chunk_id
        ):
            raise LookupError("evaluation candidate ordering is invalid")
        chunk_ids.append(chunk_id)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise LookupError("evaluation candidate ordering is invalid")
    for decision in decisions:
        vector_contribution = decision.get("vector_contribution")
        fts_contribution = decision.get("fts_contribution")
        final_decision = decision.get("final_decision")
        decision_reason = decision.get("decision_reason")
        budget_evidence = decision.get("budget_evidence")
        if (
            not isinstance(decision.get("fusion_score"), (int, float))
            or isinstance(decision.get("fusion_score"), bool)
            or not isfinite(float(decision["fusion_score"]))
            or not isinstance(final_decision, str)
            or final_decision not in _VALID_FINAL_DECISIONS
            or not _valid_decision_reason(
                final_decision,
                decision_reason,
                budget_evidence,
            )
            or not _valid_contribution(vector_contribution, branch="vector")
            or not _valid_contribution(fts_contribution, branch="fts")
            or (vector_contribution is None and fts_contribution is None)
            or not _fusion_score_matches_contributions(
                decision["fusion_score"],
                vector_contribution,
                fts_contribution,
                fusion_policy_version=fusion_policy_version,
            )
        ):
            raise LookupError("evaluation candidate decision is invalid")
    return chunk_ids


def _valid_decision_reason(
    final_decision: str,
    decision_reason: object,
    budget_evidence: object,
) -> bool:
    if final_decision == "BUDGET_EXCEEDED":
        return (
            isinstance(decision_reason, str)
            and decision_reason in _VALID_DECISION_REASONS
            and _valid_budget_evidence(decision_reason, budget_evidence)
        )
    return decision_reason is None and budget_evidence is None


def _valid_budget_evidence(reason: str, evidence: object) -> bool:
    if not isinstance(evidence, dict) or set(evidence) != {
        "max_evidence_chunks",
        "max_evidence_tokens",
        "selected_chunk_count",
        "selected_token_count",
        "candidate_token_count",
        "token_total",
    }:
        return False
    max_chunks = evidence.get("max_evidence_chunks")
    max_tokens = evidence.get("max_evidence_tokens")
    selected_chunks = evidence.get("selected_chunk_count")
    selected_tokens = evidence.get("selected_token_count")
    candidate_tokens = evidence.get("candidate_token_count")
    token_total = evidence.get("token_total")
    if (
        any(
            type(value) is not int
            for value in (
                max_chunks,
                max_tokens,
                selected_chunks,
                selected_tokens,
                candidate_tokens,
                token_total,
            )
        )
        or max_chunks < 1
        or max_tokens < 1
        or selected_chunks < 0
        or selected_chunks > max_chunks
        or selected_tokens < 0
        or selected_tokens > max_tokens
        or candidate_tokens < 1
        or token_total != selected_tokens + candidate_tokens
    ):
        return False
    if reason == "TOKEN_BUDGET":
        return selected_chunks < max_chunks and token_total > max_tokens
    return selected_chunks >= max_chunks


def _valid_contribution(value: object, *, branch: str) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict):
        return False
    expected_keys = (
        {"branch_rank", "cosine_distance", "similarity"}
        if branch == "vector"
        else {"branch_rank", "native_rank"}
    )
    if set(value) != expected_keys:
        return False
    branch_rank = value.get("branch_rank")
    if type(branch_rank) is not int or branch_rank < 1:
        return False
    fields = ("cosine_distance", "similarity") if branch == "vector" else ("native_rank",)
    for field in fields:
        number = value.get(field)
        if number is None or (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not isfinite(float(number))
        ):
            return False
    return True


def _fusion_score_matches_contributions(
    score: object,
    vector_contribution: object,
    fts_contribution: object,
    *,
    fusion_policy_version: str | None,
) -> bool:
    if fusion_policy_version not in {"rrf-v1", "rrf-v2"}:
        return True
    ranks = [
        contribution["branch_rank"]
        for contribution in (vector_contribution, fts_contribution)
        if isinstance(contribution, dict)
    ]
    expected = sum(1 / (60 + rank) for rank in ranks)
    return abs(float(score) - expected) <= 1e-12


def _validate_branch_observations(observations: object) -> None:
    if not isinstance(observations, list) or not observations:
        raise LookupError("evaluation branch observation is invalid")
    for observation in observations:
        if not isinstance(observation, dict):
            raise LookupError("evaluation branch observation is invalid")
        branch = observation.get("branch")
        status = observation.get("status")
        if (
            type(observation.get("schema_version")) is not int
            or observation.get("schema_version") != 1
            or branch not in _VALID_BRANCH_STATUSES
            or status not in _VALID_BRANCH_STATUSES[branch]
            or not isinstance(observation.get("normalized_lexemes"), list)
            or not isinstance(observation.get("omitted_lexemes"), list)
            or "final_rank" in observation
            or "fusion_score" in observation
        ):
            raise LookupError("evaluation branch observation is invalid")
        chunk_id = observation.get("chunk_id")
        if chunk_id is not None and (not isinstance(chunk_id, str) or not chunk_id):
            raise LookupError("evaluation branch observation is invalid")
        if status == "ELIGIBLE" and chunk_id is None:
            raise LookupError("evaluation branch observation is invalid")
        if branch == "fts" and (
            not isinstance(observation.get("lexical_policy_id"), str)
            or not observation["lexical_policy_id"]
            or observation["lexical_policy_id"] not in _VALID_LEXICAL_POLICIES
        ):
            raise LookupError("evaluation branch observation is invalid")
        normalized_lexemes = observation["normalized_lexemes"]
        omitted_lexemes = observation["omitted_lexemes"]
        if any(not isinstance(item, str) or not item for item in normalized_lexemes):
            raise LookupError("evaluation branch observation is invalid")
        if any(not isinstance(item, str) or not item for item in omitted_lexemes):
            raise LookupError("evaluation branch observation is invalid")
        if (
            len(normalized_lexemes) != len(set(normalized_lexemes))
            or len(omitted_lexemes) != len(set(omitted_lexemes))
            or set(normalized_lexemes) & set(omitted_lexemes)
        ):
            raise LookupError("evaluation branch observation is invalid")
        branch_rank = observation.get("branch_rank")
        if status == "ELIGIBLE" and (type(branch_rank) is not int or branch_rank < 1):
            raise LookupError("evaluation branch observation is invalid")
        if status != "ELIGIBLE" and branch_rank is not None:
            raise LookupError("evaluation branch observation is invalid")
        for field in ("cosine_distance", "similarity", "native_rank"):
            number = observation.get(field)
            if number is not None and (
                isinstance(number, bool)
                or not isinstance(number, (int, float))
                or not isfinite(float(number))
            ):
                raise LookupError("evaluation branch observation is invalid")
        if branch == "vector" and observation.get("native_rank") is not None:
            raise LookupError("evaluation branch observation is invalid")
        if branch == "fts" and (
            observation.get("cosine_distance") is not None
            or observation.get("similarity") is not None
        ):
            raise LookupError("evaluation branch observation is invalid")
        if branch == "vector":
            has_scores = (
                observation.get("cosine_distance") is not None
                and observation.get("similarity") is not None
            )
            if status in {"ELIGIBLE", "BELOW_THRESHOLD"} and not has_scores:
                raise LookupError("evaluation branch observation is invalid")
            if status == "NO_CONTRIBUTION" and has_scores:
                raise LookupError("evaluation branch observation is invalid")
        else:
            native_rank = observation.get("native_rank")
            if status == "ELIGIBLE" and native_rank is None:
                raise LookupError("evaluation branch observation is invalid")
            if status != "ELIGIBLE" and native_rank is not None:
                raise LookupError("evaluation branch observation is invalid")


def _validate_candidate_observations(
    decisions: list[dict[str, object]], observations: list[dict[str, object]]
) -> None:
    eligible: dict[tuple[str, str], list[dict[str, object]]] = {}
    for observation in observations:
        if observation["status"] != "ELIGIBLE":
            continue
        chunk_id = observation.get("chunk_id")
        if not isinstance(chunk_id, str):
            raise LookupError("evaluation candidate decision is invalid")
        eligible.setdefault((observation["branch"], chunk_id), []).append(observation)

    used: set[tuple[str, str]] = set()
    for decision in decisions:
        chunk_id = decision["chunk_id"]
        for branch, field in (("vector", "vector_contribution"), ("fts", "fts_contribution")):
            contribution = decision.get(field)
            if contribution is None:
                continue
            matches = eligible.get((branch, chunk_id), [])
            if len(matches) != 1:
                raise LookupError("evaluation candidate decision is invalid")
            observation = matches[0]
            used.add((branch, chunk_id))
            if contribution["branch_rank"] != observation["branch_rank"]:
                raise LookupError("evaluation candidate decision is invalid")
            score_fields = (
                ("cosine_distance", "similarity") if branch == "vector" else ("native_rank",)
            )
            if any(
                abs(float(contribution[field_name]) - float(observation[field_name])) > 1e-12
                for field_name in score_fields
            ):
                raise LookupError("evaluation candidate decision is invalid")
    if set(eligible) != used:
        raise LookupError("evaluation candidate decision is invalid")


def _validate_trace_metadata(trace: object) -> None:
    trace_schema_version = getattr(trace, "trace_schema_version", None)
    branch_observation_schema_version = getattr(trace, "branch_observation_schema_version", None)
    retrieval_configuration_id = getattr(trace, "retrieval_configuration_id", None)
    embedding_configuration_id = getattr(trace, "embedding_configuration_id", None)
    embedding_set_ids = getattr(trace, "embedding_set_ids", None)
    chunk_set_ids = getattr(trace, "chunk_set_ids", None)
    fusion_policy_version = getattr(trace, "fusion_policy_version", None)
    question = getattr(trace, "question", None)
    decision = getattr(trace, "decision", None)
    if (
        type(trace_schema_version) is not int
        or trace_schema_version != 2
        or type(branch_observation_schema_version) is not int
        or branch_observation_schema_version != 1
        or not isinstance(retrieval_configuration_id, str)
        or not retrieval_configuration_id
        or not isinstance(question, str)
        or not isinstance(embedding_configuration_id, str)
        or not embedding_configuration_id
        or not isinstance(getattr(trace, "candidate_decisions", None), list)
        or not isinstance(getattr(trace, "branch_observations", None), list)
        or not isinstance(getattr(trace, "provider_metadata", None), dict)
        or not isinstance(embedding_set_ids, list)
        or not embedding_set_ids
        or not isinstance(chunk_set_ids, list)
        or not chunk_set_ids
        or any(not isinstance(item, str) or not item for item in embedding_set_ids)
        or any(not isinstance(item, str) or not item for item in chunk_set_ids)
    ):
        raise LookupError("evaluation trace provenance is invalid")
    provenance = _RETRIEVAL_PROVENANCE.get(retrieval_configuration_id)
    if provenance is None:
        raise LookupError("evaluation trace provenance is invalid")
    expected_fusion_policy, expected_lexical_policy, expected_branches = provenance
    if fusion_policy_version != expected_fusion_policy:
        raise LookupError("evaluation trace provenance is invalid")
    if not isinstance(decision, str) or decision not in {"ANSWER", "REFUSAL"}:
        raise LookupError("evaluation trace provenance is invalid")
    answer = getattr(trace, "answer", None)
    refusal_reason = getattr(trace, "refusal_reason", None)
    if decision == "REFUSAL":
        if answer is not None or refusal_reason != "INSUFFICIENT_EVIDENCE":
            raise LookupError("evaluation trace provenance is invalid")
    elif not isinstance(answer, str) or not answer.strip() or refusal_reason is not None:
        raise LookupError("evaluation trace provenance is invalid")
    parsed_markers = getattr(trace, "parsed_markers", None)
    if not isinstance(parsed_markers, list) or any(
        not isinstance(marker, str) or not marker for marker in parsed_markers
    ):
        raise LookupError("evaluation trace provenance is invalid")
    decisions = [dict(item) for item in trace.candidate_decisions]
    _ordered_candidate_ids(decisions, fusion_policy_version=fusion_policy_version)
    _validate_branch_observations(trace.branch_observations)
    _validate_candidate_observations(decisions, trace.branch_observations)
    branches = {observation["branch"] for observation in trace.branch_observations}
    if branches != expected_branches:
        raise LookupError("evaluation trace provenance is invalid")
    if expected_lexical_policy is not None and any(
        observation["lexical_policy_id"] != expected_lexical_policy
        for observation in trace.branch_observations
        if observation["branch"] == "fts"
    ):
        raise LookupError("evaluation trace provenance is invalid")
    _validate_lexical_provenance(
        question=question,
        observations=trace.branch_observations,
        expected_lexical_policy=expected_lexical_policy,
    )
    _retrieval_latency(trace.provider_metadata)


def _validate_lexical_provenance(
    *,
    question: str,
    observations: list[dict[str, object]],
    expected_lexical_policy: str | None,
) -> None:
    expected_normalized: tuple[str, ...] = ()
    expected_omitted: tuple[str, ...] = ()
    if expected_lexical_policy == "fts-m3-or-v2":
        lexical = normalize_fts_m3_or_v2_details(question)
        expected_normalized = lexical.normalized_lexemes
        expected_omitted = lexical.omitted_lexemes
    for observation in observations:
        normalized = tuple(observation["normalized_lexemes"])
        omitted = tuple(observation["omitted_lexemes"])
        if observation["branch"] == "vector":
            if observation.get("lexical_policy_id") is not None or normalized or omitted:
                raise LookupError("evaluation trace provenance is invalid")
            continue
        if (
            normalized != expected_normalized
            or omitted != expected_omitted
            or observation.get("lexical_policy_id") != expected_lexical_policy
        ):
            raise LookupError("evaluation trace provenance is invalid")


def _retrieval_latency(provider_metadata: object) -> float:
    if not isinstance(provider_metadata, dict):
        raise LookupError("evaluation retrieval latency is invalid")
    retrieval = provider_metadata.get("retrieval")
    latency = retrieval.get("latency_ms") if isinstance(retrieval, dict) else None
    if (
        isinstance(latency, bool)
        or not isinstance(latency, (int, float))
        or not isfinite(float(latency))
        or latency < 0
    ):
        raise LookupError("evaluation retrieval latency is invalid")
    resolution, phases = _validate_phase_timing(provider_metadata)
    expected = sum(
        float(phases[name]["duration_ms"]) for name in ("candidate_retrieval", "evidence_selection")
    )
    if abs(float(latency) - expected) > resolution:
        raise LookupError("evaluation retrieval latency is invalid")
    return float(latency)


def _validate_phase_timing(
    provider_metadata: dict[str, object],
) -> tuple[float, dict[str, dict[str, object]]]:
    timing = provider_metadata.get("timing")
    if not isinstance(timing, dict):
        raise LookupError("evaluation phase timing is invalid")
    resolution = timing.get("clock_resolution_ms")
    phases = timing.get("phases")
    if (
        isinstance(resolution, bool)
        or not isinstance(resolution, (int, float))
        or not isfinite(float(resolution))
        or resolution <= 0
        or not isinstance(phases, dict)
        or set(phases)
        != {"query_embedding", "candidate_retrieval", "evidence_selection", "generation"}
    ):
        raise LookupError("evaluation phase timing is invalid")
    previous_end: float | None = None
    for phase_name in (
        "query_embedding",
        "candidate_retrieval",
        "evidence_selection",
        "generation",
    ):
        phase = phases[phase_name]
        if not isinstance(phase, dict):
            raise LookupError("evaluation phase timing is invalid")
        start = phase.get("start_tick")
        end = phase.get("end_tick")
        duration = phase.get("duration_ms")
        if (
            any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(float(value))
                for value in (start, end, duration)
            )
            or end < start
            or duration < 0
            or (previous_end is not None and start != previous_end)
        ):
            raise LookupError("evaluation phase timing is invalid")
        if abs(float(duration) - (float(end) - float(start)) * 1000) > float(resolution):
            raise LookupError("evaluation phase timing is invalid")
        previous_end = float(end)
    return float(resolution), phases
