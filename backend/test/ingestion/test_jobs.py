from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
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
)
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


@dataclass
class InvalidMetadataObjectStore(RecordingObjectStore):
    def put_stream(self, *, workspace_id: str, stream, media_type: str) -> ObjectMetadata:
        return replace(
            super().put_stream(
                workspace_id=workspace_id,
                stream=stream,
                media_type=media_type,
            ),
            sha256="invalid",
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

    assert submission.parser_configuration_id == (
        "pdf-parser-pypdf-6-14-2-plain-layout-v1"
    )
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
