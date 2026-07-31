from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    QuestionTraceTable,
)
from knora.answering.stores import (
    AnsweringStore,
    QuestionTraceRecord,
    RetrievalCandidate,
    RetrievalConfiguration,
)
from knora.providers.embedding import EmbeddingConfiguration


class PostgresAnsweringStore(AnsweringStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def retrieve_candidates(
        self,
        *,
        workspace_id: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
    ) -> tuple[RetrievalCandidate, ...]:
        distance = ChunkEmbeddingTable.embedding.cosine_distance(list(query_vector)).label(
            "cosine_distance"
        )
        statement = (
            select(
                DocumentTable,
                DocumentVersionTable,
                ChunkSetTable,
                EmbeddingSetTable,
                ChunkTable,
                distance,
            )
            .join(
                DocumentVersionTable,
                DocumentVersionTable.document_id == DocumentTable.id,
            )
            .join(ChunkSetTable, ChunkSetTable.document_version_id == DocumentVersionTable.id)
            .join(ChunkTable, ChunkTable.chunk_set_id == ChunkSetTable.id)
            .join(ChunkEmbeddingTable, ChunkEmbeddingTable.chunk_id == ChunkTable.id)
            .join(
                EmbeddingSetTable,
                EmbeddingSetTable.id == ChunkEmbeddingTable.embedding_set_id,
            )
            .where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.active_embedding_set_id == EmbeddingSetTable.id,
                EmbeddingSetTable.chunk_set_id == ChunkSetTable.id,
                EmbeddingSetTable.embedding_configuration_id == embedding_configuration.id,
                EmbeddingSetTable.status == "completed",
            )
            .order_by(
                distance.asc(),
                DocumentTable.id.asc(),
                ChunkTable.ordinal.asc(),
                ChunkTable.id.asc(),
            )
            .limit(retrieval_configuration.candidate_k)
        )
        with self._session_factory() as session:
            rows = session.execute(statement).all()
        return tuple(
            RetrievalCandidate(
                document_id=document.id,
                document_version_id=version.id,
                source_key=document.source_key,
                source_name=document.source_name,
                chunk_set_id=chunk_set.id,
                embedding_set_id=embedding_set.id,
                embedding_configuration_id=embedding_set.embedding_configuration_id,
                chunk_id=chunk.id,
                chunk_ordinal=chunk.ordinal,
                heading_path=tuple(chunk.heading_path),
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                content_checksum=chunk.content_checksum,
                token_count=chunk.token_count,
                cosine_distance=float(raw_distance),
                similarity=1.0 - float(raw_distance),
            )
            for document, version, chunk_set, embedding_set, chunk, raw_distance in rows
        )

    def persist_trace(self, trace: QuestionTraceRecord) -> str:
        trace_id = str(uuid4())
        with self._session_factory.begin() as session:
            session.add(
                QuestionTraceTable(
                    id=trace_id,
                    workspace_id=trace.workspace_id,
                    question=trace.question,
                    retrieval_configuration_id=trace.retrieval_configuration_id,
                    embedding_configuration_id=trace.embedding_configuration_id,
                    embedding_set_ids=list(trace.embedding_set_ids),
                    chunk_set_ids=list(trace.chunk_set_ids),
                    retrieved_chunk_ids=list(trace.retrieved_chunk_ids),
                    candidate_decisions=list(trace.candidate_decisions),
                    decision=trace.decision,
                    answer=trace.answer,
                    refused=trace.decision == "REFUSAL",
                    refusal_reason=trace.refusal_reason,
                    generation_status=trace.generation_status,
                    alias_mapping=trace.alias_mapping,
                    parsed_markers=list(trace.parsed_markers),
                    validation_outcome=trace.validation_outcome,
                    provider_metadata=trace.provider_metadata,
                    latency_ms=trace.latency_ms,
                )
            )
        return trace_id
