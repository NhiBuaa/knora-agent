from dataclasses import replace

import pytest
from evals.calibration.vietnamese_qwen_v1 import (
    LabeledObservation,
    QwenCalibrationPolicy,
    calibrate_observation_document,
    calibrate_qwen_threshold,
)
from evals.datasets.vietnamese_rag_v1 import VietnameseCase, VietnameseDataset
from evals.runners.vietnamese_retrieval import CandidateObservation, RetrievalObservation


def _labeled(case_id, *, score, relevant=True, split="calibration", behavior="ANSWER"):
    case = VietnameseCase(
        case_id,
        "question",
        "source.pdf",
        1 if behavior == "ANSWER" else None,
        ("a" * 64,) if behavior == "ANSWER" else (),
        ("fact",) if behavior == "ANSWER" else (),
        behavior,
        split,
    )
    observation = RetrievalObservation(
        case_id,
        f"diagnostic-{case_id}",
        "answering_store_diagnostic",
        "profile",
        "c" * 64,
        "retrieval-qwen-diagnostic-v1",
        ("set",),
        (CandidateObservation("source.pdf", 1, ("a" if relevant else "b") * 64, score),),
        False,
        10.0,
    )
    return LabeledObservation(case, observation)


def _policy():
    return QwenCalibrationPolicy(
        profile_id="profile",
        dataset_sha256="d" * 64,
        corpus_sha256="c" * 64,
        model_digest="sha256:" + "e" * 64,
        chunk_set_ids=("set",),
    )


def test_calibration_fits_only_positives_and_seals_when_held_out_passes():
    fit = (_labeled("fit-1", score=0.9), _labeled("fit-2", score=0.8))
    held_out = (
        _labeled("guideline-chapters-01", score=0.85, split="held_out"),
        _labeled("negative", score=0.1, relevant=False, split="held_out", behavior="REFUSAL"),
    )
    result = calibrate_qwen_threshold(fit, held_out, _policy())
    assert result.status == "PASSED"
    assert result.threshold == 0.8
    assert result.artifact is not None
    assert result.artifact["held_out_negative_refusal_rate"] == 1.0


def test_seven_chapter_regression_failure_prevents_threshold_publication():
    result = calibrate_qwen_threshold(
        (_labeled("fit", score=0.8),),
        (
            _labeled("guideline-chapters-01", score=0.7, split="held_out"),
            _labeled("negative", score=0.1, relevant=False, split="held_out", behavior="REFUSAL"),
        ),
        _policy(),
    )
    assert result.status == "FAILED"
    assert result.artifact is None
    assert not result.regression_case_passed


def test_negative_false_answer_failure_prevents_threshold_publication():
    result = calibrate_qwen_threshold(
        (_labeled("fit", score=0.8),),
        (
            _labeled("guideline-chapters-01", score=0.9, split="held_out"),
            _labeled("negative", score=0.85, relevant=False, split="held_out", behavior="REFUSAL"),
        ),
        _policy(),
    )
    assert result.status == "FAILED"
    assert result.artifact is None
    assert result.held_out_negative_refusal_rate == 0


def test_rejects_profile_mismatch_and_negative_fit():
    with pytest.raises(ValueError, match="profile"):
        calibrate_qwen_threshold(
            (_labeled("fit", score=0.8),),
            (_labeled("guideline-chapters-01", score=0.9, split="held_out"),),
            replace(_policy(), profile_id="other"),
        )
    with pytest.raises(ValueError, match="fit"):
        calibrate_qwen_threshold(
            (_labeled("negative", score=0.1, behavior="REFUSAL"),),
            (_labeled("guideline-chapters-01", score=0.9, split="held_out"),),
            _policy(),
        )


def test_observation_document_requires_exact_dataset_checksum():
    dataset = VietnameseDataset(
        (
            _labeled("fit", score=0.8).case,
            _labeled("guideline-chapters-01", score=0.9, split="held_out").case,
            _labeled(
                "negative", score=0.1, relevant=False, split="held_out", behavior="REFUSAL"
            ).case,
        ),
        "v1",
        "d" * 64,
        "profile",
        "sha256:" + "e" * 64,
        "c" * 64,
        ("set",),
        "retrieval-qwen-diagnostic-v1",
    )
    observations = [
        _labeled("fit", score=0.8).observation,
        _labeled("guideline-chapters-01", score=0.9, split="held_out").observation,
        _labeled(
            "negative", score=0.1, relevant=False, split="held_out", behavior="REFUSAL"
        ).observation,
    ]
    from dataclasses import asdict

    document = {
        "threshold_applied": False,
        "candidate_k": 16,
        "report": {"dataset_sha256": "0" * 64},
        "observations": [asdict(item) for item in observations],
    }
    with pytest.raises(ValueError, match="dataset checksum"):
        calibrate_observation_document(dataset, document)
