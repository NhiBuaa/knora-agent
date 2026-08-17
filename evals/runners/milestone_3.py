"""Production-observation contracts and metrics for Milestone 3 evaluation."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import timedelta
from fractions import Fraction
from math import isfinite
from threading import Event, Lock, Thread
from time import get_clock_info, perf_counter
from uuid import uuid4

import httpx
from evals.datasets.milestone_3 import Milestone3Case, Milestone3CorpusManifest
from evals.runners.evaluation_ownership import (
    EvaluationOwnershipCapability,
    EvaluationOwnershipError,
    EvaluationOwnershipSnapshot,
    EvaluationOwnershipStore,
)

METRIC_CONTRACT = "m3-retrieval-metrics-v1"
RECALL_K = 8
MARKER_PATTERN = re.compile(r"\[\[(E[1-9][0-9]*)\]\]")
_MARKER_TOKEN_PATTERN = re.compile(r"\[\[([^\]]*)\]\]")
_VALID_MARKER_ID_PATTERN = re.compile(r"E[1-9][0-9]*\Z")


class ObservationFailure(ValueError):
    """A trace/corpus observation cannot be used as a retrieval-quality score."""


@dataclass(frozen=True, slots=True, order=True)
class CanonicalChunkReference:
    """Portable M3 identity, scoped to the corpus manifest's immutable Chunk Set."""

    chunk_set_provenance_id: str
    source_key: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class PublicCitation:
    evidence_id: str
    source_key: str
    excerpt: str
    source_locator: str


@dataclass(frozen=True, slots=True)
class PublicResponseProjection:
    decision: str
    answer: str | None
    refusal_reason: str | None
    citations: tuple[PublicCitation, ...]
    answer_marker_ids: tuple[str, ...]
    citation_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M3Observation:
    case_id: str
    candidates: tuple[CanonicalChunkReference, ...] = ()
    retrieval_latency_ms: float | None = None
    end_to_end_latency_ms: float | None = None
    retrieval_configuration_id: str | None = None
    chunk_set_provenance_id: str | None = None
    source_bindings: tuple[SourceBinding, ...] = ()
    public_answer: str | None = None
    public_citations: tuple[PublicCitation, ...] = ()
    decision: str | None = None
    refusal_reason: str | None = None
    answer_marker_ids: tuple[str, ...] = ()
    citation_evidence_ids: tuple[str, ...] = ()
    refusal_correctness: bool | None = None
    failure_code: str | None = None

    @classmethod
    def success(
        cls,
        *,
        case_id: str,
        candidates: tuple[CanonicalChunkReference, ...],
        retrieval_latency_ms: float,
        end_to_end_latency_ms: float,
        retrieval_configuration_id: str,
        chunk_set_provenance_id: str,
        source_bindings: tuple[SourceBinding, ...],
        public_answer: str | None = None,
        public_citations: tuple[PublicCitation, ...] = (),
        decision: str | None = None,
        refusal_reason: str | None = None,
        answer_marker_ids: tuple[str, ...] = (),
        citation_evidence_ids: tuple[str, ...] = (),
        refusal_correctness: bool | None = None,
    ) -> M3Observation:
        if (
            not isfinite(float(retrieval_latency_ms))
            or not isfinite(float(end_to_end_latency_ms))
            or retrieval_latency_ms < 0
            or end_to_end_latency_ms < 0
        ):
            raise ValueError("latency must be non-negative")
        _validate_observation_response(
            decision=decision,
            public_answer=public_answer,
            public_citations=public_citations,
            refusal_reason=refusal_reason,
            answer_marker_ids=answer_marker_ids,
            citation_evidence_ids=citation_evidence_ids,
            refusal_correctness=refusal_correctness,
        )
        return cls(
            case_id=case_id,
            candidates=candidates,
            retrieval_latency_ms=retrieval_latency_ms,
            end_to_end_latency_ms=end_to_end_latency_ms,
            retrieval_configuration_id=retrieval_configuration_id,
            chunk_set_provenance_id=chunk_set_provenance_id,
            source_bindings=source_bindings,
            public_answer=public_answer,
            public_citations=public_citations,
            decision=decision,
            refusal_reason=refusal_reason,
            answer_marker_ids=answer_marker_ids,
            citation_evidence_ids=citation_evidence_ids,
            refusal_correctness=refusal_correctness,
        )

    @classmethod
    def failure(cls, case_id: str, code: str) -> M3Observation:
        return cls(case_id=case_id, failure_code=code)

    @property
    def is_success(self) -> bool:
        if self.failure_code is not None:
            return False
        try:
            _validate_observation_response(
                decision=self.decision,
                public_answer=self.public_answer,
                public_citations=self.public_citations,
                refusal_reason=self.refusal_reason,
                answer_marker_ids=self.answer_marker_ids,
                citation_evidence_ids=self.citation_evidence_ids,
                refusal_correctness=self.refusal_correctness,
            )
        except (AttributeError, TypeError, ValueError):
            return False
        return True


def _validate_observation_response(
    *,
    decision: str | None,
    public_answer: str | None,
    public_citations: tuple[PublicCitation, ...],
    refusal_reason: str | None,
    answer_marker_ids: tuple[str, ...],
    citation_evidence_ids: tuple[str, ...],
    refusal_correctness: bool | None,
) -> None:
    if decision not in {"ANSWER", "REFUSAL"}:
        raise ValueError("public response is invalid")
    if refusal_correctness is not None and type(refusal_correctness) is not bool:
        raise ValueError("public response is invalid")
    if decision == "REFUSAL":
        if (
            public_answer is not None
            or public_citations
            or refusal_reason != "INSUFFICIENT_EVIDENCE"
            or answer_marker_ids
            or citation_evidence_ids
        ):
            raise ValueError("public response is invalid")
        return
    if (
        not isinstance(public_answer, str)
        or not public_answer.strip()
        or refusal_reason is not None
        or not public_citations
        or not answer_marker_ids
        or tuple(answer_marker_ids) != tuple(citation_evidence_ids)
        or tuple(item.evidence_id for item in public_citations)
        != tuple(citation_evidence_ids)
        or any(
            not isinstance(item, str)
            or _VALID_MARKER_ID_PATTERN.fullmatch(item) is None
            for item in citation_evidence_ids
        )
        or len(set(citation_evidence_ids)) != len(citation_evidence_ids)
        or any(
            not isinstance(item, PublicCitation)
            or not all(
                isinstance(value, str) and value.strip()
                for value in (
                    item.evidence_id,
                    item.source_key,
                    item.excerpt,
                    item.source_locator,
                )
            )
            or _VALID_MARKER_ID_PATTERN.fullmatch(item.evidence_id) is None
            for item in public_citations
        )
        or any(
            not isinstance(item, str)
            or _VALID_MARKER_ID_PATTERN.fullmatch(item) is None
            for item in answer_marker_ids
        )
    ):
        raise ValueError("public response is invalid")
    try:
        parsed_markers = _parse_public_markers(public_answer)
    except ObservationFailure as error:
        raise ValueError("public response is invalid") from error
    if parsed_markers != tuple(answer_marker_ids):
        raise ValueError("public response is invalid")


@dataclass(frozen=True, slots=True)
class EvaluationEnvironmentBinding:
    """Immutable verified manifest-to-production environment association."""

    dataset_manifest_identity: str
    corpus_manifest_identity: str
    chunk_set_provenance_id: str
    workspace_id: str
    retrieval_configuration_id: str
    embedding_configuration_id: str | None = None
    source_bindings: tuple[SourceBinding, ...] = ()
    schema_version: int = 3
    dataset_version: str | None = None
    dataset_digest: str | None = None
    corpus_id: str | None = None
    corpus_digest: str | None = None
    chunk_set_id: str | None = None
    chunk_set_digest: str | None = None
    workspace: str | None = None
    chunking_configuration: str | None = None
    generation_configuration: str | None = None
    scorer_configuration: str | None = None
    scorer_model: str | None = None
    scorer_prompt: str | None = None
    scorer_policy: str | None = None
    scorer_stochasticity: str | None = None
    source_commit: str | None = None
    evaluation_commit: str | None = None
    report_artifact_schema_version: int = 1
    strategy: str | None = None
    fusion_policy_id: str | None = None
    fusion_policy_version: str | None = None
    lexical_policy_id: str | None = None
    fts_candidate_k: int | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.embedding_configuration_id, str)
            or not self.embedding_configuration_id
        ):
            raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID")

    @classmethod
    def from_mapping(cls, value: object) -> EvaluationEnvironmentBinding:
        fields = (
            "dataset_manifest_identity",
            "corpus_manifest_identity",
            "chunk_set_provenance_id",
            "workspace_id",
            "retrieval_configuration_id",
        )
        raw_bindings = value.get("source_bindings") if isinstance(value, dict) else None
        raw_embedding_configuration_id = (
            value.get("embedding_configuration_id") if isinstance(value, dict) else None
        )
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 3
            or any(not isinstance(value.get(field), str) or not value[field] for field in fields)
            or not isinstance(raw_bindings, list)
            or not isinstance(raw_embedding_configuration_id, str)
            or not raw_embedding_configuration_id
        ):
            raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID")
        try:
            bindings = tuple(SourceBinding.from_mapping(item) for item in raw_bindings)
        except (TypeError, ValueError) as error:
            raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID") from error
        if not bindings or len({item.source_key for item in bindings}) != len(bindings):
            raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID")
        optional_fields = (
            "dataset_version",
            "dataset_digest",
            "corpus_id",
            "corpus_digest",
            "chunk_set_id",
            "chunk_set_digest",
            "workspace",
            "chunking_configuration",
            "generation_configuration",
            "scorer_configuration",
            "scorer_model",
            "scorer_prompt",
            "scorer_policy",
            "scorer_stochasticity",
            "source_commit",
            "evaluation_commit",
            "report_artifact_schema_version",
            "strategy",
            "fusion_policy_id",
            "fusion_policy_version",
            "lexical_policy_id",
            "fts_candidate_k",
        )
        return cls(
            **{field: value[field] for field in fields},
            embedding_configuration_id=raw_embedding_configuration_id,
            source_bindings=bindings,
            **{
                field: value[field]
                for field in optional_fields
                if field in value
            },
        )

    def provenance(self) -> dict[str, object]:
        modern = (
            self.dataset_version,
            self.dataset_digest,
            self.corpus_id,
            self.corpus_digest,
            self.chunk_set_id,
            self.chunk_set_digest,
            self.chunking_configuration,
            self.generation_configuration,
            self.scorer_configuration,
            self.scorer_model,
            self.scorer_prompt,
            self.scorer_policy,
            self.scorer_stochasticity,
            self.source_commit,
            self.evaluation_commit,
        )
        if all(isinstance(value, str) and value for value in modern):
            return {
                "dataset_version": self.dataset_version,
                "dataset_digest": self.dataset_digest,
                "corpus_id": self.corpus_id,
                "corpus_digest": self.corpus_digest,
                "chunk_set_id": self.chunk_set_id,
                "chunk_set_digest": self.chunk_set_digest,
                "workspace": self.workspace or self.workspace_id,
                "chunking_configuration": self.chunking_configuration,
                "embedding_configuration": self.embedding_configuration_id,
                "generation_configuration": self.generation_configuration,
                "scorer_configuration": self.scorer_configuration,
                "scorer_model": self.scorer_model,
                "scorer_prompt": self.scorer_prompt,
                "scorer_policy": self.scorer_policy,
                "scorer_stochasticity": self.scorer_stochasticity,
                "metric_contract": METRIC_CONTRACT,
                "source_commit": self.source_commit,
                "evaluation_commit": self.evaluation_commit,
                "report_artifact_schema_version": self.report_artifact_schema_version,
                "retrieval_configuration_id": self.retrieval_configuration_id,
                "strategy": self.strategy,
                "fusion_policy_id": self.fusion_policy_id,
                "fusion_policy_version": self.fusion_policy_version,
                "lexical_policy_id": self.lexical_policy_id,
                "fts_candidate_k": self.fts_candidate_k,
            }
        provenance = {
            "dataset_manifest_identity": self.dataset_manifest_identity,
            "corpus_manifest_identity": self.corpus_manifest_identity,
            "chunk_set_provenance_id": self.chunk_set_provenance_id,
            "source_bindings": [item.as_mapping() for item in self.source_bindings],
            "workspace_id": self.workspace_id,
            "retrieval_configuration_id": self.retrieval_configuration_id,
        }
        if self.embedding_configuration_id is not None:
            provenance["embedding_configuration_id"] = self.embedding_configuration_id
        return provenance

    def source_binding(self, source_key: str) -> SourceBinding:
        matches = [item for item in self.source_bindings if item.source_key == source_key]
        if len(matches) != 1:
            raise ObservationFailure("SOURCE_BINDING_MISMATCH")
        return matches[0]


@dataclass(frozen=True, slots=True)
class SourceBinding:
    source_key: str
    production_document_version_id: str
    production_chunk_set_id: str

    @classmethod
    def from_mapping(cls, value: object) -> SourceBinding:
        fields = ("source_key", "production_document_version_id", "production_chunk_set_id")
        if not isinstance(value, dict) or any(
            not isinstance(value.get(field), str) or not value[field] for field in fields
        ):
            raise ValueError("invalid source binding")
        return cls(**{field: value[field] for field in fields})

    def as_mapping(self) -> dict[str, str]:
        return {
            "source_key": self.source_key,
            "production_document_version_id": self.production_document_version_id,
            "production_chunk_set_id": self.production_chunk_set_id,
        }


def verify_corpus_closure(
    *,
    binding: EvaluationEnvironmentBinding,
    corpus: object,
    manifest: Milestone3CorpusManifest,
) -> None:
    """Reject an evaluation environment unless its complete active corpus matches its manifest."""
    if (
        getattr(corpus, "workspace_id", None) != binding.workspace_id
        or binding.workspace_id != manifest.workspace_id
        or binding.corpus_manifest_identity != manifest.version
        or binding.chunk_set_provenance_id != manifest.chunk_set_id
    ):
        raise ObservationFailure("CORPUS_CLOSURE_MISMATCH")
    documents = getattr(corpus, "documents", None)
    if not isinstance(documents, tuple):
        raise ObservationFailure("CORPUS_CLOSURE_MISMATCH")
    expected_references: dict[str, set[str]] = {}
    for reference in manifest.chunks:
        source_key, _ = reference.rsplit("#", 1)
        expected_references.setdefault(source_key, set()).add(reference)
    source_keys = [getattr(document, "source_key", None) for document in documents]
    if (
        any(not isinstance(source_key, str) for source_key in source_keys)
        or set(source_keys) != set(expected_references)
        or len(source_keys) != len(set(source_keys))
        or {item.source_key for item in binding.source_bindings} != set(expected_references)
    ):
        raise ObservationFailure("CORPUS_CLOSURE_MISMATCH")
    for document in documents:
        source_key = document.source_key
        source_binding = binding.source_binding(source_key)
        if (
            getattr(document, "document_version_id", None)
            != source_binding.production_document_version_id
            or getattr(document, "chunk_set_id", None)
            != source_binding.production_chunk_set_id
            or set(getattr(document, "chunk_references", ())) != expected_references[source_key]
        ):
            raise ObservationFailure("CORPUS_CLOSURE_MISMATCH")


@dataclass(frozen=True, slots=True)
class VerifiedM3Environment:
    """A binding that has passed mandatory corpus-closure preflight."""

    binding: EvaluationEnvironmentBinding

    @classmethod
    def prepare(
        cls,
        *,
        binding: EvaluationEnvironmentBinding,
        corpus: object,
        manifest: Milestone3CorpusManifest,
    ) -> VerifiedM3Environment:
        verify_corpus_closure(binding=binding, corpus=corpus, manifest=manifest)
        return cls(binding)


@dataclass(frozen=True, slots=True)
class SealedM3Environment:
    """Evaluation-run ownership plus the authoritative post-acquire snapshot."""

    run_id: str
    environment: VerifiedM3Environment | None


class EvaluationEnvironmentSeal:
    """Orchestration boundary for exclusive evaluation ownership.

    Production mutation paths remain owned by their normal application seams; the injected durable
    ownership store is the selected control-plane guarantee for this isolated run.
    """

    def __init__(
        self,
        *,
        ownership_store: EvaluationOwnershipStore,
        owner_id: str | None = None,
        lease_duration: timedelta = timedelta(minutes=2),
    ) -> None:
        self._ownership_store = ownership_store
        self._owner_id = owner_id or uuid4().hex
        self._lease_duration = lease_duration
        self._capability: EvaluationOwnershipCapability | None = None
        self._sealed: SealedM3Environment | None = None
        self._last_operation_id: str | None = None
        self._state_lock = Lock()

    @property
    def last_operation_id(self) -> str | None:
        """Identifier for the most recent control-plane operation, for acceptance evidence."""
        with self._state_lock:
            return self._last_operation_id

    def acquire(
        self, *, run_id: str, operation_id: str | None = None
    ) -> EvaluationOwnershipCapability:
        operation_id = operation_id or uuid4().hex
        with self._state_lock:
            self._last_operation_id = operation_id
        try:
            capability = self._ownership_store.acquire(
                run_id=run_id,
                owner_id=self._owner_id,
                lease_duration=self._lease_duration,
                operation_id=operation_id,
            )
        except EvaluationOwnershipError as error:
            raise ObservationFailure(error.code) from error
        with self._state_lock:
            self._capability = capability
        self._sealed = SealedM3Environment(run_id, environment=None)
        return capability

    def capture_preflight(
        self,
        *,
        binding: EvaluationEnvironmentBinding,
        corpus: object,
        manifest: Milestone3CorpusManifest,
    ) -> VerifiedM3Environment:
        capability = self._require_capability()
        self._assert_current(capability)
        environment = VerifiedM3Environment.prepare(
            binding=binding, corpus=corpus, manifest=manifest
        )
        self._assert_current(capability)
        self._sealed = SealedM3Environment(capability.run_id, environment)
        return environment

    def verify_unchanged(
        self, *, corpus: object, manifest: Milestone3CorpusManifest,
        binding: EvaluationEnvironmentBinding,
    ) -> None:
        capability = self._require_capability()
        self._assert_current(capability)
        if self._sealed is None or self._sealed.environment is None:
            raise ObservationFailure("EVALUATION_SEAL_REQUIRED")
        if binding != self._sealed.environment.binding:
            raise ObservationFailure("EVALUATION_ENVIRONMENT_DRIFT")
        try:
            verify_corpus_closure(
                binding=binding, corpus=corpus, manifest=manifest
            )
        except ObservationFailure as error:
            raise ObservationFailure("EVALUATION_ENVIRONMENT_DRIFT") from error
        self._assert_current(capability)

    def release(self, *, operation_id: str | None = None) -> None:
        with self._state_lock:
            capability = self._capability
            if capability is None:
                raise ObservationFailure("EVALUATION_SEAL_REQUIRED")
            mutation_id = operation_id or uuid4().hex
            self._last_operation_id = mutation_id
            try:
                self._ownership_store.release(
                    capability, operation_id=mutation_id
                )
            except EvaluationOwnershipError as error:
                raise ObservationFailure(error.code) from error
            self._capability = None
        self._sealed = None

    def renew(self, *, operation_id: str | None = None) -> EvaluationOwnershipCapability:
        with self._state_lock:
            capability = self._capability
            if capability is None:
                raise ObservationFailure("EVALUATION_SEAL_REQUIRED")
            mutation_id = operation_id or uuid4().hex
            self._last_operation_id = mutation_id
            try:
                renewed = self._ownership_store.renew(
                    capability,
                    lease_duration=self._lease_duration,
                    operation_id=mutation_id,
                )
            except EvaluationOwnershipError as error:
                raise ObservationFailure(error.code) from error
            self._capability = renewed
            return renewed

    def start_heartbeat(
        self, *, interval: timedelta | None = None
    ) -> EvaluationLeaseHeartbeat:
        self._require_capability()
        heartbeat_interval = interval or timedelta(
            seconds=min(max(self._lease_duration.total_seconds() / 3, 0.01), 30)
        )
        heartbeat = EvaluationLeaseHeartbeat(self, heartbeat_interval)
        heartbeat.start()
        return heartbeat

    def ownership_snapshot(self) -> EvaluationOwnershipSnapshot:
        capability = self._require_capability()
        return self._ownership_store.snapshot(run_id=capability.run_id)

    def _require_capability(self) -> EvaluationOwnershipCapability:
        with self._state_lock:
            if self._capability is None:
                raise ObservationFailure("EVALUATION_SEAL_REQUIRED")
            return self._capability

    def _assert_current(self, capability: EvaluationOwnershipCapability) -> None:
        with self._state_lock:
            self._last_operation_id = uuid4().hex
        try:
            self._ownership_store.assert_current(capability)
        except EvaluationOwnershipError as error:
            raise ObservationFailure(error.code) from error


class EvaluationLeaseHeartbeat:
    """Renews one sealed-run capability until the production run tears down."""

    def __init__(self, seal: EvaluationEnvironmentSeal, interval: timedelta) -> None:
        if interval <= timedelta(0):
            raise ValueError("heartbeat interval must be positive")
        self._seal = seal
        self._interval_seconds = interval.total_seconds()
        self._stop = Event()
        self._failed = Event()
        self._thread = Thread(target=self._run, name="m3-evaluation-lease-heartbeat", daemon=True)
        self._error: ObservationFailure | None = None

    @property
    def error(self) -> ObservationFailure | None:
        return self._error

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self._interval_seconds + 1)

    def raise_if_failed(self) -> None:
        if self._error is not None:
            raise self._error

    def wait(self, seconds: float) -> None:
        """Wait briefly while making heartbeat failure observable to the caller."""
        deadline = perf_counter() + max(seconds, 0)
        while True:
            self.raise_if_failed()
            remaining = deadline - perf_counter()
            if remaining <= 0:
                return
            if self._failed.wait(min(remaining, 0.05)):
                self.raise_if_failed()
            if self._stop.is_set():
                return

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self._seal.renew()
            except ObservationFailure as error:
                self._error = error
                self._failed.set()
                return
            except Exception:
                self._error = ObservationFailure("EVALUATION_SEAL_HEARTBEAT_FAILED")
                self._failed.set()
                return


class ProductionM3Executor:
    """Observe the production Q&A response and exactly its correlated persisted trace."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        trace_reader: object,
        client: httpx.AsyncClient,
        environment: VerifiedM3Environment,
        clock: Callable[[], float] | None = None,
        clock_resolution_ms: float | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._trace_reader = trace_reader
        self._client = client
        self._binding = environment.binding
        self._clock = clock or perf_counter
        self._clock_resolution_ms = (
            get_clock_info("perf_counter").resolution * 1000
            if clock_resolution_ms is None
            else clock_resolution_ms
        )
        if not isinstance(self._clock_resolution_ms, (int, float)) or not isfinite(
            float(self._clock_resolution_ms)
        ) or self._clock_resolution_ms <= 0:
            raise ValueError("clock resolution must be a finite positive number")

    async def execute(self, case: Milestone3Case) -> M3Observation:
        started = self._clock()
        response_completed: float | None = None
        try:
            if case.workspace_id != self._binding.workspace_id:
                raise ObservationFailure("EVALUATION_WORKSPACE_BINDING_MISMATCH")
            expected_embedding_configuration_id = getattr(
                self._binding, "embedding_configuration_id", None
            )
            if (
                not isinstance(expected_embedding_configuration_id, str)
                or not expected_embedding_configuration_id
            ):
                raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID")
            response = await self._client.post(
                self._endpoint,
                headers={"X-API-Key": self._api_key},
                json={"workspace_id": case.workspace_id, "question": case.question},
            )
            response_completed = self._clock()
            response.raise_for_status()
            payload = response.json()
            trace_id = payload["trace_id"]
            public = validate_public_response(payload)
            trace = self._trace_reader.read_trace(trace_id=trace_id, workspace_id=case.workspace_id)
            if getattr(trace, "trace_id", None) != trace_id:
                raise ObservationFailure("RESPONSE_TRACE_ID_MISMATCH")
            if getattr(trace, "workspace_id", None) != case.workspace_id:
                raise ObservationFailure("TRACE_WORKSPACE_MISMATCH")
            if (
                getattr(trace, "retrieval_configuration_id", None)
                != self._binding.retrieval_configuration_id
            ):
                raise ObservationFailure("RETRIEVAL_CONFIGURATION_MISMATCH")
            if (
                getattr(trace, "embedding_configuration_id", None)
                != expected_embedding_configuration_id
            ):
                raise ObservationFailure("EMBEDDING_CONFIGURATION_MISMATCH")
            if getattr(trace, "decision", None) != public.decision:
                raise ObservationFailure("RESPONSE_TRACE_DECISION_MISMATCH")
            if getattr(trace, "refusal_reason", None) != public.refusal_reason:
                raise ObservationFailure("RESPONSE_TRACE_REFUSAL_REASON_MISMATCH")
            if getattr(trace, "answer", None) != public.answer:
                raise ObservationFailure("RESPONSE_TRACE_ANSWER_MISMATCH")
            trace_markers = getattr(trace, "parsed_markers", None)
            if not isinstance(trace_markers, (list, tuple)) or (
                tuple(trace_markers) != public.answer_marker_ids
            ):
                raise ObservationFailure("RESPONSE_TRACE_MARKERS_MISMATCH")
            candidates = project_trace_candidates(
                getattr(trace, "candidates", ()),
                binding=self._binding,
            )
            citation_ids = public.citation_evidence_ids
            _validate_public_citation_aliases(
                citation_ids=citation_ids,
                alias_mapping=getattr(trace, "alias_mapping", None),
                candidates=getattr(trace, "candidates", ()),
            )
            latency = getattr(trace, "retrieval_latency_ms", None)
            if (
                isinstance(latency, bool)
                or not isinstance(latency, (int, float))
                or not isfinite(float(latency))
                or latency < 0
            ):
                raise ObservationFailure("RETRIEVAL_LATENCY_INVALID")
            return M3Observation.success(
                case_id=case.id,
                candidates=candidates,
                retrieval_latency_ms=float(latency),
                end_to_end_latency_ms=(
                    (response_completed if response_completed is not None else self._clock())
                    - started
                )
                * 1000,
                retrieval_configuration_id=self._binding.retrieval_configuration_id,
                chunk_set_provenance_id=self._binding.chunk_set_provenance_id,
                source_bindings=self._binding.source_bindings,
                public_answer=public.answer,
                public_citations=public.citations,
                decision=public.decision,
                refusal_reason=public.refusal_reason,
                answer_marker_ids=public.answer_marker_ids,
                citation_evidence_ids=public.citation_evidence_ids,
                refusal_correctness=(
                    None
                    if case.refusal_expectation is None
                    else (
                        public.decision == "REFUSAL"
                        and public.refusal_reason == case.refusal_expectation
                    )
                ),
            )
        except ObservationFailure as error:
            return M3Observation.failure(case.id, str(error))
        except (httpx.HTTPError, KeyError, PermissionError, TypeError, ValueError, LookupError):
            return M3Observation.failure(case.id, "EVALUATION_OBSERVATION_FAILURE")


def validate_public_response(payload: object) -> PublicResponseProjection:
    """Validate the complete public ANSWER/REFUSAL contract."""
    if not isinstance(payload, dict):
        raise ObservationFailure("PUBLIC_RESPONSE_INVALID")
    decision = payload.get("decision")
    citations = payload.get("citations")
    answer = payload.get("answer")
    refusal_reason = payload.get("refusal_reason")
    trace_id = payload.get("trace_id")
    if (
        decision not in {"ANSWER", "REFUSAL"}
        or not isinstance(citations, list)
        or not isinstance(trace_id, str)
        or not trace_id
        or "answer" not in payload
    ):
        raise ObservationFailure("PUBLIC_RESPONSE_INVALID")
    if decision == "ANSWER":
        if not isinstance(answer, str) or not answer.strip() or refusal_reason is not None:
            raise ObservationFailure("PUBLIC_RESPONSE_INVALID")
        citations_projection: list[PublicCitation] = []
        for citation in citations:
            if not isinstance(citation, dict):
                raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
            evidence_id = citation.get("evidence_id")
            source_key = citation.get("source_key")
            excerpt = citation.get("excerpt")
            if not all(
                isinstance(value, str) and value.strip()
                for value in (evidence_id, source_key, excerpt)
            ):
                raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
            start_line = citation.get("start_line")
            end_line = citation.get("end_line")
            if (
                type(start_line) is not int
                or type(end_line) is not int
                or start_line < 1
                or end_line < start_line
            ):
                raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
            source_locator = f"{source_key}:{start_line}:{end_line}"
            citations_projection.append(
                PublicCitation(evidence_id, source_key, excerpt, source_locator)
            )
        evidence_ids = tuple(item.evidence_id for item in citations_projection)
        if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
            raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
        answer_markers = _parse_public_markers(answer)
        if answer_markers != evidence_ids:
            raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
        return PublicResponseProjection(
            decision="ANSWER",
            answer=answer,
            refusal_reason=None,
            citations=tuple(citations_projection),
            answer_marker_ids=answer_markers,
            citation_evidence_ids=evidence_ids,
        )
    if answer is not None or citations or refusal_reason != "INSUFFICIENT_EVIDENCE":
        raise ObservationFailure("PUBLIC_RESPONSE_INVALID")
    return PublicResponseProjection(
        decision="REFUSAL",
        answer=None,
        refusal_reason=refusal_reason,
        citations=(),
        answer_marker_ids=(),
        citation_evidence_ids=(),
    )


def _public_citations(payload: object) -> tuple[PublicCitation, ...]:
    """Backward-compatible projection for callers that need only public citations."""
    return validate_public_response(payload).citations


def _parse_public_markers(answer: str) -> tuple[str, ...]:
    markers: list[str] = []
    cursor = 0
    while True:
        start = answer.find("[[", cursor)
        if start < 0:
            break
        end = answer.find("]]", start + 2)
        if end < 0:
            raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
        marker = answer[start + 2 : end]
        if _VALID_MARKER_ID_PATTERN.fullmatch(marker) is None:
            raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
        markers.append(marker)
        cursor = end + 2
    return tuple(markers)


def semantic_citation_input(observation: M3Observation) -> dict[str, object]:
    """The only semantic-scorer input: public answer plus public citation projections."""
    if not observation.is_success or observation.public_answer is None:
        raise ObservationFailure("SEMANTIC_INPUT_UNAVAILABLE")
    return {
        "answer": observation.public_answer,
        "citations": [
            {
                "evidence_id": citation.evidence_id,
                "excerpt": citation.excerpt,
                "source_locator": citation.source_locator,
            }
            for citation in observation.public_citations
        ],
    }


def validate_public_citation_aliases(
    *,
    citation_ids: tuple[str, ...],
    alias_mapping: object,
    candidates: Iterable[object],
) -> None:
    """Check public aliases against the trace without manufacturing response citations."""
    if not citation_ids:
        return
    if not isinstance(alias_mapping, dict):
        raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
    selected_ids = {
        getattr(candidate, "chunk_id", None)
        for candidate in candidates
        if getattr(candidate, "final_decision", None) == "SELECTED"
    }
    mapped_ids = tuple(alias_mapping.get(evidence_id) for evidence_id in citation_ids)
    if (
        any(chunk_id not in selected_ids for chunk_id in mapped_ids)
        or len(mapped_ids) != len(set(mapped_ids))
    ):
        raise ObservationFailure("CITATION_STRUCTURAL_ERROR")


def _validate_public_citation_aliases(
    *,
    citation_ids: tuple[str, ...],
    alias_mapping: object,
    candidates: Iterable[object],
) -> None:
    """Backward-compatible private alias for the public evaluation seam."""
    validate_public_citation_aliases(
        citation_ids=citation_ids,
        alias_mapping=alias_mapping,
        candidates=candidates,
    )


def project_trace_candidates(
    candidates: Iterable[object], *, binding: EvaluationEnvironmentBinding
) -> tuple[CanonicalChunkReference, ...]:
    """Project an already-correlated production trace; this never retrieves candidates."""
    projected: list[CanonicalChunkReference] = []
    for candidate in candidates:
        source_key = getattr(candidate, "source_key", None)
        document_version_id = getattr(candidate, "document_version_id", None)
        chunk_set_id = getattr(candidate, "chunk_set_id", None)
        ordinal = getattr(candidate, "chunk_ordinal", None)
        if not isinstance(source_key, str) or not source_key or not isinstance(ordinal, int):
            raise ObservationFailure("CANONICAL_CHUNK_REFERENCE_INVALID")
        source_binding = binding.source_binding(source_key)
        if (
            document_version_id != source_binding.production_document_version_id
            or chunk_set_id != source_binding.production_chunk_set_id
        ):
            raise ObservationFailure("SOURCE_BINDING_MISMATCH")
        projected.append(
            CanonicalChunkReference(binding.chunk_set_provenance_id, source_key, ordinal)
        )
    if len(projected) != len(set(projected)):
        raise ObservationFailure("DUPLICATE_CANONICAL_CHUNK_REFERENCE")
    return tuple(projected)


def _gold_references(
    case: Milestone3Case, chunk_set_provenance_id: str
) -> set[CanonicalChunkReference]:
    if not case.retrieval_relevance.applicable:
        return set()
    gold: set[CanonicalChunkReference] = set()
    for reference in case.retrieval_relevance.acceptable_relevant_chunks:
        try:
            source_key, raw_ordinal = reference.rsplit("#", 1)
            ordinal = int(raw_ordinal)
        except (AttributeError, ValueError):
            raise ObservationFailure("GOLD_REFERENCE_INVALID") from None
        gold.add(CanonicalChunkReference(chunk_set_provenance_id, source_key, ordinal))
    if not gold:
        raise ObservationFailure("GOLD_REFERENCE_MISSING")
    return gold


def score_retrieval(
    cases: tuple[Milestone3Case, ...],
    observations: tuple[M3Observation, ...],
    *,
    binding: EvaluationEnvironmentBinding,
) -> dict[str, object]:
    by_case = {observation.case_id: observation for observation in observations}
    if len(by_case) != len(observations) or set(by_case) != {case.id for case in cases}:
        raise ValueError("observations must contain exactly one result for every case")
    recalls: list[Fraction] = []
    reciprocal_ranks: list[Fraction] = []
    case_results: list[dict[str, object]] = []
    for case in sorted(cases, key=lambda item: item.id):
        observation = by_case[case.id]
        if not case.retrieval_relevance.applicable:
            case_results.append(
                {
                    "id": case.id,
                    "included": False,
                    "exclusion_reason": "RETRIEVAL_RELEVANCE_NOT_APPLICABLE",
                }
            )
            continue
        if not observation.is_success:
            case_results.append(
                {
                    "id": case.id,
                    "included": False,
                    "exclusion_reason": observation.failure_code,
                }
            )
            continue
        if observation.chunk_set_provenance_id != binding.chunk_set_provenance_id:
            raise ObservationFailure("CHUNK_SET_MISMATCH")
        if observation.source_bindings != binding.source_bindings:
            raise ObservationFailure("SOURCE_BINDING_MISMATCH")
        gold = _gold_references(case, binding.chunk_set_provenance_id)
        candidates = observation.candidates
        if any(
            candidate.chunk_set_provenance_id != binding.chunk_set_provenance_id
            for candidate in candidates
        ):
            raise ObservationFailure("CHUNK_SET_MISMATCH")
        top_k = candidates[:RECALL_K]
        recall_fraction = Fraction(len(gold.intersection(top_k)), len(gold))
        first_rank = next(
            (rank for rank, candidate in enumerate(candidates, start=1) if candidate in gold),
            None,
        )
        reciprocal_rank_fraction = Fraction(0, 1) if first_rank is None else Fraction(1, first_rank)
        recalls.append(recall_fraction)
        reciprocal_ranks.append(reciprocal_rank_fraction)
        case_results.append(
            {
                "id": case.id,
                "included": True,
                "recall_at_8": float(recall_fraction),
                "reciprocal_rank": float(reciprocal_rank_fraction),
                "metric_decision_values": {
                    "recall_at_8": {
                        "numerator": recall_fraction.numerator,
                        "denominator": recall_fraction.denominator,
                    },
                    "mrr": {
                        "numerator": reciprocal_rank_fraction.numerator,
                        "denominator": reciprocal_rank_fraction.denominator,
                    },
                },
                "candidate_count": len(candidates),
            }
        )
    denominator = len(recalls)
    recall_mean = sum(recalls, Fraction(0, 1)) / denominator if denominator else None
    mrr_mean = sum(reciprocal_ranks, Fraction(0, 1)) / denominator if denominator else None
    return {
        "metric_contract": METRIC_CONTRACT,
        "recall_k": RECALL_K,
        "chunk_set_provenance_id": binding.chunk_set_provenance_id,
        "denominator": denominator,
        "recall_at_8": float(recall_mean) if recall_mean is not None else None,
        "mrr": float(mrr_mean) if mrr_mean is not None else None,
        "metric_decision_values": (
            {
                "recall_at_8": {
                    "numerator": recall_mean.numerator,
                    "denominator": recall_mean.denominator,
                },
                "mrr": {
                    "numerator": mrr_mean.numerator,
                    "denominator": mrr_mean.denominator,
                },
            }
            if recall_mean is not None and mrr_mean is not None
            else {}
        ),
        "cases": case_results,
    }


def build_report(
    cases: tuple[Milestone3Case, ...],
    observations: tuple[M3Observation, ...],
    *,
    binding: EvaluationEnvironmentBinding,
    guardrails: dict[str, bool] | None = None,
    latency_tradeoffs: dict[str, object] | None = None,
    remaining_regressions: list[object] | None = None,
) -> dict[str, object]:
    """Build the M3 report projection without defining latency aggregation semantics."""
    report: dict[str, object] = {
        "schema_version": 1,
        "provenance": {
            "metric_contract": METRIC_CONTRACT,
            **binding.provenance(),
        },
        "retrieval": score_retrieval(cases, observations, binding=binding),
        "observations": [
            _observation_projection(observation)
            for observation in sorted(observations, key=lambda item: item.case_id)
        ],
        "observation_failure_count": sum(
            not observation.is_success for observation in observations
        ),
    }
    # Keep category reconciliation beside the report rather than asking callers to recompute it
    # from display values.  The import is local to preserve the runner/comparison module seam.
    from evals.runners.milestone_3_comparison import build_category_breakdown

    report["category_breakdown"] = build_category_breakdown(cases, report)
    if guardrails is not None:
        from evals.runners.milestone_3_comparison import validate_guardrail_shape

        report["guardrails"] = validate_guardrail_shape(guardrails)
    if latency_tradeoffs is not None:
        report["latency_tradeoffs"] = dict(latency_tradeoffs)
    if remaining_regressions is not None:
        report["remaining_regressions"] = list(remaining_regressions)
    return report


def _observation_projection(observation: M3Observation) -> dict[str, object]:
    projection: dict[str, object] = {
        "case_id": observation.case_id,
        "status": "observed" if observation.is_success else "failure",
        "retrieval_latency_ms": observation.retrieval_latency_ms,
        "end_to_end_latency_ms": observation.end_to_end_latency_ms,
        "retrieval_configuration_id": observation.retrieval_configuration_id,
        "chunk_set_provenance_id": observation.chunk_set_provenance_id,
        "source_bindings": [item.as_mapping() for item in observation.source_bindings],
        "decision": observation.decision,
        "public_answer": observation.public_answer,
        "refusal_reason": observation.refusal_reason,
        "answer_marker_ids": list(observation.answer_marker_ids),
        "citation_evidence_ids": list(observation.citation_evidence_ids),
        "refusal_correctness": observation.refusal_correctness,
        "public_citations": [
            {
                "evidence_id": citation.evidence_id,
                "source_key": citation.source_key,
                "excerpt": citation.excerpt,
                "source_locator": citation.source_locator,
            }
            for citation in observation.public_citations
        ],
    }
    if observation.failure_code is not None:
        projection["failure_code"] = observation.failure_code
    elif not observation.is_success:
        projection["failure_code"] = "PUBLIC_RESPONSE_INVALID"
    return projection
