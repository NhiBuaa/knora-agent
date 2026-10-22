"""Explicit trusted-host corpus preparation; no default registration or execution."""

import json
import re
from contextvars import copy_context
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Protocol

from knora.evaluation.contracts import FrozenDataset
from knora.evaluation.live_admission import LiveAdmission, live_scope
from knora.ingestion.job_processing import (
    AttemptRuntime,
    Cancellation,
    ClaimedAttempt,
    FinalizationApplied,
    FinalizationResult,
    IngestionWork,
    PdfDerivationHandler,
    PdfDerivationSuccess,
    WorkSucceeded,
)
from knora.ingestion.jobs import PdfSubmissionConfiguration
from knora.providers.embedding import EmbeddingConfiguration


def _require(condition):
    if not condition:
        raise ValueError("CORPUS_PLAN_INVALID")


@dataclass(frozen=True)
class CorpusSourcePin:
    source_id: str
    job_id: str
    document_id: str
    document_version_id: str
    source_key: str
    raw_sha256: str
    byte_size: int
    object_key: str
    original_source_object_id: str
    snapshot_id: str
    snapshot_sha256: str
    snapshot_configuration_sha256: str
    expected_revision: int
    expected_current_version_id: str | None
    expected_active_set_id: str | None


@dataclass(frozen=True)
class CorpusPreparationPlan:
    profile_id: str
    frozen_json: str
    dataset_revision: int
    workspace_revision: int
    owner_issuer: str
    owner_subject: str
    sources: tuple[CorpusSourcePin, ...]
    configuration: PdfSubmissionConfiguration
    embedding_request_digests: tuple[str, ...]
    max_provider_calls: int
    max_provider_retries: int = 0

    def __post_init__(self):
        try:
            frozen = FrozenDataset.from_json(self.frozen_json)
            _require(isinstance(self.sources, tuple) and len(self.sources) == 2)
            _require(len(frozen.gold.sources) >= 2)
            _require(isinstance(self.profile_id, str) and 0 < len(self.profile_id) <= 50)
            _require(
                (self.owner_issuer, self.owner_subject)
                == (frozen.approval.owner_issuer, frozen.approval.owner_subject)
            )
            _require(
                all(
                    type(v) is int and v >= 0
                    for v in (self.dataset_revision, self.workspace_revision)
                )
            )
            for field in (
                "source_id",
                "job_id",
                "document_id",
                "document_version_id",
                "object_key",
                "original_source_object_id",
                "snapshot_id",
            ):
                _require(len({getattr(p, field) for p in self.sources}) == 2)
                _require(
                    all(
                        isinstance(getattr(p, field), str) and getattr(p, field)
                        for p in self.sources
                    )
                )
            _require(
                {
                    (p.document_id, p.document_version_id, p.raw_sha256) for p in self.sources
                }.issubset(
                    {
                        (p.document_id, p.document_version_id, p.raw_sha256)
                        for p in frozen.gold.sources
                    }
                )
            )
            for pin in self.sources:
                _require(
                    pin.source_key == f"evaluation/{frozen.reference.dataset_id}/{pin.source_id}"
                )
                _require(re.fullmatch(r"[a-f0-9]{64}", pin.raw_sha256))
                _require(re.fullmatch(r"[a-f0-9]{64}", pin.snapshot_sha256))
                _require(re.fullmatch(r"[a-f0-9]{64}", pin.snapshot_configuration_sha256))
                _require(type(pin.byte_size) is int and pin.byte_size > 0)
                _require(type(pin.expected_revision) is int and pin.expected_revision >= 0)
                _require(
                    all(
                        v is None or isinstance(v, str) and v
                        for v in (pin.expected_current_version_id, pin.expected_active_set_id)
                    )
                )
            embedding = self.configuration.embedding_configuration
            _require(embedding == EmbeddingConfiguration.cloudflare_qwen3_06b())
            _require(
                isinstance(self.embedding_request_digests, tuple)
                and self.embedding_request_digests
                and all(
                    re.fullmatch(r"[a-f0-9]{64}", digest)
                    for digest in self.embedding_request_digests
                )
            )
            _require(type(self.max_provider_calls) is int and self.max_provider_calls > 0)
            _require(self.max_provider_retries == 0)
            _require(
                self.configuration
                in (
                    PdfSubmissionConfiguration.milestone_two(embedding_configuration=embedding),
                    PdfSubmissionConfiguration.layout_preserving(embedding_configuration=embedding),
                )
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("CORPUS_PLAN_INVALID") from error

    @property
    def frozen(self):
        return FrozenDataset.from_json(self.frozen_json)

    def payload(self):
        return {
            **asdict(self),
            "frozen_json": json.loads(self.frozen_json),
            "job_attempts_per_source": 1,
            "activation": "pinned_versions",
        }

    def scope(self):
        return live_scope(
            "corpus_prepare", self.profile_id, self.frozen.reference.workspace_id, self.payload()
        )

    def work(self, pin):
        config = self.configuration
        return IngestionWork(
            self.frozen.reference.workspace_id,
            pin.document_id,
            pin.document_version_id,
            pin.original_source_object_id,
            pin.object_key,
            "application/pdf",
            config.parser_configuration_id,
            config.normalizer_configuration_id,
            config.chunking_configuration.id,
            config.embedding_configuration.id,
            pin.raw_sha256,
            pin.byte_size,
        )


class CorpusPreparationStore(Protocol):
    def inspect(self, plan: CorpusPreparationPlan) -> None: ...
    def begin(
        self, plan: CorpusPreparationPlan, admission: LiveAdmission
    ) -> tuple[ClaimedAttempt, ...]: ...
    def check_ready(
        self, plan: CorpusPreparationPlan, admission: LiveAdmission, claim: ClaimedAttempt
    ) -> None: ...
    def activate_batch(
        self,
        plan: CorpusPreparationPlan,
        admission: LiveAdmission,
        items: tuple[tuple[ClaimedAttempt, PdfDerivationSuccess], ...],
    ) -> tuple[FinalizationResult, ...]: ...


def prepare_corpus(
    plan: CorpusPreparationPlan,
    *,
    admission: LiveAdmission,
    store: CorpusPreparationStore,
    handler: PdfDerivationHandler,
    provider_client,
    runtime: AttemptRuntime,
):
    """The host supplies the guarded client to the handler's actual embedding provider."""
    scope = plan.scope()
    admission.verify(scope)
    admission.check_corpus_envelope(
        scope,
        request_digests=plan.embedding_request_digests,
        max_calls=plan.max_provider_calls,
        max_retries=plan.max_provider_retries,
    )
    if getattr(provider_client, "_knora_live_admission", None) is not admission:
        raise ValueError("LIVE_APPROVAL_REQUIRED")
    provider = getattr(handler, "_embedding_provider", None)
    if getattr(provider, "_client", None) is not provider_client:
        raise ValueError("LIVE_APPROVAL_REQUIRED")
    store.inspect(plan)
    results = []
    with admission.corpus_operation(scope, plan.payload()):
        claims = store.begin(plan, admission)
        if len(claims) != 2 or {c.token.job_id for c in claims} != {p.job_id for p in plan.sources}:
            raise ValueError("CORPUS_JOB_MISMATCH")
        successes = []
        for claim in claims:
            pin = next(p for p in plan.sources if p.job_id == claim.token.job_id)
            if (
                claim.work != plan.work(pin)
                or claim.attempt_count != 1
                or claim.max_attempts != 1
                or claim.token.attempt_number != 1
            ):
                raise ValueError("CORPUS_JOB_MISMATCH")
            admission.check_mutation(scope)
            with admission.corpus_dispatch(
                scope, lambda claim=claim: store.check_ready(plan, admission, claim)
            ):
                outcome = _derive(handler, claim, admission, scope, runtime)
            if not isinstance(outcome, WorkSucceeded):
                raise ValueError("CORPUS_DERIVATION_FAILED")
            successes.append((claim, outcome.payload))
        state = admission.snapshot()
        if state["attempts"] != plan.max_provider_calls or state["pending"] is not None:
            raise ValueError("CORPUS_ENVELOPE_MISMATCH")
        results = store.activate_batch(plan, admission, tuple(successes))
        if len(results) != 2:
            raise ValueError("CORPUS_ACTIVATION_FAILED")
        for result in results:
            if not isinstance(result, FinalizationApplied) or result.outcome != "succeeded":
                raise ValueError("CORPUS_ACTIVATION_FAILED")
        admission.record_corpus_result(
            {
                claim.work.document_version_id: {
                    "document_id": claim.work.document_id,
                    "extraction_snapshot_id": next(
                        p.snapshot_id
                        for p in plan.sources
                        if p.document_version_id == claim.work.document_version_id
                    ),
                    "configuration_sha256": next(
                        p.snapshot_configuration_sha256
                        for p in plan.sources
                        if p.document_version_id == claim.work.document_version_id
                    ),
                    "extraction_sha256": next(
                        p.snapshot_sha256
                        for p in plan.sources
                        if p.document_version_id == claim.work.document_version_id
                    ),
                    "raw_sha256": claim.work.source_sha256,
                    "chunk_digests": [
                        chunk.content_checksum for chunk in success.extraction.chunks
                    ],
                }
                for claim, success in successes
            },
            plan.configuration.embedding_configuration.id,
        )
    return tuple(results)


def _derive(handler, claim, admission, scope, runtime):
    permit = runtime.runner.try_reserve()
    if permit is None:
        raise ValueError("CORPUS_CAPACITY_UNAVAILABLE")
    cancellation = Cancellation()
    context = copy_context()
    running = None
    try:
        deadline = runtime.monotonic_clock.now() + admission.remaining_seconds()
        running = permit.start(
            SimpleNamespace(execute=lambda work, token: context.run(handler.execute, work, token)),
            claim.work,
            cancellation,
            runtime.monotonic_clock,
        )
        while True:
            admission.check_corpus_progress(scope)
            now = runtime.monotonic_clock.now()
            completion = running.completion()
            if now >= deadline:
                raise ValueError("LIVE_APPROVAL_EXPIRED")
            if completion is not None:
                if not isinstance(completion.result, WorkSucceeded):
                    raise ValueError("CORPUS_DERIVATION_FAILED")
                return completion.result
            runtime.scheduler.wait_until(running, min(deadline, now + 0.05))
    except BaseException:
        cancellation.cancel()
        if running is not None:
            running.detach()
        raise
    finally:
        # A detached handler retains the runner slot until its physical exit.
        if running is None or running.completion() is not None:
            permit.release()
