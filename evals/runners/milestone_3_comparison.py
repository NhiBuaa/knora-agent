"""Paired Milestone 3 report, finding, and publication contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from fractions import Fraction
from math import isfinite
from types import MappingProxyType
from typing import Any

from evals.datasets.milestone_3 import QUALITY_CATEGORIES
from evals.runners.m3_claim_authority import (
    ALLOWED_CONFIGURATION_FIELDS,
    APPROVED_HUMAN_IDENTITY,
    AUTHORITY_IDENTIFIER,
    AUTHORITY_VALIDATION_FAILURE,
    CLAIM_RULE_DIGEST,
    CLAIM_RULE_VERSION,
    EQUAL_PROVENANCE_FIELDS,
    REQUIRED_GUARDRAIL_KEYS,
    ClaimRuleAuthority,
    canonical_authority_validation,
    canonical_policy_projection,
    is_non_placeholder_identity,
    test_claim_rule_authority_fixture,
    validate_approved_authority,
    validate_claim_rule_authority,
    validate_human_identity,
    validate_policy_projection,
)

__all__ = [
    "ALLOWED_CONFIGURATION_FIELDS",
    "APPROVED_HUMAN_IDENTITY",
    "AUTHORITY_IDENTIFIER",
    "AUTHORITY_VALIDATION_FAILURE",
    "CLAIM_RULE_DIGEST",
    "CLAIM_RULE_VERSION",
    "ClaimRuleAuthority",
    "ComparisonError",
    "REQUIRED_GUARDRAIL_KEYS",
    "TAXONOMY_ENUMS",
    "TAXONOMY_FIXTURE_MAP",
    "build_category_breakdown",
    "build_publication_manifest",
    "canonical_authority_validation",
    "canonical_policy_projection",
    "classify_finding",
    "compare_paired_reports",
    "is_non_placeholder_identity",
    "select_improvement",
    "test_claim_rule_authority_fixture",
    "validate_guardrails",
    "validate_guardrail_shape",
    "validate_human_identity",
    "validate_approved_authority",
    "validate_claim_rule_authority",
    "validate_policy_projection",
    "validate_publication_manifest",
]


class ComparisonError(ValueError):
    """A paired comparison cannot produce a valid, reproducible result."""


_ALLOWED_CONFIGURATION_FIELD_SET = set(ALLOWED_CONFIGURATION_FIELDS)

TAXONOMY_VERSION = "m3-failure-taxonomy-v1"
TAXONOMY_FIXTURE_MAP = MappingProxyType({
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
})
TAXONOMY_ENUMS = tuple(TAXONOMY_FIXTURE_MAP.values())
_FIXTURE_STAGES = {
    "fixture-lexical-branch-miss": "branch",
    "fixture-semantic-branch-miss": "branch",
    "fixture-fusion-union-ranked-low": "fusion",
    "fixture-evidence-selection-excluded": "evidence_selection",
}


def classify_finding(
    fixture_id: str,
    *,
    evidence: Iterable[str],
    stage: str | None = None,
    stage_evidence: Mapping[str, Any] | None = None,
    contributing_enums: Iterable[str] = (),
) -> dict[str, Any]:
    """Map one fixture to the closed taxonomy after stage/category preconditions."""
    try:
        primary_enum = TAXONOMY_FIXTURE_MAP[fixture_id]
    except KeyError:
        raise ComparisonError("UNKNOWN_TAXONOMY_FIXTURE") from None
    try:
        normalized_evidence = list(evidence)
    except TypeError:
        raise ComparisonError("FINDING_EVIDENCE_INVALID") from None
    if any(not isinstance(item, str) or not item for item in normalized_evidence):
        raise ComparisonError("FINDING_EVIDENCE_INVALID")
    expected_stage = _FIXTURE_STAGES.get(fixture_id)
    if expected_stage is not None:
        if stage != expected_stage:
            raise ComparisonError("STAGE_PRECONDITION_INVALID")
        if stage_evidence is not None and not isinstance(stage_evidence, Mapping):
            raise ComparisonError("STAGE_PRECONDITION_INVALID")
        details = stage_evidence or {}
        if expected_stage == "fusion" and (
            details.get("eligible_branch_union") is not True
            or details.get("post_fusion_rank_incorrect") is not True
        ):
            raise ComparisonError("STAGE_PRECONDITION_INVALID")
        if expected_stage == "evidence_selection" and (
            details.get("post_fusion_excluded") is not True
        ):
            raise ComparisonError("STAGE_PRECONDITION_INVALID")
    elif stage is not None:
        raise ComparisonError("STAGE_PRECONDITION_INVALID")
    try:
        contributing = tuple(contributing_enums)
    except TypeError:
        raise ComparisonError("CATEGORY_INVALID") from None
    if any(
        item not in TAXONOMY_ENUMS or item == "INSUFFICIENT_EVIDENCE_CORRECT"
        for item in contributing
    ):
        raise ComparisonError("CATEGORY_INVALID")
    if len(set(contributing)) != len(contributing):
        raise ComparisonError("CATEGORY_INVALID")
    return {
        "taxonomy_version": TAXONOMY_VERSION,
        "fixture_id": fixture_id,
        "primary_enum": primary_enum,
        "is_failure": primary_enum != "INSUFFICIENT_EVIDENCE_CORRECT",
        "evidence": normalized_evidence,
        "contributing_enums": list(contributing),
        "stage": expected_stage or stage,
    }


def _metric(report: Mapping[str, Any], name: str) -> float | None:
    retrieval = report.get("retrieval")
    value = retrieval.get(name) if isinstance(retrieval, Mapping) else None
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComparisonError("METRIC_INVALID")
    if isinstance(value, float) and not isfinite(value):
        raise ComparisonError("METRIC_INVALID")
    return float(value)


def _rational(value: object) -> Fraction:
    if isinstance(value, Mapping):
        numerator = value.get("numerator")
        denominator = value.get("denominator")
        if (
            type(numerator) is not int
            or type(denominator) is not int
            or denominator <= 0
        ):
            raise ComparisonError("METRIC_DECISION_INVALID")
        fraction = Fraction(numerator, denominator)
        if (
            numerator < 0
            or numerator > denominator
            or fraction.numerator != numerator
            or fraction.denominator != denominator
        ):
            raise ComparisonError("METRIC_DECISION_INVALID")
        return fraction
    if isinstance(value, str):
        parts = value.split("/")
        if len(parts) != 2:
            raise ComparisonError("METRIC_DECISION_INVALID")
        try:
            numerator, denominator = (int(part) for part in parts)
        except ValueError:
            raise ComparisonError("METRIC_DECISION_INVALID") from None
        if denominator <= 0:
            raise ComparisonError("METRIC_DECISION_INVALID")
        fraction = Fraction(numerator, denominator)
        if (
            numerator < 0
            or numerator > denominator
            or fraction.numerator != numerator
            or fraction.denominator != denominator
            or f"{numerator}/{denominator}" != value
        ):
            raise ComparisonError("METRIC_DECISION_INVALID")
        return fraction
    raise ComparisonError("METRIC_DECISION_UNAVAILABLE")


def _metric_decision_value(report: Mapping[str, Any], name: str) -> Fraction:
    retrieval = report.get("retrieval")
    if not isinstance(retrieval, Mapping):
        raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
    values = retrieval.get("metric_decision_values")
    if not isinstance(values, Mapping) or name not in values:
        raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
    return _rational(values[name])


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def validate_guardrail_shape(guardrails: object) -> dict[str, bool]:
    """Validate the immutable closed key/type contract, retaining false observations."""
    if not isinstance(guardrails, Mapping) or set(guardrails) != set(REQUIRED_GUARDRAIL_KEYS):
        raise ComparisonError("GUARDRAIL_FAILURE")
    if any(type(guardrails[key]) is not bool for key in REQUIRED_GUARDRAIL_KEYS):
        raise ComparisonError("GUARDRAIL_FAILURE")
    return {key: guardrails[key] for key in REQUIRED_GUARDRAIL_KEYS}


def validate_guardrails(guardrails: object) -> dict[str, bool]:
    """Validate the immutable closed guardrail contract and require all values true."""
    shaped = validate_guardrail_shape(guardrails)
    if any(shaped[key] is not True for key in REQUIRED_GUARDRAIL_KEYS):
        raise ComparisonError("GUARDRAIL_FAILURE")
    return shaped


def _has_observation_failure(report: Mapping[str, Any]) -> bool:
    reported_count = report.get("observation_failure_count")
    if reported_count is not None:
        if type(reported_count) is not int or reported_count < 0:
            raise ComparisonError("OBSERVATION_FAILURE_COUNT_INVALID")
        if reported_count > 0:
            return True
    observations = report.get("observations", [])
    if not isinstance(observations, list):
        raise ComparisonError("OBSERVATIONS_INVALID")
    return any(
        isinstance(item, Mapping) and item.get("status") in {"failure", "observation_failure"}
        for item in observations
    )


def _selection_common(
    authority: ClaimRuleAuthority,
    hybrid_report: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "authority_identifier": AUTHORITY_IDENTIFIER,
        "claim_rule_version": CLAIM_RULE_VERSION,
        "claim_rule_digest": CLAIM_RULE_DIGEST,
        "authority_source_commit": authority.source_commit,
        "authority_document_blob": authority.authority_document_blob,
        "authority_document_sha256": authority.authority_document_sha256,
        "policy_projection_blob": authority.policy_projection_blob,
        "attestation_commit": authority.attestation_commit,
        "attestation_blob": authority.attestation_blob,
        "attestation_sha256": authority.attestation_sha256,
        "sealed_manifest_sha256": authority.sealed_manifest_sha256,
        "sealed_archive_sha256": authority.sealed_archive_sha256,
        "closure_sha256": authority.closure_sha256,
        "latency_tradeoffs": hybrid_report.get("latency_tradeoffs"),
        "remaining_regressions": hybrid_report.get("remaining_regressions"),
    }


def _no_claim(
    common: Mapping[str, Any],
    reason: str,
    *,
    metric_deltas: Mapping[str, float | None] | None = None,
    metric_decision_values: Mapping[str, Any] | None = None,
    metric_decision_deltas: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        **common,
        "status": "NO_CLAIM",
        "reason": reason,
        "metric_deltas": dict(metric_deltas or {}),
        "metric_decision_values": dict(metric_decision_values or {}),
        "metric_decision_deltas": dict(metric_decision_deltas or {}),
        "selected_improvement": None,
    }


def _selection_provenance_matches(
    pair: Mapping[str, Any],
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
) -> bool:
    try:
        vector_shared = _provenance_without_allowed_differences(vector_report)
        hybrid_shared = _provenance_without_allowed_differences(hybrid_report)
        vector_configuration = _configuration_id(vector_report)
        hybrid_configuration = _configuration_id(hybrid_report)
        _validate_metric_contract(vector_report)
        _validate_metric_contract(hybrid_report)
    except ComparisonError:
        return False
    return (
        vector_shared == hybrid_shared
        and pair.get("vector_configuration_id") == vector_configuration
        and pair.get("hybrid_configuration_id") == hybrid_configuration
    )


def _decision_metrics(
    primary_metrics: tuple[str, ...],
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
) -> tuple[dict[str, dict[str, int]], dict[str, Fraction], dict[str, float], str | None]:
    values: dict[str, dict[str, int]] = {}
    deltas: dict[str, Fraction] = {}
    display_deltas: dict[str, float] = {}
    for name in primary_metrics:
        try:
            vector_value = _metric_decision_value(vector_report, name)
            hybrid_value = _metric_decision_value(hybrid_report, name)
        except ComparisonError as error:
            return values, deltas, display_deltas, str(error)
        values[name] = {
            "vector_numerator": vector_value.numerator,
            "vector_denominator": vector_value.denominator,
            "hybrid_numerator": hybrid_value.numerator,
            "hybrid_denominator": hybrid_value.denominator,
        }
        delta = hybrid_value - vector_value
        deltas[name] = delta
        display_deltas[name] = float(delta)
    return values, deltas, display_deltas, None


def _policy_gate_reason(
    projection: Mapping[str, Any],
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    deltas: tuple[Fraction, ...],
) -> tuple[str | None, dict[str, bool]]:
    try:
        validate_guardrails(vector_report.get("guardrails"))
        hybrid_guardrails = validate_guardrails(hybrid_report.get("guardrails"))
    except ComparisonError:
        return "GUARDRAIL_FAILURE", {}
    for report in (vector_report, hybrid_report):
        if not isinstance(report.get("remaining_regressions"), list):
            return "REMAINING_REGRESSIONS_MISSING", hybrid_guardrails
        latency = report.get("latency_tradeoffs")
        if not isinstance(latency, Mapping) or not all(
            key in latency for key in projection["latency_policy"]["required_observations"]
        ):
            return "LATENCY_DISCLOSURE_MISSING", hybrid_guardrails
    if not (all(delta >= 0 for delta in deltas) and any(delta > 0 for delta in deltas)):
        return "NO_QUALIFYING_DELTA", hybrid_guardrails
    return None, hybrid_guardrails


def select_improvement(
    pair: Mapping[str, Any],
    *,
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    claim_rule: Mapping[str, Any] | None = None,
    authority: ClaimRuleAuthority | Mapping[str, Any] | None = None,
    production: bool = True,
) -> dict[str, Any]:
    """Apply the approved V1 rule only after authority validation succeeds.

    ``claim_rule`` is retained as a compatibility-shaped argument so a caller cannot silently
    weaken policy: any value supplied there is an authority-validation failure.  Focused tests
    pass an explicit ``ClaimRuleAuthority`` fixture with ``production=False``.
    """
    if claim_rule is not None:
        return {
            "schema_version": 1,
            "status": AUTHORITY_VALIDATION_FAILURE,
            "reason": "CALLER_POLICY_OVERRIDE",
            "selected_improvement": None,
        }
    authority_result = canonical_authority_validation(authority, production=production)
    if authority_result["status"] != "APPROVED_EFFECTIVE":
        return {
            "schema_version": 1,
            "status": AUTHORITY_VALIDATION_FAILURE,
            "reason": authority_result["reason"],
            "selected_improvement": None,
        }
    bound_authority = authority_result["authority"]
    projection = bound_authority.validated_projection()
    primary_metrics = tuple(projection["primary_metric_set"]["ordered"])
    common = _selection_common(bound_authority, hybrid_report)
    if pair.get("provenance_match") is not True:
        return _no_claim(common, "PROVENANCE_MISMATCH")
    if not _selection_provenance_matches(pair, vector_report, hybrid_report):
        return _no_claim(common, "PROVENANCE_MISMATCH")
    if _has_observation_failure(vector_report) or _has_observation_failure(hybrid_report):
        return _no_claim(common, "OBSERVATION_FAILURE")
    metric_values, decision_deltas, metric_deltas, metric_failure = _decision_metrics(
        primary_metrics, vector_report, hybrid_report
    )
    common = {
        **common,
        "metric_deltas": metric_deltas,
        "metric_decision_values": metric_values,
        "metric_decision_deltas": {
            name: _fraction_text(value) for name, value in decision_deltas.items()
        },
    }
    if metric_failure is not None:
        return _no_claim(
            common,
            metric_failure,
            metric_deltas=metric_deltas,
            metric_decision_values=metric_values,
            metric_decision_deltas=common["metric_decision_deltas"],
        )
    blocked_reason, hybrid_guardrails = _policy_gate_reason(
        projection, vector_report, hybrid_report, tuple(decision_deltas.values())
    )
    if blocked_reason is not None:
        return {
            **common,
            "status": "NO_CLAIM",
            "reason": blocked_reason,
            "selected_improvement": None,
        }
    selected = {
        "vector_configuration_id": pair["vector_configuration_id"],
        "hybrid_configuration_id": pair["hybrid_configuration_id"],
        "metric_deltas": metric_deltas,
        "metric_decision_deltas": common["metric_decision_deltas"],
        "guardrails": hybrid_guardrails,
        "latency_tradeoffs": hybrid_report["latency_tradeoffs"],
        "remaining_regressions": hybrid_report["remaining_regressions"],
        "claim_scope": projection["claim_scope"],
        "claim_rule_version": CLAIM_RULE_VERSION,
        "claim_rule_digest": CLAIM_RULE_DIGEST,
    }
    return {
        **common,
        "status": "SELECTED",
        "reason": "QUALIFYING_DELTA_AND_GUARDRAILS",
        "selected_improvement": selected,
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
        if isinstance(value, float) and not isfinite(value):
            raise ComparisonError("METRIC_INVALID")
        return float(value)
    raise ComparisonError("METRIC_INVALID")


def _category_metric(
    case_list: list[object],
    report: Mapping[str, Any],
    metric: str,
) -> dict[str, Any]:
    raw_observations = report.get("observations", [])
    if not isinstance(raw_observations, list):
        raise ComparisonError("OBSERVATIONS_INVALID")
    observed_ids = [
        item.get("case_id")
        for item in raw_observations
        if isinstance(item, Mapping) and isinstance(item.get("case_id"), str)
    ]
    if len(observed_ids) != len(set(observed_ids)):
        raise ComparisonError("DUPLICATE_CASE_ID")
    observations = {
        item["case_id"]: item
        for item in raw_observations
        if isinstance(item, Mapping) and isinstance(item.get("case_id"), str)
    }
    retrieval = report.get("retrieval", {})
    if not isinstance(retrieval, Mapping):
        raise ComparisonError("RETRIEVAL_INVALID")
    retrieval_case_list = retrieval.get("cases", [])
    if not isinstance(retrieval_case_list, list):
        raise ComparisonError("RETRIEVAL_INVALID")
    retrieval_cases = {
        item["id"]: item
        for item in retrieval_case_list
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    applicable_count = inapplicable_count = observation_failure_count = denominator = 0
    numerator: float | int = 0
    for case in case_list:
        case_id = _case_field(case, "id")
        observation = observations.get(case_id, {})
        if not _metric_applicable(case, metric):
            inapplicable_count += 1
            continue
        applicable_count += 1
        if case_id not in observations:
            observation_failure_count += 1
            continue
        if observation.get("status") in {"failure", "observation_failure"}:
            observation_failure_count += 1
            continue
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
    try:
        metric_names = tuple(metrics)
    except TypeError:
        raise ComparisonError("METRICS_INVALID") from None
    if any(not isinstance(metric, str) or not metric for metric in metric_names):
        raise ComparisonError("METRICS_INVALID")
    grouped: dict[str, list[object]] = {}
    for case in cases:
        case_id = _case_field(case, "id")
        category = _case_field(case, "category")
        if (
            not isinstance(case_id, str)
            or not isinstance(category, str)
            or category not in QUALITY_CATEGORIES
        ):
            raise ComparisonError("CASE_INVALID")
        grouped.setdefault(category, []).append(case)
    categories: dict[str, Any] = {}
    for category, category_cases in sorted(grouped.items()):
        categories[category] = {
            "case_ids": sorted(_case_field(case, "id") for case in category_cases),
            "case_count": len(category_cases),
            **{
                metric: _category_metric(category_cases, report, metric)
                for metric in metric_names
            },
        }
    all_cases = [case for cases_for_category in grouped.values() for case in cases_for_category]
    return {
        "categories": categories,
        "aggregate": {
            metric: _category_metric(all_cases, report, metric)
            for metric in metric_names
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
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != {"schema_version", "artifact_publication_id", "artifacts"}
        or manifest.get("schema_version") != 1
        or not isinstance(manifest.get("artifact_publication_id"), str)
        or "artifact_publication_commit" in manifest
        or not isinstance(manifest.get("artifacts"), list)
    ):
        raise ComparisonError("PUBLICATION_MANIFEST_INVALID")
    entries = manifest["artifacts"]
    if not entries:
        raise ComparisonError("PUBLICATION_MANIFEST_INVALID")
    paths: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "sha256", "schema_version"}:
            raise ComparisonError("PUBLICATION_MANIFEST_INVALID")
        path = entry["path"]
        digest = entry["sha256"]
        version = entry["schema_version"]
        if (
            not isinstance(path, str)
            or not path
            or "artifact_publication_commit" in path
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or type(version) is not int
            or version < 1
        ):
            raise ComparisonError("PUBLICATION_MANIFEST_INVALID")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ComparisonError("PUBLICATION_MANIFEST_INVALID")
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
    if report.get("schema_version") != 1:
        raise ComparisonError("PROVENANCE_MISMATCH")
    expected_keys = set(EQUAL_PROVENANCE_FIELDS) | _ALLOWED_CONFIGURATION_FIELD_SET
    if set(provenance) != expected_keys:
        raise ComparisonError("PROVENANCE_MISMATCH")
    for key in EQUAL_PROVENANCE_FIELDS:
        value = provenance.get(key)
        if key == "report_artifact_schema_version":
            valid = type(value) is int and value == 1
        elif key == "recall_k":
            valid = type(value) is int and value == 8
        else:
            valid = isinstance(value, str) and bool(value)
            if key in {"source_commit", "evaluation_commit"}:
                valid = valid and bool(re.fullmatch(r"[0-9a-f]{40}", value))
        if not valid:
            raise ComparisonError("PROVENANCE_MISMATCH")
    for key in ALLOWED_CONFIGURATION_FIELDS:
        value = provenance.get(key)
        if key in {"retrieval_configuration_id", "strategy"}:
            valid = isinstance(value, str) and bool(value)
        elif key == "fts_candidate_k":
            valid = value is None or (type(value) is int and value >= 0)
        else:
            valid = value is None or (isinstance(value, str) and bool(value))
        if not valid:
            raise ComparisonError("PROVENANCE_MISMATCH")
    if provenance["metric_contract"] != "m3-retrieval-metrics-v1":
        raise ComparisonError("PROVENANCE_MISMATCH")
    return {
        key: value
        for key, value in provenance.items()
        if key not in _ALLOWED_CONFIGURATION_FIELD_SET
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


def _validate_metric_contract(report: Mapping[str, Any]) -> None:
    retrieval = report.get("retrieval")
    if not isinstance(retrieval, Mapping):
        raise ComparisonError("METRIC_CONTRACT_MISMATCH")
    if retrieval.get("metric_contract") != "m3-retrieval-metrics-v1":
        raise ComparisonError("METRIC_CONTRACT_MISMATCH")
    if retrieval.get("recall_k") != 8:
        raise ComparisonError("METRIC_CONTRACT_MISMATCH")


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
    if expected_case_ids is not None:
        raw_expected = tuple(expected_case_ids)
        if len(raw_expected) != len(set(raw_expected)):
            raise ComparisonError("CASE_SET_MISMATCH")
        canonical_expected = tuple(sorted(raw_expected))
    else:
        canonical_expected = vector_cases
    if len(canonical_expected) != len(vector_cases) or canonical_expected != vector_cases:
        raise ComparisonError("CASE_SET_MISMATCH")

    vector_config = _configuration_id(vector_report)
    hybrid_config = _configuration_id(hybrid_report)
    _validate_metric_contract(vector_report)
    _validate_metric_contract(hybrid_report)
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
