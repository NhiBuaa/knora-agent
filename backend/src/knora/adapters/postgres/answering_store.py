from dataclasses import replace
from uuid import uuid4

from sqlalchemy import func, select
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
        query_text: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
    ) -> tuple[RetrievalCandidate, ...]:
        if retrieval_configuration.strategy == "vector-only":
            return self._vector_candidates(
                workspace_id=workspace_id,
                query_vector=query_vector,
                embedding_configuration=embedding_configuration,
                retrieval_configuration=retrieval_configuration,
            )
        if retrieval_configuration.strategy != "hybrid":
            raise ValueError("unsupported retrieval strategy")
        if retrieval_configuration.fusion_policy_version != "rrf-v1":
            raise ValueError("unsupported fusion policy")
        if retrieval_configuration.fts_policy_version != "fts-v1":
            raise ValueError("unsupported FTS policy")
        vector = self._vector_candidates(
            workspace_id=workspace_id,
            query_vector=query_vector,
            embedding_configuration=embedding_configuration,
            retrieval_configuration=retrieval_configuration,
        )
        fts = self._fts_candidates(
            workspace_id=workspace_id,
            query_text=query_text,
            embedding_configuration=embedding_configuration,
            retrieval_configuration=retrieval_configuration,
        )
        return self._fuse(vector, fts)

    def _vector_candidates(
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
                distance <= 1.0 - retrieval_configuration.min_similarity,
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
                vector_contribution={
                    "branch_rank": index,
                    "cosine_distance": float(raw_distance),
                    "similarity": 1.0 - float(raw_distance),
                },
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
            )
            for index, (
                document,
                version,
                chunk_set,
                embedding_set,
                chunk,
                raw_distance,
            ) in enumerate(rows, start=1)
        )

    def _fts_candidates(
        self,
        *,
        workspace_id: str,
        query_text: str,
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
    ) -> tuple[RetrievalCandidate, ...]:
        query = func.plainto_tsquery("simple", query_text)
        rank = func.ts_rank_cd(ChunkTable.search_vector, query, 0).label("native_rank")
        statement = (
            select(
                DocumentTable,
                DocumentVersionTable,
                ChunkSetTable,
                EmbeddingSetTable,
                ChunkTable,
                rank,
            )
            .join(DocumentVersionTable, DocumentVersionTable.document_id == DocumentTable.id)
            .join(ChunkSetTable, ChunkSetTable.document_version_id == DocumentVersionTable.id)
            .join(ChunkTable, ChunkTable.chunk_set_id == ChunkSetTable.id)
            .join(EmbeddingSetTable, EmbeddingSetTable.id == DocumentTable.active_embedding_set_id)
            .where(
                DocumentTable.workspace_id == workspace_id,
                EmbeddingSetTable.chunk_set_id == ChunkSetTable.id,
                EmbeddingSetTable.embedding_configuration_id == embedding_configuration.id,
                EmbeddingSetTable.status == "completed",
                ChunkTable.search_vector.op("@@")(query),
            )
            .order_by(rank.desc(), ChunkTable.id.asc())
            .limit(retrieval_configuration.candidate_k)
        )
        with self._session_factory() as session:
            rows = session.execute(statement).all()
        return tuple(
            RetrievalCandidate(
                document_id=document.id, document_version_id=version.id,
                source_key=document.source_key, source_name=document.source_name,
                chunk_set_id=chunk_set.id, embedding_set_id=embedding_set.id,
                embedding_configuration_id=embedding_set.embedding_configuration_id,
                chunk_id=chunk.id, chunk_ordinal=chunk.ordinal,
                heading_path=tuple(chunk.heading_path), start_line=chunk.start_line,
                end_line=chunk.end_line, content=chunk.content,
                content_checksum=chunk.content_checksum, token_count=chunk.token_count,
                cosine_distance=None, similarity=None,
                fts_contribution={"branch_rank": index, "native_rank": float(raw_rank)},
                page_start=chunk.page_start, page_end=chunk.page_end,
                start_offset=chunk.start_offset, end_offset=chunk.end_offset,
            )
            for index, (
                document,
                version,
                chunk_set,
                embedding_set,
                chunk,
                raw_rank,
            ) in enumerate(rows, start=1)
        )

    @staticmethod
    def _fuse(
        vector: tuple[RetrievalCandidate, ...], fts: tuple[RetrievalCandidate, ...]
    ) -> tuple[RetrievalCandidate, ...]:
        by_chunk: dict[str, RetrievalCandidate] = {
            candidate.chunk_id: candidate for candidate in vector
        }
        for candidate in fts:
            existing = by_chunk.get(candidate.chunk_id)
            if existing is None:
                by_chunk[candidate.chunk_id] = candidate
            else:
                by_chunk[candidate.chunk_id] = replace(
                    existing, fts_contribution=candidate.fts_contribution
                )
        fused = []
        for candidate in by_chunk.values():
            score = sum(
                1 / (60 + contribution["branch_rank"])
                for contribution in (candidate.vector_contribution, candidate.fts_contribution)
                if contribution is not None
            )
            fused.append(replace(candidate, fusion_score=score))
        return tuple(
            sorted(fused, key=lambda candidate: (-candidate.fusion_score, candidate.chunk_id))
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
                    fusion_policy_version=trace.fusion_policy_version,
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
