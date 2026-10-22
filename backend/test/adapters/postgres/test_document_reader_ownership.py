"""Offline document ownership regression against the maintained adapter.

Real adapter predicates and writes run against invocation-local SQLite. Snapshot
isolation and the unrelated retrieval projection are replaced here, not in source.
This does not verify PostgreSQL isolation, row locks, migrations or retrieval.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.database import Base
from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.evaluation_datasets_tables import DatasetDraftTable, DatasetSourceTable
from knora.adapters.postgres.tables import (
    DocumentDeletionRequestTable,
    DocumentTable,
    WorkspaceTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


@pytest.fixture
def database(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'projection.sqlite'}")
    Base.metadata.create_all(
        engine,
        tables=[
            table.__table__
            for table in (
                WorkspaceTable,
                DocumentTable,
                DatasetDraftTable,
                DatasetSourceTable,
                DocumentDeletionRequestTable,
            )
        ],
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add_all([WorkspaceTable(id="w1", name="one"), WorkspaceTable(id="w2", name="two")])
        session.add_all(
            [
                DocumentTable(
                    id="ordinary",
                    workspace_id="w1",
                    source_key="evaluation/guide",
                    source_name="guide.md",
                ),
                DocumentTable(
                    id="builder",
                    workspace_id="w1",
                    source_key="unprefixed-builder",
                    source_name="source.pdf",
                ),
                DocumentTable(
                    id="foreign", workspace_id="w2", source_key="other", source_name="other.md"
                ),
            ]
        )
        session.add_all(
            [
                DatasetDraftTable(id="draft1", workspace_id="w1", name="one"),
                DatasetDraftTable(id="draft2", workspace_id="w2", name="two"),
            ]
        )
        for source_id, workspace_id, dataset_id, document_id in [
            ("owned", "w1", "draft1", "builder"),
            ("foreign-relation", "w2", "draft2", "ordinary"),
        ]:
            session.add(
                DatasetSourceTable(
                    id=source_id,
                    workspace_id=workspace_id,
                    dataset_id=dataset_id,
                    document_id=document_id,
                    document_version_id="unused-version",
                    original_source_object_id="unused-original",
                    filename="source.pdf",
                    raw_sha256="a" * 64,
                    byte_size=10,
                    object_key=source_id,
                    idempotency_key=source_id,
                )
            )
    monkeypatch.setattr(
        PostgresDocumentReader, "_begin_snapshot", staticmethod(lambda session: None)
    )
    monkeypatch.setattr(
        PostgresDocumentReader,
        "_projection",
        lambda self, session, row: SimpleNamespace(
            document_id=row.id,
            workspace_id=row.workspace_id,
            archived=row.archived,
            revision=row.revision,
        ),
    )
    yield PostgresDocumentReader(factory), factory
    engine.dispose()


def invoke(reader, operation, document_id="ordinary"):
    args = dict(workspace_id="w1", principal=WorkspacePrincipal("w1", "owner"))
    if operation == "list":
        return reader.list_documents(**args)
    args["document_id"] = document_id
    if operation == "read":
        return reader.read_document(**args)
    if operation in {"archive", "unarchive"}:
        return getattr(reader, operation)(**args, expected_revision=0)
    return reader.request_deletion(**args, idempotency_key="delete-once")


@pytest.mark.parametrize("operation", ["list", "read", "archive", "unarchive", "delete"])
def test_ordinary_evaluation_prefix_remains_accessible(database, operation):
    reader, factory = database
    if operation == "unarchive":
        with factory.begin() as session:
            session.get(DocumentTable, "ordinary").archived = True
    result = invoke(reader, operation)
    if operation == "list":
        assert [item.document_id for item in result.documents] == ["ordinary"]
    else:
        assert result.document_id == "ordinary"
    if operation in {"archive", "unarchive"}:
        with factory() as session:
            row = session.get(DocumentTable, "ordinary")
            assert row.archived is (operation == "archive")
            assert row.revision == 1
    if operation == "delete":
        assert result.state == "blocked"
        assert result.failure_reason == "DOCUMENT_DELETION_POLICY_UNAVAILABLE"
        repeated = invoke(reader, operation)
        assert repeated.request_id == result.request_id


@pytest.mark.parametrize("operation", ["list", "read", "archive", "unarchive", "delete"])
def test_actual_builder_source_is_hidden_without_prefix(database, operation):
    reader, factory = database
    if operation == "list":
        assert "builder" not in [item.document_id for item in invoke(reader, operation).documents]
    else:
        with pytest.raises(KnoraError, match="DOCUMENT_NOT_FOUND"):
            invoke(reader, operation, "builder")
    with factory() as session:
        assert session.get(DocumentTable, "builder").revision == 0
        assert (
            session.query(DocumentDeletionRequestTable).filter_by(document_id="builder").count()
            == 0
        )


@pytest.mark.parametrize("operation", ["list", "read", "archive", "unarchive", "delete"])
def test_foreign_workspace_document_remains_inaccessible(database, operation):
    reader, factory = database
    if operation == "list":
        assert "foreign" not in [item.document_id for item in invoke(reader, operation).documents]
    else:
        with pytest.raises(KnoraError, match="DOCUMENT_NOT_FOUND"):
            invoke(reader, operation, "foreign")
    with factory() as session:
        assert session.get(DocumentTable, "foreign").revision == 0
        assert (
            session.query(DocumentDeletionRequestTable).filter_by(document_id="foreign").count()
            == 0
        )


@pytest.mark.parametrize("operation", ["list_documents", "read_document"])
def test_mismatched_principal_is_rejected(database, operation):
    reader, _ = database
    args = dict(workspace_id="w1", principal=WorkspacePrincipal("w2", "owner"))
    if operation == "read_document":
        args["document_id"] = "ordinary"
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        getattr(reader, operation)(**args)
