from dataclasses import dataclass
from enum import StrEnum
from math import ceil


class CalibrationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CalibrationCaseObservation:
    case_id: str
    top_similarities: tuple[float, ...]
    gold_chunk_ids: tuple[str, ...]
    top_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CalibrationSnapshot:
    artifact_id: str
    artifact_sha256: str
    observed_table_sha256: str
    cases: tuple[CalibrationCaseObservation, ...]
    hard_negative_similarities: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CalibrationPolicy:
    mean_recall_minimum: float
    top_two_hit_rate_minimum: float
    percentile: float
    score_decimals: int

    @classmethod
    def r9(cls) -> "CalibrationPolicy":
        return cls(0.90, 0.90, 0.10, 12)


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    status: CalibrationStatus
    vector_min_similarity: float | None
    artifact_sha256: str
    observed_table_sha256: str
    gate_results: tuple[bool, bool, bool, bool]

    def require_threshold(self) -> float:
        if self.status is not CalibrationStatus.PASSED or self.vector_min_similarity is None:
            raise ValueError("calibration has not passed")
        return self.vector_min_similarity


def _recall(case: CalibrationCaseObservation, threshold: float | None = None) -> float:
    eligible = tuple(
        chunk_id
        for chunk_id, score in zip(case.top_chunk_ids, case.top_similarities, strict=True)
        if threshold is None or score >= threshold
    )
    gold = set(case.gold_chunk_ids)
    return len(gold.intersection(eligible)) / len(gold)


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(percentile * len(ordered)) - 1)]


def select_calibrated_threshold(
    snapshot: CalibrationSnapshot, policy: CalibrationPolicy
) -> CalibrationResult:
    if not snapshot.cases or any(not case.gold_chunk_ids for case in snapshot.cases):
        raise ValueError("calibration snapshot has no applicable gold cases")
    recalls = [_recall(case) for case in snapshot.cases]
    first_gold_scores = [
        max(
            score
            for chunk_id, score in zip(
                case.top_chunk_ids, case.top_similarities, strict=True
            )
            if chunk_id in case.gold_chunk_ids
        )
        for case in snapshot.cases
        if set(case.gold_chunk_ids).intersection(case.top_chunk_ids)
    ]
    top_two_hits = sum(
        bool(set(case.gold_chunk_ids).intersection(case.top_chunk_ids[:2]))
        for case in snapshot.cases
    ) / len(snapshot.cases)
    hard_max = max(snapshot.hard_negative_similarities, default=float("-inf"))
    p10 = (
        _nearest_rank_percentile(first_gold_scores, policy.percentile)
        if len(first_gold_scores) == len(snapshot.cases)
        else float("-inf")
    )
    boundaries = sorted(
        {
            round(score, policy.score_decimals)
            for case in snapshot.cases
            for score in case.top_similarities
        },
        reverse=True,
    )
    preserving = [
        boundary
        for boundary in boundaries
        if all(
            _recall(case, boundary) == baseline
            for case, baseline in zip(snapshot.cases, recalls, strict=True)
        )
        and hard_max < boundary
    ]
    gates = (
        sum(recalls) / len(recalls) >= policy.mean_recall_minimum,
        top_two_hits >= policy.top_two_hit_rate_minimum,
        hard_max < p10,
        bool(preserving),
    )
    passed = all(gates)
    return CalibrationResult(
        status=CalibrationStatus.PASSED if passed else CalibrationStatus.FAILED,
        vector_min_similarity=max(preserving) if passed else None,
        artifact_sha256=snapshot.artifact_sha256,
        observed_table_sha256=snapshot.observed_table_sha256,
        gate_results=gates,
    )
