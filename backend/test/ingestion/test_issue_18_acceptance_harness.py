from __future__ import annotations

from dataclasses import replace

import pytest
from backend.test.fixtures.issue_18_acceptance import (
    AcceptanceEmbeddingProvider,
    AcceptanceExtractor,
    AcceptanceObjectStore,
    ImmediateRunner,
    PdfSubmissionConfiguration,
    ProviderStatusSentinel,
    RecordingCoordinationStore,
    RetryableStorageSentinel,
    SourceRetentionProbe,
    handler_for,
    make_claim,
    pdf_extraction,
    pdf_metadata,
    pdf_raw_bytes,
    pdf_success,
    work_for,
)

from knora.domain.errors import KnoraError
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    Cancellation,
    FailedTerminal,
    HandlerFailureKindV1,
    PdfDerivationProfile,
    ProcessIngestionJob,
    RetryPolicyV1,
    RetryScheduled,
    UuidOperationIds,
    WorkFailed,
    WorkSucceeded,
)
from knora.ingestion.pdf import PdfExtractionError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class ZeroRandom:
    def next_int_inclusive(self, upper_bound_microseconds: int) -> int:
        return 0


@pytest.mark.parametrize(
    ("field", "observed"),
    [
        ("workspace_id", "workspace-other"),
        ("object_key", "object-other"),
        ("sha256", "f" * 64),
        ("byte_size", 999),
        ("media_type", "application/octet-stream"),
    ],
    ids=["workspace", "object-key", "sha256", "byte-size", "media-type"],
)
def test_tc07a_each_object_metadata_mismatch_stops_before_read_or_provider(
    field: str,
    observed: str | int,
) -> None:
    expected = pdf_metadata()
    observed_metadata = replace(expected, **{field: observed})
    object_store = AcceptanceObjectStore(metadata=observed_metadata)
    handler, _, extractor, provider = handler_for(
        expected,
        object_store=object_store,
    )

    outcome = handler.execute(work_for(expected), Cancellation())

    assert outcome == WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input")
    assert object_store.head_calls == 1
    assert object_store.open_read_calls == 0
    assert extractor.calls == 0
    assert provider.calls == 0


def test_tc01b_worker_uses_the_immutable_profile_after_current_selection_moves() -> None:
    profile_a = EmbeddingConfiguration.milestone_one_local()
    profile_b = EmbeddingConfiguration(
        id="embedding-profile-b",
        provider="deterministic-profile-b",
        model="profile-b-model",
        dimensions=1536,
        distance_metric="cosine",
    )
    metadata = pdf_metadata()
    handler, _, extractor, provider = handler_for(
        metadata,
        embedding_configuration=profile_a,
    )
    work = work_for(
        metadata,
        PdfDerivationProfile.milestone_two(embedding_configuration=profile_a),
    )
    current_selection = profile_b

    outcome = handler.execute(work, Cancellation())

    assert isinstance(outcome, WorkSucceeded)
    assert current_selection != provider.configurations[0]
    assert provider.configurations == [profile_a]
    assert extractor.configurations[0].normalizer_version == "pdf-normalizer-m2-v1"


@pytest.mark.parametrize(
    ("failure", "expected_kind", "expected_code"),
    [
        (
            ConnectionError("timeout"),
            HandlerFailureKindV1.PROVIDER_TRANSIENT,
            "provider_transient",
        ),
        (
            TimeoutError("timeout"),
            HandlerFailureKindV1.PROVIDER_TRANSIENT,
            "provider_transient",
        ),
        (
            ProviderStatusSentinel(429),
            HandlerFailureKindV1.PROVIDER_TRANSIENT,
            "provider_transient",
        ),
        (
            ProviderStatusSentinel(503),
            HandlerFailureKindV1.PROVIDER_TRANSIENT,
            "provider_transient",
        ),
        (
            KnoraError("PROVIDER_REQUEST_FAILED"),
            HandlerFailureKindV1.PROVIDER_TRANSIENT,
            "provider_transient",
        ),
    ],
    ids=[
        "provider-connection",
        "provider-timeout",
        "provider-429",
        "provider-503",
        "provider-request",
    ],
)
def test_tc03_provider_transients_become_retryable_handler_facts(
    failure: BaseException,
    expected_kind: HandlerFailureKindV1,
    expected_code: str,
) -> None:
    metadata = pdf_metadata()
    _, _, extractor, _ = handler_for(metadata)
    configuration = EmbeddingConfiguration.milestone_one_local()
    extraction = pdf_extraction()
    success = pdf_success(
        extraction=extraction,
        vector_dimensions=configuration.dimensions,
    )
    provider = AcceptanceEmbeddingProvider(
        batch=EmbeddingBatch(
            vectors=success.vectors,
            provider=success.embedding_provider,
            model=success.embedding_model,
        ),
        failure=failure,
    )
    handler, _, _, _ = handler_for(
        metadata,
        extractor=extractor,
        provider=provider,
    )

    outcome = handler.execute(work_for(metadata), Cancellation())

    assert outcome == WorkFailed(expected_kind, expected_code)


def test_tc03d_transient_object_store_failure_is_retryable_and_provider_is_not_called() -> None:
    metadata = pdf_metadata()
    object_store = AcceptanceObjectStore(
        metadata=metadata,
        open_error=RetryableStorageSentinel(),
    )
    handler, _, extractor, provider = handler_for(metadata, object_store=object_store)

    outcome = handler.execute(work_for(metadata), Cancellation())

    assert outcome == WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
    assert extractor.calls == 0
    assert provider.calls == 0


@pytest.mark.parametrize(
    ("error", "expected_kind", "expected_code"),
    [
        (
            PdfExtractionError(
                "PDF_EXTRACTOR_UNAVAILABLE", reason="CHILD_CRASH", retryable=True
            ),
            HandlerFailureKindV1.WORKER_UNEXPECTED,
            "PDF_EXTRACTOR_UNAVAILABLE",
        ),
        (
            PdfExtractionError("PDF_TEXT_INSUFFICIENT", reason="INSUFFICIENT_EXTRACTABLE_TEXT"),
            HandlerFailureKindV1.INVALID_INPUT,
            "PDF_TEXT_INSUFFICIENT",
        ),
        (
            PdfExtractionError("PDF_ENCRYPTED", reason="ENCRYPTED"),
            HandlerFailureKindV1.UNSUPPORTED_INPUT,
            "PDF_ENCRYPTED",
        ),
        (
            PdfExtractionError("PDF_RESOURCE_LIMIT_EXCEEDED", reason="RAW_FILE_SIZE"),
            HandlerFailureKindV1.RESOURCE_LIMIT,
            "PDF_RESOURCE_LIMIT_EXCEEDED",
        ),
        (
            PdfExtractionError("PDF_MALFORMED", reason="MALFORMED"),
            HandlerFailureKindV1.INVALID_INPUT,
            "PDF_MALFORMED",
        ),
    ],
    ids=["child-crash", "text-insufficient", "encrypted", "resource-limit", "malformed"],
)
def test_tc03_extractor_taxonomy_is_preserved_as_typed_handler_facts(
    error: PdfExtractionError,
    expected_kind: HandlerFailureKindV1,
    expected_code: str,
) -> None:
    metadata = pdf_metadata()
    extractor = AcceptanceExtractor(result=pdf_extraction(), failure=error)
    handler, _, _, provider = handler_for(metadata, extractor=extractor)

    outcome = handler.execute(work_for(metadata), Cancellation())

    assert outcome == WorkFailed(expected_kind, expected_code)
    assert provider.calls == 0


@pytest.mark.parametrize(
    ("success_kwargs", "expected_code"),
    [
        ({"vector_dimensions": 1535}, "vector_mismatch"),
        ({"provider": "wrong-provider"}, "vector_mismatch"),
        ({"model": "wrong-model"}, "vector_mismatch"),
    ],
    ids=["wrong-dimension", "wrong-provider", "wrong-model"],
)
def test_tc03j_to_l_vector_identity_mismatch_is_terminal_before_persistence(
    success_kwargs: dict[str, object],
    expected_code: str,
) -> None:
    metadata = pdf_metadata()
    configuration = EmbeddingConfiguration.milestone_one_local()
    wrong_success = pdf_success(
        PdfSubmissionConfiguration.milestone_two(
            embedding_configuration=configuration
        ),
        **success_kwargs,
    )
    provider = AcceptanceEmbeddingProvider(
        batch=EmbeddingBatch(
            vectors=wrong_success.vectors,
            provider=wrong_success.embedding_provider,
            model=wrong_success.embedding_model,
        )
    )
    handler, _, _, _ = handler_for(metadata, provider=provider)

    outcome = handler.execute(work_for(metadata), Cancellation())

    assert outcome == WorkFailed(HandlerFailureKindV1.VECTOR_MISMATCH, expected_code)


def test_tc03j_provider_vector_count_mismatch_is_terminal_before_persistence() -> None:
    metadata = pdf_metadata()
    configuration = EmbeddingConfiguration.milestone_one_local()
    expected = pdf_success(
        PdfSubmissionConfiguration.milestone_two(
            embedding_configuration=configuration
        ),
    )
    provider = AcceptanceEmbeddingProvider(
        batch=EmbeddingBatch(
            vectors=expected.vectors[:-1],
            provider=expected.embedding_provider,
            model=expected.embedding_model,
        )
    )
    handler, _, _, _ = handler_for(metadata, provider=provider)

    outcome = handler.execute(work_for(metadata), Cancellation())

    assert outcome == WorkFailed(HandlerFailureKindV1.VECTOR_MISMATCH, "vector_mismatch")
    assert provider.calls == 1


def test_tc03_retryable_handler_fact_reaches_worker_retry_policy() -> None:
    metadata = pdf_metadata()
    handler, _, _, _ = handler_for(
        metadata,
        provider=AcceptanceEmbeddingProvider(
            batch=EmbeddingBatch(
                vectors=pdf_success().vectors,
                provider="deterministic-local",
                model="text-embedding-3-small",
            ),
            failure=TimeoutError("provider timeout"),
        ),
    )
    work = work_for(metadata)
    store = RecordingCoordinationStore(claim=make_claim(work))
    processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(ZeroRandom()),
        runner=ImmediateRunner(),
    )

    result = processor.run_once("worker-18")

    assert isinstance(result, RetryScheduled)
    assert store.retry_calls == 1


def test_tc07b_parent_read_is_incremental_and_retention_is_bounded() -> None:
    raw = pdf_raw_bytes(b"x" * 256)
    metadata = pdf_metadata(raw=raw)
    retention = SourceRetentionProbe(raw_source_size=len(raw))
    object_store = AcceptanceObjectStore(metadata=metadata, raw=raw, retention_probe=retention)
    handler, _, _, provider = handler_for(metadata, object_store=object_store)

    outcome = handler.execute(work_for(metadata), Cancellation())

    assert isinstance(outcome, WorkSucceeded)
    assert retention.whole_object_read_count == 0
    assert retention.tagged_reference_count == 0
    assert sum(tag.size for tag in retention.observed_tags) == retention.raw_source_size
    assert retention.peak_live_parent_raw_source_bytes < retention.raw_source_size
    assert provider.calls == 1


def test_tc09_terminal_worker_paths_never_delete_the_original_source_object() -> None:
    metadata = pdf_metadata()
    object_store = AcceptanceObjectStore(metadata=metadata)
    handler, _, _, _ = handler_for(metadata, object_store=object_store)
    work = work_for(metadata)
    store = RecordingCoordinationStore(claim=make_claim(work))
    success_processor = ProcessIngestionJob(
        store=store,
        handler=handler,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(ZeroRandom()),
        runner=ImmediateRunner(),
    )

    success_result = success_processor.run_once("worker-18")

    assert not isinstance(success_result, FailedTerminal)
    assert object_store.delete_calls == []

    mismatched_store = AcceptanceObjectStore(
        metadata=replace(metadata, sha256="f" * 64),
    )
    failed_handler, _, _, _ = handler_for(metadata, object_store=mismatched_store)
    failed_store = RecordingCoordinationStore(claim=make_claim(work))
    failed_processor = ProcessIngestionJob(
        store=failed_store,
        handler=failed_handler,
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(ZeroRandom()),
        runner=ImmediateRunner(),
    )

    failed_result = failed_processor.run_once("worker-18")

    assert isinstance(failed_result, FailedTerminal)
    assert mismatched_store.delete_calls == []
