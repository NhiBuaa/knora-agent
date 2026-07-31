from uuid import uuid4

from sqlalchemy import select

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    DocumentTable,
    EmbeddingSetTable,
    WorkspaceTable,
)
from knora.answering.stores import RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


def ingest(
    workspace_id: str,
    source_key: str,
    *,
    content: bytes = b"# Refunds\n\nRefund requests are accepted within thirty days.\n",
    configuration: EmbeddingConfiguration | None = None,
):
    return IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key=source_key,
            source_name="refunds.md",
            media_type="text/markdown",
            raw_content=content,
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=(
                configuration or EmbeddingConfiguration.milestone_one_local()
            ),
        ),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
    )


def test_retrieval_filters_workspace_and_active_embedding_set_in_sql() -> None:
    workspace_a = f"question-a-{uuid4()}"
    workspace_b = f"question-b-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add_all(
            [
                WorkspaceTable(id=workspace_a, name="Question A"),
                WorkspaceTable(id=workspace_b, name="Question B"),
            ]
        )
    original = ingest(workspace_a, "support/refunds-a")
    changed_content = b"# Refunds\n\nRefund requests are accepted within forty five days.\n"
    active = ingest(workspace_a, "support/refunds-a", content=changed_content)
    ingest(workspace_a, "support/refunds-a-2", content=changed_content)
    ingest(
        workspace_a,
        "support/other-configuration",
        content=changed_content,
        configuration=EmbeddingConfiguration(
            id="embedding-other-m1",
            provider="deterministic-local",
            model="text-embedding-3-small",
            dimensions=1536,
            distance_metric="cosine",
        ),
    )
    ingest(workspace_b, "support/refunds-b")

    with SessionFactory() as session:
        query_vector = tuple(
            session.scalars(
                select(ChunkEmbeddingTable.embedding)
                .join(
                    EmbeddingSetTable,
                    EmbeddingSetTable.id == ChunkEmbeddingTable.embedding_set_id,
                )
                .join(
                    DocumentTable,
                    DocumentTable.active_embedding_set_id == EmbeddingSetTable.id,
                )
                .where(
                    DocumentTable.workspace_id == workspace_a,
                    DocumentTable.source_key == "support/refunds-a",
                )
            ).first()
        )

    candidates = PostgresAnsweringStore(SessionFactory).retrieve_candidates(
        workspace_id=workspace_a,
        query_vector=query_vector,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=RetrievalConfiguration.milestone_one(),
    )

    assert candidates
    assert {candidate.source_key for candidate in candidates} == {
        "support/refunds-a",
        "support/refunds-a-2",
    }
    assert candidates[0].similarity == 1.0
    assert all(candidate.embedding_set_id != original.embedding_set_id for candidate in candidates)
    assert all(
        candidate.embedding_set_id == active.embedding_set_id
        for candidate in candidates
        if candidate.source_key == "support/refunds-a"
    )
    assert all(
        candidate.embedding_configuration_id == "embedding-local-m1-v2"
        for candidate in candidates
    )
    assert [
        (-candidate.similarity, candidate.document_id, candidate.chunk_ordinal, candidate.chunk_id)
        for candidate in candidates
    ] == sorted(
        (
            -candidate.similarity,
            candidate.document_id,
            candidate.chunk_ordinal,
            candidate.chunk_id,
        )
        for candidate in candidates
    )
