"""Deterministic PDF evidence coverage from reviewed bindings and saved captures."""

from __future__ import annotations

import json
from dataclasses import asdict

from knora.evaluation.contracts import (
    DatasetSelection,
    FrozenDataset,
    canonical_json,
    digest_json,
)


def _chunk_ids(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def _observation_reasons(observation: object) -> list[str]:
    if not isinstance(observation, dict):
        return ["MALFORMED_OBSERVATION"]
    status = observation.get("status")
    if status in ("FAILED", "NOT_RUN", "BLOCKED", "INDETERMINATE"):
        return [f"OBSERVATION_{status}"]
    if status != "OBSERVED":
        return ["MALFORMED_OBSERVATION"]
    trace_id = observation.get("trace_id")
    reasons = []
    if not isinstance(trace_id, str) or not trace_id.strip():
        reasons.append("MISSING_TRACE")
    if (
        observation.get("decision") not in ("ANSWER", "REFUSAL")
        or not _chunk_ids(observation.get("candidate_chunk_ids"))
        or not _chunk_ids(observation.get("generation_chunk_ids"))
        or observation.get("failure_code") is not None
        or (
            observation.get("citation_correctness") is not None
            and type(observation["citation_correctness"]) is not bool
        )
        or (
            observation.get("public_answer") is not None
            and not isinstance(observation["public_answer"], str)
        )
        or (
            observation.get("public_citations") is not None
            and not isinstance(observation["public_citations"], list)
        )
    ):
        reasons.append("MALFORMED_OBSERVATION")
    return reasons


def _coverage(groups: list[set[str]], candidates: list[str], evaluable: bool, scope: str) -> dict:
    denominator = len(groups) if evaluable else 0
    candidate_ids = set(candidates)
    numerator = sum(bool(group & candidate_ids) for group in groups) if evaluable else 0
    return {
        "name": "evidence_group_coverage",
        "scope": scope,
        "k": None,
        "numerator": numerator,
        "denominator": denominator,
        "applicable_denominator": len(groups),
        "value": numerator / denominator if denominator else None,
    }


def _aggregate(cases: list[dict], key: str, scope: str) -> dict:
    metric = _coverage([], [], False, scope)
    for field in ("numerator", "denominator", "applicable_denominator"):
        metric[field] = sum(case[key][field] for case in cases)
    if metric["denominator"]:
        metric["value"] = metric["numerator"] / metric["denominator"]
    return metric


def score_pdf_run(
    frozen: FrozenDataset,
    selection: DatasetSelection,
    bindings: dict[str, dict],
    observations: dict[str, dict],
    *,
    run_id: str,
    binding_digest: str,
) -> dict:
    """Score complete cases only; unresolved gold or captures never become valid misses."""
    selection = DatasetSelection.from_json(selection.to_json(), frozen)
    by_id = {case.case_id: case for case in frozen.gold.cases}
    cases = []
    attempted = observed = 0
    for case_id in selection.selected_case_ids:
        case = by_id[case_id]
        raw = observations.get(case_id, {"status": "NOT_RUN"})
        observation = raw if isinstance(raw, dict) else {}
        reasons = _observation_reasons(raw)
        valid_observation = not reasons
        status = observation.get("status", "INVALID")
        attempted += status in ("OBSERVED", "FAILED", "INDETERMINATE")
        observed += valid_observation
        groups = []
        for group in case.evidence_groups:
            chunk_ids: set[str] = set()
            for anchor in group.alternatives:
                binding = bindings.get(digest_json(asdict(anchor)))
                if binding is None:
                    reasons.append("MISSING_BINDING")
                elif not isinstance(binding, dict):
                    reasons.append("MALFORMED_BINDING")
                elif binding.get("status") in ("MISSING", "AMBIGUOUS"):
                    reasons.append(f"{binding['status']}_BINDING")
                elif binding.get("status") != "READY" or not _chunk_ids(binding.get("chunk_ids")):
                    reasons.append("MALFORMED_BINDING")
                elif not binding["chunk_ids"]:
                    reasons.append("MISSING_BINDING")
                else:
                    chunk_ids.update(binding["chunk_ids"])
            groups.append(chunk_ids)
        applicable = case.expected == "ANSWER"
        evaluable = applicable and not reasons
        candidates = (
            list(dict.fromkeys(observation["candidate_chunk_ids"])) if valid_observation else []
        )
        generation = (
            list(dict.fromkeys(observation["generation_chunk_ids"])) if valid_observation else []
        )
        cases.append(
            {
                **json.loads(canonical_json(asdict(case))),
                "status": status,
                "trace_id": observation.get("trace_id"),
                "decision": observation.get("decision"),
                "failure_code": observation.get("failure_code"),
                "public_answer": observation.get("public_answer"),
                "public_citations": observation.get("public_citations"),
                "candidate_chunk_ids": candidates,
                "generation_chunk_ids": generation,
                "refusal_correctness": (
                    observation["decision"] == case.expected if valid_observation else None
                ),
                "citation_correctness": (
                    observation.get("citation_correctness") if valid_observation else None
                ),
                "applicable": applicable,
                "evaluable": evaluable,
                "reasons": list(dict.fromkeys(reasons)),
                "retrieval": _coverage(
                    groups, candidates, evaluable, "full_ordered_fused_candidates"
                ),
                "generation_evidence_coverage": _coverage(
                    groups, generation, evaluable, "generation_evidence"
                ),
            }
        )
    return {
        "schema_version": 1,
        "report_kind": "deterministic_partial_pdf",
        "quality_status": "SEMANTIC_PENDING",
        "run_id": run_id,
        "workspace_id": selection.reference.workspace_id,
        "selection_digest": digest_json(asdict(selection)),
        "binding_digest": binding_digest,
        "dataset": asdict(selection.reference),
        "population": {
            "dataset": len(frozen.gold.cases),
            "selected": len(cases),
            "context_only": len(selection.context_only_case_ids),
            "attempted": attempted,
            "observed": observed,
            "applicable": sum(case["applicable"] for case in cases),
            "evaluable": sum(case["evaluable"] for case in cases),
        },
        "retrieval": _aggregate(cases, "retrieval", "full_ordered_fused_candidates"),
        "generation_evidence_coverage": _aggregate(
            cases, "generation_evidence_coverage", "generation_evidence"
        ),
        "cases": cases,
        "context_only_cases": [
            json.loads(canonical_json(asdict(by_id[case_id])))
            for case_id in selection.context_only_case_ids
        ],
    }
