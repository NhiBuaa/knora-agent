from __future__ import annotations

import hashlib
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from io import BytesIO

from knora.ingestion.job_processing import (
    AttemptCompletion,
    AttemptRef,
    AttemptTimingV1,
    CancellationToken,
    ClaimedAttempt,
    FencingToken,
    FinalizationApplied,
    HeartbeatApplied,
    IngestionWork,
    PdfDerivationHandler,
    PdfDerivationProfile,
    PdfDerivationSuccess,
    RecoveryRetryScheduled,
    RetryScheduleApplied,
)
from knora.ingestion.jobs import PdfSubmissionConfiguration
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionResult,
    PreparedPdfChunk,
)
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


def pdf_raw_bytes(label: bytes = b"fixture") -> bytes:
    return b"%PDF-1.7\n" + label


def pdf_metadata(
    *,
    workspace_id: str = "workspace-18",
    object_key: str = "object-18",
    raw: bytes | None = None,
    media_type: str = "application/pdf",
) -> ObjectMetadata:
    content = pdf_raw_bytes() if raw is None else raw
    return ObjectMetadata(
        workspace_id=workspace_id,
        object_key=object_key,
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        media_type=media_type,
    )


def pdf_extraction(
    configuration: PdfExtractionConfiguration | None = None,
    *,
    page_texts: tuple[str, ...] = ("Page one fixture.", "Page two fixture."),
) -> PdfExtractionResult:
    configuration = configuration or PdfExtractionConfiguration.milestone_two()
    pages = tuple(
        NormalizedPdfPage(
            page_number=page_number,
            text=text,
            content_checksum=hashlib.sha256(text.encode()).hexdigest(),
        )
        for page_number, text in enumerate(page_texts, start=1)
    )
    chunks = tuple(
        PreparedPdfChunk(
            ordinal=ordinal,
            page_number=page.page_number,
            page_start=page.page_number,
            page_end=page.page_number,
            start_offset=0,
            end_offset=len(page.text),
            content=page.text,
            content_checksum=page.content_checksum,
            token_count=max(1, len(page.text.split())),
        )
        for ordinal, page in enumerate(pages)
    )
    return PdfExtractionResult(
        pages=pages,
        chunks=chunks,
        parser_version=configuration.parser_version,
        extraction_options_version=configuration.extraction_options_version,
        normalizer_version=configuration.normalizer_version,
        tokenizer_name=configuration.tokenizer_name,
        tokenizer_version=configuration.tokenizer_version,
        chunking_policy_version=configuration.chunking_policy_version,
        derivation_identity=configuration.derivation_identity,
    )


def pdf_success(
    configuration: PdfSubmissionConfiguration | None = None,
    *,
    extraction: PdfExtractionResult | None = None,
    vector_value: float = 0.1,
    vector_dimensions: int | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> PdfDerivationSuccess:
    configuration = configuration or PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    extraction = extraction or pdf_extraction()
    embedding = configuration.embedding_configuration
    dimensions = embedding.dimensions if vector_dimensions is None else vector_dimensions
    return PdfDerivationSuccess(
        extraction=extraction,
        vectors=tuple(
            tuple(vector_value for _ in range(dimensions)) for _ in extraction.chunks
        ),
        embedding_provider=embedding.provider if provider is None else provider,
        embedding_model=embedding.model if model is None else model,
    )


def work_for(
    metadata: ObjectMetadata,
    profile: PdfDerivationProfile | None = None,
) -> IngestionWork:
    profile = profile or PdfDerivationProfile.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    return IngestionWork(
        workspace_id=metadata.workspace_id,
        document_id="document-18",
        document_version_id="version-18",
        source_object_id="source-object-18",
        source_object_key=metadata.object_key,
        source_media_type=metadata.media_type,
        source_sha256=metadata.sha256,
        source_byte_size=metadata.byte_size,
        parser_configuration_id=profile.parser_configuration_id,
        normalizer_configuration_id=profile.normalizer_configuration_id,
        chunking_configuration_id=profile.chunking_configuration_id,
        embedding_configuration_id=profile.embedding_configuration.id,
    )


@dataclass(frozen=True, slots=True)
class SourceByteTag:
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass
class SourceRetentionProbe:
    raw_source_size: int
    live_parent_raw_source_bytes: int = 0
    peak_live_parent_raw_source_bytes: int = 0
    whole_object_read_count: int = 0
    read_sizes: list[int] = field(default_factory=list)
    observed_tags: list[SourceByteTag] = field(default_factory=list)
    live_tags: set[SourceByteTag] = field(default_factory=set)

    @property
    def tagged_reference_count(self) -> int:
        return len(self.live_tags)

    def retain(self, tag: SourceByteTag) -> None:
        if tag in self.live_tags:
            raise AssertionError("source tag was retained twice")
        self.live_tags.add(tag)
        self.observed_tags.append(tag)
        self.live_parent_raw_source_bytes += tag.size
        self.peak_live_parent_raw_source_bytes = max(
            self.peak_live_parent_raw_source_bytes,
            self.live_parent_raw_source_bytes,
        )

    def release(self, tag: SourceByteTag) -> None:
        if tag not in self.live_tags:
            raise AssertionError("source tag was released without a live reference")
        self.live_tags.remove(tag)
        self.live_parent_raw_source_bytes -= tag.size
        if self.live_parent_raw_source_bytes < 0:
            raise AssertionError("source retention probe released more bytes than it retained")


class SourceDerivedBytes(bytes):
    def __new__(
        cls,
        value: bytes,
        *,
        probe: SourceRetentionProbe,
        tag: SourceByteTag,
    ) -> SourceDerivedBytes:
        instance = super().__new__(cls, value)
        instance._probe = probe
        instance.source_tag = tag
        instance._released = False
        probe.retain(tag)
        return instance

    def release_source_tag(self) -> None:
        if not self._released:
            self._released = True
            self._probe.release(self.source_tag)

    def __del__(self) -> None:
        self.release_source_tag()


class InstrumentedSource(BytesIO):
    def __init__(self, raw: bytes, probe: SourceRetentionProbe | None) -> None:
        super().__init__(raw)
        self._probe = probe

    def read(self, size: int = -1) -> bytes:
        if size < 0 and self._probe is not None:
            self._probe.whole_object_read_count += 1
        start = self.tell()
        data = super().read(size)
        if data and self._probe is not None:
            self._probe.read_sizes.append(len(data))
            return SourceDerivedBytes(
                data,
                probe=self._probe,
                tag=SourceByteTag(start=start, end=start + len(data)),
            )
        return data


@dataclass
class AcceptanceObjectStore:
    metadata: ObjectMetadata
    raw: bytes = field(default_factory=pdf_raw_bytes)
    retention_probe: SourceRetentionProbe | None = None
    head_error: BaseException | None = None
    open_error: BaseException | None = None
    head_calls: int = 0
    open_read_calls: int = 0
    delete_calls: list[tuple[str, str]] = field(default_factory=list)

    def head(self, *, workspace_id: str, object_key: str) -> ObjectMetadata:
        self.head_calls += 1
        if self.head_error is not None:
            raise self.head_error
        return self.metadata

    def open_read(self, *, workspace_id: str, object_key: str) -> InstrumentedSource:
        self.open_read_calls += 1
        if self.open_error is not None:
            raise self.open_error
        return InstrumentedSource(self.raw, self.retention_probe)

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        self.delete_calls.append((workspace_id, object_key))


@dataclass
class AcceptanceExtractor:
    result: PdfExtractionResult
    failure: BaseException | None = None
    retention_probe: SourceRetentionProbe | None = None
    probe: object | None = None
    chunk_size: int = 8
    calls: int = 0
    configurations: list[PdfExtractionConfiguration] = field(default_factory=list)

    def extract(self, stream, configuration: PdfExtractionConfiguration) -> PdfExtractionResult:
        self.calls += 1
        self.configurations.append(configuration)
        span = self.probe.span("extractor") if self.probe is not None else nullcontext()
        with span:
            while chunk := stream.read(self.chunk_size):
                release_source_tag = getattr(chunk, "release_source_tag", None)
                if release_source_tag is not None:
                    release_source_tag()
                elif self.retention_probe is not None:
                    self.retention_probe.release(len(chunk))
            if self.failure is not None:
                raise self.failure
            return self.result


@dataclass
class AcceptanceEmbeddingProvider:
    batch: EmbeddingBatch
    failure: BaseException | None = None
    heartbeat_callback: Callable[[], None] | None = None
    probe: object | None = None
    calls: int = 0
    texts: list[list[str]] = field(default_factory=list)
    configurations: list[EmbeddingConfiguration] = field(default_factory=list)

    def embed(self, texts: list[str], configuration: EmbeddingConfiguration) -> EmbeddingBatch:
        self.calls += 1
        self.texts.append(texts)
        self.configurations.append(configuration)
        span = self.probe.span("provider") if self.probe is not None else nullcontext()
        with span:
            if self.heartbeat_callback is not None:
                self.heartbeat_callback()
            if self.failure is not None:
                raise self.failure
            return self.batch


class RetryableStorageSentinel(RuntimeError):
    retryable = True


class ProviderStatusSentinel(RuntimeError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"provider status {status_code}")


class DefiniteRollbackSentinel(RuntimeError):
    pass


@dataclass
class ImmediateRunning:
    completion_value: AttemptCompletion | None = None

    def completion(self) -> AttemptCompletion | None:
        return self.completion_value

    def wait_until(self, deadline: float) -> None:
        return None

    def detach(self) -> None:
        return None


class ImmediatePermit:
    def __init__(self) -> None:
        self.released = False

    def start(self, handler, work, cancellation: CancellationToken, monotonic_clock):
        return ImmediateRunning(
            AttemptCompletion(monotonic_clock.now(), handler.execute(work, cancellation))
        )

    def release(self) -> None:
        self.released = True


class ImmediateRunner:
    def __init__(self) -> None:
        self.permits: list[ImmediatePermit] = []

    def try_reserve(self) -> ImmediatePermit:
        permit = ImmediatePermit()
        self.permits.append(permit)
        return permit


def make_claim(work: IngestionWork) -> ClaimedAttempt:
    now = datetime.now(UTC)
    return ClaimedAttempt(
        token=FencingToken(
            job_id="job-18",
            attempt_number=1,
            worker_id="worker-18",
            lease_version=1,
        ),
        work=work,
        attempt_count=1,
        max_attempts=4,
        attempt_started_at=now,
        initial_lease_expires_at=now + timedelta(minutes=2),
        deadline_at=now + timedelta(minutes=15),
    )


@dataclass
class RecordingCoordinationStore:
    claim: ClaimedAttempt
    retry_result: RetryScheduleApplied | None = None
    finalization_result: FinalizationApplied | None = None
    finalization_calls: int = 0
    retry_calls: int = 0
    terminal_calls: int = 0
    heartbeat_calls: int = 0

    def observe_expired_attempt(self):
        return None

    def apply_expired_recovery(self, **kwargs):
        return RecoveryRetryScheduled(
            attempt=AttemptRef(self.claim.token.job_id, self.claim.token.attempt_number),
            next_attempt_at=self.claim.attempt_started_at,
        )

    def claim_next_attempt(self, **kwargs):
        return self.claim

    def heartbeat(self, **kwargs):
        self.heartbeat_calls += 1
        return HeartbeatApplied(lease_expires_at=self.claim.initial_lease_expires_at)

    def finalize_success(self, **kwargs):
        self.finalization_calls += 1
        return self.finalization_result or FinalizationApplied(
            attempt=AttemptRef(self.claim.token.job_id, self.claim.token.attempt_number)
        )

    def finalize_superseded(self, **kwargs):
        self.finalization_calls += 1
        return self.finalization_result or FinalizationApplied(
            attempt=AttemptRef(self.claim.token.job_id, self.claim.token.attempt_number),
            outcome="superseded",
        )

    def finalize_terminal_failure(self, **kwargs):
        self.terminal_calls += 1
        return FinalizationApplied(
            attempt=AttemptRef(self.claim.token.job_id, self.claim.token.attempt_number)
        )

    def schedule_retry(self, **kwargs):
        self.retry_calls += 1
        return self.retry_result or RetryScheduleApplied(
            attempt=AttemptRef(self.claim.token.job_id, self.claim.token.attempt_number),
            next_attempt_at=self.claim.attempt_started_at,
        )


def handler_for(
    metadata: ObjectMetadata,
    *,
    extraction: PdfExtractionResult | None = None,
    object_store: AcceptanceObjectStore | None = None,
    extractor: AcceptanceExtractor | None = None,
    provider: AcceptanceEmbeddingProvider | None = None,
    embedding_configuration: EmbeddingConfiguration | None = None,
) -> tuple[
    PdfDerivationHandler,
    AcceptanceObjectStore,
    AcceptanceExtractor,
    AcceptanceEmbeddingProvider,
]:
    embedding_configuration = (
        embedding_configuration or EmbeddingConfiguration.milestone_one_local()
    )
    profile = PdfDerivationProfile.milestone_two(
        embedding_configuration=embedding_configuration
    )
    extraction = extraction or pdf_extraction(profile.extraction_configuration)
    success = pdf_success(
        PdfSubmissionConfiguration.milestone_two(
            embedding_configuration=embedding_configuration
        ),
        extraction=extraction,
    )
    object_store = object_store or AcceptanceObjectStore(metadata=metadata)
    extractor = extractor or AcceptanceExtractor(
        result=extraction,
        retention_probe=object_store.retention_probe,
    )
    provider = provider or AcceptanceEmbeddingProvider(
        batch=EmbeddingBatch(
            vectors=success.vectors,
            provider=success.embedding_provider,
            model=success.embedding_model,
        )
    )
    return (
        PdfDerivationHandler(
            object_store=object_store,
            extractor=extractor,
            embedding_provider=provider,
            profile=profile,
        ),
        object_store,
        extractor,
        provider,
    )


def fixed_timing() -> AttemptTimingV1:
    return AttemptTimingV1.standard()
