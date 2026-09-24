from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace

import pytest

from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import (
    IngestionJobs,
    PdfSubmissionCommand,
    PdfSubmissionConfiguration,
    PdfSubmissionResult,
)
from knora.ingestion.object_store import ObjectMetadata
from knora.providers.embedding import EmbeddingConfiguration
from knora.workspaces.ports import WorkspaceAdmission


@dataclass
class RecordingObjectStore:
    puts: list[bytes] = field(default_factory=list)

    def put_stream(self, *, workspace_id: str, stream, media_type: str) -> ObjectMetadata:
        content = stream.read()
        self.puts.append(content)
        return ObjectMetadata(
            workspace_id=workspace_id,
            object_key="opaque/source-object",
            sha256=sha256(content).hexdigest(),
            byte_size=len(content),
            media_type=media_type,
        )


class StoreMustNotExecute:
    def authorize_workspace(self, *, workspace_id: str) -> None:
        raise AssertionError("workspace lookup happened after archived admission rejection")


class ReplayStoreMustNotStage(StoreMustNotExecute):
    def read_pdf_submission_replay(self, *, workspace_id: str, idempotency_key: str):
        return PdfSubmissionResult(
            ingestion_job_id="job-1",
            submission_outcome="idempotency_replay",
            status="queued",
            document_id="document-1",
            document_version_id="version-1",
            retained_object_key="opaque/source-object",
        )


class ArchivedAdmission:
    def admit(self, *, principal, operation: str, operation_id: str) -> None:
        raise KnoraError("WORKSPACE_ARCHIVED")


@dataclass
class RecordingAdmission:
    calls: list[tuple[str, str]] = field(default_factory=list)

    def admit(self, *, principal, operation: str, operation_id: str) -> WorkspaceAdmission:
        self.calls.append((operation, operation_id))
        return WorkspaceAdmission(
            id="admission-1",
            workspace_id=principal.workspace_id,
            operation=operation,
            operation_id=operation_id,
            admitted_at=datetime.now(UTC),
        )


class SubmissionStoreRecordingAdmission:
    def __init__(self) -> None:
        self.admission_id: str | None = None

    def authorize_workspace(self, *, workspace_id: str) -> None:
        return None

    def commit_pdf_submission(self, prepared, *, admission_id: str | None = None):
        self.admission_id = admission_id
        return PdfSubmissionResult(
            ingestion_job_id="job-1",
            submission_outcome="created",
            status="queued",
            document_id="document-1",
            document_version_id="version-1",
            retained_object_key=prepared.source_object.object_key,
        )


def test_pdf_submission_binds_its_admission_to_the_created_job() -> None:
    admission = RecordingAdmission()
    submission_store = SubmissionStoreRecordingAdmission()
    service = IngestionJobs(
        object_store=RecordingObjectStore(),
        store=submission_store,
        admission_store=admission,
    )

    service.submit_pdf(
        PdfSubmissionCommand(
            workspace_id="workspace-a",
            source_key="support/refunds",
            source_name="refunds.pdf",
            media_type="application/pdf",
            stream=BytesIO(b"%PDF-1.7\nfixture"),
            idempotency_key="upload-1",
            configuration=PdfSubmissionConfiguration.milestone_two(
                embedding_configuration=EmbeddingConfiguration.milestone_one_local()
            ),
        ),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="key-a"),
    )

    assert submission_store.admission_id == "admission-1"


def test_only_terminal_ingestion_statuses_close_linked_admissions() -> None:
    from knora.adapters.postgres.ingestion_jobs.coordination import (
        close_workspace_admissions_for_terminal_job,
    )

    class RecordingSession:
        def __init__(self) -> None:
            self.statements = []

        def execute(self, statement) -> None:
            self.statements.append(statement)

    session = RecordingSession()
    timestamp = datetime.now(UTC)

    close_workspace_admissions_for_terminal_job(
        session=session,
        job=SimpleNamespace(id="job-1", status="retry_scheduled"),
        terminal_at=timestamp,
    )
    assert session.statements == []

    close_workspace_admissions_for_terminal_job(
        session=session,
        job=SimpleNamespace(id="job-1", status="succeeded"),
        terminal_at=timestamp,
    )
    assert len(session.statements) == 1


def test_archived_workspace_rejects_pdf_before_workspace_lookup_or_staging() -> None:
    object_store = RecordingObjectStore()
    service = IngestionJobs(
        object_store=object_store,
        store=StoreMustNotExecute(),
        admission_store=ArchivedAdmission(),
    )

    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="support/refunds",
                source_name="refunds.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nfixture"),
                idempotency_key="upload-1",
                configuration=PdfSubmissionConfiguration.milestone_two(
                    embedding_configuration=EmbeddingConfiguration.milestone_one_local()
                ),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="key-a"),
        )

    assert object_store.puts == []


def test_invalid_pdf_submission_does_not_persist_an_admission() -> None:
    admission = RecordingAdmission()
    service = IngestionJobs(
        object_store=RecordingObjectStore(),
        store=StoreMustNotExecute(),
        admission_store=admission,
    )

    with pytest.raises(KnoraError, match="INVALID_SOURCE_KEY"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="",
                source_name="refunds.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nfixture"),
                idempotency_key="upload-1",
                configuration=PdfSubmissionConfiguration.milestone_two(
                    embedding_configuration=EmbeddingConfiguration.milestone_one_local()
                ),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="key-a"),
        )

    assert admission.calls == []


def test_archived_workspace_returns_existing_pdf_replay_without_staging() -> None:
    object_store = RecordingObjectStore()
    service = IngestionJobs(
        object_store=object_store,
        store=ReplayStoreMustNotStage(),
        admission_store=ArchivedAdmission(),
    )

    result = service.submit_pdf(
        PdfSubmissionCommand(
            workspace_id="workspace-a",
            source_key="support/refunds",
            source_name="refunds.pdf",
            media_type="application/pdf",
            stream=BytesIO(b"%PDF-1.7\nfixture"),
            idempotency_key="upload-1",
            configuration=PdfSubmissionConfiguration.milestone_two(
                embedding_configuration=EmbeddingConfiguration.milestone_one_local()
            ),
        ),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="key-a"),
    )

    assert result.submission_outcome == "idempotency_replay"
    assert object_store.puts == []


class ProviderMustNotRun:
    def embed(self, *_args, **_kwargs):
        raise AssertionError("provider called for archived Workspace")


class AnswerStoreMustNotRun:
    def retrieve_candidates(self, **_kwargs):
        raise AssertionError("retrieval lookup happened for archived Workspace")


@pytest.mark.asyncio
async def test_archived_workspace_rejects_question_before_provider_or_retrieval() -> None:
    service = AnswerQuestion(
        embedding_provider=ProviderMustNotRun(),
        generation_provider=ProviderMustNotRun(),
        store=AnswerStoreMustNotRun(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        admission_store=ArchivedAdmission(),
    )

    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="What changed?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="key-a"),
        )
