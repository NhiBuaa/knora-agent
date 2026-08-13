from pathlib import Path

from evals.calibration.validate_m3_retrieval_v1 import (
    validate,
    validate_with_semantic_review,
)

ROOT = Path(__file__).parents[1]


def test_frozen_calibration_inputs_pass_deterministic_pre_execution_gates() -> None:
    result = validate(
        ROOT / "calibration" / "m3_retrieval_v1",
        ROOT / "datasets" / "milestone_3.jsonl",
    )

    assert result["artifact_id"] == "m3-retrieval-calibration-v1"
    assert result["deterministic_independence"] == "PASS"
    assert result["independent_semantic_review"] == "PENDING"
    assert result["first_execution_allowed"] is False


def test_independent_attestation_opens_first_execution_gate() -> None:
    result = validate_with_semantic_review(
        ROOT / "calibration" / "m3_retrieval_v1",
        ROOT / "datasets" / "milestone_3.jsonl",
        ROOT.parent
        / ".agents/manual-tests/milestone-3/evidence"
        / "issue-56-tc-05-independent-review-attestation-v1.json",
        "0993fd91db8bb285692b17e1855459cc4e5b3d4d59e91df73d7d433ddc3b4558",
    )

    assert result["artifact_sha256"] == (
        "692eac26a4d4857bb7fd147213ca8b5691961b3b4878f7dc915bda55ef281f07"
    )
    assert result["independent_semantic_review"] == "PASS"
    assert result["first_execution_allowed"] is True
