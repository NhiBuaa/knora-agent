import os
import runpy
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.reembedding_store import PostgresCloudflareReindexStore
from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    QuestionTraceTable,
    WorkspaceTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration

CONFIG = EmbeddingConfiguration.cloudflare_qwen3_06b()
SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "reindex-cloudflare.py"


def _ingest(
    workspace_id: str, source_key: str, *, archived: bool = False, content: str | None = None
) -> str:
    result = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key=source_key,
            source_name=f"{source_key}.md",
            media_type="text/markdown",
            raw_content=(content or f"# Policy\n\n{source_key} policy text.").encode(),
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
    )
    if archived:
        with SessionFactory.begin() as session:
            session.get(DocumentTable, result.document_id).archived = True
    return result.document_id


def _workspace() -> str:
    workspace_id = f"reindex-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Cloudflare reindex"))
    return workspace_id


def _batch(document, *, invalid: bool = False) -> EmbeddingBatch:
    return EmbeddingBatch(
        vectors=tuple(tuple([float("nan") if invalid else 0.25] * 1024) for _ in document.chunks),
        provider=CONFIG.provider,
        model=CONFIG.model,
    )


def _missing_pdf(workspace_id: str) -> str:
    missing_id = str(uuid4())
    version_id = str(uuid4())
    source_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(
            DocumentTable(
                id=missing_id,
                workspace_id=workspace_id,
                source_key=f"missing-{missing_id}",
                source_name="missing.pdf",
                current_document_version_id=None,
                revision=0,
            )
        )
        session.flush()
        session.add(
            DocumentVersionTable(
                id=version_id,
                document_id=missing_id,
                raw_sha256="a" * 64,
                media_type="application/pdf",
                version_number=1,
            )
        )
        session.flush()
        session.get(DocumentTable, missing_id).current_document_version_id = version_id
        session.add(
            OriginalSourceObjectTable(
                id=source_id,
                workspace_id=workspace_id,
                document_version_id=version_id,
                object_key=f"test/{source_id}",
                raw_sha256="a" * 64,
                byte_size=1,
                media_type="application/pdf",
            )
        )
        session.flush()
        session.add(
            IngestionJobTable(
                id=str(uuid4()),
                workspace_id=workspace_id,
                operation="submit",
                document_id=missing_id,
                target_document_version_id=version_id,
                source_object_id=source_id,
                content_fingerprint=str(uuid4()),
                parser_configuration_id="p",
                normalizer_configuration_id="n",
                chunking_configuration_id="chunking-m1-v1",
                embedding_configuration_id="embedding-local-m1-v2",
                status="failed",
                safe_failure_code="PDF_TEXT_INSUFFICIENT",
                failure_reason="terminal_input",
                attempt_count=1,
                max_attempts=4,
                started_at=datetime.now(UTC),
                terminal_at=datetime.now(UTC),
            )
        )
    return missing_id


def test_inventory_includes_all_workspaces_archived_and_unindexable_without_writes() -> None:
    first, second = _workspace(), _workspace()
    text_id = _ingest(first, "policy")
    archived_id = _ingest(second, "archive", archived=True)
    missing_id = _missing_pdf(first)
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(
        workspace_ids=(first, second), approved_unindexable_ids=(missing_id,)
    )
    assert {document.document_id for document in inventory.eligible} == {text_id, archived_id}
    assert inventory.unindexable == ((missing_id, "PDF_TEXT_INSUFFICIENT"),)
    assert inventory.blockers == ()
    assert next(d for d in inventory.eligible if d.document_id == archived_id).archived
    assert len(store.inventory(workspace_ids=(first, second)).blockers) == 1
    with SessionFactory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(EmbeddingSetTable)
                .join(ChunkSetTable)
                .join(DocumentVersionTable)
                .where(
                    DocumentVersionTable.document_id.in_((text_id, archived_id)),
                    EmbeddingSetTable.embedding_configuration_id == CONFIG.id,
                )
            )
            == 0
        )


def test_approved_exclusion_drift_blocks_activation() -> None:
    workspace_id = _workspace()
    text_id = _ingest(workspace_id, "policy")
    missing_id = _missing_pdf(workspace_id)
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(
        workspace_ids=(workspace_id,), approved_unindexable_ids=(missing_id,)
    )
    staged = {
        document.document_id: store.stage(document, CONFIG, _batch(document))
        for document in inventory.eligible
    }
    with SessionFactory.begin() as session:
        session.get(DocumentTable, missing_id).revision += 1
    with pytest.raises(KnoraError):
        store.activate(inventory, staged, CONFIG)
    with SessionFactory() as session:
        assert (
            session.get(DocumentTable, text_id).active_embedding_configuration_id
            == "embedding-local-m1-v2"
        )


def test_approved_missing_text_does_not_hide_partial_derivation() -> None:
    workspace_id = _workspace()
    missing_id = _missing_pdf(workspace_id)
    with SessionFactory.begin() as session:
        version_id = session.get(DocumentTable, missing_id).current_document_version_id
        session.add(
            ChunkSetTable(
                id=str(uuid4()),
                document_version_id=version_id,
                chunking_configuration_id="chunking-m1-v1",
                status="processing",
            )
        )
    inventory = PostgresCloudflareReindexStore(SessionFactory).inventory(
        workspace_ids=(workspace_id,), approved_unindexable_ids=(missing_id,)
    )
    assert inventory.unindexable == ()
    assert (missing_id, "CURRENT_TEXT_DERIVATION_MISSING_REPROCESS_REQUIRED") in inventory.blockers


def test_cleanup_rejects_partial_obsolete_vector_set() -> None:
    workspace_id = _workspace()
    _ingest(workspace_id, "policy", content="# Policy\n\nFirst paragraph.\n\nSecond paragraph.")
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(workspace_ids=(workspace_id,))
    document = inventory.eligible[0]
    store.activate(
        inventory, {document.document_id: store.stage(document, CONFIG, _batch(document))}, CONFIG
    )
    with SessionFactory.begin() as session:
        old_vector = session.scalar(
            select(ChunkEmbeddingTable).where(
                ChunkEmbeddingTable.embedding_set_id == document.active_embedding_set_id
            )
        )
        session.delete(old_vector)
    with pytest.raises(KnoraError):
        store.cleanup(store.inventory(workspace_ids=(workspace_id,)), CONFIG, e2e_confirmed=True)


def test_inventory_blocks_incomplete_active_vector_coverage() -> None:
    workspace_id = _workspace()
    document_id = _ingest(
        workspace_id, "policy", content="# Policy\n\nFirst paragraph.\n\nSecond paragraph."
    )
    with SessionFactory.begin() as session:
        active_set_id = session.get(DocumentTable, document_id).active_embedding_set_id
        old_vector = session.scalar(
            select(ChunkEmbeddingTable).where(ChunkEmbeddingTable.embedding_set_id == active_set_id)
        )
        session.delete(old_vector)
    inventory = PostgresCloudflareReindexStore(SessionFactory).inventory(
        workspace_ids=(workspace_id,)
    )
    assert inventory.eligible == ()
    assert inventory.blockers == ((document_id, "ACTIVE_VECTOR_COVERAGE_INCOMPLETE"),)


def test_stage_then_atomic_activation_and_idempotent_reuse() -> None:
    first_workspace, second_workspace = _workspace(), _workspace()
    first = _ingest(first_workspace, "first")
    second = _ingest(second_workspace, "second", archived=True)
    source_id = str(uuid4())
    with SessionFactory.begin() as session:
        version_id = session.get(DocumentTable, second).current_document_version_id
        session.get(DocumentVersionTable, version_id).media_type = "application/pdf"
        session.add(
            OriginalSourceObjectTable(
                id=source_id,
                workspace_id=second_workspace,
                document_version_id=version_id,
                object_key=f"test/{source_id}",
                raw_sha256="b" * 64,
                byte_size=1,
                media_type="application/pdf",
            )
        )
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(workspace_ids=(first_workspace, second_workspace))
    old = {
        document.document_id: (
            document.active_embedding_set_id,
            document.revision,
            document.version_id,
            document.workspace_id,
        )
        for document in inventory.eligible
    }
    staged = {}
    for document in inventory.eligible:
        staged[document.document_id] = store.stage(document, CONFIG, _batch(document))
    with SessionFactory() as session:
        for document_id in (first, second):
            row = session.get(DocumentTable, document_id)
            assert (row.active_embedding_set_id, row.revision) == old[document_id][:2]
    assert (
        store.stage(inventory.eligible[0], CONFIG, _batch(inventory.eligible[0], invalid=True))
        == staged[inventory.eligible[0].document_id]
    )
    store.activate(inventory, staged, CONFIG)
    with SessionFactory() as session:
        for document_id in (first, second):
            row = session.get(DocumentTable, document_id)
            assert row.active_embedding_set_id == staged[document_id]
            assert row.active_embedding_configuration_id == CONFIG.id
            assert row.current_document_version_id == old[document_id][2]
            assert row.workspace_id == old[document_id][3]
            assert row.revision == old[document_id][1] + 1
        assert session.get(DocumentTable, second).archived
        assert session.get(OriginalSourceObjectTable, source_id).document_version_id == version_id
    repeated = store.inventory(workspace_ids=(first_workspace, second_workspace))
    store.activate(repeated, staged, CONFIG)
    with SessionFactory() as session:
        assert session.get(DocumentTable, first).revision == old[first][1] + 1


def test_invalid_batch_and_revision_drift_keep_old_active_vectors() -> None:
    workspace_id = _workspace()
    first = _ingest(workspace_id, "first")
    second = _ingest(workspace_id, "second")
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(workspace_ids=(workspace_id,))
    with pytest.raises(KnoraError):
        store.stage(
            inventory.eligible[0],
            CONFIG,
            EmbeddingBatch(
                vectors=((float("nan"),),), provider=CONFIG.provider, model=CONFIG.model
            ),
        )
    staged = {
        document.document_id: store.stage(document, CONFIG, _batch(document))
        for document in inventory.eligible
    }
    with SessionFactory.begin() as session:
        session.get(DocumentTable, second).revision += 1
    with pytest.raises(KnoraError):
        store.activate(inventory, staged, CONFIG)
    with SessionFactory() as session:
        for document_id in (first, second):
            assert (
                session.get(DocumentTable, document_id).active_embedding_configuration_id
                == "embedding-local-m1-v2"
            )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ChunkEmbeddingTable)
                .join(EmbeddingSetTable)
                .where(
                    EmbeddingSetTable.embedding_configuration_id == "embedding-local-m1-v2",
                    EmbeddingSetTable.chunk_set_id.in_(
                        document.chunk_set_id for document in inventory.eligible
                    ),
                )
            )
            > 0
        )


def test_cleanup_requires_confirmation_and_preserves_metadata() -> None:
    workspace_id = _workspace()
    other_workspace_id = _workspace()
    document_id = _ingest(workspace_id, "policy")
    other_document_id = _ingest(other_workspace_id, "foreign-policy")
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(workspace_ids=(workspace_id,))
    document = inventory.eligible[0]
    old_set_id = document.active_embedding_set_id
    source_id, trace_id = str(uuid4()), str(uuid4())
    with SessionFactory.begin() as session:
        session.add(
            OriginalSourceObjectTable(
                id=source_id,
                workspace_id=workspace_id,
                document_version_id=document.version_id,
                object_key=f"test/{source_id}",
                raw_sha256="c" * 64,
                byte_size=1,
                media_type="application/pdf",
            )
        )
        session.add(
            QuestionTraceTable(
                id=trace_id,
                workspace_id=workspace_id,
                question="retained provenance",
                embedding_configuration_id=document.active_embedding_configuration_id,
                embedding_set_ids=[old_set_id],
                chunk_set_ids=[document.chunk_set_id],
                retrieved_chunk_ids=[chunk.chunk_id for chunk in document.chunks],
                candidate_decisions=[],
                branch_observations=[],
                decision="ANSWER",
                answer="retained provenance",
                refused=False,
                generation_status="completed",
                alias_mapping={"E1": document.chunks[0].chunk_id},
                parsed_markers=["E1"],
                validation_outcome="valid",
                provider_metadata={},
            )
        )
    staged = {document_id: store.stage(document, CONFIG, _batch(document))}
    with pytest.raises(KnoraError):
        store.cleanup(inventory, CONFIG, e2e_confirmed=False)
    with pytest.raises(KnoraError):
        store.cleanup(inventory, CONFIG, e2e_confirmed=True)
    store.activate(inventory, staged, CONFIG)
    active = store.inventory(workspace_ids=(workspace_id,))

    def snapshot():
        with SessionFactory() as session:
            metadata = {}
            for table, ids in (
                (DocumentTable, (document_id, other_document_id)),
                (DocumentVersionTable, (document.version_id,)),
                (OriginalSourceObjectTable, (source_id,)),
                (ChunkSetTable, (document.chunk_set_id,)),
                (ChunkTable, tuple(chunk.chunk_id for chunk in document.chunks)),
                (EmbeddingSetTable, (old_set_id, staged[document_id])),
                (
                    EmbeddingConfigurationTable,
                    (document.active_embedding_configuration_id, CONFIG.id),
                ),
                (QuestionTraceTable, (trace_id,)),
            ):
                metadata[table.__tablename__] = tuple(
                    (
                        row_id,
                        tuple(
                            getattr(session.get(table, row_id), column.name)
                            for column in table.__table__.columns
                        ),
                    )
                    for row_id in ids
                )
            vector_rows = session.scalars(
                select(ChunkEmbeddingTable)
                .where(
                    ChunkEmbeddingTable.embedding_set_id.in_(
                        (
                            old_set_id,
                            staged[document_id],
                            session.get(DocumentTable, other_document_id).active_embedding_set_id,
                        )
                    )
                )
                .order_by(ChunkEmbeddingTable.id)
            ).all()
            vectors = tuple(
                (row.id, row.embedding_set_id, row.chunk_id, tuple(row.embedding))
                for row in vector_rows
            )
            return metadata, vectors

    before_metadata, before_vectors = snapshot()
    with SessionFactory() as session:
        foreign_set_id = session.get(DocumentTable, other_document_id).active_embedding_set_id
    selected_old_vectors = tuple(row for row in before_vectors if row[1] == old_set_id)
    assert selected_old_vectors
    assert store.cleanup(active, CONFIG, e2e_confirmed=True) == len(selected_old_vectors)
    assert (
        store.cleanup(store.inventory(workspace_ids=(workspace_id,)), CONFIG, e2e_confirmed=True)
        == 0
    )
    after_metadata, after_vectors = snapshot()
    assert after_metadata == before_metadata
    assert after_vectors == tuple(row for row in before_vectors if row[1] != old_set_id)
    assert any(row[1] == foreign_set_id for row in after_vectors)
    assert any(row[1] == staged[document_id] for row in after_vectors)
    with SessionFactory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ChunkEmbeddingTable)
                .where(ChunkEmbeddingTable.embedding_set_id == old_set_id)
            )
            == 0
        )
        assert session.scalar(
            select(func.count())
            .select_from(ChunkEmbeddingTable)
            .where(ChunkEmbeddingTable.embedding_set_id == staged[document_id])
        ) == len(document.chunks)


def test_default_cli_inventory_has_no_cloud_credentials_or_writes() -> None:
    workspace_id = _workspace()
    document_id = _ingest(workspace_id, "policy")
    environment = dict(os.environ)
    environment.pop("KNORA_CLOUDFLARE_ACCOUNT_ID", None)
    environment.pop("KNORA_CLOUDFLARE_API_TOKEN", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--workspace-id", workspace_id],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0
    assert "eligible=1" in result.stdout
    assert "mode=inventory" in result.stdout
    with SessionFactory() as session:
        assert (
            session.get(DocumentTable, document_id).active_embedding_configuration_id
            == "embedding-local-m1-v2"
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(EmbeddingSetTable)
                .join(ChunkSetTable)
                .join(DocumentVersionTable)
                .where(
                    DocumentVersionTable.document_id == document_id,
                    EmbeddingSetTable.embedding_configuration_id == CONFIG.id,
                )
            )
            == 0
        )


def test_cli_argument_errors_do_not_echo_values() -> None:
    marker = "secret-argument-value"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--unknown", marker],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert marker not in result.stdout + result.stderr


def test_provider_failure_stages_only_and_rerun_reuses_completed_set() -> None:
    workspace_id = _workspace()
    _ingest(workspace_id, "first")
    _ingest(workspace_id, "second")
    script = runpy.run_path(str(SCRIPT))
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(workspace_ids=(workspace_id,))

    class FailingProvider:
        def __init__(self) -> None:
            self.calls = 0

        def embed_documents(self, texts, configuration):
            self.calls += 1
            if self.calls == 2:
                raise KnoraError("PROVIDER_REQUEST_FAILED")
            return EmbeddingBatch(
                vectors=tuple((0.25,) * 1024 for _ in texts),
                provider=configuration.provider,
                model=configuration.model,
            )

    with pytest.raises(KnoraError) as failure:
        script["apply"](store, inventory, FailingProvider(), CONFIG)
    assert failure.value.code == "PROVIDER_REQUEST_FAILED"
    with SessionFactory() as session:
        assert all(
            session.get(DocumentTable, document.document_id).active_embedding_configuration_id
            == "embedding-local-m1-v2"
            for document in inventory.eligible
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(EmbeddingSetTable)
                .where(
                    EmbeddingSetTable.chunk_set_id.in_(
                        document.chunk_set_id for document in inventory.eligible
                    ),
                    EmbeddingSetTable.embedding_configuration_id == CONFIG.id,
                )
            )
            == 1
        )
    provider = FailingProvider()
    provider.calls = -1
    script["apply"](store, store.inventory(workspace_ids=(workspace_id,)), provider, CONFIG)
    assert provider.calls == 0


def test_apply_rejects_corrupt_inactive_completed_set_before_provider_or_activation() -> None:
    workspace_id = _workspace()
    _ingest(workspace_id, "first", content="# Policy\n\nFirst.\n\nSecond.")
    _ingest(workspace_id, "second", content="# Policy\n\nThird.\n\nFourth.")
    store = PostgresCloudflareReindexStore(SessionFactory)
    inventory = store.inventory(workspace_ids=(workspace_id,))
    first = inventory.eligible[0]
    assert len(first.chunks) == 2
    staged_id = store.stage(first, CONFIG, _batch(first))
    with SessionFactory.begin() as session:
        incomplete = session.scalar(
            select(ChunkEmbeddingTable).where(ChunkEmbeddingTable.embedding_set_id == staged_id)
        )
        session.delete(incomplete)
    with SessionFactory() as session:
        before_documents = {
            document.document_id: (
                session.get(DocumentTable, document.document_id).active_embedding_set_id,
                session.get(DocumentTable, document.document_id).revision,
            )
            for document in inventory.eligible
        }
        old_set_ids = [pointer for pointer, _ in before_documents.values()]
        before_old_vectors = tuple(
            (row.id, row.embedding_set_id, row.chunk_id, tuple(row.embedding))
            for row in session.scalars(
                select(ChunkEmbeddingTable)
                .where(ChunkEmbeddingTable.embedding_set_id.in_(old_set_ids))
                .order_by(ChunkEmbeddingTable.id)
            )
        )

    class NoProviderCalls:
        def embed_documents(self, texts, configuration):
            pytest.fail("corrupt completed set must fail before provider call")

    with pytest.raises(KnoraError) as failure:
        runpy.run_path(str(SCRIPT))["apply"](store, inventory, NoProviderCalls(), CONFIG)
    assert failure.value.code == "REINDEX_VECTOR_COVERAGE_INCOMPLETE"
    with SessionFactory() as session:
        assert {
            document.document_id: (
                session.get(DocumentTable, document.document_id).active_embedding_set_id,
                session.get(DocumentTable, document.document_id).revision,
            )
            for document in inventory.eligible
        } == before_documents
        assert (
            tuple(
                (row.id, row.embedding_set_id, row.chunk_id, tuple(row.embedding))
                for row in session.scalars(
                    select(ChunkEmbeddingTable)
                    .where(ChunkEmbeddingTable.embedding_set_id.in_(old_set_ids))
                    .order_by(ChunkEmbeddingTable.id)
                )
            )
            == before_old_vectors
        )
