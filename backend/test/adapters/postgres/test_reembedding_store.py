from uuid import uuid4

from sqlalchemy import func, select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.reembedding_store import PostgresReembeddingStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentTable,
    EmbeddingSetTable,
    RetrievalV2CutoverTable,
    WorkspaceTable,
)
from knora.answering.reembedding_v2 import ReembedProductionCorpus
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class GeminiFixtureProvider:
    def embed_documents(self, texts, configuration):
        return EmbeddingBatch(
            vectors=tuple(tuple([0.25 + index / 100] * 1536) for index, _ in enumerate(texts)),
            provider=configuration.provider,
            model=configuration.model,
        )


def test_reembedding_store_preserves_full_population_chunk_sets_and_records_cutover() -> None:
    workspace_id = f"reembed-{uuid4()}"
    source_keys = ("support/refunds", "support/shipping")
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Re-embedding"))
    ingest = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="test")
    before_chunk_sets: dict[str, str] = {}
    for source_key in source_keys:
        result = ingest.execute(
            IngestDocumentCommand(
                workspace_id=workspace_id,
                source_key=source_key,
                source_name=f"{source_key}.md",
                media_type="text/markdown",
                raw_content=f"# Policy\n\n{source_key} policy text.".encode(),
                chunking_configuration=ChunkingConfiguration.milestone_one(),
                embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
            ),
            principal,
        )
        before_chunk_sets[source_key] = result.chunk_set_id

    result = ReembedProductionCorpus(
        provider=GeminiFixtureProvider(),
        store=PostgresReembeddingStore(
            SessionFactory, authority_source_keys=source_keys
        ),
    ).execute(
        workspace_id=workspace_id,
        configuration=EmbeddingConfiguration.gemini_m3(),
    )

    with SessionFactory() as session:
        documents = session.scalars(
            select(DocumentTable)
            .where(DocumentTable.workspace_id == workspace_id)
            .order_by(DocumentTable.source_key)
        ).all()
        active_configurations = {
            document.source_key: document.active_embedding_configuration_id
            for document in documents
        }
        assert active_configurations == {
            source_key: "embedding-gemini-m1-v1" for source_key in source_keys
        }
        active_sets = session.scalars(
            select(EmbeddingSetTable).where(
                EmbeddingSetTable.id.in_(
                    document.active_embedding_set_id for document in documents
                )
            )
        ).all()
        assert {embedding_set.chunk_set_id for embedding_set in active_sets} == set(
            before_chunk_sets.values()
        )
        assert session.scalar(
            select(func.count())
            .select_from(ChunkSetTable)
            .join(EmbeddingSetTable, EmbeddingSetTable.chunk_set_id == ChunkSetTable.id)
            .join(DocumentTable, DocumentTable.active_embedding_set_id == EmbeddingSetTable.id)
            .where(DocumentTable.workspace_id == workspace_id)
        ) == 2
        assert session.scalar(
            select(func.count())
            .select_from(EmbeddingSetTable)
            .where(
                EmbeddingSetTable.chunk_set_id.in_(before_chunk_sets.values()),
                EmbeddingSetTable.embedding_configuration_id == "embedding-local-m1-v2",
            )
        ) == 2
        cutover = session.get(
            RetrievalV2CutoverTable,
            (workspace_id, "embedding-gemini-m1-v1"),
        )
        assert cutover is not None
        assert cutover.population_digest == result.population_digest
        assert cutover.status == "completed"
