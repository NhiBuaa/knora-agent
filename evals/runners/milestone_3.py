"""Production-observation contracts and metrics for Milestone 3 evaluation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from threading import Event, Lock, Thread
from time import perf_counter
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
    ) -> M3Observation:
        if retrieval_latency_ms < 0 or end_to_end_latency_ms < 0:
            raise ValueError("latency must be non-negative")
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
        )

    @classmethod
    def failure(cls, case_id: str, code: str) -> M3Observation:
        return cls(case_id=case_id, failure_code=code)

    @property
    def is_success(self) -> bool:
        return self.failure_code is None


@dataclass(frozen=True, slots=True)
class EvaluationEnvironmentBinding:
    """Immutable verified manifest-to-production environment association."""

    dataset_manifest_identity: str
    corpus_manifest_identity: str
    chunk_set_provenance_id: str
    workspace_id: str
    retrieval_configuration_id: str
    source_bindings: tuple[SourceBinding, ...] = ()
    schema_version: int = 3

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
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 3
            or any(not isinstance(value.get(field), str) or not value[field] for field in fields)
            or not isinstance(raw_bindings, list)
        ):
            raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID")
        try:
            bindings = tuple(SourceBinding.from_mapping(item) for item in raw_bindings)
        except (TypeError, ValueError) as error:
            raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID") from error
        if not bindings or len({item.source_key for item in bindings}) != len(bindings):
            raise ObservationFailure("EVALUATION_ENVIRONMENT_BINDING_INVALID")
        return cls(**{field: value[field] for field in fields}, source_bindings=bindings)

    def provenance(self) -> dict[str, object]:
        return {
            "dataset_manifest_identity": self.dataset_manifest_identity,
            "corpus_manifest_identity": self.corpus_manifest_identity,
            "chunk_set_provenance_id": self.chunk_set_provenance_id,
            "source_bindings": [item.as_mapping() for item in self.source_bindings],
            "workspace_id": self.workspace_id,
            "retrieval_configuration_id": self.retrieval_configuration_id,
        }

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

    def acquire(self, *, run_id: str) -> EvaluationOwnershipCapability:
        operation_id = uuid4().hex
        with self._state_lock:
            self._last_operation_id = operation_id
        try:
            capability = self._ownership_store.acquire(
                run_id=run_id,
                owner_id=self._owner_id,
                lease_duration=self._lease_duration,
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

    def release(self) -> None:
        with self._state_lock:
            capability = self._capability
            if capability is None:
                raise ObservationFailure("EVALUATION_SEAL_REQUIRED")
            self._last_operation_id = uuid4().hex
            try:
                self._ownership_store.release(capability)
            except EvaluationOwnershipError as error:
                raise ObservationFailure(error.code) from error
            self._capability = None
        self._sealed = None

    def renew(self) -> EvaluationOwnershipCapability:
        with self._state_lock:
            capability = self._capability
            if capability is None:
                raise ObservationFailure("EVALUATION_SEAL_REQUIRED")
            self._last_operation_id = uuid4().hex
            try:
                renewed = self._ownership_store.renew(
                    capability, lease_duration=self._lease_duration
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

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self._seal.renew()
            except ObservationFailure as error:
                self._error = error
                return
            except Exception:
                self._error = ObservationFailure("EVALUATION_SEAL_HEARTBEAT_FAILED")
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
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._trace_reader = trace_reader
        self._client = client
        self._binding = environment.binding

    async def execute(self, case: Milestone3Case) -> M3Observation:
        started = perf_counter()
        try:
            if case.workspace_id != self._binding.workspace_id:
                raise ObservationFailure("EVALUATION_WORKSPACE_BINDING_MISMATCH")
            response = await self._client.post(
                self._endpoint,
                headers={"X-API-Key": self._api_key},
                json={"workspace_id": case.workspace_id, "question": case.question},
            )
            response.raise_for_status()
            payload = response.json()
            trace_id = payload["trace_id"]
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
            candidates = project_trace_candidates(
                getattr(trace, "candidates", ()),
                binding=self._binding,
            )
            public_citations = _public_citations(payload)
            citation_ids = tuple(citation.evidence_id for citation in public_citations)
            _validate_public_citation_aliases(
                citation_ids=citation_ids,
                alias_mapping=getattr(trace, "alias_mapping", None),
                candidates=getattr(trace, "candidates", ()),
            )
            latency = getattr(trace, "retrieval_latency_ms", None)
            if isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0:
                raise ObservationFailure("RETRIEVAL_LATENCY_INVALID")
            return M3Observation.success(
                case_id=case.id,
                candidates=candidates,
                retrieval_latency_ms=float(latency),
                end_to_end_latency_ms=(perf_counter() - started) * 1000,
                retrieval_configuration_id=self._binding.retrieval_configuration_id,
                chunk_set_provenance_id=self._binding.chunk_set_provenance_id,
                source_bindings=self._binding.source_bindings,
                public_answer=payload["answer"],
                public_citations=public_citations,
            )
        except ObservationFailure as error:
            return M3Observation.failure(case.id, str(error))
        except (httpx.HTTPError, KeyError, TypeError, ValueError, LookupError):
            return M3Observation.failure(case.id, "EVALUATION_OBSERVATION_FAILURE")


def _public_citations(payload: object) -> tuple[PublicCitation, ...]:
    """Validate public citation structure without filling it from trace data."""
    if not isinstance(payload, dict):
        raise ObservationFailure("PUBLIC_RESPONSE_INVALID")
    decision = payload.get("decision")
    citations = payload.get("citations")
    answer = payload.get("answer")
    if decision not in {"ANSWER", "REFUSAL"} or not isinstance(citations, list):
        raise ObservationFailure("PUBLIC_RESPONSE_INVALID")
    if decision == "ANSWER":
        citations_projection: list[PublicCitation] = []
        for citation in citations:
            if not isinstance(citation, dict):
                raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
            evidence_id = citation.get("evidence_id")
            source_key = citation.get("source_key")
            excerpt = citation.get("excerpt")
            if not all(
                isinstance(value, str) and value for value in (evidence_id, source_key, excerpt)
            ):
                raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
            source_locator = f"{source_key}:{citation.get('start_line')}:{citation.get('end_line')}"
            citations_projection.append(
                PublicCitation(evidence_id, source_key, excerpt, source_locator)
            )
        evidence_ids = tuple(item.evidence_id for item in citations_projection)
        if (
            not isinstance(answer, str)
            or not evidence_ids
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
        if tuple(MARKER_PATTERN.findall(answer)) != evidence_ids:
            raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
        return tuple(citations_projection)
    elif citations:
        raise ObservationFailure("CITATION_STRUCTURAL_ERROR")
    return ()


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


def _validate_public_citation_aliases(
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
    candidate_ids = {getattr(candidate, "chunk_id", None) for candidate in candidates}
    if any(alias_mapping.get(evidence_id) not in candidate_ids for evidence_id in citation_ids):
        raise ObservationFailure("CITATION_STRUCTURAL_ERROR")


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
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
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
        recall = len(gold.intersection(top_k)) / len(gold)
        first_rank = next(
            (rank for rank, candidate in enumerate(candidates, start=1) if candidate in gold),
            None,
        )
        rr = 0.0 if first_rank is None else 1.0 / first_rank
        recalls.append(recall)
        reciprocal_ranks.append(rr)
        case_results.append(
            {
                "id": case.id,
                "included": True,
                "recall_at_8": recall,
                "reciprocal_rank": rr,
                "candidate_count": len(candidates),
            }
        )
    denominator = len(recalls)
    return {
        "metric_contract": METRIC_CONTRACT,
        "recall_k": RECALL_K,
        "chunk_set_provenance_id": binding.chunk_set_provenance_id,
        "denominator": denominator,
        "recall_at_8": sum(recalls) / denominator if denominator else None,
        "mrr": sum(reciprocal_ranks) / denominator if denominator else None,
        "cases": case_results,
    }


def build_report(
    cases: tuple[Milestone3Case, ...],
    observations: tuple[M3Observation, ...],
    *,
    binding: EvaluationEnvironmentBinding,
) -> dict[str, object]:
    """Build the M3 report projection without defining latency aggregation semantics."""
    return {
        "schema_version": 1,
        "provenance": {
            "metric_contract": METRIC_CONTRACT,
            "recall_k": RECALL_K,
            **binding.provenance(),
        },
        "retrieval": score_retrieval(cases, observations, binding=binding),
        "observations": [
            _observation_projection(observation)
            for observation in sorted(observations, key=lambda item: item.case_id)
        ],
    }


def _observation_projection(observation: M3Observation) -> dict[str, object]:
    projection: dict[str, object] = {
        "case_id": observation.case_id,
        "status": "observed" if observation.is_success else "failure",
        "retrieval_latency_ms": observation.retrieval_latency_ms,
        "end_to_end_latency_ms": observation.end_to_end_latency_ms,
        "retrieval_configuration_id": observation.retrieval_configuration_id,
        "chunk_set_provenance_id": observation.chunk_set_provenance_id,
        "source_bindings": [item.as_mapping() for item in observation.source_bindings],
    }
    if observation.failure_code is not None:
        projection["failure_code"] = observation.failure_code
    return projection
