import json
from pathlib import Path

import evals.runners.m3_claim_authority as authority_module
import pytest
from evals.runners.m3_claim_authority import (
    canonical_authority_validation,
    canonical_policy_projection,
)


def test_production_authority_binds_the_independent_m3_review_chain() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    result = canonical_authority_validation(
        repository_root=repository_root,
        sealed_archive_path=repository_root
        / ".agents/review/m3-improvement-claim-v1-approval-sealed-v2.tar",
        closure_path=repository_root
        / ".agents/review/m3-remediation-v4-review-closure-final.json",
    )

    assert result["status"] == "APPROVED_EFFECTIVE"
    authority = result["authority"]
    assert authority.external_reviewer_id == "codex-agent:/root/m3_final_package_review_v4"
    closure = json.loads(
        (repository_root / ".agents/review/m3-remediation-v4-review-closure-final.json")
        .read_text(encoding="utf-8")
    )
    assert authority.review_subject_commit == closure["subject_commit"]
    assert authority.review_subject_blob == closure["subject_blob"]
    assert authority.review_scope_digest.startswith("sha256:")
    assert authority.review_response_digest.startswith("sha256:")
    assert authority.external_reviewer_id != authority.approved_by


def test_policy_projection_is_loaded_from_the_committed_json_document() -> None:
    projection = canonical_policy_projection()
    assert projection["authority_identifier"] == "m3-improvement-claim-v1"
    assert projection["provenance"]["allowed_differences"] == [
        "retrieval_configuration_id",
        "strategy",
        "fusion_policy_id",
        "fusion_policy_version",
        "lexical_policy_id",
        "fts_candidate_k",
    ]


def test_approved_review_response_requires_evidence_projection() -> None:
    response = {
        "schema_version": 2,
        "status": "completed",
        "verdict": "APPROVE",
        "critical_count": 0,
        "major_count": 0,
        "minor_count": 0,
        "finding": None,
    }

    with pytest.raises(ValueError, match="REMEDIATION_RESPONSE_SCHEMA_INVALID"):
        authority_module._validate_review_response_contract(response)


def test_approved_review_response_requires_exact_typed_scope_coverage() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    scope = json.loads(
        (repository_root / ".agents/review/m3-remediation-v4-scope-projection-final.json")
        .read_text(encoding="utf-8")
    )
    subject_paths = tuple(scope["subject_paths"])
    requirements = tuple(scope["requirements"])
    response = {
        "schema_version": 3,
        "status": "completed",
        "verdict": "APPROVE",
        "critical_count": 0,
        "major_count": 0,
        "minor_count": 0,
        "finding": None,
        "findings": [],
        "review_basis": "exact subject and scope review",
        "reviewed_paths": list(subject_paths),
        "requirement_coverage": [
            {
                "requirement": requirement,
                "result": "PASS",
                "evidence_paths": [subject_paths[0]],
            }
            for requirement in requirements
        ],
    }

    authority_module._validate_review_response_contract(
        response,
        required_requirements=requirements,
        subject_paths=subject_paths,
    )

    response["requirement_coverage"].pop()
    with pytest.raises(ValueError, match="REMEDIATION_RESPONSE_REQUIREMENT_COVERAGE_INVALID"):
        authority_module._validate_review_response_contract(
            response,
            required_requirements=requirements,
            subject_paths=subject_paths,
        )
