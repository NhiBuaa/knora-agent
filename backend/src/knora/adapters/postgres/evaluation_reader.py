from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class EvaluationCandidateProjection:
    chunk_id: str
    source_key: str
    chunk_ordinal: int
    workspace_id: str
    content: str


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


@dataclass(frozen=True, slots=True)
class ActiveCorpusDocumentProjection:
    source_key: str
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
            chunk_ids = [decision["chunk_id"] for decision in trace.candidate_decisions]
            rows = session.execute(
                select(ChunkTable, DocumentTable)
                .join(ChunkSetTable, ChunkSetTable.id == ChunkTable.chunk_set_id)
                .join(
                    DocumentVersionTable,
                    DocumentVersionTable.id == ChunkSetTable.document_version_id,
                )
                .join(DocumentTable, DocumentTable.id == DocumentVersionTable.document_id)
                .where(
                    ChunkTable.id.in_(chunk_ids),
                    DocumentTable.workspace_id == workspace_id,
                )
            ).all()
        by_chunk = {chunk.id: (chunk, document) for chunk, document in rows}
        missing_chunk_ids = [chunk_id for chunk_id in chunk_ids if chunk_id not in by_chunk]
        if missing_chunk_ids:
            raise LookupError("evaluation candidate not found")
        candidates = tuple(
            EvaluationCandidateProjection(
                chunk_id=chunk_id,
                source_key=by_chunk[chunk_id][1].source_key,
                chunk_ordinal=by_chunk[chunk_id][0].ordinal,
                workspace_id=by_chunk[chunk_id][1].workspace_id,
                content=by_chunk[chunk_id][0].content,
            )
            for chunk_id in chunk_ids
        )
        retrieval = trace.provider_metadata.get("retrieval", {})
        latency = retrieval.get("latency_ms", 0.0) if isinstance(retrieval, dict) else 0.0
        return EvaluationTraceProjection(
            trace_id=trace.id,
            workspace_id=trace.workspace_id,
            retrieval_configuration_id=trace.retrieval_configuration_id or "",
            embedding_configuration_id=trace.embedding_configuration_id or "",
            candidates=candidates,
            alias_mapping=dict(trace.alias_mapping),
            provider_metadata=dict(trace.provider_metadata),
            retrieval_latency_ms=float(latency),
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
                normalized_content_checksum=identities[source_key][0].normalized_content_checksum,
                chunking_configuration_id=identities[source_key][1].chunking_configuration_id,
                embedding_configuration_id=identities[source_key][2].embedding_configuration_id,
                chunk_references=tuple(grouped[source_key]),
            )
            for source_key in sorted(grouped)
        )
        return ActiveCorpusProjection(workspace_id=workspace_id, documents=documents)
