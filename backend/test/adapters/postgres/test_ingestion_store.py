from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    WorkspaceTable,
)
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
        winner = None

        def embed(self, texts, configuration):
            if not self.triggered:
                self.triggered = True
                self.winner = first_use_case.execute(
                    _command(workspace_id, "support/refund-policy", b"# Refunds\n\n45 days.\n"),
                    principal,
                )
            return super().embed(texts, configuration)

    late_provider = LateProvider()
    late_use_case = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=late_provider, store=store
    )
    with pytest.raises(KnoraError, match="DOCUMENT_CONCURRENTLY_UPDATED"):
        late_use_case.execute(
            _command(workspace_id, "support/refund-policy", b"# Refunds\n\n60 days.\n"), principal
        )

    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        assert document.revision == 2
        assert document.active_embedding_set_id == late_provider.winner.embedding_set_id
        assert session.scalar(
            select(func.count())
            .select_from(DocumentVersionTable)
            .where(DocumentVersionTable.document_id == first.document_id)
        ) == 2
        assert session.scalar(
            select(func.count())
            .select_from(ChunkSetTable)
            .join(
                DocumentVersionTable,
                DocumentVersionTable.id == ChunkSetTable.document_version_id,
            )
            .where(DocumentVersionTable.document_id == first.document_id)
        ) == 2
        assert session.scalar(
            select(func.count())
            .select_from(EmbeddingSetTable)
            .join(ChunkSetTable, ChunkSetTable.id == EmbeddingSetTable.chunk_set_id)
            .join(
                DocumentVersionTable,
                DocumentVersionTable.id == ChunkSetTable.document_version_id,
            )
            .where(DocumentVersionTable.document_id == first.document_id)
        ) == 2

    retry = first_use_case.execute(
        _command(workspace_id, "support/refund-policy", b"# Refunds\n\n60 days.\n"), principal
    )
    assert retry.outcome == "created"
    assert retry.activation_changed is True
    assert retry.document_id == first.document_id


@pytest.mark.parametrize(
    "cross_workspace", [False, True], ids=["same-workspace", "cross-workspace"]
)
def test_active_embedding_set_cannot_belong_to_another_document(
    cross_workspace: bool,
) -> None:
    workspace_id = f"test-{uuid4()}"
    other_workspace_id = f"test-{uuid4()}" if cross_workspace else workspace_id
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Active set invariant test"))
        if cross_workspace:
            session.add(
                WorkspaceTable(id=other_workspace_id, name="Other Workspace invariant test")
            )

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    first = use_case.execute(
        _command(workspace_id, "support/first", b"# First\n\nFirst document.\n"), principal
    )
    second = use_case.execute(
        _command(other_workspace_id, "support/second", b"# Second\n\nSecond document.\n"),
        WorkspacePrincipal(workspace_id=other_workspace_id, key_id="cli-other"),
    )

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == first.document_id)
            .values(active_embedding_set_id=second.embedding_set_id)
        )

    with SessionFactory() as session:
        document = session.scalar(
            select(DocumentTable).where(DocumentTable.id == first.document_id)
        )
        assert document.active_embedding_set_id == first.embedding_set_id
        assert document.revision == 1


def test_active_embedding_set_must_be_completed() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Active completion invariant test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    result = use_case.execute(
        _command(workspace_id, "support/refunds", b"# Refunds\n\nThirty days.\n"),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="cli"),
    )
    pending_set_id = str(uuid4())
    pending_configuration_id = f"embedding-pending-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(
            EmbeddingConfigurationTable(
                id=pending_configuration_id,
                provider="deterministic-local",
                model="text-embedding-3-small",
                dimensions=1536,
                distance_metric="cosine",
            )
        )
        session.add(
            EmbeddingSetTable(
                id=pending_set_id,
                chunk_set_id=result.chunk_set_id,
                embedding_configuration_id=pending_configuration_id,
                status="pending",
            )
        )

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == result.document_id)
            .values(active_embedding_set_id=pending_set_id)
        )

    with SessionFactory() as session:
        document = session.get(DocumentTable, result.document_id)
        assert document.active_embedding_set_id == result.embedding_set_id
        assert document.revision == 1


def test_active_embedding_set_cannot_become_incomplete() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Active status invariant test"))

    result = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        _command(workspace_id, "support/refunds", b"# Refunds\n\nThirty days.\n"),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="cli"),
    )

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            update(EmbeddingSetTable)
            .where(EmbeddingSetTable.id == result.embedding_set_id)
            .values(status="pending")
        )

    with SessionFactory() as session:
        embedding_set = session.get(EmbeddingSetTable, result.embedding_set_id)
        assert embedding_set.status == "completed"


def test_active_embedding_set_cannot_be_deleted() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Active delete invariant test"))

    result = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        _command(workspace_id, "support/refunds", b"# Refunds\n\nThirty days.\n"),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="cli"),
    )

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            delete(EmbeddingSetTable).where(EmbeddingSetTable.id == result.embedding_set_id)
        )

    with SessionFactory() as session:
        assert session.get(EmbeddingSetTable, result.embedding_set_id) is not None


def test_active_embedding_set_must_match_the_required_configuration() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Active configuration invariant test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    first = use_case.execute(
        _command(workspace_id, "support/refunds", b"# Refunds\n\nThirty days.\n"), principal
    )
    alternate_configuration = EmbeddingConfiguration(
        id=f"embedding-alternate-{uuid4()}",
        provider="deterministic-local",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
    )
    alternate = use_case.execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key="support/refunds",
            source_name="refund-policy.md",
            media_type="text/markdown",
            raw_content=b"# Refunds\n\nForty five days.\n",
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=alternate_configuration,
        ),
        principal,
    )

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == first.document_id)
            .values(active_embedding_set_id=first.embedding_set_id)
        )

    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        assert document.active_embedding_set_id == alternate.embedding_set_id
        assert document.revision == 2


def test_activation_locks_target_set_against_concurrent_invalidation() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Active lock invariant test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    target = use_case.execute(
        _command(workspace_id, "support/refunds", b"# Refunds\n\nThirty days.\n"), principal
    )
    alternate_configuration = EmbeddingConfiguration(
        id=f"embedding-alternate-{uuid4()}",
        provider="deterministic-local",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
    )
    use_case.execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key="support/refunds",
            source_name="refund-policy.md",
            media_type="text/markdown",
            raw_content=b"# Refunds\n\nForty five days.\n",
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=alternate_configuration,
        ),
        principal,
    )

    activation_session = SessionFactory()
    invalidation_session = SessionFactory()
    try:
        activation_session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == target.document_id)
            .values(
                active_embedding_set_id=target.embedding_set_id,
                active_embedding_configuration_id=target.embedding_configuration_id,
            )
        )
        invalidation_session.execute(text("SET LOCAL lock_timeout = '250ms'"))

        with pytest.raises(OperationalError, match="lock timeout"):
            invalidation_session.execute(
                update(EmbeddingSetTable)
                .where(EmbeddingSetTable.id == target.embedding_set_id)
                .values(status="pending")
            )
    finally:
        invalidation_session.rollback()
        activation_session.rollback()
        invalidation_session.close()
        activation_session.close()


def test_invalidation_locks_target_set_against_concurrent_activation() -> None:
    workspace_id = f"test-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Invalidation lock invariant test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    target = use_case.execute(
        _command(workspace_id, "support/refunds", b"# Refunds\n\nThirty days.\n"), principal
    )
    alternate_configuration = EmbeddingConfiguration(
        id=f"embedding-alternate-{uuid4()}",
        provider="deterministic-local",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
    )
    use_case.execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key="support/refunds",
            source_name="refund-policy.md",
            media_type="text/markdown",
            raw_content=b"# Refunds\n\nForty five days.\n",
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=alternate_configuration,
        ),
        principal,
    )

    invalidation_session = SessionFactory()
    activation_session = SessionFactory()
    try:
        invalidation_session.execute(
            update(EmbeddingSetTable)
            .where(EmbeddingSetTable.id == target.embedding_set_id)
            .values(status="pending")
        )
        activation_session.execute(text("SET LOCAL lock_timeout = '250ms'"))

        with pytest.raises(OperationalError, match="lock timeout"):
            activation_session.execute(
                update(DocumentTable)
                .where(DocumentTable.id == target.document_id)
                .values(
                    active_embedding_set_id=target.embedding_set_id,
                    active_embedding_configuration_id=target.embedding_configuration_id,
                )
            )
    finally:
        activation_session.rollback()
        invalidation_session.rollback()
        activation_session.close()
        invalidation_session.close()


def test_persistence_failure_is_sanitized_and_rolls_back_the_derivation() -> None:
    workspace_id = f"test-{uuid4()}"
    source_key = "support/persistence-failure"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Persistence failure test"))

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key=source_key,
        source_name=f"database-canary-{'x' * 300}.md",
        media_type="text/markdown",
        raw_content=b"# Refunds\n\nThirty days.\n",
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(KnoraError) as captured:
        use_case.execute(
            command,
            WorkspacePrincipal(workspace_id=workspace_id, key_id="cli"),
        )

    assert captured.value.code == "PERSISTENCE_OPERATION_FAILED"
    assert "database-canary" not in str(captured.value)
    with SessionFactory() as session:
        assert session.scalar(
            select(DocumentTable).where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.source_key == source_key,
            )
        ) is None


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
