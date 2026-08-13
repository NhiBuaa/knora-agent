from pathlib import Path

from evals.calibration.validate_m3_retrieval_v1 import validate

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
