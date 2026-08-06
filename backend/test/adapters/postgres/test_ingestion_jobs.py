from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    IdempotencyRecordTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import PdfSubmissionConfiguration, PreparedPdfSubmission
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration


def prepared_submission(
    workspace_id: str,
    *,
    raw_sha256: str = "a" * 64,
    object_key: str | None = None,
    idempotency_key: str = "request-1",
    chunking_configuration_id: str = "chunking-m2-pdf-v1",
) -> PreparedPdfSubmission:
    configuration = PdfSubmissionConfiguration(
        parser_configuration_id="pdf-parser-pypdf-m2-v1",
        normalizer_configuration_id="pdf-normalizer-m2-v1",
        chunking_configuration=ChunkingConfiguration(
            id=chunking_configuration_id,
            parser_version="pypdf-baseline-v1",
            chunker_version="page-block-v1",
            tokenizer_name="cl100k_base",
            tokenizer_version="tiktoken-0.12.0",
            target_tokens=500,
            overlap_tokens=75,
            max_tokens=650,
        ),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    fingerprint = "\n".join(
        (
            workspace_id,
            "support/refund-policy",
            raw_sha256,
            configuration.parser_configuration_id,
            configuration.normalizer_configuration_id,
            configuration.chunking_configuration.id,
            configuration.embedding_configuration.id,
        )
    )
    return PreparedPdfSubmission(
        workspace_id=workspace_id,
        source_key="support/refund-policy",
        source_name="refund-policy.pdf",
        source_object=ObjectMetadata(
            workspace_id=workspace_id,
            object_key=object_key or uuid4().hex,
            sha256=raw_sha256,
            byte_size=123,
            media_type="application/pdf",
        ),
        content_fingerprint=fingerprint,
        idempotency_operation="submit_pdf",
        idempotency_key=idempotency_key,
        idempotency_expires_at=datetime.now(UTC) + timedelta(hours=24),
        configuration=configuration,
    )


def test_postgres_pdf_submission_commits_source_current_pointer_and_queued_job() -> None:
    workspace_id = f"test-m2-submit-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="PDF submission"))
    store = PostgresIngestionJobStore(SessionFactory)
    prepared = prepared_submission(workspace_id)

    result = store.commit_pdf_submission(prepared)

    assert result.submission_outcome == "created"
    assert result.status == "queued"
    assert result.retained_object_key == prepared.source_object.object_key
    with SessionFactory() as session:
        document = session.get(DocumentTable, result.document_id)
        version = session.get(DocumentVersionTable, result.document_version_id)
        source_object = session.scalar(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.document_version_id == result.document_version_id
            )
        )
        job = session.get(IngestionJobTable, result.ingestion_job_id)
        assert document.current_document_version_id == version.id
        assert document.revision == 1
        assert version.version_number == 1
        assert version.raw_sha256 == prepared.source_object.sha256
        assert version.normalized_content is None
        assert source_object.object_key == prepared.source_object.object_key
        assert source_object.workspace_id == workspace_id
        assert source_object.byte_size == 123
        assert job.target_document_version_id == version.id
        assert job.parser_configuration_id == "pdf-parser-pypdf-m2-v1"
        assert job.normalizer_configuration_id == "pdf-normalizer-m2-v1"
        assert job.chunking_configuration_id == "chunking-m2-pdf-v1"
        assert job.embedding_configuration_id == "embedding-local-m1-v2"
        assert job.attempt_count == 0
        assert job.max_attempts == 4


def test_postgres_pdf_submission_separates_replay_dedup_and_source_version_identity() -> None:
    workspace_id = f"test-m2-dedup-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="PDF deduplication"))
    store = PostgresIngestionJobStore(SessionFactory)
    first_input = prepared_submission(workspace_id)

    first = store.commit_pdf_submission(first_input)
    replay = store.commit_pdf_submission(
        prepared_submission(
            workspace_id,
            object_key=uuid4().hex,
            idempotency_key="request-1",
        )
    )
    deduplicated = store.commit_pdf_submission(
        prepared_submission(
            workspace_id,
            object_key=uuid4().hex,
            idempotency_key="request-2",
        )
    )
    changed_configuration = store.commit_pdf_submission(
        prepared_submission(
            workspace_id,
            object_key=uuid4().hex,
            idempotency_key="request-3",
            chunking_configuration_id="chunking-m2-pdf-v2",
        )
    )
    changed_source = store.commit_pdf_submission(
        prepared_submission(
            workspace_id,
            raw_sha256="b" * 64,
            object_key=uuid4().hex,
            idempotency_key="request-4",
        )
    )

    assert replay.submission_outcome == "idempotency_replay"
    assert replay.ingestion_job_id == first.ingestion_job_id
    assert replay.retained_object_key == first_input.source_object.object_key
    assert deduplicated.submission_outcome == "deduplicated"
    assert deduplicated.ingestion_job_id == first.ingestion_job_id
    assert changed_configuration.document_version_id == first.document_version_id
    assert changed_configuration.ingestion_job_id != first.ingestion_job_id
    assert changed_source.document_version_id != first.document_version_id
    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        changed_version = session.get(DocumentVersionTable, changed_source.document_version_id)
        assert document.current_document_version_id == changed_version.id
        assert changed_version.version_number == 2
        assert session.scalar(select(func.count()).select_from(DocumentVersionTable).where(
            DocumentVersionTable.document_id == first.document_id
        )) == 2
        assert session.scalar(select(func.count()).select_from(OriginalSourceObjectTable).where(
            OriginalSourceObjectTable.document_version_id == first.document_version_id
        )) == 1
        assert session.scalar(select(func.count()).select_from(IngestionJobTable).where(
            IngestionJobTable.document_id == first.document_id
        )) == 3
        assert session.scalar(select(func.count()).select_from(IdempotencyRecordTable).where(
            IdempotencyRecordTable.workspace_id == workspace_id
        )) == 4


def test_postgres_pdf_submission_rejects_idempotency_key_conflict_without_mutation() -> None:
    workspace_id = f"test-m2-conflict-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="PDF conflict"))
    store = PostgresIngestionJobStore(SessionFactory)
    first = store.commit_pdf_submission(prepared_submission(workspace_id))

    with pytest.raises(KnoraError, match="IDEMPOTENCY_KEY_CONFLICT"):
        store.commit_pdf_submission(
            prepared_submission(
                workspace_id,
                raw_sha256="b" * 64,
                idempotency_key="request-1",
            )
        )

    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        assert document.current_document_version_id == first.document_version_id
        assert session.scalar(select(func.count()).select_from(IngestionJobTable).where(
            IngestionJobTable.document_id == first.document_id
        )) == 1


def test_postgres_pdf_submission_converges_concurrent_duplicates_to_one_identity() -> None:
    workspace_id = f"test-m2-concurrent-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Concurrent PDF submission"))
    store = PostgresIngestionJobStore(SessionFactory)
    submissions = [
        prepared_submission(workspace_id, object_key=uuid4().hex)
        for _ in range(4)
    ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(store.commit_pdf_submission, submissions))

    assert {result.ingestion_job_id for result in results} == {results[0].ingestion_job_id}
    assert {result.document_version_id for result in results} == {
        results[0].document_version_id
    }
    assert [result.submission_outcome for result in results].count("created") == 1
    assert [result.submission_outcome for result in results].count("idempotency_replay") == 3
    with SessionFactory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(IngestionJobTable)
            .where(IngestionJobTable.workspace_id == workspace_id)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordTable)
            .where(IdempotencyRecordTable.workspace_id == workspace_id)
        ) == 1


def test_current_version_pointer_rejects_cross_document_assignment_and_hard_delete() -> None:
    workspace_id = f"test-m2-current-pointer-{uuid4()}"
    other_workspace_id = f"test-m2-current-pointer-other-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Current pointer constraints"))
        session.add(WorkspaceTable(id=other_workspace_id, name="Other Workspace"))
    store = PostgresIngestionJobStore(SessionFactory)
    first = store.commit_pdf_submission(prepared_submission(workspace_id))
    second_input = prepared_submission(
        workspace_id,
        object_key=uuid4().hex,
        idempotency_key="request-2",
    )
    second_input = PreparedPdfSubmission(
        workspace_id=second_input.workspace_id,
        source_key="support/other-policy",
        source_name="other-policy.pdf",
        source_object=second_input.source_object,
        content_fingerprint=second_input.content_fingerprint.replace(
            "support/refund-policy", "support/other-policy"
        ),
        idempotency_operation=second_input.idempotency_operation,
        idempotency_key=second_input.idempotency_key,
        idempotency_expires_at=second_input.idempotency_expires_at,
        configuration=second_input.configuration,
    )
    second = store.commit_pdf_submission(second_input)

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == first.document_id)
            .values(current_document_version_id=second.document_version_id)
        )

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.execute(
            delete(DocumentVersionTable).where(
                DocumentVersionTable.id == first.document_version_id
            )
        )

    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        assert document.current_document_version_id == first.document_version_id
        assert session.get(DocumentVersionTable, first.document_version_id) is not None

    with pytest.raises(IntegrityError), SessionFactory.begin() as session:
        session.add(
            OriginalSourceObjectTable(
                id=uuid4().hex,
                workspace_id=other_workspace_id,
                document_version_id=first.document_version_id,
                object_key=uuid4().hex,
                raw_sha256="f" * 64,
                byte_size=123,
                media_type="application/pdf",
            )
        )

    with SessionFactory() as session:
        job = session.get(IngestionJobTable, first.ingestion_job_id)
        source_object = session.get(OriginalSourceObjectTable, job.source_object_id)
        with pytest.raises(IntegrityError), SessionFactory.begin() as other_session:
            other_session.add(
                IngestionJobTable(
                    id=uuid4().hex,
                    workspace_id=other_workspace_id,
                    operation="submit_pdf",
                    document_id=job.document_id,
                    target_document_version_id=job.target_document_version_id,
                    source_object_id=source_object.id,
                    content_fingerprint="cross-workspace",
                    parser_configuration_id=job.parser_configuration_id,
                    normalizer_configuration_id=job.normalizer_configuration_id,
                    chunking_configuration_id=job.chunking_configuration_id,
                    embedding_configuration_id=job.embedding_configuration_id,
                    status="queued",
                    attempt_count=0,
                    max_attempts=4,
                )
            )


def test_postgres_pdf_submission_serializes_competing_source_versions() -> None:
    workspace_id = f"test-m2-competing-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Competing PDF versions"))
    store = PostgresIngestionJobStore(SessionFactory)
    base = store.commit_pdf_submission(prepared_submission(workspace_id))
    competing = (
        prepared_submission(
            workspace_id,
            raw_sha256="b" * 64,
            object_key=uuid4().hex,
            idempotency_key="request-2",
        ),
        prepared_submission(
            workspace_id,
            raw_sha256="c" * 64,
            object_key=uuid4().hex,
            idempotency_key="request-3",
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(store.commit_pdf_submission, competing))

    with SessionFactory() as session:
        versions = session.scalars(
            select(DocumentVersionTable)
            .where(DocumentVersionTable.document_id == base.document_id)
            .order_by(DocumentVersionTable.version_number)
        ).all()
        document = session.get(DocumentTable, base.document_id)
        assert [version.version_number for version in versions] == [1, 2, 3]
        assert len({version.id for version in versions}) == 3
        assert document.current_document_version_id in {
            result.document_version_id for result in results
        }


def test_source_version_and_current_pointer_roll_back_when_object_identity_conflicts() -> None:
    workspace_id = f"test-m2-source-rollback-{uuid4()}"
    object_key = uuid4().hex
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="PDF source rollback"))
    store = PostgresIngestionJobStore(SessionFactory)
    first = store.commit_pdf_submission(
        prepared_submission(workspace_id, object_key=object_key)
    )

    with pytest.raises(KnoraError, match="PERSISTENCE_OPERATION_FAILED"):
        store.commit_pdf_submission(
            prepared_submission(
                workspace_id,
                raw_sha256="b" * 64,
                object_key=object_key,
                idempotency_key="request-2",
            )
        )

    with SessionFactory() as session:
        document = session.get(DocumentTable, first.document_id)
        assert document.current_document_version_id == first.document_version_id
        assert session.scalar(
            select(func.count())
            .select_from(DocumentVersionTable)
            .where(DocumentVersionTable.document_id == first.document_id)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(IngestionJobTable)
            .where(IngestionJobTable.document_id == first.document_id)
        ) == 1


def test_raw_distinct_pdf_versions_can_share_a_normalized_checksum() -> None:
    workspace_id = f"test-m2-pdf-identity-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="PDF identity"))
    store = PostgresIngestionJobStore(SessionFactory)
    first = store.commit_pdf_submission(prepared_submission(workspace_id))
    second = store.commit_pdf_submission(
        prepared_submission(
            workspace_id,
            raw_sha256="b" * 64,
            object_key=uuid4().hex,
            idempotency_key="request-2",
        )
    )

    with SessionFactory.begin() as session:
        session.execute(
            update(DocumentVersionTable)
            .where(
                DocumentVersionTable.id.in_([
                    first.document_version_id,
                    second.document_version_id,
                ])
            )
            .values(
                normalized_content="same extracted text",
                normalized_content_checksum="d" * 64,
            )
        )

    with SessionFactory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(DocumentVersionTable)
            .where(
                DocumentVersionTable.document_id == first.document_id,
                DocumentVersionTable.normalized_content_checksum == "d" * 64,
            )
        ) == 2
