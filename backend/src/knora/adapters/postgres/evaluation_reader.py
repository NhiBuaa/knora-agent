from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    QuestionTraceTable,
)
from knora.answering.retrieval_v2 import normalize_fts_m3_or_v2_details

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
    final_rank: int
    fusion_score: float
    final_decision: str
    decision_reason: str | None
    vector_contribution: dict[str, object] | None
    fts_contribution: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class EvaluationTraceProjection:
    trace_id: str
    workspace_id: str
    retrieval_configuration_id: str
    embedding_configuration_id: str
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


@dataclass(frozen=True, slots=True)
class ActiveCorpusDocumentProjection:
    source_key: str
    document_version_id: str
    chunk_set_id: str
    normalized_content_checksum: str
    chunking_configuration_id: str
    embedding_configuration_id: str
    chunk_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ActiveCorpusProjection:
    workspace_id: str
    documents: tuple[ActiveCorpusDocumentProjection, ...]


class PostgresEvaluationReader:
    """Read-only, trace-scoped projections for the local evaluation runner."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def read_trace(
        self, *, trace_id: str, workspace_id: str
    ) -> EvaluationTraceProjection:
        with self._session_factory() as session:
            trace = session.scalar(
                select(QuestionTraceTable).where(
                    QuestionTraceTable.id == trace_id,
                    QuestionTraceTable.workspace_id == workspace_id,
                )
            )
            if trace is None:
                raise LookupError("evaluation trace not found")
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
                select(ChunkTable, DocumentTable, DocumentVersionTable)
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
        by_chunk = {chunk.id: (chunk, document, version) for chunk, document, version in rows}
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
        candidates = tuple(
            EvaluationCandidateProjection(
                chunk_id=chunk_id,
                chunk_set_id=by_chunk[chunk_id][0].chunk_set_id,
                document_version_id=by_chunk[chunk_id][2].id,
                source_key=by_chunk[chunk_id][1].source_key,
                chunk_ordinal=by_chunk[chunk_id][0].ordinal,
                workspace_id=by_chunk[chunk_id][1].workspace_id,
                content=by_chunk[chunk_id][0].content,
                final_rank=int(decision["final_rank"]),
                fusion_score=float(decision["fusion_score"]),
                final_decision=str(decision["final_decision"]),
                decision_reason=decision.get("decision_reason"),
                vector_contribution=decision.get("vector_contribution"),
                fts_contribution=decision.get("fts_contribution"),
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
                .where(DocumentTable.workspace_id == workspace_id)
                .order_by(DocumentTable.source_key, ChunkTable.ordinal)
            ).all()
        grouped: dict[str, list] = {}
        identities: dict[str, tuple] = {}
        for document, version, chunk_set, embedding_set, chunk in rows:
            grouped.setdefault(document.source_key, []).append(
                f"{document.source_key}#{chunk.ordinal}"
            )
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
            )
            for source_key in sorted(grouped)
        )
        return ActiveCorpusProjection(workspace_id=workspace_id, documents=documents)


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
        if (
            not isinstance(decision.get("fusion_score"), (int, float))
            or isinstance(decision.get("fusion_score"), bool)
            or not isfinite(float(decision["fusion_score"]))
            or not isinstance(final_decision, str)
            or final_decision not in _VALID_FINAL_DECISIONS
            or not _valid_decision_reason(final_decision, decision_reason)
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


def _valid_decision_reason(final_decision: str, decision_reason: object) -> bool:
    if final_decision == "BUDGET_EXCEEDED":
        return isinstance(decision_reason, str) and decision_reason in _VALID_DECISION_REASONS
    if decision_reason is None:
        return True
    return isinstance(decision_reason, str) and decision_reason in _VALID_DECISION_REASONS


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
        if len(normalized_lexemes) != len(set(normalized_lexemes)) or len(
            omitted_lexemes
        ) != len(set(omitted_lexemes)) or set(normalized_lexemes) & set(omitted_lexemes):
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
                ("cosine_distance", "similarity")
                if branch == "vector"
                else ("native_rank",)
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
            if (
                observation.get("lexical_policy_id") is not None
                or normalized
                or omitted
            ):
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
        float(phases[name]["duration_ms"])
        for name in ("candidate_retrieval", "evidence_selection")
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
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            for value in (start, end, duration)
        ) or end < start or duration < 0 or (
            previous_end is not None and start != previous_end
        ):
            raise LookupError("evaluation phase timing is invalid")
        if abs(float(duration) - (float(end) - float(start)) * 1000) > float(resolution):
            raise LookupError("evaluation phase timing is invalid")
        previous_end = float(end)
    return float(resolution), phases
