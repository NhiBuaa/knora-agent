from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.database import Base
from knora.adapters.postgres.evaluation_datasets_tables import (
    DatasetDraftTable,
    DatasetSourceTable,
    ExtractionSnapshotTable,
)
from knora.adapters.postgres.ingestion_jobs.lifecycle import PostgresObjectLifecycleStore
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)


def test_dataset_source_reference_blocks_original_source_hard_delete_before_deeper_checks():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            WorkspaceTable.__table__,
            DocumentTable.__table__,
            DocumentVersionTable.__table__,
            OriginalSourceObjectTable.__table__,
            DatasetDraftTable.__table__,
            DatasetSourceTable.__table__,
            ExtractionSnapshotTable.__table__,
        ],
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(WorkspaceTable(id="w1", name="Workspace"))
        session.add(
            DocumentTable(
                id="doc1",
                workspace_id="w1",
                source_key="evaluation/d1/s1",
                source_name="source.pdf",
                revision=0,
            )
        )
        session.add(
            DocumentVersionTable(
                id="ver1",
                document_id="doc1",
                raw_sha256="a" * 64,
                media_type="application/pdf",
                version_number=1,
            )
        )
        session.add(
            OriginalSourceObjectTable(
                id="obj1",
                workspace_id="w1",
                document_version_id="ver1",
                object_key="evaluation/d1/s1",
                raw_sha256="a" * 64,
                byte_size=1,
                media_type="application/pdf",
            )
        )
        session.add(DatasetDraftTable(id="d1", workspace_id="w1", name="Gold", status="DRAFT"))
        session.add(
            DatasetSourceTable(
                id="s1",
                workspace_id="w1",
                dataset_id="d1",
                document_id="doc1",
                document_version_id="ver1",
                original_source_object_id="obj1",
                filename="source.pdf",
                raw_sha256="a" * 64,
                byte_size=1,
                object_key="evaluation/d1/s1",
                idempotency_key="upload-1",
                status="READY",
            )
        )
    with factory.begin() as session:
        source = session.get(OriginalSourceObjectTable, "obj1")
        try:
            PostgresObjectLifecycleStore._assert_original_source_hard_deleteable(
                session=session, source=source
            )
        except PermissionError as error:
            assert "evaluation dataset" in str(error)
        else:
            raise AssertionError("evaluation source must retain its original PDF")
