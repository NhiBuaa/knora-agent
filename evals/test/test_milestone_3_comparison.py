import pytest
from evals.runners.milestone_3_comparison import (
    TAXONOMY_FIXTURE_MAP,
    ComparisonError,
    build_category_breakdown,
    build_publication_manifest,
    classify_finding,
    compare_paired_reports,
    select_improvement,
    test_claim_rule_authority_fixture,
    validate_publication_manifest,
)


def _report(configuration: str, *, case_ids=("case-a", "case-b"), corpus="corpus-1"):
    retrieval_cases = [
        {
            "id": case_id,
            "included": True,
            "recall_at_8": 0.5,
            "reciprocal_rank": 0.5,
            "metric_decision_values": {
                "recall_at_8": {"numerator": 1, "denominator": 2},
                "mrr": {"numerator": 1, "denominator": 2},
            },
        }
        for case_id in case_ids
    ]
    def metric(case_count):
        return {
            "applicable_count": case_count,
            "inapplicable_count": 0,
            "observation_failure_count": 0,
            "numerator": case_count * 0.5,
            "denominator": case_count,
            "value": 0.5 if case_count else None,
        }
    def guard_metric(case_count):
        return {
            "applicable_count": case_count,
            "inapplicable_count": 0,
            "observation_failure_count": 0,
            "numerator": case_count,
            "denominator": case_count,
            "value": 1.0 if case_count else None,
        }
    categories = {
        "lexical_exact_match": {
            "case_ids": list(case_ids),
            "case_count": len(case_ids),
            "recall_at_8": metric(len(case_ids)),
            "mrr": metric(len(case_ids)),
        },
        "semantic_paraphrase": {
            "case_ids": [],
            "case_count": 0,
            "recall_at_8": metric(0),
            "mrr": metric(0),
        },
        "multi_source": {
            "case_ids": [],
            "case_count": 0,
            "recall_at_8": metric(0),
            "mrr": metric(0),
        },
        "insufficient_evidence_refusal": {
            "case_ids": [],
            "case_count": 0,
            "recall_at_8": metric(0),
            "mrr": metric(0),
        },
    }
    for category_projection in categories.values():
        for metric_name in (
            "structural_validity",
            "citation_correctness",
            "refusal_correctness",
            "semantic_citation_correctness",
        ):
            category_projection[metric_name] = guard_metric(category_projection["case_count"])
    aggregate = {
        "recall_at_8": metric(len(case_ids)),
        "mrr": metric(len(case_ids)),
        "structural_validity": guard_metric(len(case_ids)),
        "citation_correctness": guard_metric(len(case_ids)),
        "refusal_correctness": guard_metric(len(case_ids)),
        "semantic_citation_correctness": guard_metric(len(case_ids)),
    }
    return {
        "schema_version": 1,
        "binding_v3": {
            "schema_version": 3,
            "dataset_manifest_identity": "dataset-1",
            "corpus_manifest_identity": corpus,
            "chunk_set_provenance_id": "chunk-set-1",
            "workspace_id": "workspace-1",
            "retrieval_configuration_id": configuration,
            "source_bindings": [
                {
                    "source_key": "support/a",
                    "production_document_version_id": "version-1",
                    "production_chunk_set_id": "chunk-set-1",
                }
            ],
            "environment_binding_digest": (
                "sha256:b2b12549d0602ea6f86613f482b47425c6c3d686a66d8cdb13a18194f6ee7f65"
            ),
        },
        "provenance": {
            "dataset_version": "dataset-1",
            "dataset_digest": "sha256:" + "a" * 64,
            "corpus_id": corpus,
            "corpus_digest": "sha256:" + "b" * 64,
            "chunk_set_id": "chunk-set-1",
            "chunk_set_digest": "sha256:" + "c" * 64,
            "workspace": "workspace-1",
            "chunking_configuration": "chunking-1",
            "embedding_configuration": "embedding-1",
            "generation_configuration": "generation-1",
            "scorer_configuration": "scorer-1",
            "scorer_model": "scorer-model-1",
            "scorer_prompt": "prompt-1",
            "scorer_policy": "policy-1",
            "scorer_stochasticity": "deterministic",
            "metric_contract": "m3-retrieval-metrics-v1",
            "source_commit": "1" * 40,
            "evaluation_commit": "2" * 40,
            "report_artifact_schema_version": 1,
            "retrieval_configuration_id": configuration,
            "strategy": "vector-only" if "vector" in configuration else "hybrid",
            "fts_candidate_k": None if "vector" in configuration else 8,
            "fusion_policy_id": None if "vector" in configuration else "rrf-v2",
            "fusion_policy_version": None if "vector" in configuration else "rrf-v2",
            "lexical_policy_id": None if "vector" in configuration else "fts-m3-or-v2",
        },
        "observations": [
            {
                "case_id": case_id,
                "status": "observed",
                "retrieval_latency_ms": 1.0,
                "end_to_end_latency_ms": 2.0,
                "retrieval_configuration_id": configuration,
                "chunk_set_provenance_id": "chunk-set-1",
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
                        "production_chunk_set_id": "chunk-set-1",
                    }
                ],
                "structural_validity": True,
                "citation_correctness": True,
                "refusal_correctness": True,
                "semantic_citation_correctness": True,
            }
            for case_id in case_ids
        ],
        "retrieval": {
            "metric_contract": "m3-retrieval-metrics-v1",
            "recall_k": 8,
            "recall_at_8": 0.5,
            "mrr": 0.5,
            "denominator": len(case_ids),
            "cases": retrieval_cases,
            "metric_decision_values": {
                "recall_at_8": {"numerator": 1, "denominator": 2},
                "mrr": {"numerator": 1, "denominator": 2},
            },
        },
        "guardrails": {
            "structural_validity": True,
            "citation_correctness": True,
            "refusal_correctness": True,
        },
        "observation_failure_count": 0,
        "category_breakdown": {
            "categories": categories,
            "aggregate": aggregate,
        },
        "latency_tradeoffs": {
            "retrieval": {"count": len(case_ids), "observed_per_case": True},
            "end_to_end": {"count": len(case_ids), "observed_per_case": True},
        },
        "remaining_regressions": [],
    }


def test_compare_paired_reports_requires_exact_same_cases_and_only_config_differs():
    result = compare_paired_reports(
        _report("retrieval-m3-vector-v2"),
        _report("retrieval-m3-rrf-v2"),
        expected_case_ids=("case-a", "case-b"),
    )

    assert result["case_ids"] == ["case-a", "case-b"]
    assert result["pair_cardinality"] == 4
    assert result["provenance_match"] is True

    with pytest.raises(ComparisonError, match="EXPECTED_CASE_SET_REQUIRED"):
        compare_paired_reports(_report("retrieval-m3-vector-v2"), _report("retrieval-m3-rrf-v2"))

    with pytest.raises(ComparisonError, match="CASE_SET_MISMATCH"):
        compare_paired_reports(
            _report("retrieval-m3-vector-v2", case_ids=("case-a",)),
            _report("retrieval-m3-rrf-v2"),
            expected_case_ids=("case-a", "case-b"),
        )

    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(
            _report("retrieval-m3-vector-v2"),
            _report("retrieval-m3-rrf-v2", corpus="different"),
            expected_case_ids=("case-a", "case-b"),
        )


def test_findings_use_closed_taxonomy_and_correct_refusal_is_not_a_failure():
    stages = {
        "fixture-lexical-branch-miss": (
            "branch",
            {
                "branch": "lexical",
                "gold_evidence_present": True,
                "eligible_gold_evidence": False,
                "miss_confirmed": True,
            },
        ),
        "fixture-semantic-branch-miss": (
            "branch",
            {
                "branch": "semantic",
                "gold_evidence_present": True,
                "eligible_gold_evidence": False,
                "miss_confirmed": True,
            },
        ),
        "fixture-fusion-union-ranked-low": (
            "fusion",
            {
                "branches_completed": {"lexical": True, "semantic": True},
                "eligible_branch_union": True,
                "post_fusion_rank_incorrect": True,
            },
        ),
        "fixture-evidence-selection-excluded": (
            "evidence_selection",
            {
                "fused_ordering_available": True,
                "fused_ordering_version": "rrf-v2",
                "post_fusion_excluded": True,
            },
        ),
    }
    for fixture_id, expected in TAXONOMY_FIXTURE_MAP.items():
        stage, stage_evidence = stages.get(fixture_id, (None, None))
        finding = classify_finding(
            fixture_id,
            evidence=["fixture evidence"],
            stage=stage,
            stage_evidence=stage_evidence,
        )
        assert finding["primary_enum"] == expected
        assert finding["is_failure"] is (expected != "INSUFFICIENT_EVIDENCE_CORRECT")
        assert finding["evidence"] == ["fixture evidence"]


def test_taxonomy_stage_evidence_requires_exact_boolean_values() -> None:
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding(
            "fixture-fusion-union-ranked-low",
            evidence=["fixture evidence"],
            stage="fusion",
            stage_evidence={
                "branches_completed": {"lexical": 1, "semantic": True},
                "eligible_branch_union": True,
                "post_fusion_rank_incorrect": True,
            },
        )


def test_no_claim_is_explicit_when_pair_has_no_qualifying_delta_or_guardrail_fails():
    vector = _report("retrieval-m3-vector-v2")
    hybrid = _report("retrieval-m3-rrf-v2")
    hybrid["retrieval"]["recall_at_8"] = 0.5
    hybrid["retrieval"]["mrr"] = 0.5
    hybrid["guardrails"] = {"citation_correctness": False}
    pair = compare_paired_reports(
        vector, hybrid, expected_case_ids=("case-a", "case-b")
    )

    result = select_improvement(
        pair,
        vector_report=vector,
        hybrid_report=hybrid,
        authority=test_claim_rule_authority_fixture(),
        production=False,
    )

    assert result["status"] == "NO_CLAIM"
    assert result["selected_improvement"] is None
    assert result["reason"]


def test_category_breakdown_separates_membership_applicability_and_observation_failures():
    class Relevance:
        def __init__(self, applicable):
            self.applicable = applicable

    class Case:
        def __init__(self, case_id, category, applicable):
            self.id = case_id
            self.category = category
            self.retrieval_relevance = Relevance(applicable)

    report = _report("retrieval-m3-vector-v2", case_ids=("a", "b", "c"))
    report["observations"] = [
        {"case_id": "a", "status": "observed", "recall_at_8": 1.0},
        {"case_id": "b", "status": "failure", "failure_code": "EVALUATION_OBSERVATION_FAILURE"},
        {"case_id": "c", "status": "observed", "recall_at_8": 0.0},
    ]
    breakdown = build_category_breakdown(
        (
            Case("a", "lexical_exact_match", True),
            Case("b", "lexical_exact_match", True),
            Case("c", "insufficient_evidence_refusal", False),
        ),
        report,
        metrics=("recall_at_8",),
    )

    lexical = breakdown["categories"]["lexical_exact_match"]["recall_at_8"]
    assert lexical["applicable_count"] == 2
    assert lexical["observation_failure_count"] == 1
    assert lexical["numerator"] == 1.0
    assert lexical["denominator"] == 1


def test_publication_manifest_id_is_content_based_and_excludes_self_reference():
    manifest = build_publication_manifest(
        {"reports/vector.json": b"vector", "reports/hybrid.json": b"hybrid"},
        schema_versions={"reports/vector.json": 1, "reports/hybrid.json": 1},
    )
    assert manifest["artifact_publication_id"]
    assert "artifact_publication_commit" not in manifest
    assert validate_publication_manifest(manifest) is True
