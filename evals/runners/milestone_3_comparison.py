"""Paired Milestone 3 report, finding, and publication contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from fractions import Fraction
from math import isfinite
from pathlib import Path
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
    "APPROVED_RETRIEVAL_CONFIGURATIONS",
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
    "select_production_improvement",
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

APPROVED_RETRIEVAL_CONFIGURATIONS = MappingProxyType(
    {
        "retrieval-m3-vector-v2": MappingProxyType(
            {
                "strategy": "vector-only",
                "fusion_policy_id": None,
                "fusion_policy_version": None,
                "lexical_policy_id": None,
                "fts_candidate_k": None,
            }
        ),
        "retrieval-m3-rrf-v2": MappingProxyType(
            {
                "strategy": "hybrid",
                "fusion_policy_id": "rrf-v2",
                "fusion_policy_version": "rrf-v2",
                "lexical_policy_id": "fts-m3-or-v2",
                "fts_candidate_k": 8,
            }
        ),
    }
)

TAXONOMY_VERSION = "m3-failure-taxonomy-v1"
_VALID_MARKER_ID_PATTERN = re.compile(r"E[1-9][0-9]*\Z")
_SHA256_DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
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
REPORT_CATEGORY_METRICS = (
    "recall_at_8",
    "mrr",
    "structural_validity",
    "citation_correctness",
    "refusal_correctness",
    "semantic_citation_correctness",
)
_FIXTURE_STAGES = {
    "fixture-lexical-branch-miss": "branch",
    "fixture-semantic-branch-miss": "branch",
    "fixture-fusion-union-ranked-low": "fusion",
    "fixture-evidence-selection-excluded": "evidence_selection",
}


def _exact_bool_mapping(value: object, expected: Mapping[str, bool]) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == set(expected)
        and all(type(value[key]) is bool for key in expected)
        and all(value[key] is expected[key] for key in expected)
    )


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
    if stage_evidence is not None and not isinstance(stage_evidence, Mapping):
        raise ComparisonError("STAGE_PRECONDITION_INVALID")
    details = stage_evidence or {}
    if expected_stage is not None:
        if stage != expected_stage:
            raise ComparisonError("STAGE_PRECONDITION_INVALID")
        if expected_stage == "branch":
            expected_branch = "lexical" if fixture_id.startswith("fixture-lexical") else "semantic"
            if (
                details.get("branch") != expected_branch
                or details.get("gold_evidence_present") is not True
                or details.get("eligible_gold_evidence") is not False
                or details.get("miss_confirmed") is not True
            ):
                raise ComparisonError("STAGE_PRECONDITION_INVALID")
        if expected_stage == "fusion" and (
            not _exact_bool_mapping(
                details.get("branches_completed"),
                {"lexical": True, "semantic": True},
            )
            or details.get("eligible_branch_union") is not True
            or details.get("post_fusion_rank_incorrect") is not True
        ):
            raise ComparisonError("STAGE_PRECONDITION_INVALID")
        if expected_stage == "evidence_selection" and (
            details.get("fused_ordering_available") is not True
            or details.get("fused_ordering_version") != "rrf-v2"
            or details.get("post_fusion_excluded") is not True
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
    if contributing:
        contributing_evidence = details.get("contributing_stage_evidence")
        if not isinstance(contributing_evidence, Mapping):
            raise ComparisonError("STAGE_PRECONDITION_INVALID")
        for enum in contributing:
            contribution = contributing_evidence.get(enum)
            if not isinstance(contribution, Mapping):
                raise ComparisonError("STAGE_PRECONDITION_INVALID")
            if enum in {"LEXICAL_MISS", "SEMANTIC_MISS"}:
                valid = (
                    contribution.get("gold_evidence_present") is True
                    and contribution.get("eligible_gold_evidence") is False
                    and contribution.get("miss_confirmed") is True
                )
            elif enum == "FUSION_RANKING_ERROR":
                valid = (
                    _exact_bool_mapping(
                        contribution.get("branches_completed"),
                        {"lexical": True, "semantic": True},
                    )
                    and contribution.get("eligible_branch_union") is True
                    and contribution.get("post_fusion_rank_incorrect") is True
                )
            elif enum == "EVIDENCE_SELECTION_ERROR":
                valid = (
                    contribution.get("fused_ordering_available") is True
                    and contribution.get("fused_ordering_version") == "rrf-v2"
                    and contribution.get("post_fusion_excluded") is True
                )
            else:
                valid = contribution.get("stage_proven") is True
            if not valid:
                raise ComparisonError("STAGE_PRECONDITION_INVALID")
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
    if "observation_failure_count" not in report:
        raise ComparisonError("OBSERVATION_FAILURE_COUNT_MISSING")
    reported_count = report.get("observation_failure_count")
    if type(reported_count) is not int or reported_count < 0:
        raise ComparisonError("OBSERVATION_FAILURE_COUNT_INVALID")
    observations = report.get("observations")
    if not isinstance(observations, list):
        raise ComparisonError("OBSERVATIONS_INVALID")
    observed_count = sum(
        isinstance(item, Mapping) and item.get("status") in {"failure", "observation_failure"}
        for item in observations
    )
    if observed_count != reported_count:
        raise ComparisonError("OBSERVATION_FAILURE_COUNT_MISMATCH")
    return reported_count > 0


def _validate_observation_set(
    report: Mapping[str, Any], expected_case_ids: tuple[str, ...]
) -> tuple[dict[str, Any], ...]:
    observations = report.get("observations")
    if not isinstance(observations, list):
        raise ComparisonError("OBSERVATIONS_INVALID")
    by_id: dict[str, Any] = {}
    for observation in observations:
        if not isinstance(observation, Mapping) or not isinstance(
            observation.get("case_id"), str
        ):
            raise ComparisonError("OBSERVATIONS_INVALID")
        case_id = observation["case_id"]
        if case_id in by_id:
            raise ComparisonError("DUPLICATE_CASE_ID")
        if case_id not in expected_case_ids:
            raise ComparisonError("CASE_SET_MISMATCH")
        status = observation.get("status")
        if status not in {"observed", "failure", "observation_failure"}:
            raise ComparisonError("OBSERVATION_STATUS_INVALID")
        if status == "observed":
            for field in ("retrieval_latency_ms", "end_to_end_latency_ms"):
                value = observation.get(field)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not isfinite(float(value))
                    or value < 0
                ):
                    raise ComparisonError("OBSERVATION_LATENCY_INVALID")
            if observation.get("failure_code") is not None:
                raise ComparisonError("OBSERVATION_FAILURE_CODE_INVALID")
            for field in ("retrieval_configuration_id", "chunk_set_provenance_id"):
                value = observation.get(field)
                if not isinstance(value, str) or not value:
                    raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
            if observation.get("decision") not in {"ANSWER", "REFUSAL"}:
                raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
            _validate_public_observation_projection(observation)
            if any(
                type(observation.get(field)) is not bool
                for field in REQUIRED_GUARDRAIL_KEYS
            ):
                raise ComparisonError("GUARDRAIL_FAILURE")
            provenance = report.get("provenance")
            if not isinstance(provenance, Mapping):
                raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
            if (
                observation.get("retrieval_configuration_id")
                != provenance.get("retrieval_configuration_id")
                or observation.get("chunk_set_provenance_id")
                != provenance.get("chunk_set_id")
            ):
                raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
            bindings = observation.get("source_bindings")
            if not isinstance(bindings, list) or not bindings:
                raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
            source_keys: list[str] = []
            for binding in bindings:
                if not isinstance(binding, Mapping) or set(binding) != {
                    "source_key",
                    "production_document_version_id",
                    "production_chunk_set_id",
                } or any(
                    not isinstance(binding[field], str) or not binding[field]
                    for field in (
                        "source_key",
                        "production_document_version_id",
                        "production_chunk_set_id",
                    )
                ):
                    raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
                source_keys.append(binding["source_key"])
            if len(source_keys) != len(set(source_keys)):
                raise ComparisonError("PROVENANCE_MISMATCH")
        else:
            failure_code = observation.get("failure_code")
            if not isinstance(failure_code, str) or not failure_code:
                raise ComparisonError("OBSERVATION_FAILURE_CODE_INVALID")
        by_id[case_id] = observation
    if tuple(sorted(by_id)) != expected_case_ids:
        raise ComparisonError("CASE_SET_MISMATCH")
    _has_observation_failure(report)
    return tuple(by_id[case_id] for case_id in expected_case_ids)


def _validate_public_observation_projection(observation: Mapping[str, Any]) -> None:
    decision = observation.get("decision")
    answer = observation.get("public_answer")
    refusal_reason = observation.get("refusal_reason")
    citations = observation.get("public_citations")
    markers = observation.get("answer_marker_ids")
    citation_ids = observation.get("citation_evidence_ids")
    if not isinstance(citations, list) or not isinstance(markers, list) or not isinstance(
        citation_ids, list
    ):
        raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
    if any(
        not isinstance(item, str) or not _VALID_MARKER_ID_PATTERN.fullmatch(item)
        for item in (*markers, *citation_ids)
    ) or len(set(markers)) != len(markers) or len(set(citation_ids)) != len(citation_ids):
        raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
    public_ids: list[str] = []
    for citation in citations:
        if not isinstance(citation, Mapping) or set(citation) != {
            "evidence_id",
            "source_key",
            "excerpt",
            "source_locator",
        }:
            raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
        if any(
            not isinstance(citation[field], str) or not citation[field].strip()
            for field in ("evidence_id", "source_key", "excerpt", "source_locator")
        ) or _VALID_MARKER_ID_PATTERN.fullmatch(citation["evidence_id"]) is None:
            raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
        public_ids.append(citation["evidence_id"])
    if len(public_ids) != len(set(public_ids)) or tuple(public_ids) != tuple(citation_ids):
        raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
    if decision == "ANSWER":
        if not isinstance(answer, str) or not answer.strip() or refusal_reason is not None:
            raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
        parsed_markers = tuple(re.findall(r"\[\[(E[1-9][0-9]*)\]\]", answer))
        if (
            parsed_markers != tuple(markers)
            or tuple(markers) != tuple(citation_ids)
            or answer.count("[[") != len(parsed_markers)
            or answer.count("]]") != len(parsed_markers)
        ):
            raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
    elif decision == "REFUSAL":
        if (
            answer is not None
            or citations
            or markers
            or citation_ids
            or refusal_reason != "INSUFFICIENT_EVIDENCE"
        ):
            raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
    else:
        raise ComparisonError("OBSERVATION_RESPONSE_INVALID")
    if type(observation.get("refusal_correctness")) is not bool:
        raise ComparisonError("OBSERVATION_RESPONSE_INVALID")


def _validate_latency_disclosure(report: Mapping[str, Any]) -> None:
    latency = report.get("latency_tradeoffs")
    if not isinstance(latency, Mapping):
        raise ComparisonError("LATENCY_DISCLOSURE_MISSING")
    required = {"retrieval", "end_to_end"}
    if set(latency) != required:
        raise ComparisonError("LATENCY_DISCLOSURE_MISSING")
    observations = report.get("observations")
    if not isinstance(observations, list):
        raise ComparisonError("OBSERVATIONS_INVALID")
    successful_count = sum(
        isinstance(item, Mapping) and item.get("status") == "observed"
        for item in observations
    )
    for name in sorted(required):
        observation = latency.get(name)
        if not isinstance(observation, Mapping):
            raise ComparisonError("LATENCY_DISCLOSURE_INVALID")
        count = observation.get("count")
        if (
            type(count) is not int
            or count < 0
            or count != successful_count
            or observation.get("observed_per_case") is not (successful_count > 0)
        ):
            raise ComparisonError("LATENCY_DISCLOSURE_INVALID")


def _validate_report_guardrails(report: Mapping[str, Any]) -> dict[str, bool]:
    observations = report.get("observations")
    if not isinstance(observations, list):
        raise ComparisonError("GUARDRAIL_FAILURE")
    observed = [item for item in observations if isinstance(item, Mapping)]
    answer_observations = [item for item in observed if item.get("decision") == "ANSWER"]
    refusal_values = [item.get("refusal_correctness") for item in observed]
    expected = {
        "structural_validity": bool(observed)
        and len(observed) == len(observations)
        and all(item.get("status") == "observed" for item in observed)
        and all(item.get("structural_validity") is True for item in observed),
        "citation_correctness": bool(answer_observations)
        and all(item.get("citation_correctness") is True for item in answer_observations),
        "refusal_correctness": bool(refusal_values)
        and all(value is True for value in refusal_values),
    }
    try:
        shaped = validate_guardrail_shape(report.get("guardrails"))
    except ComparisonError:
        raise ComparisonError("GUARDRAIL_FAILURE") from None
    if shaped != expected:
        raise ComparisonError("GUARDRAIL_FAILURE")
    return shaped


def _validate_category_metric(value: object, *, case_count: int) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "applicable_count",
        "inapplicable_count",
        "observation_failure_count",
        "numerator",
        "denominator",
        "value",
    }:
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    applicable = value["applicable_count"]
    inapplicable = value["inapplicable_count"]
    failures = value["observation_failure_count"]
    denominator = value["denominator"]
    if any(
        type(item) is not int or item < 0
        for item in (applicable, inapplicable, failures, denominator)
    ):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    if applicable + inapplicable != case_count or failures > applicable:
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    if denominator != applicable - failures:
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    numerator = value["numerator"]
    if isinstance(numerator, bool) or not isinstance(numerator, (int, float)):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    if isinstance(numerator, float) and not isfinite(numerator):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    if numerator < 0 or numerator > denominator:
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    projected = value["value"]
    if denominator == 0:
        if projected is not None or numerator != 0:
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    else:
        if isinstance(projected, bool) or not isinstance(projected, (int, float)):
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        if isinstance(projected, float) and not isfinite(projected):
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        if float(projected) != float(numerator) / denominator:
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")


def _expected_report_metric(
    report: Mapping[str, Any], case_ids: tuple[str, ...], metric: str
) -> dict[str, Any]:
    observations = report.get("observations")
    retrieval = report.get("retrieval")
    if not isinstance(observations, list) or not isinstance(retrieval, Mapping):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    observation_by_id = {
        item["case_id"]: item
        for item in observations
        if isinstance(item, Mapping) and isinstance(item.get("case_id"), str)
    }
    retrieval_cases = retrieval.get("cases")
    if not isinstance(retrieval_cases, list):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    retrieval_by_id = {
        item["id"]: item
        for item in retrieval_cases
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    applicable = inapplicable = failures = denominator = 0
    numerator: float | int = 0
    for case_id in case_ids:
        observation = observation_by_id.get(case_id)
        if observation is None:
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        if metric in {"recall_at_8", "mrr"}:
            retrieval_case = retrieval_by_id.get(case_id)
            if not isinstance(retrieval_case, Mapping):
                raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
            included = retrieval_case.get("included")
            if included is False and retrieval_case.get("exclusion_reason") == (
                "RETRIEVAL_RELEVANCE_NOT_APPLICABLE"
            ):
                inapplicable += 1
                continue
            if type(included) is not bool:
                raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        else:
            if (
                metric == "semantic_citation_correctness"
                and observation.get("decision") == "REFUSAL"
            ):
                inapplicable += 1
                continue
        applicable += 1
        if observation.get("status") in {"failure", "observation_failure"}:
            failures += 1
            continue
        if metric in {"recall_at_8", "mrr"}:
            retrieval_case = retrieval_by_id[case_id]
            if retrieval_case.get("included") is not True:
                raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
            decision = retrieval_case.get("metric_decision_values")
            if not isinstance(decision, Mapping) or metric not in decision:
                raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
            value = _rational(decision[metric])
            contribution: float | int = float(value)
        else:
            value = observation.get(metric)
            if type(value) is not bool:
                raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
            contribution = int(value)
        denominator += 1
        numerator += contribution
    return {
        "applicable_count": applicable,
        "inapplicable_count": inapplicable,
        "observation_failure_count": failures,
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _assert_metric_projection_matches(
    actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    for field in (
        "applicable_count",
        "inapplicable_count",
        "observation_failure_count",
        "denominator",
    ):
        if actual.get(field) != expected[field]:
            raise ComparisonError("CATEGORY_BREAKDOWN_RECONCILIATION_FAILED")
    if float(actual["numerator"]) != float(expected["numerator"]):
        raise ComparisonError("CATEGORY_BREAKDOWN_RECONCILIATION_FAILED")
    actual_value = actual.get("value")
    expected_value = expected["value"]
    if actual_value is None or expected_value is None:
        if actual_value is not expected_value:
            raise ComparisonError("CATEGORY_BREAKDOWN_RECONCILIATION_FAILED")
    elif float(actual_value) != float(expected_value):
        raise ComparisonError("CATEGORY_BREAKDOWN_RECONCILIATION_FAILED")


def _validate_category_breakdown(
    report: Mapping[str, Any],
    *,
    expected_case_ids: tuple[str, ...] | None = None,
    require_all_categories: bool = True,
) -> None:
    breakdown = report.get("category_breakdown")
    if not isinstance(breakdown, Mapping) or set(breakdown) != {"categories", "aggregate"}:
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    categories = breakdown.get("categories")
    aggregate = breakdown.get("aggregate")
    if not isinstance(categories, Mapping) or not isinstance(aggregate, Mapping):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    if require_all_categories and set(categories) != {
        "lexical_exact_match",
        "semantic_paraphrase",
        "multi_source",
        "insufficient_evidence_refusal",
    }:
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    all_category_ids: list[str] = []
    metric_names: set[str] | None = None
    for _category, projection in categories.items():
        if not isinstance(projection, Mapping):
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        case_count = projection.get("case_count")
        case_ids = projection.get("case_ids")
        if type(case_count) is not int or case_count < 0 or not isinstance(case_ids, list):
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        if case_count != len(case_ids) or len(case_ids) != len(set(case_ids)):
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        all_category_ids.extend(case_ids)
        projection_metrics = set(projection) - {"case_ids", "case_count"}
        if metric_names is None:
            metric_names = projection_metrics
        elif projection_metrics != metric_names:
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        if metric_names != set(REPORT_CATEGORY_METRICS):
            raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
        for metric in REPORT_CATEGORY_METRICS:
            _validate_category_metric(projection.get(metric), case_count=case_count)
    if expected_case_ids is not None and (
        len(all_category_ids) != len(set(all_category_ids))
        or tuple(sorted(all_category_ids)) != expected_case_ids
    ):
        raise ComparisonError("CATEGORY_CASE_SET_MISMATCH")
    if metric_names != set(REPORT_CATEGORY_METRICS):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    aggregate_metrics = set(aggregate)
    if aggregate_metrics != set(REPORT_CATEGORY_METRICS):
        raise ComparisonError("CATEGORY_BREAKDOWN_INVALID")
    aggregate_case_ids = tuple(sorted(all_category_ids))
    for metric in REPORT_CATEGORY_METRICS:
        _validate_category_metric(aggregate.get(metric), case_count=sum(
            projection["case_count"] for projection in categories.values()
        ))
        expected = _expected_report_metric(report, aggregate_case_ids, metric)
        _assert_metric_projection_matches(aggregate[metric], expected)
        for _category, projection in categories.items():
            category_ids = tuple(sorted(projection["case_ids"]))
            expected = _expected_report_metric(report, category_ids, metric)
            _assert_metric_projection_matches(projection[metric], expected)


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
        vector_configuration = _validate_configuration_semantics(vector_report)
        hybrid_configuration = _validate_configuration_semantics(hybrid_report)
        vector_bindings = _observation_source_bindings(vector_report)
        hybrid_bindings = _observation_source_bindings(hybrid_report)
    except ComparisonError:
        return False
    return (
        vector_shared == hybrid_shared
        and pair.get("shared_provenance") == vector_shared
        and pair.get("vector_configuration_id") == vector_configuration
        and pair.get("hybrid_configuration_id") == hybrid_configuration
        and vector_bindings == hybrid_bindings
    )


def _observation_source_bindings(
    report: Mapping[str, Any],
) -> dict[str, tuple[tuple[str, str, str], ...]]:
    observations = report.get("observations")
    if not isinstance(observations, list):
        raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
    result: dict[str, tuple[tuple[str, str, str], ...]] = {}
    for observation in observations:
        if not isinstance(observation, Mapping) or not isinstance(
            observation.get("case_id"), str
        ):
            raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
        if observation.get("status") != "observed":
            continue
        bindings = observation.get("source_bindings")
        if not isinstance(bindings, list):
            raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
        normalized: list[tuple[str, str, str]] = []
        for binding in bindings:
            if not isinstance(binding, Mapping) or set(binding) != {
                "source_key",
                "production_document_version_id",
                "production_chunk_set_id",
            } or any(
                not isinstance(binding[field], str) or not binding[field]
                for field in (
                    "source_key",
                    "production_document_version_id",
                    "production_chunk_set_id",
                )
            ):
                raise ComparisonError("OBSERVATION_PROVENANCE_INVALID")
            normalized.append(
                (
                    binding["source_key"],
                    binding["production_document_version_id"],
                    binding["production_chunk_set_id"],
                )
            )
        if len({item[0] for item in normalized}) != len(normalized):
            raise ComparisonError("PROVENANCE_MISMATCH")
        result[observation["case_id"]] = tuple(sorted(normalized))
    observed_sets = {bindings for bindings in result.values()}
    if len(observed_sets) > 1:
        raise ComparisonError("PROVENANCE_MISMATCH")
    return result


def _validate_pair_contract(pair: Mapping[str, Any]) -> tuple[str, ...]:
    required_keys = {
        "schema_version",
        "case_ids",
        "pair_cardinality",
        "expected_pair_cardinality",
        "pair_key",
        "pair_records",
        "provenance_match",
        "vector_configuration_id",
        "hybrid_configuration_id",
        "shared_provenance",
    }
    if not isinstance(pair, Mapping) or set(pair) != required_keys:
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    if pair.get("schema_version") != 1 or pair.get("pair_key") != (
        "(case_id, retrieval_configuration_id)"
    ):
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    case_ids = pair.get("case_ids")
    if not isinstance(case_ids, list) or not case_ids or any(
        not isinstance(case_id, str) or not case_id for case_id in case_ids
    ):
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    if len(case_ids) != len(set(case_ids)) or tuple(case_ids) != tuple(sorted(case_ids)):
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    vector_configuration = pair.get("vector_configuration_id")
    hybrid_configuration = pair.get("hybrid_configuration_id")
    if (
        vector_configuration != "retrieval-m3-vector-v2"
        or hybrid_configuration != "retrieval-m3-rrf-v2"
        or pair.get("provenance_match") is not True
    ):
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    pair_records = pair.get("pair_records")
    expected_records = [
        {"case_id": case_id, "retrieval_configuration_id": vector_configuration}
        for case_id in case_ids
    ] + [
        {"case_id": case_id, "retrieval_configuration_id": hybrid_configuration}
        for case_id in case_ids
    ]
    if pair_records != expected_records:
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    expected_cardinality = 2 * len(case_ids)
    if (
        type(pair.get("pair_cardinality")) is not int
        or type(pair.get("expected_pair_cardinality")) is not int
        or pair["pair_cardinality"] != expected_cardinality
        or pair["expected_pair_cardinality"] != expected_cardinality
    ):
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    if not isinstance(pair.get("shared_provenance"), Mapping):
        raise ComparisonError("PAIR_CONTRACT_INVALID")
    return tuple(case_ids)


def _decision_metrics(
    primary_metrics: tuple[str, ...],
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    expected_case_ids: tuple[str, ...],
) -> tuple[dict[str, dict[str, int]], dict[str, Fraction], dict[str, float], str | None]:
    def recompute(report: Mapping[str, Any], metric: str) -> Fraction:
        retrieval = report.get("retrieval")
        if not isinstance(retrieval, Mapping) or not isinstance(retrieval.get("cases"), list):
            raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
        observations = report.get("observations")
        if not isinstance(observations, list):
            raise ComparisonError("OBSERVATIONS_INVALID")
        observation_by_id = {
            item["case_id"]: item
            for item in observations
            if isinstance(item, Mapping) and isinstance(item.get("case_id"), str)
        }
        cases = {
            item.get("id"): item
            for item in retrieval["cases"]
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
        if set(cases) != set(expected_case_ids) or len(cases) != len(expected_case_ids):
            raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
        included: list[Fraction] = []
        for case_id in expected_case_ids:
            item = cases[case_id]
            if item.get("included") is False:
                continue
            if item.get("included") is not True:
                raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
            if observation_by_id.get(case_id, {}).get("status") != "observed":
                raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
            decisions = item.get("metric_decision_values")
            if not isinstance(decisions, Mapping) or metric not in decisions:
                raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
            included.append(_rational(decisions[metric]))
        if not included:
            raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
        result = sum(included, Fraction(0, 1)) / len(included)
        retrieval_decisions = retrieval.get("metric_decision_values")
        if not isinstance(retrieval_decisions, Mapping) or metric not in retrieval_decisions:
            raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
        if _rational(retrieval_decisions[metric]) != result:
            raise ComparisonError("METRIC_DECISION_RECONCILIATION_FAILED")
        if retrieval.get("denominator") != len(included):
            raise ComparisonError("METRIC_DENOMINATOR_INVALID")
        return result

    values: dict[str, dict[str, int]] = {}
    deltas: dict[str, Fraction] = {}
    display_deltas: dict[str, float] = {}
    for name in primary_metrics:
        try:
            vector_value = recompute(vector_report, name)
            hybrid_value = recompute(hybrid_report, name)
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
        _validate_report_guardrails(vector_report)
        hybrid_guardrails = validate_guardrails(_validate_report_guardrails(hybrid_report))
    except ComparisonError:
        return "GUARDRAIL_FAILURE", {}
    for report in (vector_report, hybrid_report):
        if not isinstance(report.get("remaining_regressions"), list):
            return "REMAINING_REGRESSIONS_MISSING", hybrid_guardrails
        try:
            _validate_latency_disclosure(report)
        except ComparisonError as error:
            return str(error), hybrid_guardrails
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
    repository_root: Path | None = None,
    sealed_archive_path: Path | None = None,
    closure_path: Path | None = None,
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
    authority_result = canonical_authority_validation(
        authority,
        production=production,
        repository_root=repository_root,
        sealed_archive_path=sealed_archive_path,
        closure_path=closure_path,
    )
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
    try:
        expected_case_ids = _validate_pair_contract(pair)
    except ComparisonError as error:
        return _no_claim(common, str(error))
    try:
        _validate_observation_set(vector_report, expected_case_ids)
        _validate_observation_set(hybrid_report, expected_case_ids)
        if _has_observation_failure(vector_report) or _has_observation_failure(hybrid_report):
            return _no_claim(common, "OBSERVATION_FAILURE")
        _validate_report_guardrails(vector_report)
        _validate_report_guardrails(hybrid_report)
        _validate_metric_contract(vector_report, expected_case_ids)
        _validate_metric_contract(hybrid_report, expected_case_ids)
        _validate_category_breakdown(
            vector_report, expected_case_ids=expected_case_ids
        )
        _validate_category_breakdown(
            hybrid_report, expected_case_ids=expected_case_ids
        )
    except ComparisonError as error:
        reason = (
            "OBSERVATION_FAILURE"
            if str(error).startswith("OBSERVATION_FAILURE")
            else str(error)
        )
        return _no_claim(common, reason)
    if not _selection_provenance_matches(pair, vector_report, hybrid_report):
        return _no_claim(common, "PROVENANCE_MISMATCH")
    metric_values, decision_deltas, metric_deltas, metric_failure = _decision_metrics(
        primary_metrics, vector_report, hybrid_report, expected_case_ids
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


def select_production_improvement(
    pair: Mapping[str, Any],
    *,
    vector_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    repository_root: Path,
    sealed_archive_path: Path | None = None,
    closure_path: Path | None = None,
) -> dict[str, Any]:
    """Canonical production entry point with no caller-supplied policy or authority seam."""
    return select_improvement(
        pair,
        vector_report=vector_report,
        hybrid_report=hybrid_report,
        production=True,
        repository_root=repository_root,
        sealed_archive_path=sealed_archive_path,
        closure_path=closure_path,
    )


def _case_field(case: object, name: str, default: Any = None) -> Any:
    if isinstance(case, Mapping):
        return case.get(name, default)
    return getattr(case, name, default)


def _metric_applicable(case: object, metric: str) -> bool:
    if metric == "semantic_citation_correctness":
        return _case_field(case, "expected_behavior") == "ANSWER"
    if metric in {
        "structural_validity",
        "citation_correctness",
        "refusal_correctness",
    }:
        return True
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
        report_case = report_cases.get(case_id, {})
        value = report_case.get(metric)
        if value is None and metric == "mrr":
            # The retrieval report names each per-case MRR value reciprocal_rank;
            # preserve that value when reconciling category denominators.
            value = report_case.get("reciprocal_rank")
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
    metrics: Iterable[str] = REPORT_CATEGORY_METRICS,
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
        elif key in {"dataset_digest", "corpus_digest", "chunk_set_digest"}:
            valid = isinstance(value, str) and _SHA256_DIGEST_PATTERN.fullmatch(value) is not None
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


def _validate_configuration_semantics(report: Mapping[str, Any]) -> str:
    configuration = _configuration_id(report)
    expected = APPROVED_RETRIEVAL_CONFIGURATIONS.get(configuration)
    if expected is None:
        raise ComparisonError("RETRIEVAL_CONFIGURATION_INVALID")
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ComparisonError("PROVENANCE_MISMATCH")
    for field, expected_value in expected.items():
        if provenance.get(field) != expected_value:
            raise ComparisonError("RETRIEVAL_CONFIGURATION_SEMANTICS_MISMATCH")
    return configuration


def _validate_metric_display(value: object, decision: Fraction) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not isfinite(value))
        or float(value) != float(decision)
    ):
        raise ComparisonError("METRIC_DECISION_RECONCILIATION_FAILED")


def _validate_metric_contract(
    report: Mapping[str, Any], expected_case_ids: tuple[str, ...] | None = None
) -> None:
    retrieval = report.get("retrieval")
    if not isinstance(retrieval, Mapping):
        raise ComparisonError("METRIC_CONTRACT_MISMATCH")
    if retrieval.get("metric_contract") != "m3-retrieval-metrics-v1":
        raise ComparisonError("METRIC_CONTRACT_MISMATCH")
    if retrieval.get("recall_k") != 8:
        raise ComparisonError("METRIC_CONTRACT_MISMATCH")
    if not isinstance(retrieval.get("cases"), list) or not retrieval["cases"]:
        raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
    metric_values = retrieval.get("metric_decision_values")
    denominator = retrieval.get("denominator")
    if type(denominator) is not int or denominator < 0:
        raise ComparisonError("METRIC_DENOMINATOR_INVALID")
    if denominator == 0:
        if retrieval.get("recall_at_8") is not None or retrieval.get("mrr") is not None:
            raise ComparisonError("METRIC_DECISION_RECONCILIATION_FAILED")
        if metric_values != {}:
            raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
    else:
        if not isinstance(metric_values, Mapping) or set(metric_values) != {
            "recall_at_8",
            "mrr",
        }:
            raise ComparisonError("METRIC_DECISION_UNAVAILABLE")
        for name, value in metric_values.items():
            decision = _rational(value)
            _validate_metric_display(
                retrieval.get("recall_at_8" if name == "recall_at_8" else "mrr")
                if name in {"recall_at_8", "mrr"}
                else None,
                decision,
            )
    case_ids: list[str] = []
    for item in retrieval["cases"]:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
        case_ids.append(item["id"])
        included = item.get("included")
        if type(included) is not bool:
            raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
        if included:
            values = item.get("metric_decision_values")
            if not isinstance(values, Mapping) or set(values) != {"recall_at_8", "mrr"}:
                raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
            for name, value in values.items():
                decision = _rational(value)
                _validate_metric_display(
                    item.get("recall_at_8" if name == "recall_at_8" else "reciprocal_rank"),
                    decision,
                )
        elif not isinstance(item.get("exclusion_reason"), str) or not item["exclusion_reason"]:
            raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
    if len(case_ids) != len(set(case_ids)):
        raise ComparisonError("DUPLICATE_CASE_ID")
    if expected_case_ids is not None and tuple(sorted(case_ids)) != expected_case_ids:
        raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
    observations = report.get("observations")
    if isinstance(observations, list):
        observation_by_id = {
            item["case_id"]: item
            for item in observations
            if isinstance(item, Mapping) and isinstance(item.get("case_id"), str)
        }
        for item in retrieval["cases"]:
            observation = observation_by_id.get(item["id"])
            if not isinstance(observation, Mapping):
                raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
            if item.get("included") is True or item.get("exclusion_reason") == (
                "RETRIEVAL_RELEVANCE_NOT_APPLICABLE"
            ):
                if observation.get("status") != "observed":
                    raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")
            elif observation.get("status") not in {"failure", "observation_failure"}:
                raise ComparisonError("METRIC_CASE_PROJECTION_INVALID")


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
    if expected_case_ids is None:
        raise ComparisonError("EXPECTED_CASE_SET_REQUIRED")
    raw_expected = tuple(expected_case_ids)
    if (
        len(raw_expected) != len(set(raw_expected))
        or any(not isinstance(item, str) or not item for item in raw_expected)
    ):
        raise ComparisonError("CASE_SET_MISMATCH")
    canonical_expected = tuple(sorted(raw_expected))
    if len(canonical_expected) != len(vector_cases) or canonical_expected != vector_cases:
        raise ComparisonError("CASE_SET_MISMATCH")

    vector_config = _validate_configuration_semantics(vector_report)
    hybrid_config = _validate_configuration_semantics(hybrid_report)
    _validate_observation_set(vector_report, canonical_expected)
    _validate_observation_set(hybrid_report, canonical_expected)
    if _observation_source_bindings(vector_report) != _observation_source_bindings(
        hybrid_report
    ):
        raise ComparisonError("PROVENANCE_MISMATCH")
    _validate_metric_contract(vector_report, canonical_expected)
    _validate_metric_contract(hybrid_report, canonical_expected)
    _validate_category_breakdown(
        vector_report, expected_case_ids=canonical_expected
    )
    _validate_category_breakdown(
        hybrid_report, expected_case_ids=canonical_expected
    )
    if vector_config == hybrid_config:
        raise ComparisonError("RETRIEVAL_CONFIGURATION_NOT_PAIRED")
    if (
        vector_config != "retrieval-m3-vector-v2"
        or hybrid_config != "retrieval-m3-rrf-v2"
    ):
        raise ComparisonError("RETRIEVAL_CONFIGURATION_NOT_APPROVED")
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
