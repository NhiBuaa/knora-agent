"""Typed orchestration for one durable Ingestion Job attempt and PDF derivation work."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite
from threading import Event
from typing import NewType, Protocol, TypeVar
from uuid import uuid4

from knora.domain.errors import KnoraError
from knora.ingestion.object_store import ObjectMetadata, ObjectStore
from knora.ingestion.pdf import (
    PdfExtractionConfiguration,
    PdfExtractionError,
    PdfExtractionResult,
    PdfTextExtractor,
)
from knora.providers.embedding import EmbeddingConfiguration, EmbeddingProvider

SuccessT = TypeVar("SuccessT")

ClaimOperationId = NewType("ClaimOperationId", str)
HeartbeatOperationId = NewType("HeartbeatOperationId", str)
TransitionOperationId = NewType("TransitionOperationId", str)


class CoordinationInvariantError(RuntimeError):
    """Signals impossible coordination input or a slice not yet delivered."""


class HandlerFailureKindV1(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNSUPPORTED_INPUT = "unsupported_input"
    CONFIGURATION_INVALID = "configuration_invalid"
    RESOURCE_LIMIT = "resource_limit"
    VECTOR_MISMATCH = "vector_mismatch"
    PROVIDER_TRANSIENT = "provider_transient"
    DATABASE_TRANSIENT = "database_transient"
    STORAGE_TRANSIENT = "storage_transient"
    WORKER_UNEXPECTED = "worker_unexpected"


class FailureCauseV1(StrEnum):
    PROVIDER_TRANSIENT = "provider_transient"
    DATABASE_TRANSIENT = "database_transient"
    STORAGE_TRANSIENT = "storage_transient"
    WORKER_UNEXPECTED = "worker_unexpected"
    ATTEMPT_TIMEOUT = "attempt_timeout"
    LEASE_EXPIRED = "lease_expired"
    INVALID_INPUT = "invalid_input"
    UNSUPPORTED_INPUT = "unsupported_input"
    CONFIGURATION_INVALID = "configuration_invalid"
    RESOURCE_LIMIT = "resource_limit"
    VECTOR_MISMATCH = "vector_mismatch"


_SAFE_CODES_BY_KIND: dict[HandlerFailureKindV1, frozenset[str]] = {
    HandlerFailureKindV1.INVALID_INPUT: frozenset(
        {"invalid_input", "PDF_TEXT_INSUFFICIENT", "PDF_MALFORMED"}
    ),
    HandlerFailureKindV1.UNSUPPORTED_INPUT: frozenset(
        {"unsupported_input", "PDF_ENCRYPTED", "PDF_UNSUPPORTED"}
    ),
    HandlerFailureKindV1.CONFIGURATION_INVALID: frozenset({"configuration_invalid"}),
    HandlerFailureKindV1.RESOURCE_LIMIT: frozenset(
        {"resource_limit", "PDF_RESOURCE_LIMIT_EXCEEDED"}
    ),
    HandlerFailureKindV1.VECTOR_MISMATCH: frozenset({"vector_mismatch"}),
    HandlerFailureKindV1.PROVIDER_TRANSIENT: frozenset({"provider_transient"}),
    HandlerFailureKindV1.DATABASE_TRANSIENT: frozenset({"database_transient"}),
    HandlerFailureKindV1.STORAGE_TRANSIENT: frozenset({"storage_transient"}),
    HandlerFailureKindV1.WORKER_UNEXPECTED: frozenset(
        {"worker_unexpected", "PDF_EXTRACTOR_UNAVAILABLE"}
    ),
}

_TERMINAL_REASONS: dict[FailureCauseV1, str] = {
    FailureCauseV1.INVALID_INPUT: "terminal_input",
    FailureCauseV1.UNSUPPORTED_INPUT: "terminal_input",
    FailureCauseV1.CONFIGURATION_INVALID: "terminal_config",
    FailureCauseV1.RESOURCE_LIMIT: "resource_limit",
    FailureCauseV1.VECTOR_MISMATCH: "terminal_config",
}

_RETRYABLE_CAUSES = frozenset(
    {
        FailureCauseV1.PROVIDER_TRANSIENT,
        FailureCauseV1.DATABASE_TRANSIENT,
        FailureCauseV1.STORAGE_TRANSIENT,
        FailureCauseV1.WORKER_UNEXPECTED,
        FailureCauseV1.ATTEMPT_TIMEOUT,
        FailureCauseV1.LEASE_EXPIRED,
    }
)

_RETRY_WINDOWS_MICROSECONDS = {
    1: 5_000_000,
    2: 30_000_000,
    3: 120_000_000,
}


class RandomSource(Protocol):
    def next_int_inclusive(self, upper_bound_microseconds: int) -> int: ...


class SystemRandomSource:
    """Process-local full-jitter source over inclusive integer microsecond windows."""

    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        if upper_bound_microseconds < 0:
            raise ValueError("retry jitter upper bound must be non-negative")
        return secrets.randbelow(upper_bound_microseconds + 1)


@dataclass(frozen=True, slots=True)
class ScheduleRetry:
    delay_microseconds: int
    window_upper_bound_microseconds: int
    policy_version: str = "retry-policy-v1"
    jitter_version: str = "full-jitter-v1"

    def __post_init__(self) -> None:
        if (
            isinstance(self.delay_microseconds, bool)
            or isinstance(self.window_upper_bound_microseconds, bool)
            or not isinstance(self.delay_microseconds, int)
            or not isinstance(self.window_upper_bound_microseconds, int)
            or self.delay_microseconds < 0
            or self.window_upper_bound_microseconds < self.delay_microseconds
        ):
            raise ValueError("retry delay must be an integer within its inclusive jitter window")


@dataclass(frozen=True, slots=True)
class RetryExhausted:
    policy_version: str = "retry-policy-v1"


@dataclass(frozen=True, slots=True)
class FailTerminal:
    policy_version: str = "retry-policy-v1"


RetryDecision = ScheduleRetry | RetryExhausted | FailTerminal


class RetryPolicyV1:
    """Classify canonical observed facts without leaking retryability into causes."""

    def __init__(self, random_source: RandomSource) -> None:
        self._random_source = random_source

    def decide(
        self,
        cause: FailureCauseV1,
        attempt_count: int,
        max_attempts: int,
    ) -> RetryDecision:
        if cause not in _RETRYABLE_CAUSES:
            return FailTerminal()
        if attempt_count >= max_attempts:
            return RetryExhausted()
        upper_bound = _RETRY_WINDOWS_MICROSECONDS[attempt_count]
        delay = self._random_source.next_int_inclusive(upper_bound)
        if delay < 0 or delay > upper_bound:
            raise CoordinationInvariantError(
                "RandomSource returned a retry delay outside the window"
            )
        return ScheduleRetry(
            delay_microseconds=delay,
            window_upper_bound_microseconds=upper_bound,
        )


@dataclass(frozen=True, slots=True)
class AttemptRef:
    job_id: str
    attempt_number: int


@dataclass(frozen=True, slots=True)
class FencingToken:
    job_id: str
    attempt_number: int
    worker_id: str
    lease_version: int


class CoordinationOutcomeIndeterminate(RuntimeError):
    """A mutation's durable outcome could not be authoritatively reconciled."""

    def __init__(
        self,
        *,
        operation_id: str,
        operation_kind: str = "heartbeat",
        token: FencingToken | None = None,
        job_id: str | None = None,
        attempt_number: int | None = None,
    ) -> None:
        if token is not None:
            job_id = token.job_id
            attempt_number = token.attempt_number
        self.operation_kind = operation_kind
        self.operation_id = operation_id
        self.job_id = job_id
        self.attempt_number = attempt_number
        self.attempt = (
            AttemptRef(job_id, attempt_number)
            if job_id is not None and attempt_number is not None
            else None
        )
        super().__init__(
            f"coordination outcome is indeterminate for {operation_kind} operation {operation_id}"
        )


@dataclass(frozen=True, slots=True)
class IngestionWork:
    workspace_id: str
    document_id: str
    document_version_id: str
    source_object_id: str
    source_object_key: str
    source_media_type: str
    parser_configuration_id: str
    normalizer_configuration_id: str
    chunking_configuration_id: str
    embedding_configuration_id: str
    source_sha256: str = ""
    source_byte_size: int = 0


@dataclass(frozen=True, slots=True)
class ClaimedAttempt:
    token: FencingToken
    work: IngestionWork
    attempt_count: int
    max_attempts: int
    attempt_started_at: datetime
    initial_lease_expires_at: datetime
    deadline_at: datetime


@dataclass(frozen=True, slots=True)
class ExpiredAttemptObservation:
    """An optimistic database-time observation that grants no processing ownership."""

    job_id: str
    attempt_number: int
    worker_id: str
    lease_version: int
    attempt_count: int
    max_attempts: int
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AttemptTimingV1:
    lease_duration: timedelta
    max_attempt_runtime: timedelta

    @classmethod
    def standard(cls) -> AttemptTimingV1:
        return cls(lease_duration=timedelta(minutes=2), max_attempt_runtime=timedelta(minutes=15))


@dataclass(frozen=True, slots=True)
class WorkSucceeded[SuccessT]:
    payload: SuccessT


@dataclass(frozen=True, slots=True)
class WorkSuperseded:
    """A handler-established stale-version condition, never a zero-row inference."""

    replacement_document_version_id: str | None = None
    replacement_ingestion_job_id: str | None = None

    def __post_init__(self) -> None:
        for identifier in (
            self.replacement_document_version_id,
            self.replacement_ingestion_job_id,
        ):
            if identifier is not None and not identifier:
                raise ValueError("replacement identifiers must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class WorkFailed:
    failure_kind: HandlerFailureKindV1
    safe_code: str

    def __post_init__(self) -> None:
        if self.safe_code not in _SAFE_CODES_BY_KIND[self.failure_kind]:
            raise ValueError("safe_code is not allowlisted for failure_kind")


WorkOutcome = WorkSucceeded[SuccessT] | WorkSuperseded | WorkFailed


@dataclass(frozen=True, slots=True)
class PdfDerivationSuccess:
    extraction: PdfExtractionResult
    vectors: tuple[tuple[float, ...], ...]
    embedding_provider: str
    embedding_model: str


@dataclass(frozen=True, slots=True)
class PdfDerivationProfile:
    parser_configuration_id: str
    normalizer_configuration_id: str
    chunking_configuration_id: str
    extraction_configuration: PdfExtractionConfiguration
    embedding_configuration: EmbeddingConfiguration

    @classmethod
    def milestone_two(
        cls, *, embedding_configuration: EmbeddingConfiguration
    ) -> PdfDerivationProfile:
        extraction = PdfExtractionConfiguration.milestone_two()
        return cls(
            parser_configuration_id="pdf-parser-pypdf-6-14-2-plain-layout-v1",
            normalizer_configuration_id=extraction.normalizer_version,
            chunking_configuration_id="chunking-m2-pdf-pypdf-6-14-2-v1",
            extraction_configuration=extraction,
            embedding_configuration=embedding_configuration,
        )


class PdfDerivationHandler:
    """Prepare one immutable PDF derivation outside the coordination transaction."""

    def __init__(
        self,
        *,
        object_store: ObjectStore,
        extractor: PdfTextExtractor,
        embedding_provider: EmbeddingProvider,
        profile: PdfDerivationProfile | None = None,
        profile_resolver: Callable[[IngestionWork], PdfDerivationProfile] | None = None,
    ) -> None:
        if profile is None and profile_resolver is None:
            raise ValueError("PdfDerivationHandler needs a profile or profile resolver")
        self._object_store = object_store
        self._extractor = extractor
        self._embedding_provider = embedding_provider
        self._profile = profile
        self._profile_resolver = profile_resolver

    def execute(
        self, work: IngestionWork, cancellation: CancellationToken
    ) -> WorkOutcome[PdfDerivationSuccess]:
        del cancellation
        profile = (
            self._profile_resolver(work)
            if self._profile_resolver is not None
            else self._profile
        )
        if profile is None or not self._profile_matches_work(work, profile):
            return WorkFailed(HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid")

        try:
            metadata = self._object_store.head(
                workspace_id=work.workspace_id,
                object_key=work.source_object_key,
            )
        except KnoraError as error:
            if error.code == "OBJECT_NOT_FOUND":
                return WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input")
            return WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
        except (ConnectionError, OSError, TimeoutError):
            return WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
        except Exception as error:
            if getattr(error, "retryable", False):
                return WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
            return WorkFailed(HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected")

        if not self._metadata_matches(work, metadata):
            return WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input")

        try:
            stream = self._object_store.open_read(
                workspace_id=work.workspace_id,
                object_key=work.source_object_key,
            )
        except KnoraError as error:
            if error.code == "OBJECT_NOT_FOUND":
                return WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input")
            return WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
        except (ConnectionError, OSError, TimeoutError):
            return WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
        except Exception as error:
            if getattr(error, "retryable", False):
                return WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
            return WorkFailed(HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected")

        try:
            extraction = self._extractor.extract(
                stream, profile.extraction_configuration
            )
        except PdfExtractionError as error:
            return self._pdf_extraction_failure(error)
        except Exception:
            return WorkFailed(HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected")
        finally:
            stream.close()

        try:
            extraction_matches_profile = self._extraction_matches_profile(
                extraction, profile
            )
        except (AttributeError, TypeError, ValueError):
            extraction_matches_profile = False
        if not extraction_matches_profile:
            return WorkFailed(HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid")

        try:
            batch = self._embedding_provider.embed(
                [chunk.content for chunk in extraction.chunks],
                profile.embedding_configuration,
            )
        except KnoraError as error:
            if error.code == "PROVIDER_REQUEST_FAILED":
                return WorkFailed(HandlerFailureKindV1.PROVIDER_TRANSIENT, "provider_transient")
            if error.code == "PROVIDER_RESPONSE_INVALID":
                return WorkFailed(HandlerFailureKindV1.VECTOR_MISMATCH, "vector_mismatch")
            return WorkFailed(HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected")
        except (ConnectionError, TimeoutError):
            return WorkFailed(HandlerFailureKindV1.PROVIDER_TRANSIENT, "provider_transient")
        except Exception as error:
            if getattr(error, "retryable", False) or getattr(error, "status_code", 0) in {
                408,
                429,
                500,
                502,
                503,
                504,
            }:
                return WorkFailed(HandlerFailureKindV1.PROVIDER_TRANSIENT, "provider_transient")
            return WorkFailed(HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected")

        try:
            vectors = tuple(tuple(float(value) for value in vector) for vector in batch.vectors)
            provider = batch.provider
            model = batch.model
        except (AttributeError, TypeError, ValueError):
            return WorkFailed(HandlerFailureKindV1.VECTOR_MISMATCH, "vector_mismatch")
        configuration = profile.embedding_configuration
        if (
            len(vectors) != len(extraction.chunks)
            or any(
                len(vector) != configuration.dimensions
                or any(not isfinite(value) for value in vector)
                for vector in vectors
            )
            or provider != configuration.provider
            or model != configuration.model
        ):
            return WorkFailed(HandlerFailureKindV1.VECTOR_MISMATCH, "vector_mismatch")

        return WorkSucceeded(
            PdfDerivationSuccess(
                extraction=extraction,
                vectors=vectors,
                embedding_provider=provider,
                embedding_model=model,
            )
        )

    @staticmethod
    def _profile_matches_work(work: IngestionWork, profile: PdfDerivationProfile) -> bool:
        extraction = profile.extraction_configuration
        return (
            profile.parser_configuration_id == work.parser_configuration_id
            and profile.normalizer_configuration_id == work.normalizer_configuration_id
            and profile.chunking_configuration_id == work.chunking_configuration_id
            and profile.embedding_configuration.id == work.embedding_configuration_id
            and profile.normalizer_configuration_id == extraction.normalizer_version
        )

    @staticmethod
    def _metadata_matches(work: IngestionWork, metadata: ObjectMetadata) -> bool:
        return (
            metadata.workspace_id == work.workspace_id
            and metadata.object_key == work.source_object_key
            and metadata.sha256 == work.source_sha256
            and metadata.byte_size == work.source_byte_size
            and metadata.media_type == work.source_media_type
        )

    @staticmethod
    def _extraction_matches_profile(
        extraction: PdfExtractionResult, profile: PdfDerivationProfile
    ) -> bool:
        configuration = profile.extraction_configuration
        if (
            extraction.parser_version != configuration.parser_version
            or extraction.extraction_options_version != configuration.extraction_options_version
            or extraction.normalizer_version != configuration.normalizer_version
            or extraction.tokenizer_name != configuration.tokenizer_name
            or extraction.tokenizer_version != configuration.tokenizer_version
            or extraction.chunking_policy_version != configuration.chunking_policy_version
            or extraction.derivation_identity != configuration.derivation_identity
            or not extraction.chunks
        ):
            return False
        if (
            len({page.page_number for page in extraction.pages}) != len(extraction.pages)
            or any(
                page.page_number < 1
                or page.content_checksum != _sha256_text(page.text)
                for page in extraction.pages
            )
        ):
            return False
        pages = {page.page_number: page for page in extraction.pages}
        for ordinal, chunk in enumerate(extraction.chunks):
            page = pages.get(chunk.page_number)
            if (
                chunk.ordinal != ordinal
                or page is None
                or chunk.page_start != chunk.page_number
                or chunk.page_end != chunk.page_number
                or chunk.start_offset < 0
                or chunk.start_offset >= chunk.end_offset
                or chunk.end_offset > len(page.text)
                or chunk.content != page.text[chunk.start_offset : chunk.end_offset]
                or chunk.content_checksum != _sha256_text(chunk.content)
                or chunk.token_count <= 0
            ):
                return False
        return True

    @staticmethod
    def _pdf_extraction_failure(error: PdfExtractionError) -> WorkFailed:
        if error.retryable:
            safe_code = (
                error.code
                if error.code == "PDF_EXTRACTOR_UNAVAILABLE"
                else "worker_unexpected"
            )
            return WorkFailed(HandlerFailureKindV1.WORKER_UNEXPECTED, safe_code)
        if error.code == "PDF_ENCRYPTED":
            return WorkFailed(HandlerFailureKindV1.UNSUPPORTED_INPUT, "PDF_ENCRYPTED")
        if error.code == "PDF_RESOURCE_LIMIT_EXCEEDED":
            return WorkFailed(HandlerFailureKindV1.RESOURCE_LIMIT, error.code)
        if error.code == "PDF_UNSUPPORTED":
            return WorkFailed(HandlerFailureKindV1.UNSUPPORTED_INPUT, error.code)
        if error.code in {"PDF_TEXT_INSUFFICIENT", "PDF_MALFORMED"}:
            return WorkFailed(HandlerFailureKindV1.INVALID_INPUT, error.code)
        return WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CanonicalFailureV1:
    cause: FailureCauseV1
    safe_code: str
    failure_reason: str | None
    cause_version: str
    mapping_version: str


class CauseMappingV1:
    """The closed, pure V1 mapping from observed handler facts to canonical facts."""

    _causes: dict[HandlerFailureKindV1, FailureCauseV1] = {
        HandlerFailureKindV1.INVALID_INPUT: FailureCauseV1.INVALID_INPUT,
        HandlerFailureKindV1.UNSUPPORTED_INPUT: FailureCauseV1.UNSUPPORTED_INPUT,
        HandlerFailureKindV1.CONFIGURATION_INVALID: FailureCauseV1.CONFIGURATION_INVALID,
        HandlerFailureKindV1.RESOURCE_LIMIT: FailureCauseV1.RESOURCE_LIMIT,
        HandlerFailureKindV1.VECTOR_MISMATCH: FailureCauseV1.VECTOR_MISMATCH,
        HandlerFailureKindV1.PROVIDER_TRANSIENT: FailureCauseV1.PROVIDER_TRANSIENT,
        HandlerFailureKindV1.DATABASE_TRANSIENT: FailureCauseV1.DATABASE_TRANSIENT,
        HandlerFailureKindV1.STORAGE_TRANSIENT: FailureCauseV1.STORAGE_TRANSIENT,
        HandlerFailureKindV1.WORKER_UNEXPECTED: FailureCauseV1.WORKER_UNEXPECTED,
    }

    @classmethod
    def map(cls, failed: WorkFailed) -> CanonicalFailureV1:
        return CanonicalFailureV1(
            cause=cls._causes[failed.failure_kind],
            safe_code=failed.safe_code,
            failure_reason=None,
            cause_version="failure-causes-v1",
            mapping_version="cause-mapping-v1",
        )

    @classmethod
    def map_terminal(cls, failed: WorkFailed) -> CanonicalFailureV1:
        return cls.terminalize(cls.map(failed))

    @classmethod
    def terminalize(cls, observed: CanonicalFailureV1) -> CanonicalFailureV1:
        cause = observed.cause
        failure_reason = _TERMINAL_REASONS.get(cause)
        if failure_reason is None:
            raise CoordinationInvariantError(
                "retryable cause cannot be terminalized without exhaustion"
            )
        return CanonicalFailureV1(
            cause=cause,
            safe_code=observed.safe_code,
            failure_reason=failure_reason,
            cause_version=observed.cause_version,
            mapping_version=observed.mapping_version,
        )


@dataclass(frozen=True, slots=True)
class NoEligibleClaim:
    pass


@dataclass(frozen=True, slots=True)
class ClaimLeaseLost:
    attempt: AttemptRef


@dataclass(frozen=True, slots=True)
class FinalizationApplied:
    attempt: AttemptRef
    outcome: str = "succeeded"
    replacement_document_version_id: str | None = None
    replacement_ingestion_job_id: str | None = None


@dataclass(frozen=True, slots=True)
class RetryScheduleApplied:
    attempt: AttemptRef
    next_attempt_at: datetime


@dataclass(frozen=True, slots=True)
class RecoveryRetryScheduled:
    attempt: AttemptRef
    next_attempt_at: datetime


@dataclass(frozen=True, slots=True)
class RecoveryFailedExhausted:
    attempt: AttemptRef


@dataclass(frozen=True, slots=True)
class StaleObservation:
    pass


@dataclass(frozen=True, slots=True)
class NotExpired:
    pass


@dataclass(frozen=True, slots=True)
class Fenced:
    pass


@dataclass(frozen=True, slots=True)
class HeartbeatApplied:
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class InvalidTransition:
    pass


ClaimResult = ClaimedAttempt | NoEligibleClaim | ClaimLeaseLost
FinalizationResult = FinalizationApplied | Fenced | InvalidTransition
RetryScheduleResult = RetryScheduleApplied | Fenced | InvalidTransition
HeartbeatResult = HeartbeatApplied | Fenced
RecoveryResult = RecoveryRetryScheduled | RecoveryFailedExhausted | StaleObservation | NotExpired


@dataclass(frozen=True, slots=True)
class NoEligibleJob:
    pass


@dataclass(frozen=True, slots=True)
class Succeeded:
    attempt: AttemptRef


@dataclass(frozen=True, slots=True)
class Superseded:
    attempt: AttemptRef
    replacement_document_version_id: str | None = None
    replacement_ingestion_job_id: str | None = None


@dataclass(frozen=True, slots=True)
class FailedTerminal:
    attempt: AttemptRef
    failure_reason: str
    safe_code: str


@dataclass(frozen=True, slots=True)
class LeaseLost:
    attempt: AttemptRef


@dataclass(frozen=True, slots=True)
class RetryScheduled:
    attempt: AttemptRef
    safe_code: str
    next_attempt_at: datetime


RunOnceResult = NoEligibleJob | Succeeded | Superseded | RetryScheduled | FailedTerminal | LeaseLost


class CancellationToken(Protocol):
    def cancel(self) -> None: ...

    def is_cancelled(self) -> bool: ...


class Cancellation:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


class WorkHandler(Protocol[SuccessT]):
    def execute(
        self, work: IngestionWork, cancellation: CancellationToken
    ) -> WorkOutcome[SuccessT]: ...


@dataclass(frozen=True, slots=True)
class HandlerRaised:
    pass


@dataclass(frozen=True, slots=True)
class AttemptCompletion[SuccessT]:
    completed_at: float
    result: WorkOutcome[SuccessT] | HandlerRaised


class RunningAttempt(Protocol[SuccessT]):
    def completion(self) -> AttemptCompletion[SuccessT] | None: ...

    def wait_until(self, deadline: float) -> None: ...

    def detach(self) -> None: ...


class RunnerCapacityUnavailable(RuntimeError):
    """Signals that execution admission failed before any durable claim."""


class ExecutionPermit(Protocol):
    def start(
        self,
        handler: WorkHandler[SuccessT],
        work: IngestionWork,
        cancellation: CancellationToken,
        monotonic_clock: MonotonicClock,
    ) -> RunningAttempt[SuccessT]: ...

    def release(self) -> None: ...


class AttemptRunner(Protocol):
    def try_reserve(self) -> ExecutionPermit | None: ...


class MonotonicClock(Protocol):
    def now(self) -> float: ...


class AttemptScheduler(Protocol):
    def wait_until(self, attempt: RunningAttempt[SuccessT], deadline: float) -> None: ...


@dataclass(frozen=True, slots=True)
class AttemptRuntime:
    """One coherent local runtime for bounded attempt supervision."""

    runner: AttemptRunner
    monotonic_clock: MonotonicClock
    scheduler: AttemptScheduler


@dataclass(frozen=True, slots=True)
class AttemptTimedOut:
    pass


@dataclass(frozen=True, slots=True)
class SupervisorLeaseLost:
    pass


@dataclass(frozen=True, slots=True)
class HandlerCompleted[SuccessT]:
    completion: AttemptCompletion[SuccessT]


class AttemptSupervisor:
    """Owns local deadline precedence for one bounded attempt."""

    def __init__(
        self,
        runtime: AttemptRuntime,
        store: IngestionJobCoordinationStore,
        operation_ids: OperationIdFactory,
        timing: AttemptTimingV1,
    ) -> None:
        self._runtime = runtime
        self._store = store
        self._operation_ids = operation_ids
        self._timing = timing

    def resolve_completion(
        self, *, completed_at: float, deadline_at: float
    ) -> AttemptTimedOut | None:
        if completed_at >= deadline_at:
            return AttemptTimedOut()
        return None

    @staticmethod
    def resolve_heartbeat(result: HeartbeatResult) -> SupervisorLeaseLost | None:
        if isinstance(result, Fenced):
            return SupervisorLeaseLost()
        return None

    def supervise(
        self,
        *,
        claim: ClaimedAttempt,
        attempt: RunningAttempt[SuccessT],
        cancellation: CancellationToken,
    ) -> HandlerCompleted[SuccessT] | AttemptTimedOut | SupervisorLeaseLost:
        started_at = self._runtime.monotonic_clock.now()
        deadline_at = started_at + self._timing.max_attempt_runtime.total_seconds()
        next_heartbeat_at = started_at + 30.0
        while True:
            completion = attempt.completion()
            now = self._runtime.monotonic_clock.now()
            if now >= next_heartbeat_at and now < deadline_at:
                operation_id = self._operation_ids.new_heartbeat_id()
                try:
                    heartbeat = self._store.heartbeat(
                        operation_id=operation_id,
                        token=claim.token,
                        lease_duration=self._timing.lease_duration,
                    )
                except CoordinationOutcomeIndeterminate:
                    cancellation.cancel()
                    attempt.detach()
                    raise
                if self.resolve_heartbeat(heartbeat) is not None:
                    cancellation.cancel()
                    attempt.detach()
                    return SupervisorLeaseLost()
                next_heartbeat_at += 30.0
                continue
            if completion is not None and self.resolve_completion(
                completed_at=completion.completed_at, deadline_at=deadline_at
            ) is None:
                return HandlerCompleted(completion)
            if now >= deadline_at or completion is not None:
                cancellation.cancel()
                attempt.detach()
                return AttemptTimedOut()
            self._runtime.scheduler.wait_until(attempt, min(next_heartbeat_at, deadline_at))


class IngestionJobCoordinationStore(Protocol[SuccessT]):
    def observe_expired_attempt(self) -> ExpiredAttemptObservation | None: ...

    def apply_expired_recovery(
        self,
        *,
        operation_id: TransitionOperationId,
        observation: ExpiredAttemptObservation,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry | RetryExhausted,
    ) -> RecoveryResult: ...

    def claim_next_attempt(
        self,
        *,
        operation_id: ClaimOperationId,
        worker_id: str,
        timing: AttemptTimingV1,
    ) -> ClaimResult: ...

    def heartbeat(
        self,
        *,
        operation_id: HeartbeatOperationId,
        token: FencingToken,
        lease_duration: timedelta,
    ) -> HeartbeatResult: ...

    def finalize_success(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        success: SuccessT,
    ) -> FinalizationResult: ...

    def finalize_superseded(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        outcome: WorkSuperseded,
    ) -> FinalizationResult: ...

    def finalize_terminal_failure(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: RetryExhausted | FailTerminal | None = None,
    ) -> FinalizationResult: ...

    def schedule_retry(
        self,
        *,
        operation_id: TransitionOperationId,
        claim: ClaimedAttempt,
        failure: CanonicalFailureV1,
        decision: ScheduleRetry,
    ) -> RetryScheduleResult: ...


class OperationIdFactory(Protocol):
    def new_claim_id(self) -> ClaimOperationId: ...

    def new_heartbeat_id(self) -> HeartbeatOperationId: ...

    def new_transition_id(self) -> TransitionOperationId: ...


class UuidOperationIds:
    def new_claim_id(self) -> ClaimOperationId:
        return ClaimOperationId(str(uuid4()))

    def new_heartbeat_id(self) -> HeartbeatOperationId:
        return HeartbeatOperationId(str(uuid4()))

    def new_transition_id(self) -> TransitionOperationId:
        return TransitionOperationId(str(uuid4()))


class ProcessIngestionJob[SuccessT]:
    """Own the single-attempt lifecycle exposed by this tracer bullet."""

    def __init__(
        self,
        *,
        store: IngestionJobCoordinationStore[SuccessT],
        handler: WorkHandler[SuccessT],
        operation_ids: OperationIdFactory,
        timing: AttemptTimingV1,
        retry_policy: RetryPolicyV1,
        runtime: AttemptRuntime | None = None,
        runner: AttemptRunner | None = None,
    ) -> None:
        self._store = store
        self._handler = handler
        self._operation_ids = operation_ids
        self._timing = timing
        self._retry_policy = retry_policy
        self._runtime = runtime
        if runtime is None and runner is None:
            raise ValueError("ProcessIngestionJob needs a runner or AttemptRuntime")
        self._runner = runtime.runner if runtime is not None else runner

    def run_once(self, worker_id: str) -> RunOnceResult:
        recovered = self._recover_expired_attempt()
        if recovered is not None:
            return recovered

        permit = self._runner.try_reserve()
        if permit is None:
            raise RunnerCapacityUnavailable("no bounded execution capacity is available")
        retain_permit = False
        try:
            claim = self._store.claim_next_attempt(
                operation_id=self._operation_ids.new_claim_id(),
                worker_id=worker_id,
                timing=self._timing,
            )
            if isinstance(claim, NoEligibleClaim):
                return NoEligibleJob()
            if isinstance(claim, ClaimLeaseLost):
                return LeaseLost(attempt=claim.attempt)
            if claim.token.worker_id != worker_id:
                raise CoordinationInvariantError("claim worker does not match run_once worker")

            timed_out = False
            if self._runtime is None:
                outcome = self._handler.execute(claim.work, Cancellation())
            else:
                cancellation = Cancellation()
                try:
                    running = permit.start(
                        self._handler,
                        claim.work,
                        cancellation,
                        self._runtime.monotonic_clock,
                    )
                except BaseException:
                    outcome = WorkFailed(
                        HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected"
                    )
                else:
                    try:
                        supervised = AttemptSupervisor(
                            self._runtime, self._store, self._operation_ids, self._timing
                        ).supervise(claim=claim, attempt=running, cancellation=cancellation)
                    except CoordinationOutcomeIndeterminate:
                        retain_permit = True
                        raise
                    if isinstance(supervised, SupervisorLeaseLost):
                        retain_permit = True
                        return LeaseLost(
                            attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number)
                        )
                    if isinstance(supervised, AttemptTimedOut) or isinstance(
                        supervised.completion.result, HandlerRaised
                    ):
                        retain_permit = isinstance(supervised, AttemptTimedOut)
                        timed_out = isinstance(supervised, AttemptTimedOut)
                        outcome = WorkFailed(
                            HandlerFailureKindV1.WORKER_UNEXPECTED, "worker_unexpected"
                        )
                    else:
                        outcome = supervised.completion.result
        finally:
            if not retain_permit:
                permit.release()
        operation_id = self._operation_ids.new_transition_id()
        if isinstance(outcome, WorkSucceeded):
            finalization = self._store.finalize_success(
                operation_id=operation_id,
                claim=claim,
                success=outcome.payload,
            )
            if isinstance(finalization, FinalizationApplied):
                if finalization.outcome == "superseded":
                    return Superseded(
                        attempt=finalization.attempt,
                        replacement_document_version_id=(
                            finalization.replacement_document_version_id
                        ),
                        replacement_ingestion_job_id=finalization.replacement_ingestion_job_id,
                    )
                return Succeeded(attempt=finalization.attempt)
            if isinstance(finalization, Fenced):
                return LeaseLost(attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number))
            raise CoordinationInvariantError("success finalization was not applicable")

        if isinstance(outcome, WorkSuperseded):
            finalization = self._store.finalize_superseded(
                operation_id=operation_id,
                claim=claim,
                outcome=outcome,
            )
            if isinstance(finalization, FinalizationApplied):
                return Superseded(
                    attempt=finalization.attempt,
                    replacement_document_version_id=outcome.replacement_document_version_id,
                    replacement_ingestion_job_id=outcome.replacement_ingestion_job_id,
                )
            if isinstance(finalization, Fenced):
                return LeaseLost(attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number))
            raise CoordinationInvariantError("superseded finalization was not applicable")

        if not isinstance(outcome, WorkFailed):
            raise CoordinationInvariantError(
                "work handler returned an unsupported outcome"
            )
        if timed_out:
            observed_failure = CanonicalFailureV1(
                cause=FailureCauseV1.ATTEMPT_TIMEOUT,
                safe_code="attempt_timeout",
                failure_reason=None,
                cause_version="failure-causes-v1",
                mapping_version="supervisor-v1",
            )
        else:
            observed_failure = CauseMappingV1.map(outcome)
        decision = self._retry_policy.decide(
            observed_failure.cause,
            attempt_count=claim.attempt_count,
            max_attempts=claim.max_attempts,
        )
        if isinstance(decision, ScheduleRetry):
            scheduled = self._store.schedule_retry(
                operation_id=operation_id,
                claim=claim,
                failure=observed_failure,
                decision=decision,
            )
            if isinstance(scheduled, RetryScheduleApplied):
                return RetryScheduled(
                    attempt=scheduled.attempt,
                    safe_code=observed_failure.safe_code,
                    next_attempt_at=scheduled.next_attempt_at,
                )
            if isinstance(scheduled, Fenced):
                return LeaseLost(attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number))
            raise CoordinationInvariantError("retry scheduling was not applicable")

        if isinstance(decision, RetryExhausted):
            failure = CanonicalFailureV1(
                cause=observed_failure.cause,
                safe_code=observed_failure.safe_code,
                failure_reason="retry_exhausted",
                cause_version=observed_failure.cause_version,
                mapping_version=observed_failure.mapping_version,
            )
        else:
            failure = CauseMappingV1.terminalize(observed_failure)

        finalization = self._store.finalize_terminal_failure(
            operation_id=operation_id,
            claim=claim,
            failure=failure,
            decision=decision,
        )
        if isinstance(finalization, FinalizationApplied):
            if failure.failure_reason is None:
                raise CoordinationInvariantError(
                    "terminal finalization did not have a failure reason"
                )
            return FailedTerminal(
                attempt=finalization.attempt,
                failure_reason=failure.failure_reason,
                safe_code=failure.safe_code,
            )
        if isinstance(finalization, Fenced):
            return LeaseLost(attempt=AttemptRef(claim.token.job_id, claim.token.attempt_number))
        raise CoordinationInvariantError("terminal finalization was not applicable")

    def _recover_expired_attempt(self) -> RunOnceResult | None:
        observation = self._store.observe_expired_attempt()
        if observation is None:
            return None

        failure = CanonicalFailureV1(
            cause=FailureCauseV1.LEASE_EXPIRED,
            safe_code="lease_expired",
            failure_reason=None,
            cause_version="failure-causes-v1",
            mapping_version="cause-mapping-v1",
        )
        decision = self._retry_policy.decide(
            failure.cause,
            attempt_count=observation.attempt_count,
            max_attempts=observation.max_attempts,
        )
        if not isinstance(decision, (ScheduleRetry, RetryExhausted)):
            raise CoordinationInvariantError(
                "lease-expiry recovery requires a retry policy decision"
            )

        recovery = self._store.apply_expired_recovery(
            operation_id=self._operation_ids.new_transition_id(),
            observation=observation,
            failure=failure,
            decision=decision,
        )
        if isinstance(recovery, RecoveryRetryScheduled):
            return RetryScheduled(
                attempt=recovery.attempt,
                safe_code=failure.safe_code,
                next_attempt_at=recovery.next_attempt_at,
            )
        if isinstance(recovery, RecoveryFailedExhausted):
            return FailedTerminal(
                attempt=recovery.attempt,
                failure_reason="retry_exhausted",
                safe_code=failure.safe_code,
            )
        if isinstance(recovery, (StaleObservation, NotExpired)):
            return None
        raise CoordinationInvariantError("expired-attempt recovery was not applicable")
