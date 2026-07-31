from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
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
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestionResult
from knora.ingestion.store import DocumentHead, IngestionStore, PreparedDerivation


class PostgresIngestionStore(IngestionStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

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
                    select(DocumentTable).where(
                        DocumentTable.workspace_id == prepared.workspace_id,
                        DocumentTable.source_key == prepared.source_key,
                    )
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
                    version = DocumentVersionTable(
                        id=str(uuid4()),
                        document_id=document.id,
                        normalized_content=prepared.processed.normalized_content,
                        normalized_content_checksum=prepared.processed.normalized_content_checksum,
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
                        revision=DocumentTable.revision + 1,
                    )
                )
                if updated.rowcount != 1:
                    raise KnoraError("DOCUMENT_CONCURRENTLY_UPDATED")

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
                )
        except IntegrityError as error:
            if "documents_workspace_id_source_key" in str(error.orig):
                raise KnoraError("DOCUMENT_CONCURRENTLY_UPDATED") from error
            raise

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
            )
            session.add(row)
            session.flush()
        elif (
            row.provider != config.provider
            or row.model != config.model
            or row.dimensions != config.dimensions
            or row.distance_metric != config.distance_metric
        ):
            raise KnoraError("EMBEDDING_CONFIGURATION_IMMUTABLE")
        return row
