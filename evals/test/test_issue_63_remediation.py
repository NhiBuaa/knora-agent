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
    provenance = {
        "dataset_version": "m3-dataset-v1",
        "dataset_digest": "sha256:dataset",
        "corpus_id": "m3-corpus-v1",
        "corpus_digest": "sha256:corpus",
        "chunk_set_id": "chunk-set-m3-v1",
        "chunk_set_digest": "sha256:chunk-set",
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
        "recall_k": 8,
        "source_commit": "1" * 40,
        "evaluation_commit": "2" * 40,
        "report_artifact_schema_version": 1,
        "retrieval_configuration_id": configuration,
        "strategy": "vector" if "vector" in configuration else "hybrid",
        "fusion_policy_id": "none" if "vector" in configuration else "rrf-v2",
        "fusion_policy_version": "none" if "vector" in configuration else "2",
        "lexical_policy_id": "none" if "vector" in configuration else "fts-v2",
        "fts_candidate_k": 0 if "vector" in configuration else 8,
    }
    return {
        "schema_version": 1,
        "provenance": provenance,
        "observations": [{"case_id": case_id, "status": "observed"} for case_id in case_ids],
        "retrieval": {
            "metric_contract": "m3-retrieval-metrics-v1",
            "recall_k": 8,
            "recall_at_8": recall[0] / recall[1],
            "mrr": mrr[0] / mrr[1],
            "metric_decision_values": {
                "recall_at_8": {"numerator": recall[0], "denominator": recall[1]},
                "mrr": {"numerator": mrr[0], "denominator": mrr[1]},
            },
        },
        "guardrails": deepcopy(REQUIRED_GUARDRAILS),
        "latency_tradeoffs": {
            "retrieval": {"vector": 10, "hybrid": 12},
            "end_to_end": {"vector": 20, "hybrid": 22},
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


def test_paired_provenance_rejects_mutation_outside_declared_configuration_fields() -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    assert compare_paired_reports(vector, hybrid)["provenance_match"] is True

    tampered = deepcopy(hybrid)
    tampered["provenance"]["scorer_model"] = "other-judge"
    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(vector, tampered)

    missing = deepcopy(hybrid)
    del missing["provenance"]["evaluation_commit"]
    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        compare_paired_reports(vector, missing)


def test_exact_rational_selection_uses_unrounded_metric_contract_values() -> None:
    vector = _modern_report("retrieval-m3-vector-v2", recall=(1, 3), mrr=(1, 2))
    hybrid = _modern_report("retrieval-m3-rrf-v2", recall=(1, 3), mrr=(2, 3))
    pair = compare_paired_reports(vector, hybrid)
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
    assert rounded_mutation["status"] == "SELECTED"


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
    pair = compare_paired_reports(vector, hybrid)
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
    pair = compare_paired_reports(vector, hybrid)
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
    result = canonical_authority_validation(tampered, production=True)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "HUMAN_IDENTITY_PLACEHOLDER"


def test_policy_projection_mutation_fails_authority_validation() -> None:
    authority = test_claim_rule_authority_fixture()
    projection = deepcopy(authority.projection)
    projection["recall_k"] = 7
    tampered = replace(authority, projection=projection)
    result = canonical_authority_validation(tampered, production=True)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "POLICY_PROJECTION_INVALID"


def test_approval_payload_mutation_fails_attestation_digest_validation() -> None:
    authority = test_claim_rule_authority_fixture()
    payload = deepcopy(authority.approval_payload)
    payload["approved_at"] = "2026-08-17T03:34:44Z"
    tampered = replace(authority, approval_payload=payload)
    result = canonical_authority_validation(tampered, production=True)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "ATTESTATION_PAYLOAD_DIGEST_MISMATCH"


def test_taxonomy_stage_preconditions_and_optional_categories_are_closed() -> None:
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding("fixture-fusion-union-ranked-low", evidence=["evidence"])
    with pytest.raises(ComparisonError, match="STAGE_PRECONDITION_INVALID"):
        classify_finding(
            "fixture-fusion-union-ranked-low",
            evidence=["evidence"],
            stage="fusion",
            stage_evidence={"eligible_branch_union": True},
        )
    finding = classify_finding(
        "fixture-fusion-union-ranked-low",
        evidence=["evidence"],
        stage="fusion",
        stage_evidence={
            "eligible_branch_union": True,
            "post_fusion_rank_incorrect": True,
        },
        contributing_enums=("LEXICAL_MISS",),
    )
    assert finding["primary_enum"] == "FUSION_RANKING_ERROR"
    with pytest.raises(ComparisonError, match="CATEGORY_INVALID"):
        classify_finding(
            "fixture-fusion-union-ranked-low",
            evidence=["evidence"],
            stage="fusion",
            stage_evidence={
                "eligible_branch_union": True,
                "post_fusion_rank_incorrect": True,
            },
            contributing_enums=("RENAMED_ENUM",),
        )


def test_authority_validation_failure_is_not_policy_no_claim_and_caller_override_is_rejected(
) -> None:
    vector = _modern_report("retrieval-m3-vector-v2")
    hybrid = _modern_report("retrieval-m3-rrf-v2")
    pair = compare_paired_reports(vector, hybrid)

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
        == "AUTHORITY_CHAIN_UNVERIFIED"
    )
    approved = replace(authority, chain_verified=True, verification_method="git-seal")
    assert (
        canonical_authority_validation(approved, production=True)["status"]
        == "APPROVED_EFFECTIVE"
    )

    alternate = replace(approved, attestation_blob="0" * 40)
    result = canonical_authority_validation(alternate, production=True)
    assert result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert result["reason"] == "ATTESTATION_IDENTITY_MISMATCH"

    other_human = replace(approved, reviewer_id="AnotherHuman", approved_by="AnotherHuman")
    other_result = canonical_authority_validation(other_human, production=True)
    assert other_result["status"] == AUTHORITY_VALIDATION_FAILURE
    assert other_result["reason"] == "APPROVAL_IDENTITY_MISMATCH"


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
