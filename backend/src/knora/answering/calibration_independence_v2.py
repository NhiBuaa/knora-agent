import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthoredCalibrationItem:
    item_id: str
    item_kind: str
    content: str
    author_id: str


@dataclass(frozen=True, slots=True)
class SemanticReview:
    reviewer_id: str
    reviewer_was_author: bool
    rephrase_or_derivation_found: bool
    calibration_sha256: str


@dataclass(frozen=True, slots=True)
class IndependencePolicy:
    minimum_normalized_token_overlap: float

    @classmethod
    def v1(cls) -> "IndependencePolicy":
        return cls(minimum_normalized_token_overlap=0.8)


@dataclass(frozen=True, slots=True)
class IndependenceAudit:
    passed: bool
    calibration_sha256: str
    exact_copy_matches: tuple[tuple[str, int], ...]
    normalized_overlap_matches: tuple[tuple[str, int], ...]


def _normalized(content: str) -> str:
    value = unicodedata.normalize("NFKC", content).casefold()
    return " ".join(re.findall(r"\w+", value, flags=re.UNICODE))


def audit_calibration_independence(
    *,
    calibration_sha256: str,
    calibration_items: tuple[AuthoredCalibrationItem, ...],
    development_items: tuple[str, ...],
    semantic_review: SemanticReview,
    policy: IndependencePolicy,
) -> IndependenceAudit:
    if len(calibration_sha256) != 64 or not calibration_items:
        raise ValueError("invalid frozen calibration binding")
    normalized_development = tuple(_normalized(item) for item in development_items)
    exact: list[tuple[str, int]] = []
    overlaps: list[tuple[str, int]] = []
    for item in calibration_items:
        candidate = _normalized(item.content)
        candidate_tokens = set(candidate.split())
        for index, development in enumerate(normalized_development):
            if candidate == development:
                exact.append((item.item_id, index))
                continue
            development_tokens = set(development.split())
            denominator = min(len(candidate_tokens), len(development_tokens))
            overlap = (
                len(candidate_tokens & development_tokens) / denominator
                if denominator
                else 0.0
            )
            if overlap >= policy.minimum_normalized_token_overlap:
                overlaps.append((item.item_id, index))
    review_valid = (
        semantic_review.calibration_sha256 == calibration_sha256
        and not semantic_review.reviewer_was_author
        and semantic_review.reviewer_id
        not in {item.author_id for item in calibration_items}
        and not semantic_review.rephrase_or_derivation_found
    )
    return IndependenceAudit(
        passed=not exact and not overlaps and review_valid,
        calibration_sha256=calibration_sha256,
        exact_copy_matches=tuple(exact),
        normalized_overlap_matches=tuple(overlaps),
    )
