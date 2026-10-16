"""Reviewed PDF binding snapshots, kept outside immutable gold and legacy runners."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from math import isfinite
from time import perf_counter
from typing import Literal

import httpx
from evals.runners.milestone_3 import (
    ObservationFailure,
    project_generation_evidence,
    validate_public_citations_against_trace,
    validate_public_response,
)

from knora.evaluation.contracts import Case, DatasetSelection, FrozenDataset, digest_json


@dataclass(frozen=True)
class PdfRuntimeProfile:
    profile_id: str
    kind: Literal["offline", "live"]
    # Preparation must read the owned runtime corpus afresh; snapshots are never browser supplied.
    prepare: Callable[[FrozenDataset], dict]
    execute: Callable[[Case, dict], Awaitable[dict]]


def reviewed_pdf_preparation(
    *, binding: dict, corpus_reader: object
) -> Callable[[FrozenDataset], dict]:
    """Return a preparation callback that rechecks a reviewed dense corpus snapshot."""
    snapshot = deepcopy(binding)

    def prepare(frozen: FrozenDataset) -> dict:
        validate_pdf_binding(frozen, snapshot)
        corpus = corpus_reader.read_active_corpus(workspace_id=frozen.reference.workspace_id)
        if getattr(corpus, "workspace_id", None) != frozen.reference.workspace_id:
            raise ValueError("PDF runtime corpus workspace mismatch")
        documents = tuple(getattr(corpus, "documents", ()))
        expected = {
            source.document_version_id: source
            for source in frozen.gold.sources
            if snapshot["sources"][source.document_version_id]["status"] == "READY"
        }
        actual: dict[str, object] = {}
        # Q&A searches the workspace corpus; source-key prefixes do not scope retrieval.
        for document in documents:
            version_id = getattr(document, "document_version_id", None)
            if not isinstance(version_id, str) or version_id in actual:
                raise ValueError("PDF runtime corpus population mismatch")
            actual[version_id] = document
        if set(actual) != set(expected):
            raise ValueError("PDF runtime corpus population mismatch")
        seen_chunks: set[str] = set()
        for version_id, source in expected.items():
            document = actual[version_id]
            source_binding = snapshot["sources"][version_id]
            chunk_ids = tuple(getattr(document, "chunk_ids", ()))
            if (
                getattr(document, "raw_sha256", None) != source.raw_sha256
                or getattr(document, "chunk_set_id", None) != source_binding["chunk_set_id"]
                or getattr(document, "embedding_set_id", None) != source_binding["embedding_set_id"]
                or getattr(document, "embedding_configuration_id", None)
                != snapshot["embedding_configuration_id"]
                or chunk_ids != tuple(source_binding["chunk_ids"])
                or len(chunk_ids) != len(set(chunk_ids))
                or seen_chunks.intersection(chunk_ids)
            ):
                raise ValueError("PDF runtime corpus identity mismatch")
            seen_chunks.update(chunk_ids)
        return deepcopy(snapshot)

    return prepare


def validate_pdf_binding(frozen: FrozenDataset, binding: dict) -> None:
    """Verify the reviewed snapshot and mapping, not an approval for provider calls."""
    fields = {
        "schema_version",
        "binding_id",
        "reference",
        "retrieval_configuration_id",
        "embedding_configuration_id",
        "generation_configuration_id",
        "candidate_budget",
        "generation",
        "sources",
        "anchors",
        "approval",
    }
    if not isinstance(binding, dict) or set(binding) != fields:
        raise ValueError("Invalid PDF binding fields")
    if binding["schema_version"] != 1 or binding["reference"] != asdict(frozen.reference):
        raise ValueError("PDF binding reference mismatch")
    for name in (
        "binding_id",
        "retrieval_configuration_id",
        "embedding_configuration_id",
        "generation_configuration_id",
    ):
        if not isinstance(binding[name], str) or not binding[name].strip():
            raise ValueError("PDF binding configuration missing")
    if type(binding["candidate_budget"]) is not int or binding["candidate_budget"] < 1:
        raise ValueError("Invalid candidate budget")
    generation = binding["generation"]
    if (
        not isinstance(generation, dict)
        or set(generation) != {"provider", "model", "prompt_version"}
        or any(not isinstance(value, str) or not value.strip() for value in generation.values())
    ):
        raise ValueError("Generation provenance missing")
    approval = binding["approval"]
    if not isinstance(approval, dict) or set(approval) != {
        "owner_issuer",
        "owner_subject",
        "binding_digest",
    }:
        raise ValueError("Binding review required")
    if any(not isinstance(approval[key], str) or not approval[key].strip() for key in approval):
        raise ValueError("Binding review identity missing")
    if approval["binding_digest"] != digest_json(
        {key: value for key, value in binding.items() if key != "approval"}
    ):
        raise ValueError("Binding review digest mismatch")
    sources = binding["sources"]
    if not isinstance(sources, dict) or set(sources) != {
        source.document_version_id for source in frozen.gold.sources
    }:
        raise ValueError("PDF corpus closure mismatch")
    all_chunks: set[str] = set()
    for source in frozen.gold.sources:
        value = sources[source.document_version_id]
        if not isinstance(value, dict) or set(value) != {
            "raw_sha256",
            "status",
            "chunk_set_id",
            "embedding_set_id",
            "chunk_ids",
        }:
            raise ValueError("Invalid PDF source binding")
        chunks = value["chunk_ids"]
        if (
            value["raw_sha256"] != source.raw_sha256
            or value["status"] not in {"READY", "FAILED", "MISSING"}
            or not isinstance(chunks, list)
            or any(not isinstance(c, str) or not c.strip() for c in chunks)
            or len(chunks) != len(set(chunks))
            or all_chunks.intersection(chunks)
        ):
            raise ValueError("Invalid PDF source provenance")
        if value["status"] == "READY":
            if not chunks or any(
                not isinstance(value[k], str) or not value[k].strip()
                for k in ("chunk_set_id", "embedding_set_id")
            ):
                raise ValueError("Ready PDF source needs runtime provenance")
        elif chunks or value["chunk_set_id"] is not None or value["embedding_set_id"] is not None:
            raise ValueError("Unavailable PDF source cannot bind chunks")
        all_chunks.update(chunks)
    anchors = {
        digest_json(asdict(anchor)): anchor
        for case in frozen.gold.cases
        for group in case.evidence_groups
        for anchor in group.alternatives
    }
    if not isinstance(binding["anchors"], dict) or set(binding["anchors"]) != set(anchors):
        raise ValueError("PDF anchor population mismatch")
    for key, anchor in anchors.items():
        value = binding["anchors"][key]
        if not isinstance(value, dict) or set(value) != {"status", "chunk_ids"}:
            raise ValueError("Invalid PDF anchor binding")
        chunks = value["chunk_ids"]
        if (
            value["status"] not in {"READY", "MISSING", "AMBIGUOUS"}
            or not isinstance(chunks, list)
            or any(not isinstance(c, str) or not c.strip() for c in chunks)
            or len(chunks) != len(set(chunks))
            or not set(chunks).issubset(sources[anchor.document_version_id]["chunk_ids"])
            or (value["status"] == "READY" and not chunks)
        ):
            raise ValueError("PDF anchor points outside reviewed source")


def pdf_case_readiness(
    frozen: FrozenDataset, selection: DatasetSelection, binding: dict
) -> list[dict]:
    by_id = {case.case_id: case for case in frozen.gold.cases}
    result = []
    for case_id in selection.selected_case_ids:
        case = by_id[case_id]
        versions = (
            {
                anchor.document_version_id
                for group in case.evidence_groups
                for anchor in group.alternatives
            }
            if case.expected == "ANSWER"
            else set(case.no_answer_scope.checked_document_version_ids)
        )
        reasons = [
            "SOURCE_" + binding["sources"][version]["status"] + ":" + version
            for version in sorted(versions)
            if binding["sources"][version]["status"] != "READY"
        ]
        if case.context_dependencies:
            reasons.append("CONTEXT_EXECUTION_UNSUPPORTED")
        warnings = sorted(
            {
                "ANCHOR_BINDING_" + binding["anchors"][digest_json(asdict(anchor))]["status"]
                for group in case.evidence_groups
                for anchor in group.alternatives
                if binding["anchors"][digest_json(asdict(anchor))]["status"] != "READY"
            }
        )
        result.append(
            {
                "case_id": case_id,
                "status": "BLOCKED" if reasons else "READY",
                "reasons": reasons,
                "warnings": warnings,
            }
        )
    return result


def pdf_http_profile(
    *,
    profile_id: str,
    kind: Literal["offline", "live"],
    endpoint: str,
    api_key: str,
    trace_reader: object,
    client: httpx.AsyncClient,
    prepare: Callable[[FrozenDataset], dict],
) -> PdfRuntimeProfile:
    """Use Knora's Q&A HTTP surface and existing public/trace validators, without re-answering."""

    async def execute(case: Case, binding: dict) -> dict:
        started = perf_counter()
        # A transport exception may follow a consumed call; propagate it without retrying.
        response = await client.post(
            endpoint,
            headers={"X-API-Key": api_key},
            json={"workspace_id": binding["reference"]["workspace_id"], "question": case.question},
        )
        response_completed = perf_counter()
        trace_id = None
        try:
            response.raise_for_status()
            payload = response.json()
            trace_id = payload.get("trace_id") if isinstance(payload, dict) else None
            public = validate_public_response(payload)
            workspace_id = binding["reference"]["workspace_id"]
            trace = trace_reader.read_trace(trace_id=trace_id, workspace_id=workspace_id)
            for name, expected in {
                "trace_id": trace_id,
                "workspace_id": workspace_id,
                "retrieval_configuration_id": binding["retrieval_configuration_id"],
                "embedding_configuration_id": binding["embedding_configuration_id"],
                "decision": public.decision,
                "answer": public.answer,
                "refusal_reason": public.refusal_reason,
            }.items():
                if getattr(trace, name, None) != expected:
                    raise ObservationFailure("PDF_TRACE_" + name.upper() + "_MISMATCH")
            if tuple(trace.parsed_markers) != public.answer_marker_ids:
                raise ObservationFailure("RESPONSE_TRACE_MARKERS_MISMATCH")
            sources = binding["sources"]
            ready = [value for value in sources.values() if value["status"] == "READY"]
            if set(trace.embedding_set_ids) != {
                value["embedding_set_id"] for value in ready
            } or set(trace.chunk_set_ids) != {value["chunk_set_id"] for value in ready}:
                raise ObservationFailure("PDF_TRACE_CORPUS_MISMATCH")
            metadata = trace.provider_metadata
            generation = metadata.get("generation")
            if (public.decision == "ANSWER" or generation is not None) and (
                not isinstance(generation, dict)
                or any(generation.get(key) != value for key, value in binding["generation"].items())
            ):
                raise ObservationFailure("PDF_TRACE_GENERATION_MISMATCH")
            candidates = trace.candidates
            ids = [candidate.chunk_id for candidate in candidates]
            if len(ids) != len(set(ids)) or len(ids) > binding["candidate_budget"]:
                raise ObservationFailure("PDF_TRACE_CANDIDATE_POPULATION_INVALID")
            for rank, candidate in enumerate(candidates, 1):
                source = sources.get(candidate.document_version_id)
                if (
                    source is None
                    or candidate.workspace_id != workspace_id
                    or source["status"] != "READY"
                    or candidate.chunk_set_id != source["chunk_set_id"]
                    or candidate.chunk_id not in source["chunk_ids"]
                    or candidate.final_rank != rank
                ):
                    raise ObservationFailure("PDF_TRACE_CANDIDATE_PROVENANCE_MISMATCH")
            validate_public_citations_against_trace(
                citations=public.citations, alias_mapping=trace.alias_mapping, candidates=candidates
            )
            evidence = project_generation_evidence(trace)
            if len(evidence) != len(trace.alias_mapping):
                raise ObservationFailure("GENERATION_EVIDENCE_UNAVAILABLE")
            latency = trace.retrieval_latency_ms
            if (
                isinstance(latency, bool)
                or not isinstance(latency, (int, float))
                or not isfinite(latency)
                or latency < 0
            ):
                raise ObservationFailure("RETRIEVAL_LATENCY_INVALID")
            return {
                "case_id": case.case_id,
                "status": "OBSERVED",
                "trace_id": trace_id,
                "decision": public.decision,
                "public_answer": public.answer,
                "refusal_reason": public.refusal_reason,
                "public_citations": [asdict(citation) for citation in public.citations],
                "citation_correctness": True,
                "candidate_chunk_ids": ids,
                "generation_chunk_ids": [trace.alias_mapping[alias] for alias, _ in evidence],
                "generation_evidence": [list(item) for item in evidence],
                "provider_metadata": metadata,
                "retrieval_latency_ms": latency,
                "end_to_end_latency_ms": (response_completed - started) * 1000,
                "retrieval_configuration_id": binding["retrieval_configuration_id"],
                "embedding_configuration_id": binding["embedding_configuration_id"],
                "generation_configuration_id": binding["generation_configuration_id"],
                "candidate_budget": binding["candidate_budget"],
            }
        except (
            ObservationFailure,
            httpx.HTTPStatusError,
            KeyError,
            ValueError,
            TypeError,
            AttributeError,
            LookupError,
        ) as error:
            return {
                "case_id": case.case_id,
                "status": "FAILED",
                "trace_id": trace_id,
                "failure_code": str(error)
                if isinstance(error, ObservationFailure)
                else "EVALUATION_OBSERVATION_FAILURE",
            }

    return PdfRuntimeProfile(profile_id, kind, prepare, execute)
