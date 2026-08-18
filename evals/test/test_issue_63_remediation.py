from __future__ import annotations

import hashlib
import io
import json
import tarfile
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import evals.runners.m3_claim_authority as authority_module
import pytest
from evals.runners.milestone_3_comparison import (
    AUTHORITY_VALIDATION_FAILURE,
    ClaimRuleAuthority,
    ComparisonError,
    build_category_breakdown,
    canonical_authority_validation,
    classify_finding,
    compare_paired_reports,
    select_improvement,
    select_production_improvement,
    test_claim_rule_authority_fixture,
    validate_guardrail_shape,
    validate_guardrails,
    validate_human_identity,
)

REQUIRED_GUARDRAILS = {
    "structural_validity": True,
    "citation_correctness": True,
    "refusal_correctness": True,
}


def _modern_report(
    configuration: str,
    *,
    recall: tuple[int, int] = (1, 2),
    mrr: tuple[int, int] = (1, 2),
    case_ids: tuple[str, ...] = ("case-a", "case-b"),
) -> dict[str, object]:
    def category_metric(numerator: float, denominator: int, case_count: int) -> dict[str, object]:
        return {
            "applicable_count": case_count,
            "inapplicable_count": 0,
            "observation_failure_count": 0,
            "numerator": numerator * case_count / denominator if denominator else 0,
            "denominator": case_count,
            "value": numerator / denominator if denominator else None,
        }

    def guard_metric(case_count: int) -> dict[str, object]:
        return {
            "applicable_count": case_count,
            "inapplicable_count": 0,
            "observation_failure_count": 0,
            "numerator": case_count,
            "denominator": case_count,
            "value": 1.0 if case_count else None,
        }

    retrieval_cases = [
        {
            "id": case_id,
            "included": True,
            "recall_at_8": recall[0] / recall[1],
            "reciprocal_rank": mrr[0] / mrr[1],
            "metric_decision_values": {
                "recall_at_8": {"numerator": recall[0], "denominator": recall[1]},
                "mrr": {"numerator": mrr[0], "denominator": mrr[1]},
            },
        }
        for case_id in case_ids
    ]
    category_template = {
        "lexical_exact_match": (list(case_ids), len(case_ids)),
        "semantic_paraphrase": ([], 0),
        "multi_source": ([], 0),
        "insufficient_evidence_refusal": ([], 0),
    }
    categories = {
        category: {
            "case_ids": ids,
            "case_count": count,
            "recall_at_8": category_metric(recall[0] / recall[1], 1, count)
            if count
            else {
                "applicable_count": 0,
                "inapplicable_count": 0,
                "observation_failure_count": 0,
                "numerator": 0,
                "denominator": 0,
                "value": None,
            },
            "mrr": category_metric(mrr[0] / mrr[1], 1, count)
            if count
            else {
                "applicable_count": 0,
                "inapplicable_count": 0,
                "observation_failure_count": 0,
                "numerator": 0,
                "denominator": 0,
                "value": None,
            },
        }
        for category, (ids, count) in category_template.items()
    }
    for category_projection in categories.values():
        for metric_name in (
            "structural_validity",
            "citation_correctness",
            "refusal_correctness",
            "semantic_citation_correctness",
        ):
            category_projection[metric_name] = guard_metric(category_projection["case_count"])
    provenance = {
        "dataset_version": "m3-dataset-v1",
        "dataset_digest": "sha256:" + "a" * 64,
        "corpus_id": "m3-corpus-v1",
        "corpus_digest": "sha256:" + "b" * 64,
        "chunk_set_id": "chunk-set-m3-v1",
        "chunk_set_digest": "sha256:" + "c" * 64,
        "workspace": "evaluation-m3-v1",
        "chunking_configuration": "chunking-m3-v1",
        "embedding_configuration": "embedding-m3-v1",
        "generation_configuration": "generation-m3-v1",
        "scorer_configuration": "scorer-m3-v1",
        "scorer_model": "judge-v1",
        "scorer_prompt": "prompt-v1",
        "scorer_policy": "policy-v1",
        "scorer_stochasticity": "deterministic",
        "metric_contract": "m3-retrieval-metrics-v1",
        "source_commit": "1" * 40,
        "evaluation_commit": "2" * 40,
        "report_artifact_schema_version": 1,
        "retrieval_configuration_id": configuration,
        "strategy": "vector-only" if "vector" in configuration else "hybrid",
        "fusion_policy_id": None if "vector" in configuration else "rrf-v2",
        "fusion_policy_version": None if "vector" in configuration else "rrf-v2",
        "lexical_policy_id": None if "vector" in configuration else "fts-m3-or-v2",
        "fts_candidate_k": None if "vector" in configuration else 8,
    }
    return {
        "schema_version": 1,
        "provenance": provenance,
        "observations": [
            {
                "case_id": case_id,
                "status": "observed",
                "retrieval_latency_ms": 1.0,
                "end_to_end_latency_ms": 2.0,
                "retrieval_configuration_id": configuration,
                "chunk_set_provenance_id": "chunk-set-m3-v1",
                "decision": "ANSWER",
                "public_answer": "answer [[E1]]",
                "public_citations": [
                    {
                        "evidence_id": "E1",
                        "source_key": "support/a",
                        "excerpt": "public excerpt",
                        "source_locator": "support/a:1:1",
                    }
                ],
                "answer_marker_ids": ["E1"],
                "citation_evidence_ids": ["E1"],
                "source_bindings": [
                    {
                        "source_key": "support/a",
                        "production_document_version_id": "version-1",
                        "production_chunk_set_id": "chunk-set-m3-v1",
                    }
                ],
                "structural_validity": True,
                "citation_correctness": True,
                "refusal_correctness": True,
                "semantic_citation_correctness": True,
            }
            for case_id in case_ids
        ],
        "observation_failure_count": 0,
        "retrieval": {
            "metric_contract": "m3-retrieval-metrics-v1",
            "recall_k": 8,
            "recall_at_8": recall[0] / recall[1],
            "mrr": mrr[0] / mrr[1],
            "denominator": len(case_ids),
            "cases": retrieval_cases,
            "metric_decision_values": {
                "recall_at_8": {"numerator": recall[0], "denominator": recall[1]},
                "mrr": {"numerator": mrr[0], "denominator": mrr[1]},
            },
        },
        "guardrails": deepcopy(REQUIRED_GUARDRAILS),
        "category_breakdown": {
            "categories": categories,
            "aggregate": {
                "recall_at_8": category_metric(recall[0] / recall[1], 1, len(case_ids)),
                "mrr": category_metric(mrr[0] / mrr[1], 1, len(case_ids)),
                "structural_validity": guard_metric(len(case_ids)),
                "citation_correctness": guard_metric(len(case_ids)),
                "refusal_correctness": guard_metric(len(case_ids)),
                "semantic_citation_correctness": guard_metric(len(case_ids)),
            },
        },
        "latency_tradeoffs": {
            "retrieval": {"count": len(case_ids), "observed_per_case": True},
            "end_to_end": {"count": len(case_ids), "observed_per_case": True},
        },
        "remaining_regressions": [],
    }


def test_closed_guardrails_require_exact_schema_keys_and_true_booleans() -> None:
    valid = validate_guardrails(REQUIRED_GUARDRAILS)
    assert valid == REQUIRED_GUARDRAILS

    variants = [
        None,
        {},
        {"structural_validity": True, "citation_correctness": True},
        {**REQUIRED_GUARDRAILS, "unknown": True},
        {**REQUIRED_GUARDRAILS, "structural_validity": 1},
        {**REQUIRED_GUARDRAILS, "citation_correctness": False},
    ]
    for variant in variants:
        with pytest.raises(ComparisonError, match="GUARDRAIL_FAILURE"):
            validate_guardrails(variant)

    observed_failure = {**REQUIRED_GUARDRAILS, "citation_correctness": False}
    assert validate_guardrail_shape(observed_failure) == observed_failure


def test_denominator_reconciliation_keeps_applicable_observation_failure_auditable() -> None:
    class Relevance:
        def __init__(self, applicable: bool):
            self.applicable = applicable

    class Case:
        def __init__(self, case_id: str, category: str, applicable: bool):
            self.id = case_id
            self.category = category
            self.retrieval_relevance = Relevance(applicable)

    report = _modern_report("retrieval-m3-vector-v2", case_ids=("ok", "failed", "refusal"))
    report["observations"] = [
        {"case_id": "ok", "status": "observed", "recall_at_8": 1.0, "mrr": 1.0},
        {
            "case_id": "failed",
            "status": "observation_failure",
            "failure_code": "EVALUATION_OBSERVATION_FAILURE",
        },
        {"case_id": "refusal", "status": "observed"},
    ]
    breakdown = build_category_breakdown(
        (
            Case("ok", "lexical_exact_match", True),
            Case("failed", "lexical_exact_match", True),
            Case("refusal", "insufficient_evidence_refusal", False),
        ),
        report,
        metrics=("recall_at_8", "mrr"),
    )

    lexical = breakdown["categories"]["lexical_exact_match"]
    for metric in ("recall_at_8", "mrr"):
        assert lexical[metric] == {
            "applicable_count": 2,
            "inapplicable_count": 0,
            "observation_failure_count": 1,
            "numerator": 1.0,
            "denominator": 1,
            "value": 1.0,
        }
    aggregate = breakdown["aggregate"]["recall_at_8"]
    assert aggregate["applicable_count"] + aggregate["inapplicable_count"] == 3
    assert aggregate["observation_failure_count"] == 1
    assert aggregate["denominator"] == 1


def test_category_breakdown_reads_successful_mrr_from_retrieval_case_projection() -> None:
    class Relevance:
        applicable = True

    class Case:
        id = "case-a"
        category = "lexical_exact_match"
        retrieval_relevance = Relevance()

    report = {
        "observations": [{"case_id": "case-a", "status": "observed"}],
        "retrieval": {
            "cases": [
                {
                    "id": "case-a",
                    "recall_at_8": 1.0,
                    "reciprocal_rank": 0.5,
                }
            ]
        },
    }

    result = build_category_breakdown((Case(),), report)

    assert result["aggregate"]["mrr"] == {
        "applicable_count": 1,
        "inapplicable_count": 0,
        "observation_failure_count": 0,
        "numerator": 0.5,
        "denominator": 1,
        "value": 0.5,
    }


def test_category_breakdown_reconciles_against_per_case_metric_projections() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    hybrid["category_breakdown"]["categories"]["lexical_exact_match"]["mrr"].update(
        {"numerator": 0.0, "value": 0.0}
    )
    with pytest.raises(ComparisonError, match="CATEGORY_BREAKDOWN_RECONCILIATION_FAILED"):
        compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))


def test_observed_latency_is_required_for_qualifying_selection() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    del hybrid["observations"][0]["retrieval_latency_ms"]
    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )
    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "OBSERVATION_LATENCY_INVALID"


def test_category_case_ids_require_nonempty_strings() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    hybrid["category_breakdown"]["categories"]["lexical_exact_match"]["case_ids"] = [
        "case-a",
        1,
    ]
    with pytest.raises(ComparisonError, match="CATEGORY_BREAKDOWN_INVALID"):
        compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))


def test_paired_provenance_rejects_mutation_outside_declared_configuration_fields() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    assert compare_paired_reports(
        vector, hybrid, expected_case_ids=("case-a", "case-b")
    )["provenance_match"] is True

    tampered = deepcopy(hybrid)
    tampered["provenance"]["scorer_model"] = "other-judge"
    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(vector, tampered, expected_case_ids=("case-a", "case-b"))

    missing = deepcopy(hybrid)
    del missing["provenance"]["evaluation_commit"]
    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(vector, missing, expected_case_ids=("case-a", "case-b"))


def test_paired_provenance_rejects_matching_malformed_digest_values() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    vector["provenance"]["corpus_digest"] = "bad-digest"
    hybrid["provenance"]["corpus_digest"] = "bad-digest"

    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))


def test_selection_rejects_observation_source_binding_mutation() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    hybrid["observations"][0]["source_bindings"][0]["production_document_version_id"] = (
        "tampered-version"
    )

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )

    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "PROVENANCE_MISMATCH"


def test_paired_provenance_rejects_duplicate_source_bindings() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    for report in (vector, hybrid):
        for observation in report["observations"]:
            observation["source_bindings"].append(
                deepcopy(observation["source_bindings"][0])
            )

    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))


def test_selection_reconciles_top_level_guardrails_with_observations() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    hybrid["observations"][0]["citation_correctness"] = False

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )

    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "GUARDRAIL_FAILURE"


def test_exact_rational_selection_uses_unrounded_metric_contract_values() -> None:
    vector = _modern_report("retrieval-m3-vector-v2", recall=(1, 3), mrr=(1, 2))
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 3), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )
    assert result["status"] == "SELECTED"
    assert result["metric_decision_deltas"]["recall_at_8"] == "0/1"
    assert result["metric_decision_deltas"]["mrr"] == "1/6"
    assert result["claim_rule_digest"].startswith("sha256:")

    vector["retrieval"]["recall_at_8"] = 0.999999
    hybrid["retrieval"]["recall_at_8"] = 0.000001
    rounded_mutation = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )
    assert rounded_mutation["status"] == "NO_CLAIM"
    assert rounded_mutation["reason"] == "METRIC_DECISION_RECONCILIATION_FAILED"


@pytest.mark.parametrize(
    "mutated_guardrails",
    [
        None,
        {},
        {"structural_validity": True, "citation_correctness": True},
        {**REQUIRED_GUARDRAILS, "unknown": True},
        {**REQUIRED_GUARDRAILS, "structural_validity": "true"},
        {**REQUIRED_GUARDRAILS, "refusal_correctness": False},
    ],
)
def test_selection_maps_every_malformed_guardrail_to_policy_no_claim(mutated_guardrails) -> None:
    vector = _modern_report("retrieval-m3-vector-v2", recall=(1, 2), mrr=(1, 2))
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    hybrid["guardrails"] = mutated_guardrails
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )
    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "GUARDRAIL_FAILURE"
    assert result["selected_improvement"] is None


def test_observation_failure_and_non_qualifying_pair_are_distinct_no_claim_paths() -> None:
    vector = _modern_report("retrieval-m3-vector-v2", recall=(1, 2), mrr=(1, 2))
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(1, 2))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    authority = test_claim_rule_authority_fixture()

    no_delta = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=authority,
        production=False,
    )
    assert no_delta["status"] == "NO_CLAIM"
    assert no_delta["reason"] == "NO_QUALIFYING_DELTA"

    hybrid["observations"][0]["status"] = "observation_failure"
    failed = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=authority,
        production=False,
    )
    assert failed["status"] == "NO_CLAIM"
    assert failed["reason"] == "OBSERVATION_FAILURE"


@pytest.mark.parametrize(
    "placeholder",
    ["YOUR_IDENTITY", "YOUR_REAL_IDENTITY", "<human identity>", "", "  ", "TODO", "TBD", "UNKNOWN"],
)
def test_placeholder_human_identity_is_authority_failure(placeholder: str) -> None:
    authority = test_claim_rule_authority_fixture()
    tampered = replace(authority, reviewer_id=placeholder, approved_by=placeholder)
    result = canonical_authority_validation(tampered, production=False)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "HUMAN_IDENTITY_PLACEHOLDER"


def test_policy_projection_mutation_fails_authority_validation() -> None:
    authority = test_claim_rule_authority_fixture()
    projection = deepcopy(authority.projection)
    projection["recall_k"] = 7
    tampered = replace(authority, projection=projection)
    result = canonical_authority_validation(tampered, production=False)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "POLICY_PROJECTION_INVALID"


def test_approval_payload_mutation_fails_attestation_digest_validation() -> None:
    authority = test_claim_rule_authority_fixture()
    payload = deepcopy(authority.approval_payload)
    payload["approved_at"] = "2026-08-17T03:34:44Z"
    tampered = replace(authority, approval_payload=payload)
    result = canonical_authority_validation(tampered, production=False)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "ATTESTATION_PAYLOAD_DIGEST_MISMATCH"


def test_taxonomy_stage_preconditions_and_optional_categories_are_closed() -> None:
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding(
            "fixture-lexical-branch-miss",
            evidence=["evidence"],
            stage="branch",
            stage_evidence={},
        )
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding("fixture-fusion-union-ranked-low", evidence=["evidence"])
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding(
            "fixture-fusion-union-ranked-low",
            evidence=["evidence"],
            stage="fusion",
            stage_evidence={"eligible_branch_union": True},
        )
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding(
            "fixture-fusion-union-ranked-low",
            evidence=["evidence"],
            stage="fusion",
            stage_evidence={
                "branches_completed": {"lexical": True, "semantic": False},
                "eligible_branch_union": True,
                "post_fusion_rank_incorrect": True,
            },
        )
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding(
            "fixture-evidence-selection-excluded",
            evidence=["evidence"],
            stage="evidence_selection",
            stage_evidence={"post_fusion_excluded": True},
        )
    finding = classify_finding(
        "fixture-fusion-union-ranked-low",
        evidence=["evidence"],
        stage="fusion",
        stage_evidence={
            "branches_completed": {"lexical": True, "semantic": True},
            "eligible_branch_union": True,
            "post_fusion_rank_incorrect": True,
            "contributing_stage_evidence": {
                "branches_completed": {"lexical": True, "semantic": True},
                "LEXICAL_MISS": {
                    "gold_evidence_present": True,
                    "eligible_gold_evidence": False,
                    "miss_confirmed": True,
                }
            },
        },
        contributing_enums=("LEXICAL_MISS",),
    )
    assert finding["primary_enum"] == "FUSION_RANKING_ERROR"
    optional_only = classify_finding(
        "fixture-answer-refused",
        evidence=["evidence"],
        stage_evidence={
            "contributing_stage_evidence": {
                "CORPUS_OR_CONFIGURATION_MISMATCH": {"stage_proven": True},
            }
        },
        contributing_enums=("CORPUS_OR_CONFIGURATION_MISMATCH",),
    )
    assert optional_only["contributing_enums"] == ["CORPUS_OR_CONFIGURATION_MISMATCH"]
    with pytest.raises(ComparisonError, match="CATEGORY_INVALID"):
        classify_finding(
            "fixture-fusion-union-ranked-low",
            evidence=["evidence"],
            stage="fusion",
            stage_evidence={
                "branches_completed": {"lexical": True, "semantic": True},
                "eligible_branch_union": True,
                "post_fusion_rank_incorrect": True,
            },
            contributing_enums=("RENAMED_ENUM",),
        )


def test_authority_validation_failure_is_not_policy_no_claim_and_caller_override_is_rejected(
) -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        claim_rule={"minimum_delta": -1.0},
    )
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "CALLER_POLICY_OVERRIDE"
    assert result.get("selected_improvement") is None
    assert result.get("claim_rule_version") is None


def test_identity_syntax_fixture_is_not_production_authorization() -> None:
    authority = test_claim_rule_authority_fixture()
    assert isinstance(authority, ClaimRuleAuthority)
    assert validate_human_identity("NhiBuaa") == "NhiBuaa"
    assert (
        canonical_authority_validation(authority, production=False)["status"]
        == "APPROVED_EFFECTIVE"
    )
    assert (
        canonical_authority_validation(authority, production=True)["reason"]
        == "CALLER_AUTHORITY_OVERRIDE"
    )

    alternate = replace(authority, attestation_blob="0" * 40)
    result = canonical_authority_validation(alternate, production=True)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "CALLER_AUTHORITY_OVERRIDE"

    other_human = replace(authority, reviewer_id="AnotherHuman", approved_by="AnotherHuman")
    other_result = canonical_authority_validation(other_human, production=True)
    assert other_result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert other_result["reason"] == "CALLER_AUTHORITY_OVERRIDE"


def test_canonical_production_entry_point_requires_git_bound_authority(tmp_path: Path) -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))

    result = select_production_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        repository_root=tmp_path,
    )

    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] != "NO_QUALIFYING_DELTA"
    assert result.get("selected_improvement") is None


def test_selection_reconciles_metric_projection_and_latency_disclosure() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    authority = test_claim_rule_authority_fixture()

    hybrid["retrieval"]["metric_decision_values"]["mrr"] = {
        "numerator": 1,
        "denominator": 2,
    }
    fabricated = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=authority,
        production=False,
    )
    assert fabricated["status"] == "NO_CLAIM"
    assert fabricated["reason"] == "METRIC_DECISION_RECONCILIATION_FAILED"

    hybrid["retrieval"]["metric_decision_values"]["mrr"] = {
        "numerator": 2,
        "denominator": 3,
    }
    hybrid["latency_tradeoffs"] = {"retrieval": {}, "end_to_end": {}}
    missing_latency = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=authority,
        production=False,
    )
    assert missing_latency["status"] == "NO_CLAIM"
    assert missing_latency["reason"] == "LATENCY_DISCLOSURE_INVALID"


def test_selection_rejects_display_metric_mutation_without_epsilon() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    hybrid["retrieval"]["mrr"] += 5e-13

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )

    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "METRIC_DECISION_RECONCILIATION_FAILED"


@pytest.mark.parametrize("field", ["metric_contract", "recall_k"])
def test_selection_rejects_metric_contract_mutation_even_with_valid_pair(field: str) -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    hybrid["retrieval"][field] = "mutated" if field == "metric_contract" else 7

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )

    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "METRIC_CONTRACT_MISMATCH"


def test_selection_rejects_incomplete_fabricated_pair_contract() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    del pair["pair_records"]

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )

    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "PAIR_CONTRACT_INVALID"


def test_latency_disclosure_count_must_match_successful_observations() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 2), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid, expected_case_ids=("case-a", "case-b"))
    hybrid["latency_tradeoffs"]["retrieval"]["count"] = 1

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )

    assert result["status"] == "NO_CLAIM"
    assert result["reason"] == "LATENCY_DISCLOSURE_INVALID"


def test_sealed_archive_accepts_issue_56_member_prefixes_and_exact_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seal_id = "test-seal"
    source_commit = "a" * 40
    monkeypatch.setattr(authority_module, "SEAL_ID", seal_id)
    monkeypatch.setattr(authority_module, "SOURCE_COMMIT", source_commit)
    monkeypatch.setattr(
        authority_module,
        "ATTESTATION_PATH",
        ".agents/review/m3-improvement-claim-v1-approval.json",
    )
    members = {
        "attestation/m3-improvement-claim-v1-approval.json": b"approval-payload",
        "authority-binding.json": b"authority-binding",
        "candidate/git-archive.tar": b"git-archive",
    }
    items = [
        {
            "reference": reference,
            "byte_count": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for reference, content in sorted(members.items())
    ]
    manifest = {
        "schema_version": 1,
        "seal_id": seal_id,
        "candidate_sha": source_commit,
        "sealed_at": "2026-08-17T00:00:00Z",
        "items": items,
    }
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    )
    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w") as archive:
        payloads = {"SEALED-MANIFEST.json": manifest_bytes, **members}
        for name, content in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o444
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    archive_path = tmp_path / "sealed.tar"
    archive_path.write_bytes(archive_bytes.getvalue())

    assert authority_module._read_and_validate_sealed_archive(archive_path) == manifest_bytes
