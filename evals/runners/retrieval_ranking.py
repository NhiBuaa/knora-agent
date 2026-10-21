"""Pure ranking scorer implementing nDCG@10, Hit@k, MRR, Recall@k and gate evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class RankingEvaluationError(ValueError):
    """Raised when ranking inputs violate evaluation contract invariants."""

    pass


@dataclass(frozen=True, slots=True)
class RankingJudgment:
    query_id: str
    chunk_id: str
    content_checksum: str
    grade: int | float
    source_key: str | None = None
    rubric: str | None = None
    reviewer: str | None = None


@dataclass(frozen=True, slots=True)
class RankingCaseResult:
    query_id: str
    dcg: float
    idcg: float
    ndcg: float | None
    hit_at_k: float | None
    mrr: float | None
    recall_at_k: float | None
    precision_at_k: float | None
    status: str
    failure_reason: str | None = None
    ranked_chunk_ids: tuple[str, ...] = ()
    ranked_grades: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class MacroRankingResult:
    macro_ndcg: float | None
    macro_mrr: float | None
    macro_hit_at_k: float | None
    macro_recall_at_k: float | None
    denominators: dict[str, int]
    case_results: tuple[RankingCaseResult, ...]


@dataclass(frozen=True, slots=True)
class QuantizationGateResult:
    passed: bool
    drop: float | None
    float32_ndcg: float | None
    bits4_ndcg: float | None
    max_allowed_drop: float
    reason: str


def compute_dcg(ranked_grades: Sequence[float | int], k: int = 10) -> float:
    """Compute Discounted Cumulative Gain at cutoff k:

    DCG@k = sum_{i=1}^{min(len, k)} (2**grade_i - 1) / log2(i + 1)
    """
    if k <= 0:
        return 0.0
    dcg = 0.0
    for rank, grade in enumerate(ranked_grades[:k], start=1):
        if grade < 0:
            raise RankingEvaluationError(f"negative relevance grade {grade} at rank {rank}")
        dcg += (2.0**grade - 1.0) / math.log2(rank + 1)
    return dcg


def compute_idcg(available_grades: Sequence[float | int], k: int = 10) -> float:
    """Compute Ideal Discounted Cumulative Gain at cutoff k:

    Sort valid available grades descending, take top k, and compute DCG.
    """
    if k <= 0:
        return 0.0
    sorted_grades = sorted(available_grades, reverse=True)
    return compute_dcg(sorted_grades, k=k)


def compute_ndcg(
    ranked_grades: Sequence[float | int], available_grades: Sequence[float | int], k: int = 10
) -> float | None:
    """Compute Normalized Discounted Cumulative Gain at cutoff k:

    nDCG@k = DCG@k / IDCG@k when IDCG > 0; returns None when IDCG == 0 (not applicable).
    """
    idcg = compute_idcg(available_grades, k=k)
    if idcg <= 0.0:
        return None
    dcg = compute_dcg(ranked_grades, k=k)
    return min(1.0, dcg / idcg)


def compute_hit_at_k(
    ranked_grades: Sequence[float | int], total_positive: int | float, k: int = 10
) -> float | None:
    """Hit@k: 1.0 if any relevant item (grade > 0) is retrieved in top-k, else 0.0.

    Returns None if total_positive == 0 (no relevant items exist).
    """
    if total_positive <= 0:
        return None
    return 1.0 if any(g > 0 for g in ranked_grades[:k]) else 0.0


def compute_mrr(ranked_grades: Sequence[float | int], total_positive: int | float) -> float | None:
    """Mean Reciprocal Rank (MRR): 1 / rank of first relevant item (grade > 0).

    Returns 0.0 if no relevant items are retrieved.
    Returns None if total_positive == 0 (no relevant items exist).
    """
    if total_positive <= 0:
        return None
    for rank, grade in enumerate(ranked_grades, start=1):
        if grade > 0:
            return 1.0 / rank
    return 0.0


def compute_recall_at_k(
    ranked_grades: Sequence[float | int], total_positive: int | float, k: int = 10
) -> float | None:
    """Recall@k: sum of positive grades retrieved in top-k / total positive items.

    Returns None if total_positive == 0.
    """
    if total_positive <= 0:
        return None
    retrieved_positive = sum(g for g in ranked_grades[:k] if g > 0)
    return min(1.0, retrieved_positive / total_positive)


def compute_precision_at_k(ranked_grades: Sequence[float | int], k: int = 10) -> float | None:
    """Precision@k: proportion of top-k items that are relevant (grade > 0)."""
    if k <= 0:
        return None
    window = ranked_grades[:k]
    if not window:
        return 0.0
    return sum(1.0 for g in window if g > 0) / len(window)


def score_ranking_case(
    query_id: str,
    ranked_chunk_ids: Sequence[str],
    judgments: Mapping[str, RankingJudgment | float | int],
    *,
    universe_chunk_ids: set[str] | None = None,
    k: int = 10,
    require_exhaustive: bool = True,
) -> RankingCaseResult:
    """Score a single ranking query case against authoritative judgments.

    Strict invariants:
    - Ranked chunk IDs must contain no duplicates.
    - Every ranked candidate in top-k must have an authoritative judgment.
    - If unjudged candidates appear in top-k and require_exhaustive is True, raises
      RankingEvaluationError (unjudged items must never be silently converted to 0).
    - If IDCG == 0 (no relevant items), returns ndcg=None, marked as not-applicable.
    """
    if len(ranked_chunk_ids) != len(set(ranked_chunk_ids)):
        raise RankingEvaluationError(f"query {query_id} has duplicate ranked chunk IDs")

    if universe_chunk_ids is not None:
        for chunk_id in ranked_chunk_ids:
            if chunk_id not in universe_chunk_ids:
                raise RankingEvaluationError(
                    f"query {query_id} ranked chunk {chunk_id} outside authorized universe"
                )

    available_grades: list[float] = []
    for chunk_id, j in judgments.items():
        grade = j.grade if isinstance(j, RankingJudgment) else float(j)
        if grade < 0:
            raise RankingEvaluationError(f"negative grade {grade} for chunk {chunk_id}")
        available_grades.append(grade)

    ranked_grades: list[float] = []
    for rank, chunk_id in enumerate(ranked_chunk_ids[:k], start=1):
        if chunk_id not in judgments:
            if require_exhaustive:
                raise RankingEvaluationError(
                    f"query {query_id} has unjudged candidate at rank {rank}: {chunk_id}"
                )
            ranked_grades.append(0.0)
        else:
            j = judgments[chunk_id]
            grade = j.grade if isinstance(j, RankingJudgment) else float(j)
            ranked_grades.append(grade)

    # For metrics beyond top-k (e.g. MRR), look up remaining ranks if present
    full_ranked_grades = list(ranked_grades)
    for _rank, chunk_id in enumerate(ranked_chunk_ids[k:], start=k + 1):
        if chunk_id in judgments:
            j = judgments[chunk_id]
            grade = j.grade if isinstance(j, RankingJudgment) else float(j)
            full_ranked_grades.append(grade)
        else:
            full_ranked_grades.append(0.0)

    dcg = compute_dcg(ranked_grades, k=k)
    idcg = compute_idcg(available_grades, k=k)
    ndcg = (min(1.0, dcg / idcg)) if idcg > 0.0 else None

    total_positive = sum(g for g in available_grades if g > 0)
    hit_at_k = compute_hit_at_k(ranked_grades, total_positive, k=k)
    mrr = compute_mrr(full_ranked_grades, total_positive)
    recall_at_k = compute_recall_at_k(ranked_grades, total_positive, k=k)
    precision_at_k = compute_precision_at_k(ranked_grades, k=k)

    status = "observed" if ndcg is not None else "not_applicable"

    return RankingCaseResult(
        query_id=query_id,
        dcg=dcg,
        idcg=idcg,
        ndcg=ndcg,
        hit_at_k=hit_at_k,
        mrr=mrr,
        recall_at_k=recall_at_k,
        precision_at_k=precision_at_k,
        status=status,
        ranked_chunk_ids=tuple(ranked_chunk_ids),
        ranked_grades=tuple(ranked_grades),
    )


def macro_average_ranking(
    case_results: Sequence[RankingCaseResult | Mapping[str, Any]],
) -> MacroRankingResult:
    """Calculate macro-averaged ranking metrics across eligible cases.

    Denominators explicitly track:
    - total: total number of cases
    - evaluable: cases with valid nDCG (idcg > 0 and successful observation)
    - not_applicable: cases with idcg == 0 (e.g. refusal / no answer)
    - missing_or_failed: cases with failure_code or unjudged errors
    """
    total = len(case_results)
    evaluable_ndcg: list[float] = []
    evaluable_mrr: list[float] = []
    evaluable_hit: list[float] = []
    evaluable_recall: list[float] = []

    not_applicable = 0
    missing_or_failed = 0
    parsed_cases: list[RankingCaseResult] = []

    for item in case_results:
        if isinstance(item, RankingCaseResult):
            case = item
        else:
            case = RankingCaseResult(
                query_id=item["query_id"],
                dcg=item.get("dcg", 0.0),
                idcg=item.get("idcg", 0.0),
                ndcg=item.get("ndcg"),
                hit_at_k=item.get("hit_at_k"),
                mrr=item.get("mrr"),
                recall_at_k=item.get("recall_at_k"),
                precision_at_k=item.get("precision_at_k"),
                status=item.get("status", "observed"),
                failure_reason=item.get("failure_reason"),
                ranked_chunk_ids=tuple(item.get("ranked_chunk_ids", ())),
                ranked_grades=tuple(item.get("ranked_grades", ())),
            )
        parsed_cases.append(case)

        if case.status in ("failed", "missing", "error"):
            missing_or_failed += 1
        elif case.ndcg is None:
            not_applicable += 1
        else:
            evaluable_ndcg.append(case.ndcg)
            if case.mrr is not None:
                evaluable_mrr.append(case.mrr)
            if case.hit_at_k is not None:
                evaluable_hit.append(case.hit_at_k)
            if case.recall_at_k is not None:
                evaluable_recall.append(case.recall_at_k)

    denominators = {
        "total": total,
        "evaluable": len(evaluable_ndcg),
        "not_applicable": not_applicable,
        "missing_or_failed": missing_or_failed,
    }

    macro_ndcg = sum(evaluable_ndcg) / len(evaluable_ndcg) if evaluable_ndcg else None
    macro_mrr = sum(evaluable_mrr) / len(evaluable_mrr) if evaluable_mrr else None
    macro_hit = sum(evaluable_hit) / len(evaluable_hit) if evaluable_hit else None
    macro_recall = sum(evaluable_recall) / len(evaluable_recall) if evaluable_recall else None

    return MacroRankingResult(
        macro_ndcg=macro_ndcg,
        macro_mrr=macro_mrr,
        macro_hit_at_k=macro_hit,
        macro_recall_at_k=macro_recall,
        denominators=denominators,
        case_results=tuple(parsed_cases),
    )


def verify_quantization_ndcg_gate(
    float32_ndcg: float | None,
    bits4_ndcg: float | None,
    max_allowed_drop: float = 0.01,
) -> QuantizationGateResult:
    """Verify quality gate for TurboQuant bits4 vs float32 rescore:

    Absolute drop in macro nDCG@10 must be <= max_allowed_drop (default 0.01).
    Missing metric (None) fails the gate immediately.
    """
    if float32_ndcg is None or bits4_ndcg is None:
        return QuantizationGateResult(
            passed=False,
            drop=None,
            float32_ndcg=float32_ndcg,
            bits4_ndcg=bits4_ndcg,
            max_allowed_drop=max_allowed_drop,
            reason="MISSING_METRIC: float32_ndcg or bits4_ndcg is None",
        )

    drop = float32_ndcg - bits4_ndcg
    # Numerical tolerance for floating-point subtraction (1e-9)
    if drop > max_allowed_drop + 1e-9:
        return QuantizationGateResult(
            passed=False,
            drop=drop,
            float32_ndcg=float32_ndcg,
            bits4_ndcg=bits4_ndcg,
            max_allowed_drop=max_allowed_drop,
            reason=f"EXCESSIVE_DROP: {drop:.6f} > {max_allowed_drop}",
        )

    return QuantizationGateResult(
        passed=True,
        drop=drop,
        float32_ndcg=float32_ndcg,
        bits4_ndcg=bits4_ndcg,
        max_allowed_drop=max_allowed_drop,
        reason="PASS: drop <= max_allowed_drop",
    )
