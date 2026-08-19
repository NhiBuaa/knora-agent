from pathlib import Path

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
        / ".agents/review/m3-improvement-claim-v1-approval-closure-v2.json",
    )

    assert result["status"] == "APPROVED_EFFECTIVE"
    authority = result["authority"]
    assert authority.external_reviewer_id == "codex-agent:/root/m3_remediation_external_review_v3"
    assert authority.review_subject_commit == "688732d70ca5e3604e3a4d44509be8850add68fe"
    assert authority.review_subject_blob == "9ba863a4cc2e20e805345f47272bc903ad612315"
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
