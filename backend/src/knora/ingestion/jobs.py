from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import BinaryIO, Literal, Protocol

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.module import _validate_source_key
from knora.ingestion.object_store import ObjectMetadata, ObjectStore
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration

IDEMPOTENCY_RETENTION = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class PdfSubmissionConfiguration:
    parser_configuration_id: str
    normalizer_configuration_id: str
    chunking_configuration: ChunkingConfiguration
    embedding_configuration: EmbeddingConfiguration

    @classmethod
    def milestone_two(
        cls,
        *,
        embedding_configuration: EmbeddingConfiguration,
    ) -> PdfSubmissionConfiguration:
        return cls(
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
            embedding_configuration=embedding_configuration,
        )


@dataclass(frozen=True, slots=True)
class PdfSubmissionCommand:
    workspace_id: str
    source_key: str
    source_name: str
    media_type: str
    stream: BinaryIO
    idempotency_key: str
    configuration: PdfSubmissionConfiguration


@dataclass(frozen=True, slots=True)
class PreparedPdfSubmission:
    workspace_id: str
    source_key: str
    source_name: str
    source_object: ObjectMetadata
    content_fingerprint: str
    idempotency_operation: str
    idempotency_key: str
    idempotency_expires_at: datetime
    configuration: PdfSubmissionConfiguration


@dataclass(frozen=True, slots=True)
class PdfSubmissionResult:
    ingestion_job_id: str
    submission_outcome: Literal["created", "idempotency_replay", "deduplicated"]
    status: Literal["queued", "processing", "retry_scheduled", "succeeded", "superseded", "failed"]
    document_id: str
    document_version_id: str
    retained_object_key: str


class PdfSubmissionStore(Protocol):
    def authorize_workspace(self, *, workspace_id: str) -> None: ...

    def is_object_referenced(self, *, source_object: ObjectMetadata) -> bool: ...

    def commit_pdf_submission(
        self,
        prepared: PreparedPdfSubmission,
    ) -> PdfSubmissionResult: ...


class IngestionJobs:
    def __init__(self, *, object_store: ObjectStore, store: PdfSubmissionStore) -> None:
        self._object_store = object_store
        self._store = store

    def submit_pdf(
        self,
        command: PdfSubmissionCommand,
        principal: WorkspacePrincipal,
    ) -> PdfSubmissionResult:
        if principal.workspace_id != command.workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        self._store.authorize_workspace(workspace_id=command.workspace_id)
        _validate_source_key(command.source_key)
        if not command.idempotency_key or len(command.idempotency_key) > 255:
            raise KnoraError("INVALID_IDEMPOTENCY_KEY")
        if command.media_type != "application/pdf":
            raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")
        source_name = command.source_name.replace("\\", "/").rsplit("/", 1)[-1]
        if not source_name:
            raise KnoraError("INVALID_SOURCE_NAME")
        signature = command.stream.read(5)
        if signature != b"%PDF-":
            raise KnoraError("INVALID_PDF_SIGNATURE")
        try:
            command.stream.seek(0)
        except (AttributeError, OSError) as error:
            raise KnoraError("PDF_STREAM_NOT_SEEKABLE") from error

        source_object = self._object_store.put_stream(
            workspace_id=command.workspace_id,
            stream=command.stream,
            media_type=command.media_type,
        )
        try:
            self._validate_source_object(command, source_object)
            prepared = PreparedPdfSubmission(
                workspace_id=command.workspace_id,
                source_key=command.source_key,
                source_name=source_name,
                source_object=source_object,
                content_fingerprint=self._content_fingerprint(command, source_object.sha256),
                idempotency_operation="submit_pdf",
                idempotency_key=command.idempotency_key,
                idempotency_expires_at=datetime.now(UTC) + IDEMPOTENCY_RETENTION,
                configuration=command.configuration,
            )
        except Exception:
            self._delete_unreferenced(source_object)
            raise
        try:
            result = self._store.commit_pdf_submission(prepared)
        except Exception:
            if not self._is_object_referenced(source_object):
                self._delete_unreferenced(source_object)
            raise
        if result.retained_object_key != source_object.object_key:
            self._delete_unreferenced(source_object)
        return result

    @staticmethod
    def _content_fingerprint(command: PdfSubmissionCommand, raw_sha256: str) -> str:
        config = command.configuration
        return "\n".join(
            (
                command.workspace_id,
                command.source_key,
                raw_sha256,
                config.parser_configuration_id,
                config.normalizer_configuration_id,
                config.chunking_configuration.id,
                config.embedding_configuration.id,
            )
        )

    @staticmethod
    def _validate_source_object(
        command: PdfSubmissionCommand,
        source_object: ObjectMetadata,
    ) -> None:
        if (
            source_object.workspace_id != command.workspace_id
            or source_object.media_type != command.media_type
            or not source_object.object_key
            or len(source_object.sha256) != 64
            or source_object.byte_size <= 0
        ):
            raise KnoraError("OBJECT_STORE_METADATA_INVALID")

    def _delete_unreferenced(self, source_object: ObjectMetadata) -> None:
        with suppress(Exception):
            self._object_store.delete(
                workspace_id=source_object.workspace_id,
                object_key=source_object.object_key,
            )

    def _is_object_referenced(self, source_object: ObjectMetadata) -> bool:
        checker = getattr(self._store, "is_object_referenced", None)
        if checker is None:
            return True
        try:
            return bool(checker(source_object=source_object))
        except Exception:
            return True
