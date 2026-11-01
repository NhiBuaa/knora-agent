from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkingConfigurationTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IngestionJobTable,
    LexicalGenerationTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestionResult
from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration, LexicalProfile
from knora.ingestion.store import DocumentHead, IngestionStore, PreparedDerivation

if TYPE_CHECKING:
    from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
    from knora.ingestion.lexical_population import VerifiedLexicalPopulation


class PostgresIngestionStore(IngestionStore):
    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        search_index_store: PostgresSearchIndexStore | None = None,
        lexical_population: VerifiedLexicalPopulation | None = None,
        lexical_profile: LexicalProfile | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._search_index_store = search_index_store
        self._lexical_population = lexical_population
        self._lexical_profile = lexical_profile

    def read_document_head(self, *, workspace_id: str, source_key: str) -> DocumentHead | None:
        with self._session_factory() as session:
            document = session.scalar(
                select(DocumentTable).where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.source_key == source_key,
                )
            )
            if document is None:
                return None
            return DocumentHead(
                document_id=document.id,
                revision=document.revision,
                active_embedding_set_id=document.active_embedding_set_id,
            )

    def authorize_workspace(self, *, workspace_id: str) -> None:
        with self._session_factory() as session:
            if session.get(WorkspaceTable, workspace_id) is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")

    def commit_derivation(
        self, *, prepared: PreparedDerivation, expected_revision: int
    ) -> IngestionResult:
        try:
            with self._session_factory.begin() as session:
                workspace = session.get(WorkspaceTable, prepared.workspace_id)
                if workspace is None:
                    raise KnoraError("WORKSPACE_ACCESS_DENIED")
                document = session.scalar(
                    select(DocumentTable)
                    .where(
                        DocumentTable.workspace_id == prepared.workspace_id,
                        DocumentTable.source_key == prepared.source_key,
                    )
                    .with_for_update()
                )
                if document is None:
                    document = DocumentTable(
                        id=str(uuid4()),
                        workspace_id=prepared.workspace_id,
                        source_key=prepared.source_key,
                        source_name=prepared.source_name,
                        revision=0,
                    )
                    session.add(document)
                    session.flush()
                elif document.revision != expected_revision:
                    raise KnoraError("DOCUMENT_CONCURRENTLY_UPDATED")

                chunking = self._get_or_create_chunking(session, prepared)
                embedding_config = self._get_or_create_embedding_config(session, prepared)
                version = session.scalar(
                    select(DocumentVersionTable).where(
                        DocumentVersionTable.document_id == document.id,
                        DocumentVersionTable.normalized_content_checksum
                        == prepared.processed.normalized_content_checksum,
                    )
                )
                created = False
                if version is None:
                    next_version_number = session.scalar(
                        select(
                            func.coalesce(func.max(DocumentVersionTable.version_number), 0) + 1
                        ).where(DocumentVersionTable.document_id == document.id)
                    )
                    version = DocumentVersionTable(
                        id=str(uuid4()),
                        document_id=document.id,
                        normalized_content=prepared.processed.normalized_content,
                        normalized_content_checksum=prepared.processed.normalized_content_checksum,
                        media_type=None,
                        version_number=next_version_number,
                    )
                    session.add(version)
                    session.flush()
                    created = True

                chunk_set = session.scalar(
                    select(ChunkSetTable).where(
                        ChunkSetTable.document_version_id == version.id,
                        ChunkSetTable.chunking_configuration_id == chunking.id,
                    )
                )
                if chunk_set is None:
                    chunk_set = ChunkSetTable(
                        id=str(uuid4()),
                        document_version_id=version.id,
                        chunking_configuration_id=chunking.id,
                        status="completed",
                    )
                    session.add(chunk_set)
                    session.flush()
                    for chunk in prepared.processed.chunks:
                        session.add(
                            ChunkTable(
                                id=str(uuid4()),
                                chunk_set_id=chunk_set.id,
                                ordinal=chunk.ordinal,
                                heading_path=list(chunk.heading_path),
                                start_line=chunk.start_line,
                                end_line=chunk.end_line,
                                content=chunk.content,
                                content_checksum=chunk.content_checksum,
                                token_count=chunk.token_count,
                            )
                        )
                    created = True

                embedding_set = session.scalar(
                    select(EmbeddingSetTable).where(
                        EmbeddingSetTable.chunk_set_id == chunk_set.id,
                        EmbeddingSetTable.embedding_configuration_id == embedding_config.id,
                    )
                )
                if embedding_set is None:
                    embedding_set = EmbeddingSetTable(
                        id=str(uuid4()),
                        chunk_set_id=chunk_set.id,
                        embedding_configuration_id=embedding_config.id,
                        status="completed",
                    )
                    session.add(embedding_set)
                    session.flush()
                    chunks = session.scalars(
                        select(ChunkTable)
                        .where(ChunkTable.chunk_set_id == chunk_set.id)
                        .order_by(ChunkTable.ordinal)
                    ).all()
                    for chunk, vector in zip(chunks, prepared.embedding_batch.vectors, strict=True):
                        session.add(
                            ChunkEmbeddingTable(
                                id=str(uuid4()),
                                embedding_set_id=embedding_set.id,
                                chunk_id=chunk.id,
                                embedding=list(vector),
                            )
                        )
                    created = True

                activation_changed = document.active_embedding_set_id != embedding_set.id
                updated = session.execute(
                    update(DocumentTable)
                    .where(
                        DocumentTable.id == document.id,
                        DocumentTable.revision == expected_revision,
                    )
                    .values(
                        active_embedding_set_id=embedding_set.id,
                        active_embedding_configuration_id=embedding_config.id,
                        current_document_version_id=version.id,
                        revision=DocumentTable.revision + 1,
                    )
                )
                if updated.rowcount != 1:
                    raise KnoraError("DOCUMENT_CONCURRENTLY_UPDATED")

                profile = self._lexical_profile or (
                    self._lexical_population.profile
                    if self._lexical_population is not None
                    else None
                )
                if self._search_index_store is not None and profile is not None:
                    source_object = session.scalar(
                        select(OriginalSourceObjectTable).where(
                            OriginalSourceObjectTable.document_version_id == version.id
                        )
                    )
                    if source_object is None:
                        source_object = OriginalSourceObjectTable(
                            id=str(uuid4()),
                            workspace_id=prepared.workspace_id,
                            document_version_id=version.id,
                            object_key=f"{prepared.workspace_id}/text/{version.id}",
                            raw_sha256=prepared.processed.normalized_content_checksum,
                            byte_size=len(prepared.processed.normalized_content.encode("utf-8")),
                            media_type=prepared.media_type or "text/plain",
                        )
                        session.add(source_object)
                        session.flush()

                    parent_fingerprint = (
                        f"text-dense-parent-v1\n"
                        f"{prepared.workspace_id}\n"
                        f"{version.id}\n"
                        f"{embedding_config.id}"
                    )
                    parent_job = session.scalar(
                        select(IngestionJobTable).where(
                            IngestionJobTable.workspace_id == prepared.workspace_id,
                            IngestionJobTable.target_document_version_id == version.id,
                            IngestionJobTable.derivation_kind == "dense",
                            IngestionJobTable.parent_ingestion_job_id.is_(None),
                        )
                    )
                    database_now = session.scalar(select(func.now()))
                    if parent_job is None:
                        parent_job = IngestionJobTable(
                            id=str(uuid4()),
                            workspace_id=prepared.workspace_id,
                            operation="ingest_document",
                            document_id=document.id,
                            target_document_version_id=version.id,
                            source_object_id=source_object.id,
                            content_fingerprint=parent_fingerprint,
                            parser_configuration_id="text-parser-m1",
                            normalizer_configuration_id="text-normalizer-m1",
                            chunking_configuration_id=chunking.id,
                            derivation_kind="dense",
                            embedding_configuration_id=embedding_config.id,
                            source_revision=None,
                            workspace_revision=None,
                            status="succeeded",
                            attempt_count=1,
                            max_attempts=4,
                            created_at=database_now,
                            updated_at=database_now,
                            started_at=database_now,
                            terminal_at=database_now,
                            terminal_outcome_code="succeeded",
                        )
                        session.add(parent_job)
                        session.flush()

                    existing_gen = session.scalar(
                        select(LexicalGenerationTable).where(
                            LexicalGenerationTable.document_id == document.id,
                            LexicalGenerationTable.document_version_id == version.id,
                            LexicalGenerationTable.profile_digest == profile.digest(),
                            LexicalGenerationTable.status.in_(("requested", "active")),
                        )
                    )
                    if existing_gen is None:
                        generation_id = str(
                            uuid5(
                                NAMESPACE_URL,
                                f"knora-text-lexical-{version.id}-{profile.digest()}",
                            )
                        )
                        chunks = session.scalars(
                            select(ChunkTable)
                            .where(ChunkTable.chunk_set_id == chunk_set.id)
                            .order_by(ChunkTable.ordinal)
                        ).all()
                        lexical_chunks = tuple(
                            LexicalChunk(c.id, c.ordinal, c.content_checksum) for c in chunks
                        )
                        generation = LexicalGeneration(
                            generation_id=generation_id,
                            workspace_id=prepared.workspace_id,
                            document_id=document.id,
                            document_version_id=version.id,
                            chunk_set_id=chunk_set.id,
                            lexical_profile=profile,
                            revision=expected_revision + 1,
                            chunks=lexical_chunks,
                        )
                        self._search_index_store.request_generation_in_transaction(
                            session, generation, expected_revision=expected_revision
                        )

                        child_job = session.scalar(
                            select(IngestionJobTable).where(
                                IngestionJobTable.parent_ingestion_job_id == parent_job.id,
                                IngestionJobTable.derivation_kind == "lexical_index",
                            )
                        )
                        if child_job is None:
                            child_fingerprint = (
                                f"lexical_index-v1\n{generation.generation_id}\n"
                                f"{generation.content_digest()}\n{profile.digest()}"
                            )
                            child_job = IngestionJobTable(
                                id=str(uuid4()),
                                workspace_id=prepared.workspace_id,
                                operation="ingest_document",
                                document_id=document.id,
                                target_document_version_id=version.id,
                                source_object_id=source_object.id,
                                content_fingerprint=child_fingerprint,
                                parser_configuration_id="text-parser-m1",
                                normalizer_configuration_id="text-normalizer-m1",
                                chunking_configuration_id=chunking.id,
                                derivation_kind="lexical_index",
                                embedding_configuration_id=None,
                                lexical_profile=None,
                                lexical_generation_id=generation.generation_id,
                                parent_ingestion_job_id=parent_job.id,
                                source_revision=expected_revision + 1,
                                workspace_revision=workspace.revision,
                                status="queued",
                                attempt_count=0,
                                max_attempts=4,
                                created_at=database_now,
                                updated_at=database_now,
                            )
                            session.add(child_job)
                            session.flush()

                return IngestionResult(
                    outcome="created" if created else "reused",
                    activation_changed=activation_changed,
                    document_id=document.id,
                    document_version_id=version.id,
                    chunk_set_id=chunk_set.id,
                    embedding_set_id=embedding_set.id,
                    chunking_configuration_id=chunking.id,
                    embedding_configuration_id=embedding_config.id,
                    chunk_count=len(prepared.processed.chunks),
                    document_archived=bool(document.archived),
                )
        except IntegrityError as error:
            if "documents_workspace_id_source_key" in str(error.orig):
                raise KnoraError("DOCUMENT_CONCURRENTLY_UPDATED") from error
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None
        except SQLAlchemyError:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from None

    @staticmethod
    def _get_or_create_chunking(session, prepared: PreparedDerivation):
        config = prepared.chunking_configuration
        row = session.get(ChunkingConfigurationTable, config.id)
        if row is None:
            row = ChunkingConfigurationTable(
                id=config.id,
                parser_version=config.parser_version,
                chunker_version=config.chunker_version,
                tokenizer_name=config.tokenizer_name,
                tokenizer_version=config.tokenizer_version,
                target_tokens=config.target_tokens,
                overlap_tokens=config.overlap_tokens,
                max_tokens=config.max_tokens,
            )
            session.add(row)
            session.flush()
        elif (
            row.parser_version != config.parser_version
            or row.chunker_version != config.chunker_version
            or row.tokenizer_name != config.tokenizer_name
            or row.tokenizer_version != config.tokenizer_version
            or row.target_tokens != config.target_tokens
            or row.overlap_tokens != config.overlap_tokens
            or row.max_tokens != config.max_tokens
        ):
            raise KnoraError("CHUNKING_CONFIGURATION_IMMUTABLE")
        return row

    @staticmethod
    def _get_or_create_embedding_config(session, prepared: PreparedDerivation):
        config = prepared.embedding_configuration
        row = session.get(EmbeddingConfigurationTable, config.id)
        if row is None:
            row = EmbeddingConfigurationTable(
                id=config.id,
                provider=config.provider,
                model=config.model,
                dimensions=config.dimensions,
                distance_metric=config.distance_metric,
                deployment_identity=config.deployment_identity,
                api_contract_version=config.api_contract_version,
                input_normalization=config.input_normalization,
                input_policy_id=config.input_policy_id,
                output_dimensionality=config.output_dimensionality,
                vector_normalization=config.vector_normalization,
            )
            session.add(row)
            session.flush()
        elif (
            row.provider != config.provider
            or row.model != config.model
            or row.dimensions != config.dimensions
            or row.distance_metric != config.distance_metric
            or row.deployment_identity != config.deployment_identity
            or row.api_contract_version != config.api_contract_version
            or row.input_normalization != config.input_normalization
            or row.input_policy_id != config.input_policy_id
            or row.output_dimensionality != config.output_dimensionality
            or row.vector_normalization != config.vector_normalization
        ):
            raise KnoraError("EMBEDDING_CONFIGURATION_IMMUTABLE")
        return row
