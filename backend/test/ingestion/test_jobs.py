from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import (
    IngestionJobs,
    PdfSubmissionCommand,
    PdfSubmissionConfiguration,
    PdfSubmissionResult,
    PreparedPdfSubmission,
    ReprocessContext,
    ReprocessDocumentVersionCommand,
    ReprocessResult,
)
from knora.ingestion.object_lifecycle import ObjectLifecycleWorkItem
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import PdfExtractionConfiguration
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration


@dataclass
class RecordingObjectStore:
    puts: list[tuple[str, str, bytes]] = field(default_factory=list)
    deletes: list[tuple[str, str]] = field(default_factory=list)

    def put_stream(self, *, workspace_id: str, stream, media_type: str) -> ObjectMetadata:
        chunks: list[bytes] = []
        while chunk := stream.read(3):
            chunks.append(chunk)
        content = b"".join(chunks)
        self.puts.append((workspace_id, media_type, content))
        return ObjectMetadata(
            workspace_id=workspace_id,
            object_key="opaque/source-object-1",
            sha256=sha256(content).hexdigest(),
            byte_size=len(content),
            media_type=media_type,
        )

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        self.deletes.append((workspace_id, object_key))


def test_deployed_reprocess_replaces_only_embedding_profile_and_binds_replay() -> None:
    class Source:
        def head(self, *, workspace_id: str, object_key: str) -> ObjectMetadata:
            assert workspace_id == "workspace-a"
            assert object_key == "source-key"
            return ObjectMetadata("workspace-a", "source-key", "a" * 64, 12, "application/pdf")

    class Store:
        def __init__(self) -> None:
            self.prepared = []
            self.replay_fingerprint = None
            self.replay_result = None

        def read_reprocess_replay(self, *, workspace_id, idempotency_key, request_fingerprint):
            if self.replay_fingerprint is not None:
                if request_fingerprint != self.replay_fingerprint:
                    raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
                return self.replay_result
            return None

        def authorize_workspace(self, *, workspace_id):
            assert workspace_id == "workspace-a"

        def read_reprocess_context(self, **kwargs):
            assert kwargs["config_mode"] == "deployed"
            return ReprocessContext(
                workspace_id="workspace-a",
                document_id="document-a",
                document_version_id="version-a",
                source_object=ObjectMetadata(
                    "workspace-a", "source-key", "a" * 64, 12, "application/pdf"
                ),
                configuration=PdfSubmissionConfiguration.milestone_two(
                    embedding_configuration=EmbeddingConfiguration.milestone_one_local()
                ),
                config_source_job_id=None,
                prior_job_id="old-job",
            )

        def commit_reprocess(self, prepared):
            self.prepared.append(prepared)
            self.replay_fingerprint = prepared.request_fingerprint
            self.replay_result = ReprocessResult(
                "new-job", "version-a", "idempotency_replay", "queued"
            )
            return ReprocessResult("new-job", "version-a", "created", "queued")

    store = Store()
    command = ReprocessDocumentVersionCommand(
        "workspace-a", "version-a", "deployed", None, "reindex-1"
    )
    principal = WorkspacePrincipal("workspace-a", "key-a")
    first_profile = EmbeddingConfiguration(
        "ollama-profile-a", "ollama", "qwen3-embedding:0.6b", 1024, "cosine"
    )
    second_profile = EmbeddingConfiguration(
        "ollama-profile-b", "ollama", "qwen3-embedding:0.6b", 1024, "cosine"
    )
    service = IngestionJobs(
        object_store=Source(), store=store, deployed_embedding_configuration=first_profile
    )

    assert service.reprocess_document_version(command, principal).status == "queued"
    assert service.reprocess_document_version(command, principal).outcome == "idempotency_replay"
    prepared = store.prepared[0]
    assert prepared.configuration.embedding_configuration == first_profile
    assert prepared.configuration.chunking_configuration.id == "chunking-m2-pdf-pypdf-6-14-2-v1"
    assert prepared.prior_job_id == "old-job"
    with pytest.raises(KnoraError, match="IDEMPOTENCY_KEY_CONFLICT"):
        IngestionJobs(
            object_store=Source(), store=store, deployed_embedding_configuration=second_profile
        ).reprocess_document_version(command, principal)
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.reprocess_document_version(command, WorkspacePrincipal("workspace-b", "key-b"))


def test_existing_reprocess_modes_keep_their_persisted_replay_fingerprint() -> None:
    current = ReprocessDocumentVersionCommand(
        "workspace-a", "version-a", "current", None, "key-1"
    )
    same_as_job = ReprocessDocumentVersionCommand(
        "workspace-a", "version-a", "same_as_job", "job-a", "key-2"
    )

    assert IngestionJobs._reprocess_fingerprint(command=current) == (
        "workspace-a\nversion-a\ncurrent\n"
    )
    assert IngestionJobs._reprocess_fingerprint(command=same_as_job) == (
        "workspace-a\nversion-a\nsame_as_job\njob-a"
    )


@dataclass
class InvalidMetadataObjectStore(RecordingObjectStore):
    def put_stream(self, *, workspace_id: str, stream, media_type: str) -> ObjectMetadata:
        return replace(
            super().put_stream(
                workspace_id=workspace_id,
                stream=stream,
                media_type=media_type,
            ),
            sha256="g" * 64,
        )


@dataclass
class RecordingSubmissionStore:
    result: PdfSubmissionResult
    prepared: list[PreparedPdfSubmission] = field(default_factory=list)
    authorized: list[str] = field(default_factory=list)

    def authorize_workspace(self, *, workspace_id: str) -> None:
        self.authorized.append(workspace_id)

    def commit_pdf_submission(self, prepared: PreparedPdfSubmission) -> PdfSubmissionResult:
        self.prepared.append(prepared)
        return self.result


@dataclass
class ReplayCheckingSubmissionStore(RecordingSubmissionStore):
    expected_fingerprint: str = ""
    replay: PdfSubmissionResult | None = None
    replay_fingerprints: list[str | None] = field(default_factory=list)

    def read_pdf_submission_replay(
        self,
        *,
        workspace_id: str,
        idempotency_key: str,
        content_fingerprint: str | None = None,
    ) -> PdfSubmissionResult | None:
        assert workspace_id == "workspace-a"
        assert idempotency_key == "request-1"
        self.replay_fingerprints.append(content_fingerprint)
        if content_fingerprint is not None and content_fingerprint != self.expected_fingerprint:
            raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
        return self.replay


@dataclass
class RecordingLifecycleMaintenance:
    items: list[ObjectLifecycleWorkItem] = field(default_factory=list)

    def enqueue(self, item: ObjectLifecycleWorkItem) -> ObjectLifecycleWorkItem:
        self.items.append(item)
        return item


class FailingLifecycleClock:
    def now(self) -> datetime:
        raise OSError("database clock unavailable")


@dataclass(frozen=True)
class FixedLifecycleClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


def configuration() -> PdfSubmissionConfiguration:
    return PdfSubmissionConfiguration(
        parser_configuration_id="pdf-parser-pypdf-m2-v1",
        normalizer_configuration_id="pdf-normalizer-m2-v1",
        chunking_configuration=ChunkingConfiguration(
            id="chunking-m2-pdf-v1",
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


def test_milestone_two_submission_snapshots_the_pinned_pdf_configuration() -> None:
    submission = PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    extraction = PdfExtractionConfiguration.milestone_two()

    assert submission.parser_configuration_id == ("pdf-parser-pypdf-6-14-2-plain-layout-v1")
    assert submission.chunking_configuration.id == "chunking-m2-pdf-pypdf-6-14-2-v1"
    assert submission.normalizer_configuration_id == extraction.normalizer_version
    assert submission.chunking_configuration.parser_version == extraction.parser_version
    assert submission.chunking_configuration.chunker_version == extraction.chunking_policy_version
    assert submission.chunking_configuration.tokenizer_name == extraction.tokenizer_name
    assert submission.chunking_configuration.tokenizer_version == extraction.tokenizer_version


def created_result() -> PdfSubmissionResult:
    return PdfSubmissionResult(
        ingestion_job_id="job-1",
        submission_outcome="created",
        status="queued",
        document_id="document-1",
        document_version_id="version-1",
        retained_object_key="opaque/source-object-1",
    )


def test_pdf_submission_streams_source_and_snapshots_immutable_identity() -> None:
    object_store = RecordingObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    service = IngestionJobs(object_store=object_store, store=submission_store)
    content = b"%PDF-1.7\nsmall fixture"

    result = service.submit_pdf(
        PdfSubmissionCommand(
            workspace_id="workspace-a",
            source_key="support/refund-policy",
            source_name="refund-policy.pdf",
            media_type="application/pdf",
            stream=BytesIO(content),
            idempotency_key="request-1",
            configuration=configuration(),
        ),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result == created_result()
    assert submission_store.authorized == ["workspace-a"]
    assert object_store.puts == [("workspace-a", "application/pdf", content)]
    prepared = submission_store.prepared[0]
    assert prepared.source_object.sha256 == sha256(content).hexdigest()
    assert prepared.source_object.byte_size == len(content)
    assert prepared.content_fingerprint == (
        "workspace-a\nsupport/refund-policy\n"
        f"{sha256(content).hexdigest()}\n"
        "pdf-parser-pypdf-m2-v1\npdf-normalizer-m2-v1\n"
        "chunking-m2-pdf-v1\nembedding-local-m1-v2"
    )
    assert prepared.idempotency_operation == "submit_pdf"
    assert prepared.idempotency_key == "request-1"
    assert prepared.idempotency_expires_at > datetime.now(UTC)
    assert object_store.deletes == []


def test_pdf_submission_authorizes_before_source_storage() -> None:
    object_store = RecordingObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    service = IngestionJobs(object_store=object_store, store=submission_store)

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-b",
                source_key="support/refund-policy",
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert submission_store.authorized == []
    assert object_store.puts == []


def test_pdf_submission_removes_duplicate_object_after_idempotency_replay() -> None:
    object_store = RecordingObjectStore()
    replay = PdfSubmissionResult(
        ingestion_job_id="job-existing",
        submission_outcome="idempotency_replay",
        status="queued",
        document_id="document-1",
        document_version_id="version-1",
        retained_object_key="opaque/source-object-existing",
    )
    service = IngestionJobs(
        object_store=object_store,
        store=RecordingSubmissionStore(replay),
    )

    result = service.submit_pdf(
        PdfSubmissionCommand(
            workspace_id="workspace-a",
            source_key="support/refund-policy",
            source_name="refund-policy.pdf",
            media_type="application/pdf",
            stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
            idempotency_key="request-1",
            configuration=configuration(),
        ),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result == replay
    assert object_store.deletes == [("workspace-a", "opaque/source-object-1")]


@pytest.mark.parametrize(
    ("source_key", "content"),
    [
        ("support/returns", b"%PDF-1.7\ndifferent source key"),
        ("support/refund-policy", b"%PDF-1.7\ndifferent PDF bytes"),
    ],
)
def test_pdf_submission_rejects_replay_key_for_distinct_request_before_staging(
    source_key: str, content: bytes
) -> None:
    original = b"%PDF-1.7\noriginal PDF bytes"
    replay = PdfSubmissionResult(
        ingestion_job_id="job-existing",
        submission_outcome="idempotency_replay",
        status="succeeded",
        document_id="document-1",
        document_version_id="version-1",
        retained_object_key="opaque/source-object-existing",
    )
    object_store = RecordingObjectStore()
    submission_store = ReplayCheckingSubmissionStore(
        result=created_result(),
        expected_fingerprint="\n".join(
            (
                "workspace-a",
                "support/refund-policy",
                sha256(original).hexdigest(),
                "pdf-parser-pypdf-m2-v1",
                "pdf-normalizer-m2-v1",
                "chunking-m2-pdf-v1",
                "embedding-local-m1-v2",
            )
        ),
        replay=replay,
    )
    service = IngestionJobs(object_store=object_store, store=submission_store)

    with pytest.raises(KnoraError, match="IDEMPOTENCY_KEY_CONFLICT"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key=source_key,
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(content),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert submission_store.replay_fingerprints
    assert object_store.puts == []
    assert submission_store.prepared == []


def test_pdf_submission_enqueues_duplicate_staging_cleanup_with_lifecycle() -> None:
    object_store = RecordingObjectStore()
    replay = PdfSubmissionResult(
        ingestion_job_id="job-existing",
        submission_outcome="idempotency_replay",
        status="queued",
        document_id="document-1",
        document_version_id="version-1",
        retained_object_key="opaque/source-object-existing",
    )
    maintenance = RecordingLifecycleMaintenance()
    service = IngestionJobs(
        object_store=object_store,
        store=RecordingSubmissionStore(replay),
        lifecycle_maintenance=maintenance,
    )

    result = service.submit_pdf(
        PdfSubmissionCommand(
            workspace_id="workspace-a",
            source_key="support/refund-policy",
            source_name="refund-policy.pdf",
            media_type="application/pdf",
            stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
            idempotency_key="request-1",
            configuration=configuration(),
        ),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result == replay
    assert object_store.deletes == []
    assert len(maintenance.items) == 1
    item = maintenance.items[0]
    assert item.workspace_id == "workspace-a"
    assert item.object_key == "opaque/source-object-1"
    assert item.artifact_class == "staging"
    assert item.eligible_at is None
    assert item.lifecycle_generation == item.work_id


def test_pdf_submission_removes_object_when_metadata_validation_fails() -> None:
    object_store = InvalidMetadataObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    service = IngestionJobs(object_store=object_store, store=submission_store)

    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="support/refund-policy",
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert object_store.deletes == [("workspace-a", "opaque/source-object-1")]
    assert submission_store.prepared == []


def test_failed_upload_uses_durable_diagnostic_retention_when_lifecycle_is_configured() -> None:
    object_store = InvalidMetadataObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    maintenance = RecordingLifecycleMaintenance()
    classified_at = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    service = IngestionJobs(
        object_store=object_store,
        store=submission_store,
        lifecycle_maintenance=maintenance,
        lifecycle_clock=FixedLifecycleClock(classified_at),
    )

    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="support/refund-policy",
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert object_store.deletes == []
    assert len(maintenance.items) == 1
    item = maintenance.items[0]
    assert item.artifact_class == "failed_upload_diagnostic"
    assert item.discovery_recorded_at == classified_at
    assert item.eligible_at is not None
    assert item.eligible_at == classified_at + timedelta(hours=24)


@dataclass
class CrossWorkspaceMetadataObjectStore(RecordingObjectStore):
    def put_stream(self, *, workspace_id: str, stream, media_type: str) -> ObjectMetadata:
        metadata = super().put_stream(
            workspace_id=workspace_id,
            stream=stream,
            media_type=media_type,
        )
        return replace(metadata, workspace_id="workspace-b")


@dataclass
class EmptyKeyMetadataObjectStore(RecordingObjectStore):
    def put_stream(self, *, workspace_id: str, stream, media_type: str) -> ObjectMetadata:
        metadata = super().put_stream(
            workspace_id=workspace_id,
            stream=stream,
            media_type=media_type,
        )
        return replace(metadata, object_key="")


def test_failed_upload_outcome_is_not_masked_when_retention_clock_is_unavailable() -> None:
    object_store = InvalidMetadataObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    maintenance = RecordingLifecycleMaintenance()
    service = IngestionJobs(
        object_store=object_store,
        store=submission_store,
        lifecycle_maintenance=maintenance,
        lifecycle_clock=FailingLifecycleClock(),
    )

    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="support/refund-policy",
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert object_store.deletes == []
    assert maintenance.items == []


def test_failed_upload_does_not_enqueue_invalid_object_key() -> None:
    object_store = EmptyKeyMetadataObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    maintenance = RecordingLifecycleMaintenance()
    service = IngestionJobs(
        object_store=object_store,
        store=submission_store,
        lifecycle_maintenance=maintenance,
        lifecycle_clock=FixedLifecycleClock(datetime(2026, 8, 10, 12, 0, tzinfo=UTC)),
    )

    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="support/refund-policy",
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert object_store.deletes == []
    assert maintenance.items == []


def test_failed_upload_does_not_classify_without_an_authoritative_clock() -> None:
    object_store = InvalidMetadataObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    maintenance = RecordingLifecycleMaintenance()
    service = IngestionJobs(
        object_store=object_store,
        store=submission_store,
        lifecycle_maintenance=maintenance,
    )

    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="support/refund-policy",
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert object_store.deletes == []
    assert maintenance.items == []


def test_failed_upload_cannot_enqueue_cross_workspace_lifecycle_work() -> None:
    object_store = CrossWorkspaceMetadataObjectStore()
    submission_store = RecordingSubmissionStore(created_result())
    maintenance = RecordingLifecycleMaintenance()
    service = IngestionJobs(
        object_store=object_store,
        store=submission_store,
        lifecycle_maintenance=maintenance,
    )

    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        service.submit_pdf(
            PdfSubmissionCommand(
                workspace_id="workspace-a",
                source_key="support/refund-policy",
                source_name="refund-policy.pdf",
                media_type="application/pdf",
                stream=BytesIO(b"%PDF-1.7\nsmall fixture"),
                idempotency_key="request-1",
                configuration=configuration(),
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert maintenance.items == []
