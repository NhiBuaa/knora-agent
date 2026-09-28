import json
from dataclasses import replace
from pathlib import Path

import pytest
from evals.calibration.vietnamese_qwen_v1 import (
    LabeledObservation,
    QwenCalibrationPolicy,
    calibrate_observation_document,
    calibrate_qwen_threshold,
)
from evals.datasets.vietnamese_rag_v1 import (
    VietnameseCase,
    VietnameseDataset,
    load_vietnamese_dataset,
)
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
        held_out_negative_case_ids=("negative",),
    )


def test_calibration_fits_only_positives_without_sealing_retrieval_result():
    fit = (_labeled("fit-1", score=0.9), _labeled("fit-2", score=0.8))
    held_out = (
        _labeled("guideline-chapters-01", score=0.85, split="held_out"),
        _labeled("negative", score=0.1, relevant=False, split="held_out", behavior="REFUSAL"),
    )
    result = calibrate_qwen_threshold(fit, held_out, _policy())
    assert result.status == "RETRIEVAL_PASSED"
    assert result.threshold == 0.8
    assert result.artifact is None
    assert result.held_out_negative_refusal_rate is None
    assert result.retrieval_only_negative_candidate_presence_rate == 0.0


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


def test_high_score_answer_absent_candidate_is_diagnostic_not_false_answer():
    result = calibrate_qwen_threshold(
        (_labeled("fit", score=0.8),),
        (
            _labeled("guideline-chapters-01", score=0.9, split="held_out"),
            _labeled("negative", score=0.85, relevant=False, split="held_out", behavior="REFUSAL"),
        ),
        _policy(),
    )
    assert result.status == "RETRIEVAL_PASSED"
    assert result.threshold == 0.8
    assert result.artifact is None
    assert result.held_out_negative_refusal_rate is None
    assert result.retrieval_only_negative_candidate_presence_rate == 1.0


def test_direct_calibration_rejects_missing_held_out_negative():
    with pytest.raises(ValueError, match="held-out negative set mismatch"):
        calibrate_qwen_threshold(
            (_labeled("fit", score=0.8),),
            (
                _labeled("guideline-chapters-01", score=0.9, split="held_out"),
                _labeled(
                    "negative", score=0.1, relevant=False, split="held_out", behavior="REFUSAL"
                ),
            ),
            replace(_policy(), held_out_negative_case_ids=("negative", "other-negative")),
        )


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


def test_observation_document_requires_exact_dataset_checksum_and_all_negatives():
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
        "observations": json.loads(json.dumps([asdict(item) for item in observations])),
    }
    with pytest.raises(ValueError, match="dataset checksum"):
        calibrate_observation_document(dataset, document)
    document["report"] = {
        "dataset_sha256": dataset.dataset_sha256,
        "profile_id": dataset.profile_id,
        "corpus_sha256": dataset.corpus_sha256,
        "retrieval_configuration_id": dataset.retrieval_configuration_id,
    }
    document["observations"] = document["observations"][:-1]
    with pytest.raises(ValueError, match="missing or unexpected observations"):
        calibrate_observation_document(dataset, document)


def test_frozen_qwen_observations_pass_retrieval_without_claiming_refusal():
    evals_root = Path(__file__).resolve().parents[1]
    dataset = load_vietnamese_dataset(
        evals_root / "datasets/vietnamese_rag_v1.jsonl",
        evals_root / "datasets/vietnamese_rag_v1.manifest.json",
    )
    document = json.loads(
        (evals_root / "reports/vietnamese_rag_v1/qwen_raw_observations.json").read_text(
            encoding="utf-8"
        )
    )

    result = calibrate_observation_document(dataset, document)

    assert result.status == "RETRIEVAL_PASSED"
    assert result.held_out_hit_at_5 == 1.0
    assert result.held_out_false_insufficient_evidence_rate == 0.0
    assert result.retrieval_only_negative_candidate_presence_rate == 0.75
    assert len(result.negative_candidate_diagnostics) == 8
    assert result.held_out_negative_refusal_rate is None
    assert result.artifact is None
    gate = json.loads(
        (evals_root / "reports/vietnamese_rag_v1/calibration_gate.json").read_text(encoding="utf-8")
    )
    assert gate["model_digest"] == dataset.model_digest
    assert gate["chunk_set_ids"] == list(dataset.chunk_set_ids)
    assert gate["retrieval_configuration_id"] == dataset.retrieval_configuration_id
