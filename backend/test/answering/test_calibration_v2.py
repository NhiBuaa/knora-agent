import pytest

from knora.answering.calibration_v2 import (
    CalibrationCaseObservation,
    CalibrationPolicy,
    CalibrationSnapshot,
    CalibrationStatus,
    select_calibrated_threshold,
)


def test_threshold_selection_uses_sealed_observed_boundaries_deterministically() -> None:
    snapshot = CalibrationSnapshot(
        artifact_id="m3-retrieval-calibration-v1",
        artifact_sha256="a" * 64,
        observed_table_sha256="b" * 64,
        cases=(
            CalibrationCaseObservation("c1", (0.9, 0.8), ("g1",), ("g1", "n1")),
            CalibrationCaseObservation("c2", (0.85, 0.7), ("g2",), ("g2", "n2")),
        ),
        hard_negative_similarities=(0.2, 0.3),
    )
    policy = CalibrationPolicy.r9()

    first = select_calibrated_threshold(snapshot, policy)
    second = select_calibrated_threshold(snapshot, policy)

    assert first == second
    assert first.status is CalibrationStatus.PASSED
    assert first.vector_min_similarity == 0.85
    assert first.artifact_sha256 == "a" * 64
    assert first.observed_table_sha256 == "b" * 64


def test_failed_usefulness_gate_never_pins_threshold() -> None:
    snapshot = CalibrationSnapshot(
        artifact_id="m3-retrieval-calibration-v1",
        artifact_sha256="a" * 64,
        observed_table_sha256="b" * 64,
        cases=(CalibrationCaseObservation("c1", (0.2,), ("g1",), ("n1",)),),
        hard_negative_similarities=(0.8,),
    )

    result = select_calibrated_threshold(snapshot, CalibrationPolicy.r9())

    assert result.status is CalibrationStatus.FAILED
    assert result.vector_min_similarity is None
    with pytest.raises(ValueError, match="calibration has not passed"):
        result.require_threshold()
