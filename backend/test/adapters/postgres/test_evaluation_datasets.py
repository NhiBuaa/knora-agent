from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.database import Base
from knora.adapters.postgres.evaluation_datasets import PostgresDatasetStore
from knora.adapters.postgres.evaluation_datasets_tables import (
    DatasetDraftTable,
    DatasetSourceTable,
    ExtractionSnapshotTable,
)
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import NormalizedPdfPage, PdfExtractionConfiguration, PdfExtractionResult


def test_registration_preserves_immutable_source_identity_and_no_runtime_pointer():
    engine = create_engine("sqlite:///:memory:")
    selected = [
        WorkspaceTable.__table__,
        DocumentTable.__table__,
        DocumentVersionTable.__table__,
        OriginalSourceObjectTable.__table__,
        DatasetDraftTable.__table__,
        DatasetSourceTable.__table__,
        ExtractionSnapshotTable.__table__,
    ]
    # Metadata's sorted order preserves FK creation dependencies.
    Base.metadata.create_all(engine, tables=selected)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(WorkspaceTable(id="w1", name="Workspace"))
    store = PostgresDatasetStore(factory)
    draft = store.create_dataset("w1", "Manual gold")
    metadata = ObjectMetadata("w1", "abc123", "a" * 64, 5, "application/pdf")
    source, created = store.add_source("w1", draft.id, "one.pdf", metadata, "key")
    assert created
    replay, created = store.add_source("w1", draft.id, "one.pdf", metadata, "key")
    assert not created and replay == source
    with factory() as session:
        document = session.get(DocumentTable, source.document_id)
        version = session.get(DocumentVersionTable, source.document_version_id)
        original = session.scalar(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.document_version_id == version.id
            )
        )
        assert document.current_document_version_id is None
        assert document.active_embedding_set_id is None
        assert version.raw_sha256 == metadata.sha256
        assert original.object_key == metadata.object_key
        assert session.get(DatasetSourceTable, source.id).original_source_object_id == original.id


def test_extraction_snapshot_is_persisted_with_page_checksum():
    engine = create_engine("sqlite:///:memory:")
    selected = [
        WorkspaceTable.__table__,
        DocumentTable.__table__,
        DocumentVersionTable.__table__,
        OriginalSourceObjectTable.__table__,
        DatasetDraftTable.__table__,
        DatasetSourceTable.__table__,
        ExtractionSnapshotTable.__table__,
    ]
    Base.metadata.create_all(engine, tables=selected)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(WorkspaceTable(id="w1", name="Workspace"))
    store = PostgresDatasetStore(factory)
    draft = store.create_dataset("w1", "Manual gold")
    source, _ = store.add_source(
        "w1",
        draft.id,
        "one.pdf",
        ObjectMetadata("w1", "abc123", "a" * 64, 5, "application/pdf"),
        "key",
    )
    config = PdfExtractionConfiguration.layout_preserving()
    result = PdfExtractionResult(
        (NormalizedPdfPage(1, "Example page", "0" * 64),),
        (),
        config.parser_version,
        config.extraction_options_version,
        config.normalizer_version,
        config.tokenizer_name,
        config.tokenizer_version,
        config.chunking_policy_version,
        config.derivation_identity,
    )
    ready = store.record_extraction(source, result, None)
    assert ready.status == "READY"
    snapshot = store.get_snapshot("w1", draft.id, source.id)
    assert snapshot.pages[0].text == "Example page"
    assert snapshot.pages[0].content_checksum == "0" * 64
    assert snapshot.configuration_sha256 == config.derivation_identity
