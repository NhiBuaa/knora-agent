from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import BinaryIO, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.module import _validate_source_key
from knora.ingestion.object_lifecycle import (
    FAILED_UPLOAD_DIAGNOSTIC_RETENTION,
    LifecycleClock,
    LifecycleWorkState,
    ObjectLifecycleMaintenance,
    ObjectLifecycleWorkItem,
)
from knora.ingestion.object_store import ObjectMetadata, ObjectStore
from knora.ingestion.pdf import PdfExtractionConfiguration
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration

IDEMPOTENCY_RETENTION = timedelta(hours=24)
PUBLIC_JOB_STATUSES = Literal[
    "queued", "processing", "retry_scheduled", "succeeded", "superseded", "failed"
]
PUBLIC_FAILURE_REASONS = Literal[
    "retry_exhausted", "terminal_input", "terminal_config", "resource_limit"
]
REPROCESS_CONFIG_MODES = Literal["same_as_job", "current"]


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
        pdf = PdfExtractionConfiguration.milestone_two()
        return cls(
            parser_configuration_id="pdf-parser-pypdf-6-14-2-plain-layout-v1",
            normalizer_configuration_id=pdf.normalizer_version,
            chunking_configuration=ChunkingConfiguration(
                id="chunking-m2-pdf-pypdf-6-14-2-v1",
                parser_version=pdf.parser_version,
                chunker_version=pdf.chunking_policy_version,
                tokenizer_name=pdf.tokenizer_name,
                tokenizer_version=pdf.tokenizer_version,
                target_tokens=pdf.target_tokens,
                overlap_tokens=pdf.overlap_tokens,
                max_tokens=pdf.max_tokens,
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


@dataclass(frozen=True, slots=True)
class JobStatusProjection:
    ingestion_job_id: str
    status: PUBLIC_JOB_STATUSES
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime
    terminal_at: datetime | None
    target_document_version_id: str
    current_document_version_id: str | None
    served_document_version_id: str | None
    serving_state: Literal["unavailable", "current", "previous"]
    failure_reason: PUBLIC_FAILURE_REASONS | None
    error_code: str | None
    result_document_version_id: str | None
    replacement_document_version_id: str | None = None
    replacement_ingestion_job_id: str | None = None
    reprocess_of_job_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReprocessDocumentVersionCommand:
    workspace_id: str
    document_version_id: str
    config_mode: REPROCESS_CONFIG_MODES
    config_source_job_id: str | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ReprocessContext:
    workspace_id: str
    document_id: str
    document_version_id: str
    source_object: ObjectMetadata
    configuration: PdfSubmissionConfiguration
    config_source_job_id: str | None
    prior_job_id: str | None


@dataclass(frozen=True, slots=True)
class PreparedReprocess:
    workspace_id: str
    document_id: str
    document_version_id: str
    source_object: ObjectMetadata
    request_fingerprint: str
    idempotency_operation: str
    idempotency_key: str
    idempotency_expires_at: datetime
    requested_config_mode: REPROCESS_CONFIG_MODES
    resolved_config_mode: REPROCESS_CONFIG_MODES
    config_source_job_id: str | None
    prior_job_id: str | None
    configuration: PdfSubmissionConfiguration
    actor_key_id: str


@dataclass(frozen=True, slots=True)
class ReprocessResult:
    ingestion_job_id: str
    document_version_id: str
    outcome: Literal["created", "reused", "idempotency_replay"]
    status: PUBLIC_JOB_STATUSES
    audit_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReprocessAuditProjection:
    audit_event_id: str
    workspace_id: str
    actor_key_id: str
    action: str
    target_document_version_id: str
    requested_config_mode: REPROCESS_CONFIG_MODES
    resolved_config_mode: REPROCESS_CONFIG_MODES
    config_source_job_id: str | None
    ingestion_job_id: str
    outcome: Literal["created", "reused"]
    created_at: datetime
    trace_id: str | None


class PdfSubmissionStore(Protocol):
    def authorize_workspace(self, *, workspace_id: str) -> None: ...

    def is_object_referenced(self, *, source_object: ObjectMetadata) -> bool: ...

    def commit_pdf_submission(
        self,
        prepared: PreparedPdfSubmission,
    ) -> PdfSubmissionResult: ...

    def get_job_status(
        self, *, workspace_id: str, ingestion_job_id: str
    ) -> JobStatusProjection | None: ...

    def read_reprocess_context(
        self,
        *,
        workspace_id: str,
        document_version_id: str,
        config_mode: REPROCESS_CONFIG_MODES,
        config_source_job_id: str | None,
    ) -> ReprocessContext | None: ...

    def commit_reprocess(self, prepared: PreparedReprocess) -> ReprocessResult: ...

    def read_reprocess_replay(
        self, *, workspace_id: str, idempotency_key: str, request_fingerprint: str
    ) -> ReprocessResult | None: ...

    def read_reprocess_audit(
        self, *, workspace_id: str, audit_event_id: str
    ) -> ReprocessAuditProjection | None: ...


class IngestionJobs:
    def __init__(
        self,
        *,
        object_store: ObjectStore,
        store: PdfSubmissionStore,
        lifecycle_maintenance: ObjectLifecycleMaintenance | None = None,
        lifecycle_clock: LifecycleClock | None = None,
    ) -> None:
        self._object_store = object_store
        self._store = store
        self._lifecycle_maintenance = lifecycle_maintenance
        self._lifecycle_clock = lifecycle_clock

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
            self._handle_failed_upload(
                source_object, expected_workspace_id=command.workspace_id
            )
            raise
        try:
            result = self._store.commit_pdf_submission(prepared)
        except Exception:
            if not self._is_object_referenced(source_object):
                self._handle_failed_upload(
                    source_object, expected_workspace_id=command.workspace_id
                )
            raise
        if result.retained_object_key != source_object.object_key:
            self._schedule_unreferenced_cleanup(source_object)
        return result

    def get_job_status(
        self,
        *,
        ingestion_job_id: str,
        principal: WorkspacePrincipal,
    ) -> JobStatusProjection:
        projection = self._store.get_job_status(
            workspace_id=principal.workspace_id,
            ingestion_job_id=ingestion_job_id,
        )
        if projection is None:
            raise KnoraError("INGESTION_JOB_NOT_FOUND")
        return projection

    def reprocess_document_version(
        self,
        command: ReprocessDocumentVersionCommand,
        principal: WorkspacePrincipal,
    ) -> ReprocessResult:
        if principal.workspace_id != command.workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        self._store.authorize_workspace(workspace_id=command.workspace_id)
        if not command.idempotency_key:
            raise KnoraError("MISSING_IDEMPOTENCY_KEY")
        if len(command.idempotency_key) > 255:
            raise KnoraError("INVALID_IDEMPOTENCY_KEY")
        if command.config_mode not in {"same_as_job", "current"}:
            raise KnoraError("INVALID_CONFIG_MODE")
        if command.config_mode == "same_as_job" and not command.config_source_job_id:
            raise KnoraError("CONFIG_SOURCE_JOB_REQUIRED")
        if command.config_mode == "current" and command.config_source_job_id is not None:
            raise KnoraError("CONFIG_SOURCE_JOB_NOT_ALLOWED")

        request_fingerprint = self._reprocess_fingerprint(command=command)
        replay_reader = getattr(self._store, "read_reprocess_replay", None)
        if replay_reader is not None:
            replay = replay_reader(
                workspace_id=command.workspace_id,
                idempotency_key=command.idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay

        context = self._store.read_reprocess_context(
            workspace_id=command.workspace_id,
            document_version_id=command.document_version_id,
            config_mode=command.config_mode,
            config_source_job_id=command.config_source_job_id,
        )
        if context is None:
            raise KnoraError("DOCUMENT_VERSION_NOT_FOUND")
        try:
            observed = self._object_store.head(
                workspace_id=context.workspace_id,
                object_key=context.source_object.object_key,
            )
        except KnoraError as error:
            if error.code == "OBJECT_NOT_FOUND":
                raise KnoraError("SOURCE_OBJECT_NOT_AVAILABLE") from error
            raise
        except Exception as error:
            raise KnoraError("SOURCE_OBJECT_NOT_AVAILABLE") from error
        if (
            observed.workspace_id != context.source_object.workspace_id
            or observed.object_key != context.source_object.object_key
            or observed.sha256 != context.source_object.sha256
            or observed.byte_size != context.source_object.byte_size
            or observed.media_type != context.source_object.media_type
        ):
            raise KnoraError("SOURCE_OBJECT_NOT_AVAILABLE")

        prepared = PreparedReprocess(
            workspace_id=context.workspace_id,
            document_id=context.document_id,
            document_version_id=context.document_version_id,
            source_object=context.source_object,
            request_fingerprint=request_fingerprint,
            idempotency_operation="reprocess_document_version",
            idempotency_key=command.idempotency_key,
            idempotency_expires_at=datetime.now(UTC) + IDEMPOTENCY_RETENTION,
            requested_config_mode=command.config_mode,
            resolved_config_mode=command.config_mode,
            config_source_job_id=context.config_source_job_id,
            prior_job_id=context.prior_job_id,
            configuration=context.configuration,
            actor_key_id=principal.key_id,
        )
        return self._store.commit_reprocess(prepared)

    @staticmethod
    def _reprocess_fingerprint(
        *,
        command: ReprocessDocumentVersionCommand,
    ) -> str:
        return "\n".join(
            (
                command.workspace_id,
                command.document_version_id,
                command.config_mode,
                command.config_source_job_id or "",
            )
        )

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
            not isinstance(source_object.workspace_id, str)
            or source_object.workspace_id != command.workspace_id
            or not isinstance(source_object.object_key, str)
            or source_object.media_type != command.media_type
            or not source_object.object_key
            or not isinstance(source_object.sha256, str)
            or len(source_object.sha256) != 64
            or any(
                character not in "0123456789abcdefABCDEF" for character in source_object.sha256
            )
            or isinstance(source_object.byte_size, bool)
            or not isinstance(source_object.byte_size, int)
            or source_object.byte_size <= 0
            or not isinstance(source_object.media_type, str)
        ):
            raise KnoraError("OBJECT_STORE_METADATA_INVALID")

    def _delete_unreferenced(self, source_object: ObjectMetadata) -> None:
        with suppress(Exception):
            self._object_store.delete(
                workspace_id=source_object.workspace_id,
                object_key=source_object.object_key,
            )

    def _schedule_unreferenced_cleanup(self, source_object: ObjectMetadata) -> None:
        """Route an unretained post-submit staging object to asynchronous cleanup.

        A replay or fingerprint deduplication can leave the newly uploaded object unrelated to
        the durable Document Version returned by the submission transaction.  Production owns
        cleanup through the lifecycle application port; callers without that port retain the
        legacy best-effort compensation behavior used by older synchronous adapters.
        """

        maintenance = self._lifecycle_maintenance
        if maintenance is None:
            self._delete_unreferenced(source_object)
            return
        lifecycle_id = str(
            uuid5(
                NAMESPACE_URL,
                f"staging-cleanup:{source_object.workspace_id}:{source_object.object_key}",
            )
        )
        with suppress(Exception):
            maintenance.enqueue(
                ObjectLifecycleWorkItem(
                    work_id=lifecycle_id,
                    workspace_id=source_object.workspace_id,
                    object_key=source_object.object_key,
                    state=LifecycleWorkState.QUEUED,
                    artifact_class="staging",
                    lifecycle_generation=lifecycle_id,
                )
            )

    def _handle_failed_upload(
        self, source_object: ObjectMetadata, *, expected_workspace_id: str
    ) -> None:
        if source_object.workspace_id != expected_workspace_id:
            # A malformed provider result must never cause lifecycle work to be written into a
            # different Workspace. Leave ownership recovery to the configured inventory path.
            return
        if not isinstance(source_object.object_key, str) or not source_object.object_key:
            # A malformed provider result without an opaque key cannot be addressed safely by
            # lifecycle cleanup. Leave recovery to inventory instead of creating unusable work.
            return
        maintenance = self._lifecycle_maintenance
        if maintenance is None:
            # Older synchronous callers that have no lifecycle application port retain their
            # established compensation behavior. Production bootstrap always supplies the port,
            # which makes failed-upload retention durable and asynchronous.
            self._delete_unreferenced(source_object)
            return
        if self._lifecycle_clock is None:
            # A process-local wall-clock value is not an authoritative classification timestamp.
            # Leave the object for a later inventory/reconciliation pass instead of starting a
            # retention window that cannot be proven durable.
            return
        try:
            classified_at = self._lifecycle_clock.now()
        except Exception:
            # A failed authoritative timestamp read cannot change the already-observed upload
            # outcome. Leave the object for a later inventory/reconciliation pass instead of
            # inventing a non-durable retention start time or masking the original exception.
            return
        if not isinstance(classified_at, datetime) or classified_at.tzinfo is None:
            return
        lifecycle_id = str(
            uuid5(
                NAMESPACE_URL,
                f"failed-upload:{source_object.workspace_id}:{source_object.object_key}",
            )
        )
        with suppress(Exception):
            maintenance.enqueue(
                ObjectLifecycleWorkItem(
                    work_id=lifecycle_id,
                    workspace_id=source_object.workspace_id,
                    object_key=source_object.object_key,
                    state=LifecycleWorkState.QUEUED,
                    artifact_class="failed_upload_diagnostic",
                    lifecycle_generation=lifecycle_id,
                    eligible_at=classified_at + FAILED_UPLOAD_DIAGNOSTIC_RETENTION,
                    # This is the Knora-owned durable classification timestamp for the
                    # diagnostic-retention window.  The lifecycle adapter persists it with the
                    # work identity; it is not derived from Idempotency Record retention.
                    discovery_recorded_at=classified_at,
                )
            )

    def _is_object_referenced(self, source_object: ObjectMetadata) -> bool:
        checker = getattr(self._store, "is_object_referenced", None)
        if checker is None:
            return True
        try:
            return bool(checker(source_object=source_object))
        except Exception:
            return True
