"""Fit Qwen retrieval thresholds without looking at held-out labels."""

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from evals.datasets.vietnamese_rag_v1 import (
    VietnameseCase,
    VietnameseDataset,
    load_vietnamese_dataset,
)
from evals.runners.vietnamese_retrieval import CandidateObservation, RetrievalObservation

POLICY_ID = "qwen-vietnamese-evidence-v1"
REGRESSION_CASE_ID = "guideline-chapters-01"


@dataclass(frozen=True, slots=True)
class LabeledObservation:
    case: VietnameseCase
    observation: RetrievalObservation


@dataclass(frozen=True, slots=True)
class QwenCalibrationPolicy:
    profile_id: str
    dataset_sha256: str
    corpus_sha256: str
    model_digest: str
    chunk_set_ids: tuple[str, ...]
    policy_id: str = POLICY_ID
    minimum_held_out_hit_at_5: float = 0.80
    maximum_held_out_false_insufficient_evidence_rate: float = 0.10
    minimum_held_out_negative_refusal_rate: float = 1.00
    maximum_fit_miss_rate: float = 0.10


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    status: str
    threshold: float | None
    held_out_hit_at_5: float
    held_out_false_insufficient_evidence_rate: float
    held_out_negative_refusal_rate: float
    regression_case_passed: bool
    artifact: dict[str, object] | None


def _eligible(item: LabeledObservation, threshold: float):
    return tuple(
        candidate for candidate in item.observation.candidates if candidate.similarity >= threshold
    )


def _has_gold(item: LabeledObservation, threshold: float) -> bool:
    case = item.case
    return any(
        candidate.source_key == case.source_key
        and candidate.page_start == case.page_start
        and candidate.checksum in case.acceptable_chunk_checksums
        for candidate in _eligible(item, threshold)[:5]
    )


def _check_provenance(item: LabeledObservation, policy: QwenCalibrationPolicy) -> None:
    observation = item.observation
    if observation.case_id != item.case.id or not observation.observation_id:
        raise ValueError("observation identity mismatch")
    if observation.profile_id != policy.profile_id:
        raise ValueError("profile mismatch")
    if observation.corpus_sha256 != policy.corpus_sha256:
        raise ValueError("corpus mismatch")
    if set(observation.chunk_set_ids) != set(policy.chunk_set_ids):
        raise ValueError("chunk set mismatch")
    if observation.retrieval_configuration_id != "retrieval-qwen-diagnostic-v1":
        raise ValueError("diagnostic retrieval configuration mismatch")
    if observation.source != "answering_store_diagnostic":
        raise ValueError("calibration requires direct production store observations")
    if any(
        not math.isfinite(candidate.similarity) or not -1 <= candidate.similarity <= 1
        for candidate in observation.candidates
    ):
        raise ValueError("invalid candidate similarity")


def calibrate_qwen_threshold(
    calibration_observations: tuple[LabeledObservation, ...],
    held_out_observations: tuple[LabeledObservation, ...],
    policy: QwenCalibrationPolicy,
) -> CalibrationResult:
    if not calibration_observations or not held_out_observations:
        raise ValueError("calibration and held-out observations are required")
    all_items = (*calibration_observations, *held_out_observations)
    if len({item.case.id for item in all_items}) != len(all_items):
        raise ValueError("overlapping calibration and held-out IDs")
    if any(
        item.case.split != "calibration" or item.case.expected_behavior != "ANSWER"
        for item in calibration_observations
    ):
        raise ValueError("fit requires calibration positives only")
    if any(item.case.split != "held_out" for item in held_out_observations):
        raise ValueError("held-out split mismatch")
    if not any(item.case.id == REGRESSION_CASE_ID for item in held_out_observations):
        raise ValueError("seven-chapter regression is missing")
    for item in all_items:
        _check_provenance(item, policy)
    fit_gold_scores = []
    for item in calibration_observations:
        gold_scores = [
            candidate.similarity
            for candidate in item.observation.candidates[:5]
            if candidate.source_key == item.case.source_key
            and candidate.page_start == item.case.page_start
            and candidate.checksum in item.case.acceptable_chunk_checksums
        ]
        if not gold_scores:
            raise ValueError("fit positive lacks a top-five relevant candidate")
        fit_gold_scores.append(max(gold_scores))
    ordered = sorted(fit_gold_scores)
    threshold = ordered[math.floor(policy.maximum_fit_miss_rate * len(ordered))]
    positives = [item for item in held_out_observations if item.case.expected_behavior == "ANSWER"]
    negatives = [item for item in held_out_observations if item.case.expected_behavior == "REFUSAL"]
    if not positives or not negatives:
        raise ValueError("held-out answers and negatives are required")
    hit_at_5 = sum(_has_gold(item, threshold) for item in positives) / len(positives)
    false_insufficient = sum(not _eligible(item, threshold) for item in positives) / len(positives)
    negative_empty = sum(not _eligible(item, threshold) for item in negatives) / len(negatives)
    regression_passed = next(
        _has_gold(item, threshold)
        for item in held_out_observations
        if item.case.id == REGRESSION_CASE_ID
    )
    passed = (
        hit_at_5 >= policy.minimum_held_out_hit_at_5
        and false_insufficient <= policy.maximum_held_out_false_insufficient_evidence_rate
        and negative_empty >= policy.minimum_held_out_negative_refusal_rate
        and regression_passed
    )
    artifact = None
    if passed:
        artifact = {
            "schema_version": 1,
            "status": "PASSED",
            "profile_id": policy.profile_id,
            "model_digest": policy.model_digest,
            "dataset_sha256": policy.dataset_sha256,
            "corpus_sha256": policy.corpus_sha256,
            "chunk_set_ids": list(policy.chunk_set_ids),
            "policy_id": policy.policy_id,
            "threshold": threshold,
            "held_out_hit_at_5": hit_at_5,
            "held_out_false_insufficient_evidence_rate": false_insufficient,
            "held_out_negative_refusal_rate": negative_empty,
            "regression_case_passed": regression_passed,
        }
        artifact["artifact_sha256"] = hashlib.sha256(
            json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    return CalibrationResult(
        "PASSED" if passed else "FAILED",
        threshold if passed else None,
        hit_at_5,
        false_insufficient,
        negative_empty,
        regression_passed,
        artifact,
    )


def calibrate_observation_document(
    dataset: VietnameseDataset, document: dict[str, object]
) -> CalibrationResult:
    report = document.get("report")
    if not isinstance(report, dict) or report.get("dataset_sha256") != dataset.dataset_sha256:
        raise ValueError("dataset checksum mismatch")
    for field, expected in (
        ("profile_id", dataset.profile_id),
        ("corpus_sha256", dataset.corpus_sha256),
        ("retrieval_configuration_id", dataset.retrieval_configuration_id),
    ):
        if report.get(field) != expected:
            raise ValueError(f"{field} mismatch")
    if document.get("threshold_applied") is not False or document.get("candidate_k") != 16:
        raise ValueError("calibration requires raw 16-candidate observations")
    raw_observations = document.get("observations")
    if not isinstance(raw_observations, list):
        raise ValueError("observations missing")
    observations = {}
    for raw in raw_observations:
        if not isinstance(raw, dict) or not isinstance(raw.get("candidates"), list):
            raise ValueError("invalid observation")
        observation = RetrievalObservation(
            **{
                **raw,
                "chunk_set_ids": tuple(raw["chunk_set_ids"]),
                "candidates": tuple(CandidateObservation(**item) for item in raw["candidates"]),
            }
        )
        if observation.case_id in observations:
            raise ValueError("duplicate observation")
        observations[observation.case_id] = observation
    if set(observations) != {case.id for case in dataset.cases}:
        raise ValueError("missing or unexpected observations")
    labeled = tuple(LabeledObservation(case, observations[case.id]) for case in dataset.cases)
    policy = QwenCalibrationPolicy(
        profile_id=dataset.profile_id,
        dataset_sha256=dataset.dataset_sha256,
        corpus_sha256=dataset.corpus_sha256,
        model_digest=dataset.model_digest,
        chunk_set_ids=dataset.chunk_set_ids,
    )
    return calibrate_qwen_threshold(
        tuple(item for item in labeled if item.case.split == "calibration"),
        tuple(item for item in labeled if item.case.split == "held_out"),
        policy,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate a Qwen retrieval evidence threshold")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = load_vietnamese_dataset(args.dataset, args.manifest)
    document = json.loads(args.observations.read_text(encoding="utf-8"))
    result = calibrate_observation_document(dataset, document)
    output = {
        "schema_version": 1,
        "status": result.status,
        "profile_id": dataset.profile_id,
        "dataset_sha256": dataset.dataset_sha256,
        "corpus_sha256": dataset.corpus_sha256,
        "policy_id": POLICY_ID,
        "held_out_hit_at_5": result.held_out_hit_at_5,
        "held_out_false_insufficient_evidence_rate": (
            result.held_out_false_insufficient_evidence_rate
        ),
        "held_out_negative_refusal_rate": result.held_out_negative_refusal_rate,
        "retrieval_only_negative_empty_candidate_rate": (result.held_out_negative_refusal_rate),
        "regression_case_passed": result.regression_case_passed,
        "sealed_artifact": result.artifact,
        "negative_rate_semantics": (
            "fraction with no threshold-eligible retrieved candidate; not a generation refusal"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result.status, "sealed": result.artifact is not None}))


if __name__ == "__main__":
    main()
