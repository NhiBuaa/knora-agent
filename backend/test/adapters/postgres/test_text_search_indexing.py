from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.job_processing import (
    Cancellation,
    IngestionWork,
    WorkSucceeded,
)
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.ingestion.search_indexing import (
    LexicalIndexHandler,
    LexicalProfile,
    StageReceipt,
)
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration

SAMPLE_PROFILE = LexicalProfile(
    id="lexical-bm25-v1",
    tokenizer="tiktoken",
    tokenizer_version="cl100k_base",
    k1=1.2,
    b=0.75,
    avg_len=256.0,
    statistics_digest="0" * 64,
)


def test_text_ingestion_creates_atomic_dense_parent_and_lexical_child() -> None:
    workspace_id = f"test-atomic-ingest-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Test Atomic Ingest"))

    search_store = PostgresSearchIndexStore(SessionFactory)
    ingestion_store = PostgresIngestionStore(
        SessionFactory,
        search_index_store=search_store,
        lexical_profile=SAMPLE_PROFILE,
    )
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=ingestion_store,
    )
    content = b"# Document Title\n\nFirst line of text.\nSecond line of text.\n"
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key="notes/atomic-doc",
        source_name="atomic-doc.md",
        media_type="text/markdown",
        raw_content=content,
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")

    result = use_case.execute(command, principal)
    assert result.outcome == "created"

    with SessionFactory() as session:
        # Verify OriginalSourceObjectTable created
        source_object = session.scalar(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.document_version_id == result.document_version_id
            )
        )
        assert source_object is not None
        assert source_object.media_type == "text/markdown"

        # Verify parent dense job created and succeeded
        parent_job = session.scalar(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.target_document_version_id == result.document_version_id,
                IngestionJobTable.derivation_kind == "dense",
            )
        )
        assert parent_job is not None
        assert parent_job.status == "succeeded"
        assert parent_job.parent_ingestion_job_id is None

        # Verify lexical generation requested
        head = session.get(LexicalHeadTable, result.document_id)
        assert head is not None
        assert head.revision == 1
        assert head.desired_generation_id is not None

        gen = session.get(LexicalGenerationTable, head.desired_generation_id)
        assert gen is not None
        assert gen.status == "requested"
        assert gen.document_version_id == result.document_version_id

        # Verify child lexical_index job created
        child_job = session.scalar(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.parent_ingestion_job_id == parent_job.id,
                IngestionJobTable.derivation_kind == "lexical_index",
            )
        )
        assert child_job is not None
        assert child_job.status == "queued"
        assert child_job.lexical_generation_id == gen.id


def test_text_ingestion_reingest_same_checksum_is_idempotent() -> None:
    workspace_id = f"test-reingest-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Test Reingest"))

    search_store = PostgresSearchIndexStore(SessionFactory)
    ingestion_store = PostgresIngestionStore(
        SessionFactory,
        search_index_store=search_store,
        lexical_profile=SAMPLE_PROFILE,
    )
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=ingestion_store,
    )
    content = b"# Reingest Test\n\nContent that will be ingested twice.\n"
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key="notes/reingest-doc",
        source_name="reingest-doc.md",
        media_type="text/markdown",
        raw_content=content,
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")

    created = use_case.execute(command, principal)
    reused = use_case.execute(command, principal)

    assert created.outcome == "created"
    assert reused.outcome == "reused"

    with SessionFactory() as session:
        child_jobs = session.scalars(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.derivation_kind == "lexical_index",
            )
        ).all()
        # Exactly 1 child job enqueued, no duplicate
        assert len(child_jobs) == 1


def test_text_chunks_retain_line_locators() -> None:
    workspace_id = f"test-locators-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Test Locators"))

    search_store = PostgresSearchIndexStore(SessionFactory)
    ingestion_store = PostgresIngestionStore(
        SessionFactory,
        search_index_store=search_store,
        lexical_profile=SAMPLE_PROFILE,
    )
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=ingestion_store,
    )
    content = b"# Section 1\nLine 1\nLine 2\n\n# Section 2\nLine 5\nLine 6\n"
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key="notes/locators-doc",
        source_name="locators-doc.md",
        media_type="text/markdown",
        raw_content=content,
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    result = use_case.execute(command, principal)

    with SessionFactory() as session:
        chunks = session.scalars(
            select(ChunkTable)
            .where(ChunkTable.chunk_set_id == result.chunk_set_id)
            .order_by(ChunkTable.ordinal)
        ).all()
        assert len(chunks) > 0
        for chunk in chunks:
            # Preserves line locators as required by Milestone 1 contract
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line


def test_worker_can_load_and_stage_text_lexical_generation() -> None:
    workspace_id = f"test-stage-text-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Test Stage Text"))

    search_store = PostgresSearchIndexStore(SessionFactory)
    ingestion_store = PostgresIngestionStore(
        SessionFactory,
        search_index_store=search_store,
        lexical_profile=SAMPLE_PROFILE,
    )
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=ingestion_store,
    )
    content = b"# Staging Test\nThis text document will be staged by LexicalIndexHandler.\n"
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key="notes/stage-doc",
        source_name="stage-doc.md",
        media_type="text/markdown",
        raw_content=content,
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    use_case.execute(command, principal)

    with SessionFactory() as session:
        child_job = session.scalar(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.derivation_kind == "lexical_index",
            )
        )
        assert child_job is not None
        source = session.get(OriginalSourceObjectTable, child_job.source_object_id)
        assert source is not None
        work = IngestionWork(
            workspace_id=child_job.workspace_id,
            document_id=child_job.document_id,
            document_version_id=child_job.target_document_version_id,
            source_object_id=child_job.source_object_id,
            source_object_key=source.object_key,
            source_media_type=source.media_type,
            source_sha256=source.raw_sha256,
            source_byte_size=source.byte_size,
            parser_configuration_id=child_job.parser_configuration_id,
            normalizer_configuration_id=child_job.normalizer_configuration_id,
            chunking_configuration_id=child_job.chunking_configuration_id,
            embedding_configuration_id=child_job.embedding_configuration_id,
            derivation_kind=child_job.derivation_kind,
            lexical_generation_id=child_job.lexical_generation_id,
            source_revision=child_job.source_revision,
            workspace_revision=child_job.workspace_revision,
            ingestion_job_id=child_job.id,
        )

    # Verify search_store.load_generation succeeds on this text document
    loaded_input = search_store.load_generation(work)
    assert len(loaded_input.generation.chunks) == 1
    assert len(loaded_input.chunk_texts) == 1

    # Mock index port to test LexicalIndexHandler execution
    staged_payloads = []

    class MockIndexPort:
        def stage_generation(self, gen, texts, chunk_vectors=None):
            staged_payloads.append((gen, texts, chunk_vectors))
            return StageReceipt(
                generation_id=gen.generation_id,
                point_count=len(gen.chunks),
                content_digest=gen.content_digest(),
            )

    handler = LexicalIndexHandler(
        store=search_store,
        index=MockIndexPort(),
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
    )
    cancellation = Cancellation()
    outcome = handler.execute(work, cancellation)

    assert isinstance(outcome, WorkSucceeded)
    assert outcome.payload.generation.generation_id == loaded_input.generation.generation_id
    assert len(staged_payloads) == 1


def test_text_ingestion_transaction_rollback_leaves_no_orphans() -> None:
    workspace_id = f"test-rollback-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Test Rollback"))

    class FaultySearchIndexStore:
        def request_generation_in_transaction(self, *args, **kwargs):
            raise RuntimeError("Simulated failure during lexical generation request")

    ingestion_store = PostgresIngestionStore(
        SessionFactory,
        search_index_store=FaultySearchIndexStore(),
        lexical_profile=SAMPLE_PROFILE,
    )
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=ingestion_store,
    )
    content = b"# Rollback Test\nContent that must be rolled back completely.\n"
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key="notes/rollback-doc",
        source_name="rollback-doc.md",
        media_type="text/markdown",
        raw_content=content,
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")

    with pytest.raises(RuntimeError, match="Simulated failure"):
        use_case.execute(command, principal)

    with SessionFactory() as session:
        jobs = session.scalars(
            select(IngestionJobTable).where(IngestionJobTable.workspace_id == workspace_id)
        ).all()
        assert len(jobs) == 0

        gens = session.scalars(
            select(LexicalGenerationTable).where(
                LexicalGenerationTable.workspace_id == workspace_id
            )
        ).all()
        assert len(gens) == 0

        sources = session.scalars(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.workspace_id == workspace_id
            )
        ).all()
        assert len(sources) == 0
