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
from knora.ingestion.documents import DocumentLifecycleService, DocumentProjection
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.jobs import (
    IngestionJobs,
    PdfSubmissionCommand,
    PdfSubmissionConfiguration,
    PdfSubmissionResult,
    ReprocessContext,
    ReprocessDocumentVersionCommand,
)
from knora.ingestion.module import IngestDocument
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.processing import ChunkingConfiguration
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


class FailingReprocessObjectStore:
    def head(self, **_kwargs):
        raise RuntimeError("source head failed")


class ReprocessStoreForFailure:
    def authorize_workspace(self, *, workspace_id: str) -> None:
        del workspace_id

    def read_reprocess_context(self, **_kwargs):
        configuration = PdfSubmissionConfiguration.milestone_two(
            embedding_configuration=EmbeddingConfiguration.milestone_one_local()
        )
        return ReprocessContext(
            workspace_id="workspace-a",
            document_id="document-1",
            document_version_id="version-1",
            source_object=ObjectMetadata(
                workspace_id="workspace-a",
                object_key="opaque/source-object",
                sha256="a" * 64,
                byte_size=10,
                media_type="application/pdf",
            ),
            configuration=configuration,
            config_source_job_id=None,
            prior_job_id=None,
        )


class ReprocessStoreContextFailure(ReprocessStoreForFailure):
    def read_reprocess_context(self, **_kwargs):
        raise RuntimeError("database read failed")


def test_reprocess_database_failure_closes_admission_before_archived_retry() -> None:
    admission = ArchiveAfterClosedAdmission()
    service = IngestionJobs(
        object_store=FailingReprocessObjectStore(),
        store=ReprocessStoreContextFailure(),
        admission_store=admission,
    )
    command = ReprocessDocumentVersionCommand(
        workspace_id="workspace-a",
        document_version_id="version-1",
        config_mode="current",
        config_source_job_id=None,
        idempotency_key="reprocess-db-failure-1",
    )

    with pytest.raises(RuntimeError, match="database read failed"):
        service.reprocess_document_version(command, WorkspacePrincipal("workspace-a", "alice"))
    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        service.reprocess_document_version(command, WorkspacePrincipal("workspace-a", "alice"))
    assert admission.closed == [("admission-1", "now")]


def test_reprocess_failure_closes_admission_before_archived_retry() -> None:
    admission = ArchiveAfterClosedAdmission()
    service = IngestionJobs(
        object_store=FailingReprocessObjectStore(),
        store=ReprocessStoreForFailure(),
        admission_store=admission,
    )
    command = ReprocessDocumentVersionCommand(
        workspace_id="workspace-a",
        document_version_id="version-1",
        config_mode="current",
        config_source_job_id=None,
        idempotency_key="reprocess-failure-1",
    )

    with pytest.raises(KnoraError, match="SOURCE_OBJECT_NOT_AVAILABLE"):
        service.reprocess_document_version(command, WorkspacePrincipal("workspace-a", "alice"))
    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        service.reprocess_document_version(command, WorkspacePrincipal("workspace-a", "alice"))
    assert admission.closed == [("admission-1", "now")]


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
    closed: list[tuple[str, str]] = field(default_factory=list)

    def admit(self, *, principal, operation: str, operation_id: str) -> WorkspaceAdmission:
        self.calls.append((operation, operation_id))
        return WorkspaceAdmission(
            id="admission-1",
            workspace_id=principal.workspace_id,
            operation=operation,
            operation_id=operation_id,
            admitted_at=datetime.now(UTC),
        )

    def close(self, *, admission_id: str, terminal_at: datetime | None = None) -> None:
        self.closed.append((admission_id, "terminal" if terminal_at is not None else "now"))


class ArchiveAfterClosedAdmission(RecordingAdmission):
    archived = False

    def admit(self, *, principal, operation: str, operation_id: str) -> WorkspaceAdmission:
        if self.archived:
            raise KnoraError("WORKSPACE_ARCHIVED")
        return super().admit(
            principal=principal, operation=operation, operation_id=operation_id
        )

    def close(self, *, admission_id: str, terminal_at: datetime | None = None) -> None:
        super().close(admission_id=admission_id, terminal_at=terminal_at)
        self.archived = True


class FailingPdfObjectStore(RecordingObjectStore):
    def put_stream(self, *, workspace_id: str, stream, media_type: str) -> ObjectMetadata:
        del workspace_id, stream, media_type
        raise RuntimeError("staging failed")


class AuthorizingPdfStore:
    def authorize_workspace(self, *, workspace_id: str) -> None:
        del workspace_id


def test_pdf_failure_closes_admission_before_archived_retry() -> None:
    admission = ArchiveAfterClosedAdmission()
    service = IngestionJobs(
        object_store=FailingPdfObjectStore(),
        store=AuthorizingPdfStore(),
        admission_store=admission,
    )
    command = PdfSubmissionCommand(
        workspace_id="workspace-a",
        source_key="support/refunds",
        source_name="refunds.pdf",
        media_type="application/pdf",
        stream=BytesIO(b"%PDF-1.7\nfixture"),
        idempotency_key="upload-failure-1",
        configuration=PdfSubmissionConfiguration.milestone_two(
            embedding_configuration=EmbeddingConfiguration.milestone_one_local()
        ),
    )

    with pytest.raises(RuntimeError, match="staging failed"):
        service.submit_pdf(command, WorkspacePrincipal("workspace-a", "alice"))
    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        service.submit_pdf(command, WorkspacePrincipal("workspace-a", "alice"))
    assert admission.closed == [("admission-1", "now")]


@pytest.mark.parametrize("ingestion_job_id", [None, "job-1"])
def test_admission_store_rejects_closed_retry_after_archive(ingestion_job_id) -> None:
    """A terminal request cannot reuse its stale admission to start a new effect."""

    from knora.adapters.postgres.workspace_admission import PostgresWorkspaceAdmissionStore

    class Session:
        def __init__(self) -> None:
            self.workspace = SimpleNamespace(id="workspace-a", archived=True)
            self.admission = SimpleNamespace(
                id="admission-1",
                workspace_id="workspace-a",
                operation="ask_question",
                operation_id="request-1",
                admitted_at=datetime.now(UTC),
                ingestion_job_id=ingestion_job_id,
                terminal_at=datetime.now(UTC),
            )

        def scalar(self, statement):
            entity = statement.column_descriptions[0].get("entity")
            return (
                self.workspace
                if entity is not None and entity.__name__ == "WorkspaceTable"
                else self.admission
            )

    class SessionFactory:
        def begin(self):
            class Context:
                def __enter__(self):
                    self.session = Session()
                    return self.session

                def __exit__(self, *_args):
                    return False

            return Context()

    with pytest.raises(KnoraError, match="WORKSPACE_ARCHIVED"):
        PostgresWorkspaceAdmissionStore(SessionFactory()).admit(
            principal=WorkspacePrincipal("workspace-a", "alice"),
            operation="ask_question",
            operation_id="request-1",
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


class _DocumentAdmissionProcessor:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def process(self, **_kwargs):
        if self.fail:
            raise RuntimeError("processor failed")
        return SimpleNamespace(
            normalized_content="content",
            normalized_content_checksum="checksum",
            normalized_token_count=1,
            chunks=(
                SimpleNamespace(
                    ordinal=0,
                    heading_path=(),
                    start_line=1,
                    end_line=1,
                    content="content",
                    content_checksum="checksum",
                    token_count=1,
                ),
            ),
        )


class _DocumentAdmissionEmbedding:
    def embed(self, texts, configuration):
        from knora.providers.embedding import EmbeddingBatch

        return EmbeddingBatch(
            vectors=tuple(tuple([0.0] * configuration.dimensions) for _ in texts),
            provider=configuration.provider,
            model=configuration.model,
        )

    embed_documents = embed


class _DocumentAdmissionStore:
    def authorize_workspace(self, *, workspace_id: str) -> None:
        del workspace_id

    def read_document_head(self, *, workspace_id: str, source_key: str):
        del workspace_id, source_key
        return None

    def commit_derivation(self, *, prepared, expected_revision: int):
        del prepared, expected_revision
        return "committed"


class _QuestionAdmissionEmbedding:
    def embed(self, texts, configuration):
        from knora.providers.embedding import EmbeddingBatch

        return EmbeddingBatch(
            vectors=tuple(tuple([0.0] * configuration.dimensions) for _ in texts),
            provider=configuration.provider,
            model=configuration.model,
        )

    embed_queries = embed


class _QuestionAdmissionStore:
    def retrieve_candidates(self, **_kwargs):
        return ()

    def persist_trace(self, _trace):
        return "trace-1"


@pytest.mark.asyncio
async def test_sync_question_closes_admission_on_refusal() -> None:
    admission = RecordingAdmission()
    service = AnswerQuestion(
        embedding_provider=_QuestionAdmissionEmbedding(),
        generation_provider=ProviderMustNotRun(),
        store=_QuestionAdmissionStore(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        admission_store=admission,
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="What changed?"),
        WorkspacePrincipal("workspace-a", "alice"),
    )

    assert result.decision == "REFUSAL"
    assert admission.closed == [("admission-1", "now")]


class _LifecycleAdmissionDelegate:
    def archive(self, **kwargs):
        return DocumentProjection(
            "document-1", kwargs["workspace_id"], "source", "source.md", False, 0
        )

    def unarchive(self, **kwargs):
        return DocumentProjection(
            "document-1", kwargs["workspace_id"], "source", "source.md", False, 0
        )

    def request_deletion(self, **kwargs):
        return SimpleNamespace(
            request_id="request-1", document_id=kwargs["document_id"], state="requested"
        )


def test_document_lifecycle_closes_admission_after_success() -> None:
    admission = RecordingAdmission()
    service = DocumentLifecycleService(_LifecycleAdmissionDelegate(), admission_store=admission)

    service.archive(
        "workspace-a",
        "document-1",
        WorkspacePrincipal("workspace-a", "alice", ("documents:write",)),
    )

    assert admission.closed == [("admission-1", "now")]


@pytest.mark.parametrize(
    "processor", [_DocumentAdmissionProcessor(), _DocumentAdmissionProcessor(fail=True)]
)
def test_sync_document_closes_admission_on_success_or_exception(processor) -> None:
    admission = RecordingAdmission()
    service = IngestDocument(
        processor=processor,
        embedding_provider=_DocumentAdmissionEmbedding(),
        store=_DocumentAdmissionStore(),
        admission_store=admission,
    )
    command = IngestDocumentCommand(
        workspace_id="workspace-a",
        source_key="support/refunds",
        source_name="refunds.md",
        media_type="text/markdown",
        raw_content=b"content",
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    if processor.fail:
        with pytest.raises(RuntimeError, match="processor failed"):
            service.execute(command, WorkspacePrincipal("workspace-a", "alice"))
    else:
        assert service.execute(command, WorkspacePrincipal("workspace-a", "alice")) == "committed"
    assert admission.closed == [("admission-1", "now")]
