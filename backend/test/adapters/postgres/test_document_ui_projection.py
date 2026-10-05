"""Display projections exercise real persisted source and retrieval state."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from fixtures.issue_18_acceptance import pdf_metadata, pdf_success
from sqlalchemy import event, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from knora import main
from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkTable,
    DocumentTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IngestionJobTable,
    RetrievalV2CutoverTable,
    WorkspaceTable,
)
from knora.answering.stores import RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.documents import DocumentLifecycleService
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    CanonicalFailureV1,
    ClaimedAttempt,
    ClaimOperationId,
    FailureCauseV1,
    FinalizationApplied,
    TransitionOperationId,
)
from knora.ingestion.jobs import PdfSubmissionConfiguration, PreparedPdfSubmission
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.main import create_app
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


@pytest.fixture
def database():
    # Roll back all data (including isolated queue clearing) after each projection case.
    engine = SessionFactory.kw["bind"]
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        transaction = connection.begin()
        connection.execute(
            text(
                "TRUNCATE TABLE workspace_admissions, reprocess_audit_records, "
                "idempotency_records, ingestion_job_attempts, ingestion_jobs"
            )
        )
        factory = sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        workspace_id = str(uuid4())
        with factory.begin() as session:
            session.add(WorkspaceTable(id=workspace_id, name="UI projection"))
        yield factory, workspace_id, WorkspacePrincipal(workspace_id, "projection")
        transaction.rollback()


def ingest_text(factory, workspace_id, principal, source_key="guide"):
    return IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(factory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key=source_key,
            source_name="guide.md",
            media_type="text/markdown",
            raw_content=b"# Guide\n\nA useful guide to refunds.\n",
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        principal,
    )


def submit_pdf(factory, workspace_id, label):
    configuration = PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    metadata = pdf_metadata(
        workspace_id=workspace_id, object_key=uuid4().hex, raw=b"%PDF-1.7\n" + label.encode()
    )
    result = PostgresIngestionJobStore(factory).commit_pdf_submission(
        PreparedPdfSubmission(
            workspace_id=workspace_id,
            source_key="pdf-guide",
            source_name="guide.pdf",
            source_object=metadata,
            content_fingerprint=f"{workspace_id}:{label}",
            idempotency_operation="submit_pdf",
            idempotency_key=uuid4().hex,
            idempotency_expires_at=datetime.now(UTC) + timedelta(hours=24),
            configuration=configuration,
        )
    )
    return result, configuration


def claim(factory):
    result = PostgresIngestionJobStore(factory).claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="ui-test",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(result, ClaimedAttempt)
    return result


def test_previous_served_version_retains_last_success_and_blocked_deletion_after_fresh_get(
    database,
):
    factory, workspace_id, principal = database
    successful, configuration = submit_pdf(factory, workspace_id, "success")
    store = PostgresIngestionJobStore(factory)
    assert isinstance(
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim(factory),
            success=pdf_success(configuration),
        ),
        FinalizationApplied,
    )
    with factory() as session:
        successful_job = session.get(IngestionJobTable, successful.ingestion_job_id)
        successful_timestamp = successful_job.terminal_at
    failed, _ = submit_pdf(factory, workspace_id, "failure")
    assert isinstance(
        store.finalize_terminal_failure(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim(factory),
            failure=CanonicalFailureV1(
                cause=FailureCauseV1.INVALID_INPUT,
                safe_code="invalid_input",
                failure_reason="terminal_input",
                cause_version="failure-causes-v1",
                mapping_version="cause-mapping-v1",
            ),
        ),
        FinalizationApplied,
    )
    reader = PostgresDocumentReader(factory)
    deletion = DocumentLifecycleService(reader).request_deletion(
        workspace_id, successful.document_id, principal, "delete-ui"
    )
    projection = PostgresDocumentReader(factory).read_document(
        workspace_id=workspace_id, document_id=successful.document_id, principal=principal
    )
    assert projection.serving_state == "previous"
    assert projection.served_document_version_id == successful.document_version_id
    assert projection.last_processed_at == successful_timestamp
    assert projection.ingestion_job_id == failed.ingestion_job_id
    assert projection.ingestion_status == "failed"
    assert projection.answer_availability == "available"
    assert projection.deletion_request.request_id == deletion.request_id
    assert projection.deletion_request.state == "blocked"
    assert projection.deletion_request.failure_reason == "DOCUMENT_DELETION_POLICY_UNAVAILABLE"

    key = "ui-document-key"
    app = create_app(
        api_key_authenticator=ApiKeyAuthenticator(
            (
                ApiCredential(
                    key_id="ui-key",
                    key_hash=hash_api_key(key),
                    workspace_id=workspace_id,
                    enabled=True,
                ),
            )
        ),
        document_reader=PostgresDocumentReader(factory),
    )
    response = TestClient(app).get(
        f"/v1/workspaces/{workspace_id}/documents/{successful.document_id}",
        headers={"X-API-Key": key},
    )
    assert response.status_code == 200
    assert response.json()["deletion_request"]["state"] == "blocked"
    assert response.json()["served_document_version_id"] == successful.document_version_id
    assert datetime.fromisoformat(response.json()["last_processed_at"]) == successful_timestamp


def test_latest_successful_timestamp_for_served_version_is_used(database):
    factory, workspace_id, principal = database
    first, configuration = submit_pdf(factory, workspace_id, "same")
    store = PostgresIngestionJobStore(factory)
    store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim(factory),
        success=pdf_success(configuration),
    )
    # A distinct derivation of the same source version gets a separate successful Job.
    configuration = replace(
        configuration,
        chunking_configuration=replace(
            configuration.chunking_configuration, id="chunking-ui-second-success"
        ),
    )
    metadata = pdf_metadata(
        workspace_id=workspace_id, object_key=uuid4().hex, raw=b"%PDF-1.7\nsame"
    )
    second = store.commit_pdf_submission(
        PreparedPdfSubmission(
            workspace_id=workspace_id,
            source_key="pdf-guide",
            source_name="guide.pdf",
            source_object=metadata,
            content_fingerprint=f"{workspace_id}:same-v2",
            idempotency_operation="submit_pdf",
            idempotency_key=uuid4().hex,
            idempotency_expires_at=datetime.now(UTC) + timedelta(hours=24),
            configuration=configuration,
        )
    )
    store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim(factory),
        success=pdf_success(configuration),
    )
    with factory() as session:
        last = session.get(IngestionJobTable, second.ingestion_job_id).terminal_at
    projection = PostgresDocumentReader(factory).read_document(
        workspace_id=workspace_id, document_id=first.document_id, principal=principal
    )
    assert second.document_version_id == first.document_version_id
    assert projection.last_processed_at == last


@pytest.mark.parametrize(
    "state",
    [
        "ready",
        "archived_document",
        "archived_workspace",
        "empty",
        "incompatible_document",
        "incompatible_corpus",
    ],
)
def test_answer_availability_uses_actual_retrieval_eligibility(database, state):
    factory, workspace_id, principal = database
    result = ingest_text(factory, workspace_id, principal)
    other = (
        ingest_text(factory, workspace_id, principal, "incompatible")
        if (state == "incompatible_corpus")
        else None
    )
    with factory.begin() as session:
        if state == "archived_document":
            session.get(DocumentTable, result.document_id).archived = True
        elif state == "archived_workspace":
            session.get(WorkspaceTable, workspace_id).archived = True
        elif state == "empty":
            # Completed pointer alone cannot supply any evidence.
            session.execute(
                ChunkEmbeddingTable.__table__.delete().where(
                    ChunkEmbeddingTable.embedding_set_id == result.embedding_set_id
                )
            )
            session.execute(
                ChunkTable.__table__.delete().where(ChunkTable.chunk_set_id == result.chunk_set_id)
            )
        elif state in {"incompatible_document", "incompatible_corpus"}:
            foreign_config = EmbeddingConfigurationTable(
                id="embedding-ui-incompatible",
                provider="deterministic-local",
                model="other",
                dimensions=1536,
                distance_metric="cosine",
            )
            session.add(foreign_config)
            session.flush()
            target = other or result
            other_set = EmbeddingSetTable(
                id=str(uuid4()),
                chunk_set_id=target.chunk_set_id,
                embedding_configuration_id=foreign_config.id,
                status="completed",
            )
            session.add(other_set)
            session.flush()
            document = session.get(DocumentTable, target.document_id)
            document.active_embedding_set_id = other_set.id
            document.active_embedding_configuration_id = foreign_config.id
    projection = PostgresDocumentReader(factory).read_document(
        workspace_id=workspace_id, document_id=result.document_id, principal=principal
    )
    assert projection.serving_state == "current"
    assert projection.served_document_version_id == result.document_version_id
    assert projection.answer_availability == ("available" if state == "ready" else "unavailable")
    # Synchronous history lacks a durable successful Job timestamp.
    assert projection.last_processed_at is None


def test_no_active_set_is_unavailable_and_never_fabricates_processing_history(database):
    factory, workspace_id, principal = database
    queued, _ = submit_pdf(factory, workspace_id, "queued")
    projection = PostgresDocumentReader(factory).read_document(
        workspace_id=workspace_id, document_id=queued.document_id, principal=principal
    )
    assert projection.serving_state == "unavailable"
    assert projection.served_document_version_id is None
    assert projection.last_processed_at is None
    assert projection.answer_availability == "unavailable"


@pytest.mark.parametrize("hybrid", [False, True])
def test_zero_vectors_do_not_make_vector_only_evidence_available(database, hybrid):
    factory, workspace_id, principal = database
    result = ingest_text(factory, workspace_id, principal)
    with factory.begin() as session:
        session.execute(
            update(ChunkEmbeddingTable)
            .where(ChunkEmbeddingTable.embedding_set_id == result.embedding_set_id)
            .values(embedding=[0.0] * 1536)
        )
    reader = PostgresDocumentReader(
        factory,
        deployed_retrieval_configuration=(
            RetrievalConfiguration.milestone_three_hybrid()
            if hybrid
            else RetrievalConfiguration.milestone_one()
        ),
    )
    projection = reader.read_document(
        workspace_id=workspace_id, document_id=result.document_id, principal=principal
    )
    assert projection.answer_availability == ("available" if hybrid else "unavailable")


def test_v2_cutover_gates_availability_using_deployed_retrieval_configuration(database):
    factory, workspace_id, principal = database
    result = ingest_text(factory, workspace_id, principal)
    reader = PostgresDocumentReader(
        factory,
        deployed_retrieval_configuration=RetrievalConfiguration.milestone_three_vector_v2(
            min_similarity=0.657410732025
        ),
    )
    assert (
        reader.read_document(
            workspace_id=workspace_id, document_id=result.document_id, principal=principal
        ).answer_availability
        == "unavailable"
    )
    with factory.begin() as session:
        session.add(
            RetrievalV2CutoverTable(
                workspace_id=workspace_id,
                embedding_configuration_id="embedding-local-m1-v2",
                population_digest="a" * 64,
                status="completed",
            )
        )
    assert (
        reader.read_document(
            workspace_id=workspace_id, document_id=result.document_id, principal=principal
        ).answer_availability
        == "available"
    )


def test_http_default_reader_uses_the_deployed_retrieval_configuration(database, monkeypatch):
    factory, workspace_id, principal = database
    result = ingest_text(factory, workspace_id, principal)
    monkeypatch.setattr(main, "SessionFactory", factory)
    monkeypatch.setattr(main.settings, "retrieval_configuration_id", "retrieval-m3-vector-v2")
    monkeypatch.setattr(main.settings, "vector_min_similarity", 0.657410732025)
    key = "deployment-reader-key"
    app = create_app(
        api_key_authenticator=ApiKeyAuthenticator(
            (
                ApiCredential(
                    key_id="deployment-key",
                    key_hash=hash_api_key(key),
                    workspace_id=workspace_id,
                    enabled=True,
                ),
            )
        )
    )
    response = TestClient(app).get(
        f"/v1/workspaces/{workspace_id}/documents/{result.document_id}", headers={"X-API-Key": key}
    )
    assert response.status_code == 200
    assert response.json()["answer_availability"] == "unavailable"


def test_document_reader_denies_cross_workspace_before_lookup():
    def unavailable_factory():
        raise AssertionError("Unauthorized document lookup")

    reader = PostgresDocumentReader(unavailable_factory)
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        reader.read_document(
            workspace_id="other", document_id="secret", principal=WorkspacePrincipal("owned", "key")
        )


@pytest.mark.parametrize("list_read", [False, True])
def test_document_read_keeps_one_snapshot_across_concurrent_archive_and_deletion(list_read):
    # A committed fixture and separate writer prove the isolation of the real reader factory.
    workspace_id = str(uuid4())
    principal = WorkspacePrincipal(workspace_id, "concurrent")
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Concurrent projection"))
    result = ingest_text(SessionFactory, workspace_id, principal)
    reader = PostgresDocumentReader(SessionFactory)
    engine = SessionFactory.kw["bind"]
    changed = False

    def archive_after_document_select(connection, cursor, statement, parameters, context, many):
        nonlocal changed
        if changed or not statement.startswith("SELECT documents."):
            return
        changed = True
        with SessionFactory.begin() as writer:
            writer.execute(
                update(WorkspaceTable)
                .where(WorkspaceTable.id == workspace_id)
                .values(archived=True)
            )
        reader.request_deletion(
            workspace_id=workspace_id,
            document_id=result.document_id,
            principal=principal,
            idempotency_key="concurrent-delete",
        )

    event.listen(engine, "after_cursor_execute", archive_after_document_select)
    try:
        if list_read:
            projection = reader.list_documents(
                workspace_id=workspace_id, principal=principal
            ).documents[0]
        else:
            projection = reader.read_document(
                workspace_id=workspace_id, document_id=result.document_id, principal=principal
            )
        assert changed
        assert projection.answer_availability == "available"
        assert projection.deletion_request is None
    finally:
        event.remove(engine, "after_cursor_execute", archive_after_document_select)
    fresh = reader.read_document(
        workspace_id=workspace_id, document_id=result.document_id, principal=principal
    )
    assert fresh.answer_availability == "unavailable"
    assert fresh.deletion_request.state == "blocked"


def test_archive_snapshot_conflict_returns_existing_concurrent_update_error():
    workspace_id = str(uuid4())
    principal = WorkspacePrincipal(workspace_id, "archive-conflict")
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Archive conflict"))
    result = ingest_text(SessionFactory, workspace_id, principal)
    engine = SessionFactory.kw["bind"]
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        transaction = connection.begin()
        # Establish the reader snapshot before the overlapping writer commits.
        assert (
            connection.scalar(
                select(DocumentTable.revision).where(DocumentTable.id == result.document_id)
            )
            == 1
        )
        with SessionFactory.begin() as writer:
            writer.execute(
                update(DocumentTable)
                .where(DocumentTable.id == result.document_id)
                .values(archived=True, revision=2)
            )
        factory = sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            with pytest.raises(KnoraError, match="DOCUMENT_CONCURRENTLY_UPDATED"):
                DocumentLifecycleService(PostgresDocumentReader(factory)).archive(
                    workspace_id, result.document_id, principal, expected_revision=1
                )
        finally:
            transaction.rollback()


def test_archive_does_not_mask_other_database_failures_as_revision_conflicts():
    error = OperationalError("connection", {}, psycopg.OperationalError("connection unavailable"))

    class UnavailableFactory:
        def begin(self):
            raise error

    with pytest.raises(OperationalError) as raised:
        DocumentLifecycleService(PostgresDocumentReader(UnavailableFactory())).archive(
            "owned", "document", WorkspacePrincipal("owned", "key"), expected_revision=0
        )
    assert raised.value is error


def test_archive_and_unarchive_preserve_revision_and_idempotent_behavior(database):
    factory, workspace_id, principal = database
    result = ingest_text(factory, workspace_id, principal)
    service = DocumentLifecycleService(PostgresDocumentReader(factory))
    archived = service.archive(workspace_id, result.document_id, principal, 1)
    replayed = service.archive(workspace_id, result.document_id, principal, 2)
    assert archived.archived is True
    assert archived.revision == replayed.revision == 2
    assert replayed.answer_availability == "unavailable"
    restored = service.unarchive(workspace_id, result.document_id, principal, 2)
    assert restored.archived is False
    assert restored.revision == 3
    assert restored.answer_availability == "available"
    with pytest.raises(KnoraError, match="DOCUMENT_CONCURRENTLY_UPDATED"):
        service.archive(workspace_id, result.document_id, principal, 2)
