"""One canonical, production-seam readiness path for M3 acceptance."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue
from threading import Thread
from time import perf_counter
from typing import Protocol

import httpx
from evals.datasets.milestone_3 import Milestone3Case, Milestone3CorpusManifest
from evals.runners.m3_bootstrap import (
    BootstrapResult,
    EvaluationEnvironmentBootstrap,
    ProductionRuntimeLauncher,
    inject_evaluation_runtime,
    teardown_evaluation_runtime,
)
from evals.runners.milestone_3 import (
    EvaluationEnvironmentBinding,
    EvaluationEnvironmentSeal,
    EvaluationLeaseHeartbeat,
    ObservationFailure,
    SourceBinding,
)


class TraceReader(Protocol):
    def read_trace(self, *, trace_id: str, workspace_id: str) -> object: ...


@dataclass(frozen=True, slots=True)
class ReadinessEvidence:
    phases: tuple[str, ...]
    workspace_id: str
    trace_id: str
    candidate_count: int
    retrieval_configuration_id: str
    source_bindings_verified: int
    retrieval_latency_ms: float
    end_to_end_latency_ms: float
    candidate_triples: tuple[tuple[str, str, str], ...]
    citation_matrix: tuple[tuple[str, str, bool], ...]
    semantic_input: dict[str, object]
    retrieval_provenance: dict[str, object]
    active_corpus: tuple[dict[str, object], ...]


@dataclass(slots=True)
class ReadinessFailure(RuntimeError):
    phase: str
    reason: str

    def __str__(self) -> str:
        return f"readiness phase {self.phase} failed: {self.reason}"


def _run_with_lease[ReadinessResult](
    operation: Callable[[], ReadinessResult], heartbeat: EvaluationLeaseHeartbeat
) -> ReadinessResult:
    """Run one potentially blocking readiness operation while supervising lease loss."""
    heartbeat.raise_if_failed()
    result: Queue[tuple[ReadinessResult | None, BaseException | None]] = Queue(maxsize=1)

    def invoke() -> None:
        try:
            result.put((operation(), None))
        except BaseException as error:
            result.put((None, error))

    worker = Thread(target=invoke, name="m3-readiness-operation", daemon=True)
    worker.start()
    while worker.is_alive():
        heartbeat.raise_if_failed()
        worker.join(timeout=0.05)
    heartbeat.raise_if_failed()
    value, error = result.get()
    if error is not None:
        raise error
    return value  # type: ignore[return-value]


def binding_from_corpus(
    *, base: EvaluationEnvironmentBinding, corpus: object, manifest: Milestone3CorpusManifest
) -> EvaluationEnvironmentBinding:
    documents = getattr(corpus, "documents", ())
    expected = {item.rsplit("#", 1)[0] for item in manifest.chunks}
    if {getattr(item, "source_key", None) for item in documents} != expected:
        raise ObservationFailure("CORPUS_CLOSURE_MISMATCH")
    bindings = tuple(
        SourceBinding(
            source_key=item.source_key,
            production_document_version_id=item.document_version_id,
            production_chunk_set_id=item.chunk_set_id,
        )
        for item in sorted(documents, key=lambda value: value.source_key)
    )
    return EvaluationEnvironmentBinding(
        dataset_manifest_identity=base.dataset_manifest_identity,
        corpus_manifest_identity=manifest.version,
        chunk_set_provenance_id=manifest.chunk_set_id,
        workspace_id=base.workspace_id,
        retrieval_configuration_id=base.retrieval_configuration_id,
        source_bindings=bindings,
    )


def run_readiness(
    *,
    bootstrap: EvaluationEnvironmentBootstrap,
    binding: EvaluationEnvironmentBinding,
    manifest: Milestone3CorpusManifest,
    case: Milestone3Case,
    trace_reader: TraceReader,
    seal: EvaluationEnvironmentSeal,
    launcher: ProductionRuntimeLauncher,
) -> ReadinessEvidence:
    phases: list[str] = ["dependency_startup"]
    result: BootstrapResult | None = None
    heartbeat = None
    try:
        phases.append("bootstrap_closure_binding_snapshot")
        result = bootstrap.prepare(binding=binding, manifest=manifest, run_id="readiness")
        heartbeat = seal.start_heartbeat()
        heartbeat.raise_if_failed()
        inject_evaluation_runtime(result.credential, result.endpoint)
        phases.append("production_api_startup")
        launcher.start(
            startup_auth_config=result.credential.startup_config(), endpoint=result.endpoint
        )
        heartbeat.raise_if_failed()
        health_endpoint = result.endpoint.rsplit("/v1/questions", 1)[0] + "/health"
        for _ in range(30):
            try:
                if _run_with_lease(
                    lambda: httpx.get(health_endpoint, timeout=1), heartbeat
                ).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            heartbeat.wait(0.5)
        else:
            raise ReadinessFailure("production_api_startup", "health endpoint did not become ready")
        phases.append("authenticated_question")
        request_started = perf_counter()
        response = _run_with_lease(
            lambda: httpx.post(
                result.endpoint,
                headers={"X-API-Key": result.credential.raw_key},
                json={"workspace_id": case.workspace_id, "question": case.question},
                timeout=30,
            ),
            heartbeat,
        )
        heartbeat.raise_if_failed()
        response.raise_for_status()
        end_to_end_latency_ms = (perf_counter() - request_started) * 1000
        payload = response.json()
        trace_id = payload.get("trace_id")
        if not isinstance(trace_id, str) or payload.get(
            "workspace_id", case.workspace_id
        ) != case.workspace_id:
            raise ReadinessFailure("authenticated_question", "response correlation invalid")
        phases.append("trace_provenance_verification")
        trace = _run_with_lease(
            lambda: trace_reader.read_trace(trace_id=trace_id, workspace_id=case.workspace_id),
            heartbeat,
        )
        heartbeat.raise_if_failed()
        if getattr(trace, "trace_id", None) != trace_id:
            raise ReadinessFailure("trace_provenance_verification", "trace identity mismatch")
        if (
            getattr(trace, "retrieval_configuration_id", None)
            != result.binding.retrieval_configuration_id
        ):
            raise ReadinessFailure(
                "trace_provenance_verification", "retrieval configuration mismatch"
            )
        for candidate in getattr(trace, "candidates", ()):
            source = result.binding.source_binding(candidate.source_key)
            if (candidate.document_version_id, candidate.chunk_set_id) != (
                source.production_document_version_id, source.production_chunk_set_id
            ):
                raise ReadinessFailure(
                    "trace_provenance_verification", "candidate binding mismatch"
                )
        citations = payload.get("citations", [])
        citation_matrix = tuple(
            (
                str(item.get("evidence_id")),
                str(getattr(trace, "alias_mapping", {}).get(item.get("evidence_id"))),
                getattr(trace, "alias_mapping", {}).get(item.get("evidence_id"))
                in {candidate.chunk_id for candidate in getattr(trace, "candidates", ())},
            )
            for item in citations
            if isinstance(item, dict)
        )
        phases.append("post_run_closure_verification")
        corpus = _run_with_lease(
            lambda: bootstrap._corpus_reader.read_active_corpus(
                workspace_id=result.binding.workspace_id
            ),
            heartbeat,
        )
        heartbeat.raise_if_failed()
        seal.verify_unchanged(binding=result.binding, corpus=corpus, manifest=manifest)
        if heartbeat is not None:
            heartbeat.stop()
            heartbeat.raise_if_failed()
        return ReadinessEvidence(
            tuple(phases), result.binding.workspace_id, trace_id,
            len(trace.candidates), trace.retrieval_configuration_id,
            len(result.binding.source_bindings),
            float(trace.retrieval_latency_ms), end_to_end_latency_ms,
            tuple((candidate.source_key, candidate.document_version_id, candidate.chunk_set_id)
                  for candidate in trace.candidates),
            citation_matrix,
            {"public_answer": payload.get("answer"), "public_citations": citations},
            dict(getattr(trace, "provider_metadata", {})),
            tuple({
                "source_key": item.source_key,
                "document_version_id": item.document_version_id,
                "chunk_set_id": item.chunk_set_id,
                "chunk_count": len(item.chunk_references),
                "embedding_configuration_id": item.embedding_configuration_id,
            } for item in corpus.documents),
        )
    except ReadinessFailure:
        raise
    except Exception as error:
        phase = phases[-1] if phases else "dependency_startup"
        raise ReadinessFailure(phase, type(error).__name__) from error
    finally:
        if heartbeat is not None:
            heartbeat.stop()
        stop = getattr(launcher, "stop", None)
        if stop is not None:
            stop()
        if result is not None:
            primary_error = sys.exc_info()[1]
            try:
                seal.release()
            except ObservationFailure as cleanup_error:
                if primary_error is None:
                    raise
                primary_error.add_note(f"seal teardown failed: {cleanup_error}")
        teardown_evaluation_runtime()
