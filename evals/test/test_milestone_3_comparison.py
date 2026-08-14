import pytest
from evals.runners.milestone_3_comparison import (
    TAXONOMY_FIXTURE_MAP,
    ComparisonError,
    build_category_breakdown,
    build_publication_manifest,
    classify_finding,
    compare_paired_reports,
    select_improvement,
    validate_publication_manifest,
)


def _report(configuration: str, *, case_ids=("case-a", "case-b"), corpus="corpus-1"):
    return {
        "schema_version": 1,
        "provenance": {
            "dataset_manifest_identity": "dataset-1",
            "corpus_manifest_identity": corpus,
            "chunk_set_provenance_id": "chunk-set-1",
            "workspace_id": "workspace-1",
            "retrieval_configuration_id": configuration,
            "embedding_configuration_id": "embedding-1",
            "generation_configuration_id": "generation-1",
            "scorer_configuration_id": "scorer-1",
        },
        "observations": [{"case_id": case_id, "status": "observed"} for case_id in case_ids],
        "retrieval": {"recall_at_8": 0.5, "mrr": 0.5},
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

    with pytest.raises(ComparisonError, match="CASE_SET_MISMATCH"):
        compare_paired_reports(
            _report("retrieval-m3-vector-v2", case_ids=("case-a",)),
            _report("retrieval-m3-rrf-v2"),
        )

    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(
            _report("retrieval-m3-vector-v2"),
            _report("retrieval-m3-rrf-v2", corpus="different"),
        )


def test_findings_use_closed_taxonomy_and_correct_refusal_is_not_a_failure():
    for fixture_id, expected in TAXONOMY_FIXTURE_MAP.items():
        finding = classify_finding(fixture_id, evidence=["fixture evidence"])
        assert finding["primary_enum"] == expected
        assert finding["is_failure"] is (expected != "INSUFFICIENT_EVIDENCE_CORRECT")
        assert finding["evidence"] == ["fixture evidence"]


def test_no_claim_is_explicit_when_pair_has_no_qualifying_delta_or_guardrail_fails():
    vector = _report("retrieval-m3-vector-v2")
    hybrid = _report("retrieval-m3-rrf-v2")
    hybrid["retrieval"] = {"recall_at_8": 0.5, "mrr": 0.5}
    hybrid["guardrails"] = {"citation_correctness": False}
    pair = compare_paired_reports(vector, hybrid)

    result = select_improvement(pair, vector_report=vector, hybrid_report=hybrid)

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
    assert lexical["applicable_count"] == 1
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
