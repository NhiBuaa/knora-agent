"""Paired Milestone 3 report, finding, and publication contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


class ComparisonError(ValueError):
    """A paired comparison cannot produce a valid, reproducible result."""


_ALLOWED_CONFIGURATION_FIELDS = {
    "retrieval_configuration_id",
    "strategy",
    "fusion_policy_id",
    "fusion_policy_version",
    "lexical_policy_id",
    "fts_candidate_k",
}

TAXONOMY_VERSION = "m3-failure-taxonomy-v1"
TAXONOMY_FIXTURE_MAP = {
    "fixture-lexical-branch-miss": "LEXICAL_MISS",
    "fixture-semantic-branch-miss": "SEMANTIC_MISS",
    "fixture-fusion-union-ranked-low": "FUSION_RANKING_ERROR",
    "fixture-evidence-selection-excluded": "EVIDENCE_SELECTION_ERROR",
    "fixture-answer-refused": "FALSE_REFUSAL",
    "fixture-citation-structure-invalid": "CITATION_STRUCTURAL_ERROR",
    "fixture-citation-semantic-unsupported": "CITATION_SEMANTIC_UNSUPPORTED",
    "fixture-corpus-or-config-mismatch": "CORPUS_OR_CONFIGURATION_MISMATCH",
    "fixture-observation-invalid": "EVALUATION_OBSERVATION_FAILURE",
    "fixture-provider-failure": "PROVIDER_ERROR",
    "fixture-infrastructure-failure": "INFRASTRUCTURE_ERROR",
    "fixture-insufficient-evidence-correct": "INSUFFICIENT_EVIDENCE_CORRECT",
}


def classify_finding(fixture_id: str, *, evidence: Iterable[str]) -> dict[str, Any]:
    """Map a deterministic fixture to the closed, stage-correct taxonomy."""
    try:
        primary_enum = TAXONOMY_FIXTURE_MAP[fixture_id]
    except KeyError:
        raise ComparisonError("UNKNOWN_TAXONOMY_FIXTURE") from None
    normalized_evidence = list(evidence)
    if any(not isinstance(item, str) or not item for item in normalized_evidence):
        raise ComparisonError("FINDING_EVIDENCE_INVALID")
    return {
        "taxonomy_version": TAXONOMY_VERSION,
        "fixture_id": fixture_id,
        "primary_enum": primary_enum,
        "is_failure": primary_enum != "INSUFFICIENT_EVIDENCE_CORRECT",
        "evidence": normalized_evidence,
    }


def _metric(report: Mapping[str, Any], name: str) -> float | None:
    retrieval = report.get("retrieval")
    value = retrieval.get(name) if isinstance(retrieval, Mapping) else None
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComparisonError("METRIC_INVALID")
    return float(value)


def _has_observation_failure(report: Mapping[str, Any]) -> bool:
    observations = report.get("observations", [])
    if not isinstance(observations, list):
        raise ComparisonError("OBSERVATIONS_INVALID")
    return any(
        isinstance(item, Mapping) and item.get("status") in {"failure", "observation_failure"}
        for item in observations
    )


def select_improvement(
    pair: Mapping[str, Any],
    *,
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    claim_rule: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a declared, conservative claim rule to a validated report pair."""
    if pair.get("provenance_match") is not True:
        raise ComparisonError("PROVENANCE_MISMATCH")
    rule = {
        "version": "m3-improvement-claim-v1",
        "primary_metrics": ("recall_at_8", "mrr"),
        "minimum_delta": 0.0,
        "require_all_primary_metrics": False,
        "guardrails_must_pass": True,
    }
    if claim_rule:
        rule.update(claim_rule)
    metric_deltas: dict[str, float | None] = {}
    for name in rule["primary_metrics"]:
        vector_value = _metric(vector_report, name)
        hybrid_value = _metric(hybrid_report, name)
        metric_deltas[name] = (
            None if vector_value is None or hybrid_value is None else hybrid_value - vector_value
        )
    guardrails = hybrid_report.get("guardrails", {})
    guardrails_pass = isinstance(guardrails, Mapping) and all(
        value is True for value in guardrails.values()
    )
    blocked_reason: str | None = None
    if _has_observation_failure(vector_report) or _has_observation_failure(hybrid_report):
        blocked_reason = "OBSERVATION_FAILURE"
    elif not guardrails_pass and rule["guardrails_must_pass"]:
        blocked_reason = "GUARDRAIL_FAILURE"
    else:
        deltas = [value for value in metric_deltas.values() if value is not None]
        qualifying = (
            len(deltas) == len(metric_deltas)
            and (
                all(value > rule["minimum_delta"] for value in deltas)
                if rule["require_all_primary_metrics"]
                else any(value > rule["minimum_delta"] for value in deltas)
            )
        )
        if not qualifying:
            blocked_reason = "NO_QUALIFYING_DELTA"
    if blocked_reason is not None:
        return {
            "schema_version": 1,
            "status": "NO_CLAIM",
            "claim_rule_version": rule["version"],
            "reason": blocked_reason,
            "metric_deltas": metric_deltas,
            "selected_improvement": None,
        }
    return {
        "schema_version": 1,
        "status": "SELECTED",
        "claim_rule_version": rule["version"],
        "reason": "QUALIFYING_DELTA_AND_GUARDRAILS",
        "metric_deltas": metric_deltas,
        "selected_improvement": {
            "vector_configuration_id": pair["vector_configuration_id"],
            "hybrid_configuration_id": pair["hybrid_configuration_id"],
            "metric_deltas": metric_deltas,
            "guardrails": dict(guardrails),
            "latency_tradeoffs": hybrid_report.get("latency_tradeoffs", {}),
        },
    }


def _case_field(case: object, name: str, default: Any = None) -> Any:
    if isinstance(case, Mapping):
        return case.get(name, default)
    return getattr(case, name, default)


def _metric_applicable(case: object, metric: str) -> bool:
    relevance = _case_field(case, "retrieval_relevance")
    if metric in {"recall_at_8", "mrr", "hit_rate"} and relevance is not None:
        return bool(_case_field(relevance, "applicable", False))
    applicability = _case_field(case, "metric_applicability", {})
    if isinstance(applicability, Mapping) and metric in applicability:
        return applicability[metric] is True
    return True


def _metric_observation_value(
    observation: Mapping[str, Any],
    report_cases: Mapping[str, Mapping[str, Any]],
    case_id: str,
    metric: str,
) -> float | bool | None:
    value = observation.get(metric)
    if value is None:
        value = report_cases.get(case_id, {}).get(metric)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    raise ComparisonError("METRIC_INVALID")


def _category_metric(
    case_list: list[object],
    report: Mapping[str, Any],
    metric: str,
) -> dict[str, Any]:
    observations = {
        item["case_id"]: item
        for item in report.get("observations", [])
        if isinstance(item, Mapping) and isinstance(item.get("case_id"), str)
    }
    retrieval_cases = {
        item["id"]: item
        for item in report.get("retrieval", {}).get("cases", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    applicable_count = inapplicable_count = observation_failure_count = denominator = 0
    numerator: float | int = 0
    for case in case_list:
        case_id = _case_field(case, "id")
        observation = observations.get(case_id, {})
        if observation.get("status") in {"failure", "observation_failure"}:
            observation_failure_count += 1
            continue
        if not _metric_applicable(case, metric):
            inapplicable_count += 1
            continue
        applicable_count += 1
        value = _metric_observation_value(observation, retrieval_cases, case_id, metric)
        if value is None:
            observation_failure_count += 1
            continue
        denominator += 1
        numerator += int(value) if isinstance(value, bool) else value
    return {
        "applicable_count": applicable_count,
        "inapplicable_count": inapplicable_count,
        "observation_failure_count": observation_failure_count,
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def build_category_breakdown(
    cases: Iterable[object],
    report: Mapping[str, Any],
    *,
    metrics: Iterable[str] = ("recall_at_8", "mrr"),
) -> dict[str, Any]:
    """Reconcile each metric against its own category membership and applicability set."""
    grouped: dict[str, list[object]] = {}
    for case in cases:
        case_id = _case_field(case, "id")
        category = _case_field(case, "category")
        if not isinstance(case_id, str) or not isinstance(category, str):
            raise ComparisonError("CASE_INVALID")
        grouped.setdefault(category, []).append(case)
    categories: dict[str, Any] = {}
    for category, category_cases in sorted(grouped.items()):
        categories[category] = {
            "case_ids": sorted(_case_field(case, "id") for case in category_cases),
            "case_count": len(category_cases),
            **{
                metric: _category_metric(category_cases, report, metric)
                for metric in metrics
            },
        }
    all_cases = [case for cases_for_category in grouped.values() for case in cases_for_category]
    return {
        "categories": categories,
        "aggregate": {
            metric: _category_metric(all_cases, report, metric)
            for metric in metrics
        },
    }


def build_publication_manifest(
    artifacts: Mapping[str, bytes | bytearray | str],
    *,
    schema_versions: Mapping[str, int],
) -> dict[str, Any]:
    """Build a non-self-referential content manifest for committed report artifacts."""
    entries: list[dict[str, Any]] = []
    for path, content in artifacts.items():
        if not isinstance(path, str) or not path or "artifact_publication_commit" in path:
            raise ComparisonError("ARTIFACT_PATH_INVALID")
        if path not in schema_versions:
            raise ComparisonError("SCHEMA_VERSION_MISSING")
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        entries.append(
            {
                "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "schema_version": schema_versions[path],
            }
        )
    entries.sort(key=lambda item: item["path"])
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": 1,
        "artifact_publication_id": hashlib.sha256(canonical).hexdigest(),
        "artifacts": entries,
    }


def validate_publication_manifest(manifest: Mapping[str, Any]) -> bool:
    if "artifact_publication_commit" in manifest or not isinstance(manifest.get("artifacts"), list):
        raise ComparisonError("PUBLICATION_MANIFEST_INVALID")
    entries = manifest["artifacts"]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hashlib.sha256(canonical).hexdigest()
    if manifest.get("artifact_publication_id") != expected:
        raise ComparisonError("PUBLICATION_ID_MISMATCH")
    return True


def _observed_case_ids(report: Mapping[str, Any]) -> tuple[str, ...]:
    observations = report.get("observations")
    if not isinstance(observations, list):
        raise ComparisonError("OBSERVATIONS_INVALID")
    case_ids: list[str] = []
    for observation in observations:
        if not isinstance(observation, Mapping) or not isinstance(
            observation.get("case_id"), str
        ):
            raise ComparisonError("OBSERVATIONS_INVALID")
        case_ids.append(observation["case_id"])
    if len(case_ids) != len(set(case_ids)):
        raise ComparisonError("DUPLICATE_CASE_ID")
    return tuple(sorted(case_ids))


def _provenance_without_allowed_differences(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ComparisonError("PROVENANCE_INVALID")
    return {
        key: value
        for key, value in provenance.items()
        if key not in _ALLOWED_CONFIGURATION_FIELDS
    }


def _configuration_id(report: Mapping[str, Any]) -> str:
    provenance = report.get("provenance")
    configuration = (
        provenance.get("retrieval_configuration_id")
        if isinstance(provenance, Mapping)
        else None
    )
    if not isinstance(configuration, str) or not configuration:
        raise ComparisonError("RETRIEVAL_CONFIGURATION_INVALID")
    return configuration


def compare_paired_reports(
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    *,
    expected_case_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Validate and project one vector/hybrid pair over exactly the same cases.

    Configuration-specific provenance is intentionally retained in each report, while all
    dataset, corpus, Workspace, embedding, generation and scorer provenance must match exactly.
    """
    vector_cases = _observed_case_ids(vector_report)
    hybrid_cases = _observed_case_ids(hybrid_report)
    if vector_cases != hybrid_cases:
        raise ComparisonError("CASE_SET_MISMATCH")
    canonical_expected = (
        tuple(sorted(set(expected_case_ids)))
        if expected_case_ids is not None
        else vector_cases
    )
    if len(canonical_expected) != len(vector_cases) or canonical_expected != vector_cases:
        raise ComparisonError("CASE_SET_MISMATCH")

    vector_config = _configuration_id(vector_report)
    hybrid_config = _configuration_id(hybrid_report)
    if vector_config == hybrid_config:
        raise ComparisonError("RETRIEVAL_CONFIGURATION_NOT_PAIRED")
    if _provenance_without_allowed_differences(
        vector_report
    ) != _provenance_without_allowed_differences(hybrid_report):
        raise ComparisonError("PROVENANCE_MISMATCH")

    pair_records = [
        {"case_id": case_id, "retrieval_configuration_id": vector_config}
        for case_id in vector_cases
    ] + [
        {"case_id": case_id, "retrieval_configuration_id": hybrid_config}
        for case_id in hybrid_cases
    ]
    composite_keys = {
        (record["case_id"], record["retrieval_configuration_id"])
        for record in pair_records
    }
    if len(composite_keys) != len(pair_records):
        raise ComparisonError("DUPLICATE_PAIR_KEY")
    return {
        "schema_version": 1,
        "case_ids": list(vector_cases),
        "pair_cardinality": len(pair_records),
        "expected_pair_cardinality": 2 * len(vector_cases),
        "pair_key": "(case_id, retrieval_configuration_id)",
        "pair_records": pair_records,
        "provenance_match": True,
        "vector_configuration_id": vector_config,
        "hybrid_configuration_id": hybrid_config,
        "shared_provenance": _provenance_without_allowed_differences(vector_report),
    }
