from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    QuestionTraceTable,
    RetrievalV2CutoverTable,
)
from knora.answering.retrieval_v2 import normalize_fts_m3_or_v2_details
from knora.answering.stores import (
    AnsweringStore,
    BranchObservation,
    QuestionTraceRecord,
    RetrievalCandidate,
    RetrievalConfiguration,
    RetrievalResult,
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
    ) -> RetrievalResult:
        if retrieval_configuration.id in {
            "retrieval-m3-vector-v2",
            "retrieval-m3-rrf-v2",
        }:
            self._require_v2_cutover(
                workspace_id=workspace_id,
                embedding_configuration_id=embedding_configuration.id,
            )
        with self._session_factory() as session:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            if retrieval_configuration.strategy == "vector-only":
                embedding_set_ids, chunk_set_ids = self._active_provenance(
                    workspace_id=workspace_id,
                    embedding_configuration=embedding_configuration,
                    session=session,
                )
                vector = self._vector_candidates(
                    workspace_id=workspace_id,
                    query_vector=query_vector,
                    embedding_configuration=embedding_configuration,
                    retrieval_configuration=retrieval_configuration,
                    session=session,
                )
                return RetrievalResult(
                    candidates=vector,
                    branch_observations=self._vector_observations(
                        workspace_id=workspace_id,
                        query_vector=query_vector,
                        embedding_configuration=embedding_configuration,
                        retrieval_configuration=retrieval_configuration,
                        eligible=vector,
                        session=session,
                    ),
                    embedding_set_ids=embedding_set_ids,
                    chunk_set_ids=chunk_set_ids,
                )
            if retrieval_configuration.strategy != "hybrid":
                raise ValueError("unsupported retrieval strategy")
            fusion_policy = (
                retrieval_configuration.fusion_policy_id
                or retrieval_configuration.fusion_policy_version
            )
            lexical_policy = (
                retrieval_configuration.lexical_policy_id
                or retrieval_configuration.fts_policy_version
            )
            if fusion_policy not in {"rrf-v1", "rrf-v2"}:
                raise ValueError("unsupported fusion policy")
            if lexical_policy not in {"fts-v1", "fts-m3-or-v2"}:
                raise ValueError("unsupported FTS policy")
            vector = self._vector_candidates(
                workspace_id=workspace_id,
                query_vector=query_vector,
                embedding_configuration=embedding_configuration,
                retrieval_configuration=retrieval_configuration,
                session=session,
            )
            fts = self._fts_candidates(
                workspace_id=workspace_id,
                query_text=query_text,
                embedding_configuration=embedding_configuration,
                retrieval_configuration=retrieval_configuration,
                session=session,
            )
            embedding_set_ids, chunk_set_ids = self._active_provenance(
                workspace_id=workspace_id,
                embedding_configuration=embedding_configuration,
                session=session,
            )
            return RetrievalResult(
                candidates=self._fuse(vector, fts, policy=fusion_policy),
                branch_observations=self._hybrid_observations(
                    vector=vector,
                    fts=fts,
                    query_text=query_text,
                    lexical_policy=lexical_policy,
                    workspace_id=workspace_id,
                    query_vector=query_vector,
                    embedding_configuration=embedding_configuration,
                    retrieval_configuration=retrieval_configuration,
                    session=session,
                ),
                embedding_set_ids=embedding_set_ids,
                chunk_set_ids=chunk_set_ids,
            )

    @contextmanager
    def _session_scope(self, session: Session | None):
        if session is not None:
            yield session
            return
        with self._session_factory() as local_session:
            local_session.connection(
                execution_options={"isolation_level": "REPEATABLE READ"}
            )
            yield local_session

    def _active_provenance(
        self,
        *,
        workspace_id: str,
        embedding_configuration: EmbeddingConfiguration,
        session: Session | None = None,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        statement = (
            select(EmbeddingSetTable.id, EmbeddingSetTable.chunk_set_id)
            .join(DocumentTable, DocumentTable.active_embedding_set_id == EmbeddingSetTable.id)
            .where(
                DocumentTable.workspace_id == workspace_id,
                EmbeddingSetTable.embedding_configuration_id == embedding_configuration.id,
                EmbeddingSetTable.status == "completed",
            )
            .distinct()
            .order_by(EmbeddingSetTable.id.asc(), EmbeddingSetTable.chunk_set_id.asc())
        )
        with self._session_scope(session) as active_session:
            rows = active_session.execute(statement).all()
        return (
            tuple(str(embedding_set_id) for embedding_set_id, _ in rows),
            tuple(str(chunk_set_id) for _, chunk_set_id in rows),
        )

    def _vector_candidates(
        self,
        *,
        workspace_id: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
        session: Session | None = None,
    ) -> tuple[RetrievalCandidate, ...]:
        rows = self._vector_rows(
            workspace_id=workspace_id,
            query_vector=query_vector,
            embedding_configuration=embedding_configuration,
            retrieval_configuration=retrieval_configuration,
            eligible=True,
            session=session,
        )
        return tuple(
            self._vector_candidate_from_row(row, index=index)
            for index, row in enumerate(rows, start=1)
        )

    def _vector_rows(
        self,
        *,
        workspace_id: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
        eligible: bool,
        session: Session | None = None,
    ) -> list[tuple]:
        distance = ChunkEmbeddingTable.embedding.cosine_distance(list(query_vector)).label(
            "cosine_distance"
        )
        eligibility = (
            distance <= 1.0 - retrieval_configuration.min_similarity
            if eligible
            else distance > 1.0 - retrieval_configuration.min_similarity
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
                eligibility,
            )
            .order_by(
                distance.asc(),
                DocumentTable.id.asc(),
                ChunkTable.ordinal.asc(),
                ChunkTable.id.asc(),
            )
            .limit(
                retrieval_configuration.vector_candidate_k
                or retrieval_configuration.candidate_k
            )
        )
        with self._session_scope(session) as active_session:
            return list(active_session.execute(statement).all())

    @staticmethod
    def _vector_candidate_from_row(row: tuple, *, index: int) -> RetrievalCandidate:
        document, version, chunk_set, embedding_set, chunk, raw_distance = row
        return RetrievalCandidate(
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

    def _vector_observations(
        self,
        *,
        workspace_id: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
        eligible: tuple[RetrievalCandidate, ...],
        session: Session | None = None,
    ) -> tuple[BranchObservation, ...]:
        observations = [
            BranchObservation(
                branch="vector",
                status="ELIGIBLE",
                chunk_id=candidate.chunk_id,
                branch_rank=(candidate.vector_contribution or {}).get("branch_rank"),
                cosine_distance=candidate.cosine_distance,
                similarity=candidate.similarity,
            )
            for candidate in eligible
        ]
        below_rows = self._vector_rows(
            workspace_id=workspace_id,
            query_vector=query_vector,
            embedding_configuration=embedding_configuration,
            retrieval_configuration=retrieval_configuration,
            eligible=False,
            session=session,
        )
        observations.extend(
            BranchObservation(
                branch="vector",
                status="BELOW_THRESHOLD",
                chunk_id=chunk.id,
                branch_rank=None,
                cosine_distance=float(raw_distance),
                similarity=1.0 - float(raw_distance),
            )
            for _, _, _, _, chunk, raw_distance in below_rows
        )
        if not observations:
            observations.append(BranchObservation(branch="vector", status="NO_CONTRIBUTION"))
        return tuple(observations)

    def _fts_candidates(
        self,
        *,
        workspace_id: str,
        query_text: str,
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
        session: Session | None = None,
    ) -> tuple[RetrievalCandidate, ...]:
        lexical_policy = (
            retrieval_configuration.lexical_policy_id
            or retrieval_configuration.fts_policy_version
        )
        query = self._fts_query(query_text=query_text, lexical_policy=lexical_policy)
        if query is None:
            return ()
        rank = func.ts_rank_cd(ChunkTable.search_vector, query, 0).label("native_rank")
        order = (
            (
                rank.desc(),
                DocumentTable.source_key.asc(),
                ChunkTable.ordinal.asc(),
                ChunkTable.id.asc(),
            )
            if lexical_policy == "fts-m3-or-v2"
            else (rank.desc(), ChunkTable.id.asc())
        )
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
            .order_by(*order)
            .limit(
                retrieval_configuration.fts_candidate_k
                or retrieval_configuration.candidate_k
            )
        )
        with self._session_scope(session) as active_session:
            rows = active_session.execute(statement).all()
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
    def _fts_query(*, query_text: str, lexical_policy: str):
        if lexical_policy == "fts-m3-or-v2":
            lexemes = normalize_fts_m3_or_v2_details(query_text).normalized_lexemes
            if not lexemes:
                return None
            return func.to_tsquery("simple", " | ".join(lexemes))
        return func.plainto_tsquery("simple", query_text)

    def _fts_eligible_chunk_ids(
        self,
        *,
        workspace_id: str,
        query_text: str,
        chunk_ids: set[str],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
        session: Session | None = None,
    ) -> set[str]:
        if not chunk_ids:
            return set()
        lexical_policy = (
            retrieval_configuration.lexical_policy_id
            or retrieval_configuration.fts_policy_version
        )
        query = self._fts_query(query_text=query_text, lexical_policy=lexical_policy)
        if query is None:
            return set()
        statement = (
            select(ChunkTable.id)
            .join(ChunkSetTable, ChunkSetTable.id == ChunkTable.chunk_set_id)
            .join(
                DocumentVersionTable,
                DocumentVersionTable.id == ChunkSetTable.document_version_id,
            )
            .join(DocumentTable, DocumentTable.id == DocumentVersionTable.document_id)
            .join(EmbeddingSetTable, EmbeddingSetTable.id == DocumentTable.active_embedding_set_id)
            .where(
                ChunkTable.id.in_(chunk_ids),
                DocumentTable.workspace_id == workspace_id,
                EmbeddingSetTable.chunk_set_id == ChunkSetTable.id,
                EmbeddingSetTable.embedding_configuration_id == embedding_configuration.id,
                EmbeddingSetTable.status == "completed",
                ChunkTable.search_vector.op("@@")(query),
            )
        )
        with self._session_scope(session) as active_session:
            return {str(chunk_id) for chunk_id in active_session.scalars(statement)}

    @staticmethod
    def _fuse(
        vector: tuple[RetrievalCandidate, ...],
        fts: tuple[RetrievalCandidate, ...],
        *,
        policy: str = "rrf-v1",
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
        if policy == "rrf-v2":
            key = lambda candidate: (  # noqa: E731
                -candidate.fusion_score,
                candidate.source_key,
                candidate.chunk_ordinal,
                candidate.chunk_id,
            )
        else:
            key = lambda candidate: (-candidate.fusion_score, candidate.chunk_id)  # noqa: E731
        return tuple(sorted(fused, key=key))

    def _hybrid_observations(
        self,
        *,
        vector: tuple[RetrievalCandidate, ...],
        fts: tuple[RetrievalCandidate, ...],
        query_text: str,
        lexical_policy: str,
        workspace_id: str,
        query_vector: tuple[float, ...],
        embedding_configuration: EmbeddingConfiguration,
        retrieval_configuration: RetrievalConfiguration,
        session: Session | None = None,
    ) -> tuple[BranchObservation, ...]:
        if lexical_policy == "fts-m3-or-v2":
            lexical = normalize_fts_m3_or_v2_details(query_text)
        else:
            lexical = None
        lexical_policy_id = lexical_policy
        normalized = lexical.normalized_lexemes if lexical else ()
        omitted = lexical.omitted_lexemes if lexical else ()
        observations = list(
            self._vector_observations(
                workspace_id=workspace_id,
                query_vector=query_vector,
                embedding_configuration=embedding_configuration,
                retrieval_configuration=retrieval_configuration,
                eligible=vector,
                session=session,
            )
        )

        vector_ids = {candidate.chunk_id for candidate in vector}
        fts_ids = {candidate.chunk_id for candidate in fts}
        below_threshold_ids = {
            observation.chunk_id
            for observation in observations
            if observation.branch == "vector"
            and observation.status == "BELOW_THRESHOLD"
            and observation.chunk_id is not None
        }
        observations.extend(
            BranchObservation(
                branch="fts",
                status="ELIGIBLE",
                chunk_id=candidate.chunk_id,
                branch_rank=(candidate.fts_contribution or {}).get("branch_rank"),
                native_rank=(candidate.fts_contribution or {}).get("native_rank"),
                lexical_policy_id=lexical_policy_id,
                normalized_lexemes=normalized,
                omitted_lexemes=omitted,
            )
            for candidate in fts
        )
        missing_fts_ids = (vector_ids | below_threshold_ids) - fts_ids
        if missing_fts_ids:
            fts_eligible_ids = (
                set()
                if lexical is not None and not normalized
                else self._fts_eligible_chunk_ids(
                    workspace_id=workspace_id,
                    query_text=query_text,
                    chunk_ids=missing_fts_ids,
                    embedding_configuration=embedding_configuration,
                    retrieval_configuration=retrieval_configuration,
                    session=session,
                )
            )
            observations.extend(
                BranchObservation(
                    branch="fts",
                    status=(
                        "NO_CONTRIBUTION"
                        if chunk_id in fts_eligible_ids
                        else "INELIGIBLE"
                    ),
                    chunk_id=chunk_id,
                    lexical_policy_id=lexical_policy_id,
                    normalized_lexemes=normalized,
                    omitted_lexemes=omitted,
                )
                for chunk_id in sorted(missing_fts_ids)
            )
        missing_vector_ids = fts_ids - vector_ids - below_threshold_ids
        observations.extend(
            BranchObservation(
                branch="vector",
                status="NO_CONTRIBUTION",
                chunk_id=chunk_id,
            )
            for chunk_id in sorted(missing_vector_ids)
        )
        if lexical is not None and not normalized:
            observations.append(
                BranchObservation(
                    branch="fts",
                    status="INELIGIBLE",
                    lexical_policy_id=lexical_policy_id,
                    normalized_lexemes=normalized,
                    omitted_lexemes=omitted,
                )
            )
        if not any(observation.branch == "fts" for observation in observations):
            observations.append(
                BranchObservation(
                    branch="fts",
                    status=(
                        "INELIGIBLE"
                        if lexical is not None and normalized
                        else "NO_CONTRIBUTION"
                    ),
                    lexical_policy_id=lexical_policy_id,
                    normalized_lexemes=normalized,
                    omitted_lexemes=omitted,
                )
            )
        unique: dict[tuple[str, str | None], BranchObservation] = {}
        for observation in observations:
            key = (observation.branch, observation.chunk_id)
            existing = unique.get(key)
            if existing is not None:
                if existing != observation:
                    raise ValueError("contradictory branch observations")
                continue
            unique[key] = observation
        return tuple(unique.values())

    def _require_v2_cutover(
        self, *, workspace_id: str, embedding_configuration_id: str
    ) -> None:
        with self._session_factory() as session:
            cutover = session.get(
                RetrievalV2CutoverTable,
                (workspace_id, embedding_configuration_id),
            )
        if cutover is None or cutover.status != "completed":
            raise ValueError("retrieval v2 production cutover is incomplete")

    def persist_trace(self, trace: QuestionTraceRecord) -> str:
        trace_id = str(uuid4())
        with self._session_factory.begin() as session:
            session.add(
                QuestionTraceTable(
                    id=trace_id,
                    workspace_id=trace.workspace_id,
                    question=trace.question,
                    trace_schema_version=trace.trace_schema_version,
                    branch_observation_schema_version=trace.branch_observation_schema_version,
                    retrieval_configuration_id=trace.retrieval_configuration_id,
                    fusion_policy_version=trace.fusion_policy_version,
                    embedding_configuration_id=trace.embedding_configuration_id,
                    embedding_set_ids=list(trace.embedding_set_ids),
                    chunk_set_ids=list(trace.chunk_set_ids),
                    retrieved_chunk_ids=list(trace.retrieved_chunk_ids),
                    candidate_decisions=list(trace.candidate_decisions),
                    branch_observations=list(trace.branch_observations),
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
