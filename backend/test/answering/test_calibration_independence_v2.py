from knora.answering.calibration_independence_v2 import (
    AuthoredCalibrationItem,
    IndependencePolicy,
    SemanticReview,
    audit_calibration_independence,
)


def test_independence_oracle_binds_lineage_copy_overlap_and_semantic_review() -> None:
    result = audit_calibration_independence(
        calibration_sha256="a" * 64,
        calibration_items=(
            AuthoredCalibrationItem("q1", "question", "How soon is reimbursement?", "author-a"),
        ),
        development_items=("What is the refund period?",),
        semantic_review=SemanticReview(
            reviewer_id="reviewer-independent",
            reviewer_was_author=False,
            rephrase_or_derivation_found=False,
            calibration_sha256="a" * 64,
        ),
        policy=IndependencePolicy.v1(),
    )

    assert result.passed is True
    assert result.calibration_sha256 == "a" * 64
    assert result.exact_copy_matches == ()
    assert result.normalized_overlap_matches == ()


def test_independence_oracle_fails_closed_on_copy_or_non_independent_review() -> None:
    result = audit_calibration_independence(
        calibration_sha256="a" * 64,
        calibration_items=(
            AuthoredCalibrationItem("q1", "question", "Refund period", "reviewer"),
        ),
        development_items=("refund period",),
        semantic_review=SemanticReview("reviewer", True, False, "a" * 64),
        policy=IndependencePolicy.v1(),
    )

    assert result.passed is False
    assert result.exact_copy_matches == (("q1", 0),)
