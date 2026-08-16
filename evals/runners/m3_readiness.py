"""One canonical, production-seam readiness path for M3 acceptance."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
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
    ObservationFailure,
    SourceBinding,
    validate_public_citation_aliases,
    validate_public_response,
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
    candidate_decisions: tuple[dict[str, object], ...]
    branch_observations: tuple[dict[str, object], ...]
    decision: str
    answer: str | None
    refusal_reason: str | None
    parsed_markers: tuple[str, ...]


@dataclass(slots=True)
class ReadinessFailure(RuntimeError):
    phase: str
    reason: str

    def __str__(self) -> str:
        return f"readiness phase {self.phase} failed: {self.reason}"


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
    embedding_configuration_ids = {
        item
        for item in (
            getattr(document, "embedding_configuration_id", None)
            for document in documents
        )
        if isinstance(item, str) and item
    }
    if len(embedding_configuration_ids) > 1:
        raise ObservationFailure("CORPUS_CLOSURE_MISMATCH")
    embedding_configuration_id = (
        next(iter(embedding_configuration_ids))
        if embedding_configuration_ids
        else base.embedding_configuration_id
    )
    return EvaluationEnvironmentBinding(
        dataset_manifest_identity=base.dataset_manifest_identity,
        corpus_manifest_identity=manifest.version,
        chunk_set_provenance_id=manifest.chunk_set_id,
        workspace_id=base.workspace_id,
        retrieval_configuration_id=base.retrieval_configuration_id,
        embedding_configuration_id=embedding_configuration_id,
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
    post_question: Callable[..., httpx.Response] = httpx.post,
) -> ReadinessEvidence:
    phases: list[str] = ["dependency_startup"]
    result: BootstrapResult | None = None
    try:
        phases.append("bootstrap_closure_binding_snapshot")
        result = bootstrap.prepare(binding=binding, manifest=manifest, run_id="readiness")
        inject_evaluation_runtime(result.credential, result.endpoint)
        phases.append("production_api_startup")
        launcher.start(
            startup_auth_config=result.credential.startup_config(), endpoint=result.endpoint
        )
        health_endpoint = result.endpoint.rsplit("/v1/questions", 1)[0] + "/health"
        for _ in range(30):
            try:
                if httpx.get(health_endpoint, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise ReadinessFailure("production_api_startup", "health endpoint did not become ready")
        phases.append("authenticated_question")
        request_started = perf_counter()
        response = post_question(
            result.endpoint,
            headers={"X-API-Key": result.credential.raw_key},
            json={"workspace_id": case.workspace_id, "question": case.question},
            timeout=30,
        )
        response.raise_for_status()
        end_to_end_latency_ms = (perf_counter() - request_started) * 1000
        payload = response.json()
        trace_id = payload.get("trace_id")
        response_workspace_id = payload.get("workspace_id")
        if (
            not isinstance(trace_id, str)
            or not isinstance(response_workspace_id, str)
            or response_workspace_id != case.workspace_id
        ):
            raise ReadinessFailure("authenticated_question", "response correlation invalid")
        try:
            public = validate_public_response(payload)
        except ObservationFailure as error:
            raise ReadinessFailure("trace_provenance_verification", str(error)) from error
        if public.decision != case.expected_behavior:
            raise ReadinessFailure("trace_provenance_verification", "response behavior mismatch")
        phases.append("trace_provenance_verification")
        trace = trace_reader.read_trace(trace_id=trace_id, workspace_id=case.workspace_id)
        if getattr(trace, "trace_id", None) != trace_id:
            raise ReadinessFailure("trace_provenance_verification", "trace identity mismatch")
        if getattr(trace, "workspace_id", None) != case.workspace_id:
            raise ReadinessFailure("trace_provenance_verification", "trace workspace mismatch")
        if (
            getattr(trace, "retrieval_configuration_id", None)
            != result.binding.retrieval_configuration_id
        ):
            raise ReadinessFailure(
                "trace_provenance_verification", "retrieval configuration mismatch"
            )
        if getattr(trace, "embedding_configuration_id", None) != (
            result.binding.embedding_configuration_id
        ):
            raise ReadinessFailure(
                "trace_provenance_verification", "embedding configuration mismatch"
            )
        if (
            getattr(trace, "decision", None) != public.decision
            or getattr(trace, "answer", None) != public.answer
            or getattr(trace, "refusal_reason", None) != public.refusal_reason
            or tuple(getattr(trace, "parsed_markers", ())) != public.answer_marker_ids
        ):
            raise ReadinessFailure("trace_provenance_verification", "response trace mismatch")
        for candidate in getattr(trace, "candidates", ()):
            source = result.binding.source_binding(candidate.source_key)
            if (candidate.document_version_id, candidate.chunk_set_id) != (
                source.production_document_version_id, source.production_chunk_set_id
            ):
                raise ReadinessFailure(
                    "trace_provenance_verification", "candidate binding mismatch"
                )
        try:
            validate_public_citation_aliases(
                citation_ids=public.citation_evidence_ids,
                alias_mapping=getattr(trace, "alias_mapping", None),
                candidates=getattr(trace, "candidates", ()),
            )
        except ObservationFailure as error:
            raise ReadinessFailure("trace_provenance_verification", str(error)) from error
        retrieval_latency_ms = getattr(trace, "retrieval_latency_ms", None)
        if (
            isinstance(retrieval_latency_ms, bool)
            or not isinstance(retrieval_latency_ms, (int, float))
            or not isfinite(float(retrieval_latency_ms))
            or retrieval_latency_ms < 0
        ):
            raise ReadinessFailure("trace_provenance_verification", "retrieval latency invalid")
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
        corpus = bootstrap._corpus_reader.read_active_corpus(
            workspace_id=result.binding.workspace_id
        )
        seal.verify_unchanged(binding=result.binding, corpus=corpus, manifest=manifest)
        return ReadinessEvidence(
            tuple(phases), result.binding.workspace_id, trace_id,
            len(trace.candidates), trace.retrieval_configuration_id,
            len(result.binding.source_bindings),
            float(retrieval_latency_ms), end_to_end_latency_ms,
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
            tuple(dict(item) for item in getattr(trace, "candidate_decisions", ())),
            tuple(dict(item) for item in getattr(trace, "branch_observations", ())),
            str(getattr(trace, "decision", "")),
            getattr(trace, "answer", None),
            getattr(trace, "refusal_reason", None),
            tuple(str(item) for item in getattr(trace, "parsed_markers", ())),
        )
    except ReadinessFailure:
        raise
    except Exception as error:
        phase = phases[-1] if phases else "dependency_startup"
        raise ReadinessFailure(phase, type(error).__name__) from error
    finally:
        stop = getattr(launcher, "stop", None)
        if stop is not None:
            stop()
        if result is not None:
            seal.release()
        teardown_evaluation_runtime()
