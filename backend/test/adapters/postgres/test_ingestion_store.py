from uuid import uuid4

import pytest

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import WorkspaceTable
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


def test_postgres_store_creates_then_reuses_the_same_derivation() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Ingestion store test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key="support/refund-policy",
        source_name="refund-policy.md",
        media_type="text/markdown",
        raw_content=b"# Refunds\n\nRefunds are available for 30 days.\n",
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")

    created = use_case.execute(command, principal)
    reused = use_case.execute(command, principal)

    assert created.outcome == "created"
    assert created.activation_changed is True
    assert reused.outcome == "reused"
    assert reused.activation_changed is False
    assert reused.document_id == created.document_id
    assert reused.document_version_id == created.document_version_id
    assert reused.chunk_set_id == created.chunk_set_id
    assert reused.embedding_set_id == created.embedding_set_id


def _command(workspace_id: str, source_key: str, content: bytes) -> IngestDocumentCommand:
    return IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key=source_key,
        source_name="refund-policy.md",
        media_type="text/markdown",
        raw_content=content,
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )


def test_postgres_store_versions_content_and_separates_source_keys() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Versioning test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    original = b"# Refunds\n\nRefunds are available for 30 days.\n"
    changed = b"# Refunds\n\nRefunds are available for 45 days.\n"

    first = use_case.execute(_command(workspace_id, "support/refund-policy", original), principal)
    second = use_case.execute(_command(workspace_id, "support/refund-policy", changed), principal)
    copy = use_case.execute(
        _command(workspace_id, "support/refund-policy-copy", original), principal
    )

    assert first.outcome == "created"
    assert second.outcome == "created"
    assert second.document_id == first.document_id
    assert second.document_version_id != first.document_version_id
    assert second.chunk_set_id != first.chunk_set_id
    assert second.embedding_set_id != first.embedding_set_id
    assert copy.outcome == "created"
    assert copy.document_id != first.document_id


def test_postgres_store_cas_rejects_stale_commit_without_partial_chain() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Concurrency test"))

    store = PostgresIngestionStore(SessionFactory)
    first_use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=store,
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    base = _command(workspace_id, "support/refund-policy", b"# Refunds\n\n30 days.\n")
    first = first_use_case.execute(base, principal)

    class LateProvider(DeterministicEmbeddingProvider):
        triggered = False

        def embed(self, texts, configuration):
            if not self.triggered:
                self.triggered = True
                first_use_case.execute(
                    _command(workspace_id, "support/refund-policy", b"# Refunds\n\n45 days.\n"),
                    principal,
                )
            return super().embed(texts, configuration)

    late_use_case = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=LateProvider(), store=store
    )
    with pytest.raises(KnoraError, match="DOCUMENT_CONCURRENTLY_UPDATED"):
        late_use_case.execute(
            _command(workspace_id, "support/refund-policy", b"# Refunds\n\n60 days.\n"), principal
        )

    retry = first_use_case.execute(
        _command(workspace_id, "support/refund-policy", b"# Refunds\n\n60 days.\n"), principal
    )
    assert retry.outcome == "created"
    assert retry.activation_changed is True
    assert retry.document_id == first.document_id


def test_postgres_store_rejects_configuration_id_collision() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Configuration collision test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    use_case.execute(
        _command(workspace_id, "support/refund-policy", b"# Refunds\n\n30 days.\n"), principal
    )
    altered_chunking = ChunkingConfiguration(
        id="chunking-m1-v1",
        parser_version="markdown-text-v1",
        chunker_version="heading-paragraph-v1",
        tokenizer_name="cl100k_base",
        tokenizer_version="tiktoken-0.12.0",
        target_tokens=400,
        overlap_tokens=75,
        max_tokens=650,
    )
    with pytest.raises(KnoraError, match="CHUNKING_CONFIGURATION_IMMUTABLE"):
        use_case.execute(
            _command(workspace_id, "support/refund-policy-2", b"# Refunds\n\n45 days.\n").__class__(
                workspace_id=workspace_id,
                source_key="support/refund-policy-2",
                source_name="refund-policy.md",
                media_type="text/markdown",
                raw_content=b"# Refunds\n\n45 days.\n",
                chunking_configuration=altered_chunking,
                embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
            ),
            principal,
        )

    altered_embedding = EmbeddingConfiguration(
        id="embedding-local-m1-v2",
        provider="deterministic-local",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="l2",
    )
    with pytest.raises(KnoraError, match="EMBEDDING_CONFIGURATION_IMMUTABLE"):
        use_case.execute(
            IngestDocumentCommand(
                workspace_id=workspace_id,
                source_key="support/refund-policy-3",
                source_name="refund-policy.md",
                media_type="text/markdown",
                raw_content=b"# Refunds\n\n60 days.\n",
                chunking_configuration=ChunkingConfiguration.milestone_one(),
                embedding_configuration=altered_embedding,
            ),
            principal,
        )
