"""Query Planning, protected spans extraction, and bounded query analysis.

Implements Query Plan contracts, deterministic protected span preservation,
and zero-overhead fast path for clear single-intent queries.
Refs #153 (Retrieval V3 Stage 7).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from knora.domain.errors import KnoraError

DEFAULT_QUERY_PLAN_POLICY = "query-planning-v1"
MAX_SUBQUESTIONS = 4
MAX_VARIANTS_PER_QUERY = 6
MAX_TOTAL_SEARCHES = 8
MAX_RERANK_INPUTS = 100
PLANNER_TIMEOUT_SECONDS = 15.0

# Protected span patterns
_IDENTIFIER_PATTERN = re.compile(r"\b[A-Z0-9_]{2,}(?:-[A-Z0-9_]+)+\b|\b[A-Z]{2,}_[A-Z0-9_]+\b")
_SECTION_PATTERN = re.compile(
    r"\b(?:chương|mục|điều|khoản|phần|chapter|section|clause|article|part)\s*"
    r"(?:\d+(?:\.\d+)*|[ivxlcdm]+|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\b",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_DATE_PATTERN = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_NEGATION_PATTERN = re.compile(
    r"\b(?:không(?:\s+quá|\s+được)?|chưa|chẳng|miễn|trừ\s+khi|no|not|never|without|prohibited)\b",
    re.IGNORECASE,
)
_UNIT_PATTERN = re.compile(
    r"\b(?:ngày|tháng|năm|giờ|phút|giây|triệu|tỷ|đồng|vnd|usd|bytes?|kb|mb|gb|tb|tokens?)\b",
    re.IGNORECASE,
)

# Comparison cues that signal multi-intent or decomposition
_COMPARISON_CUE = re.compile(
    r"\b(?:so\s+sánh|khác\s+nhau|giống\s+nhau|và|với|cùng\s+với|đồng\s+thời|"
    r"compare|versus|vs\.?|difference|between|both)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ProtectedSpan:
    """A segment of text that must be strictly preserved across rewriting and translation."""

    text: str
    category: str  # identifier, section, number, date, negation, unit
    start_index: int
    end_index: int


@dataclass(frozen=True, slots=True)
class Subquestion:
    """An atomic query component requiring dedicated source coverage."""

    id: str
    text: str
    required: bool = True
    depends_on: tuple[str, ...] = ()
    protected_spans: tuple[ProtectedSpan, ...] = ()


@dataclass(frozen=True, slots=True)
class QueryVariant:
    """A query alternative generated for retrieval coverage (original, rewrite, typo-fix)."""

    query: str
    reason: str
    variant_kind: str  # original, rewrite, subquestion, typo_corrected, accent_insensitive


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """Complete, validated query execution plan with resource budget guards."""

    query_id: str
    original_query: str
    is_fast_path: bool
    subquestions: tuple[Subquestion, ...]
    variants: tuple[QueryVariant, ...]
    protected_spans: tuple[ProtectedSpan, ...]
    policy_id: str = DEFAULT_QUERY_PLAN_POLICY
    max_subquestions: int = MAX_SUBQUESTIONS
    max_variants: int = MAX_VARIANTS_PER_QUERY
    max_total_searches: int = MAX_TOTAL_SEARCHES
    max_rerank_inputs: int = MAX_RERANK_INPUTS
    timeout_seconds: float = PLANNER_TIMEOUT_SECONDS
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_observation(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "policy_id": self.policy_id,
            "is_fast_path": self.is_fast_path,
            "subquestions_count": len(self.subquestions),
            "subquestion_ids": [sq.id for sq in self.subquestions],
            "variants_count": len(self.variants),
            "protected_spans_count": len(self.protected_spans),
            "protected_spans": [asdict(s) for s in self.protected_spans],
            "metadata": self.metadata,
        }


def extract_protected_spans(text: str) -> tuple[ProtectedSpan, ...]:
    """Deterministically extracts identifiers, sections, numbers, dates, negations, and units."""
    spans: list[ProtectedSpan] = []
    seen_ranges: set[tuple[int, int]] = set()

    def add_matches(pattern: re.Pattern[str], category: str) -> None:
        for match in pattern.finditer(text):
            rng = (match.start(), match.end())
            # Don't add if nested or exact duplicate
            if any(s <= rng[0] and rng[1] <= e for s, e in seen_ranges):
                continue
            seen_ranges.add(rng)
            spans.append(
                ProtectedSpan(
                    text=match.group(0),
                    category=category,
                    start_index=match.start(),
                    end_index=match.end(),
                )
            )

    # Priority order: identifiers, sections, dates, negations, units, numbers
    add_matches(_IDENTIFIER_PATTERN, "identifier")
    add_matches(_SECTION_PATTERN, "section")
    add_matches(_DATE_PATTERN, "date")
    add_matches(_NEGATION_PATTERN, "negation")
    add_matches(_UNIT_PATTERN, "unit")
    add_matches(_NUMBER_PATTERN, "number")

    spans.sort(key=lambda s: s.start_index)
    return tuple(spans)


def validate_protected_spans_preserved(
    original_spans: Sequence[ProtectedSpan], rewritten_query: str
) -> None:
    """Verifies that all protected spans from original query are preserved in rewritten text.

    Guarantees:
    - AUTH_403 is not changed to AUTH_404
    - 'không quá 14 ngày' does not lose 'không quá' or '14'
    - Chapter / Section numbers are strictly kept
    """
    norm_rewritten = unicodedata.normalize("NFKC", rewritten_query).casefold()

    for span in original_spans:
        span_norm = unicodedata.normalize("NFKC", span.text).casefold()
        if (
            span.category in {"identifier", "section", "number", "negation"}
            and span_norm not in norm_rewritten
        ):
            raise KnoraError(
                "PROTECTED_SPAN_VIOLATION",
            )


def is_fast_path_eligible(question: str) -> bool:
    """Determines whether a question can bypass neural planning and use the zero-overhead fast path.

    Clear, simple single-intent queries without complex conjunctions or reference cues
    run immediately without invoking LLM planner.
    """
    norm = unicodedata.normalize("NFKC", question).strip()
    if not norm:
        return True

    # Multi-intent / comparison requires planning
    if _COMPARISON_CUE.search(norm):
        # Check if multiple section mentions appear (e.g. "so sánh chương 2 và chương 5")
        sections = _SECTION_PATTERN.findall(norm)
        if len(sections) >= 2:
            return False

    # Check for question length or complexity
    words = norm.split()
    return len(words) <= 30


def build_fast_path_plan(question: str, query_id: str = "query-fast-path") -> QueryPlan:
    """Constructs an immediate, deterministic QueryPlan for fast-path execution."""
    protected = extract_protected_spans(question)
    subquestion = Subquestion(
        id="sub_1",
        text=question,
        required=True,
        protected_spans=protected,
    )
    variant = QueryVariant(
        query=question,
        reason="original_unmodified",
        variant_kind="original",
    )
    return QueryPlan(
        query_id=query_id,
        original_query=question,
        is_fast_path=True,
        subquestions=(subquestion,),
        variants=(variant,),
        protected_spans=protected,
    )


class QueryPlanner:
    """Deterministic Query Planner with fast-path optimization and budget guards."""

    def __init__(
        self,
        *,
        policy_id: str = DEFAULT_QUERY_PLAN_POLICY,
        max_subquestions: int = MAX_SUBQUESTIONS,
        max_variants: int = MAX_VARIANTS_PER_QUERY,
        timeout_seconds: float = PLANNER_TIMEOUT_SECONDS,
    ) -> None:
        self.policy_id = policy_id
        self.max_subquestions = max_subquestions
        self.max_variants = max_variants
        self.timeout_seconds = timeout_seconds

    def plan(self, question: str, query_id: str = "query-1") -> QueryPlan:
        if not isinstance(question, str) or not question.strip():
            raise KnoraError("QUERY_INPUT_INVALID")

        if is_fast_path_eligible(question):
            return build_fast_path_plan(question, query_id=query_id)

        # Multi-intent decomposition logic (heuristic baseline when no LLM adapter is passed)
        protected = extract_protected_spans(question)
        sections = _SECTION_PATTERN.findall(question)

        subquestions: list[Subquestion] = []
        variants: list[QueryVariant] = [
            QueryVariant(query=question, reason="original_query", variant_kind="original")
        ]

        if len(sections) >= 2:
            for idx, sec in enumerate(sections, start=1):
                sq_text = f"Thông tin quy định về {sec}"
                sq_protected = extract_protected_spans(sq_text)
                subquestions.append(
                    Subquestion(
                        id=f"sub_{idx}",
                        text=sq_text,
                        required=True,
                        protected_spans=sq_protected,
                    )
                )
                variants.append(
                    QueryVariant(
                        query=sq_text,
                        reason=f"decomposition_for_{sec}",
                        variant_kind="subquestion",
                    )
                )
        else:
            subquestions.append(
                Subquestion(
                    id="sub_1",
                    text=question,
                    required=True,
                    protected_spans=protected,
                )
            )

        # Check typo hypotheses and generate correction variants if needed
        from knora.answering.query_correction import generate_typo_hypotheses

        typo_res = generate_typo_hypotheses(question)
        if typo_res.has_typos and typo_res.corrected_query:
            for v in typo_res.variants:
                if v.query.casefold() not in {var.query.casefold() for var in variants}:
                    variants.append(v)

        # Enforce finite limits
        subquestions = subquestions[: self.max_subquestions]
        variants = variants[: self.max_variants]

        return QueryPlan(
            query_id=query_id,
            original_query=question,
            is_fast_path=False,
            subquestions=tuple(subquestions),
            variants=tuple(variants),
            protected_spans=protected,
            policy_id=self.policy_id,
            max_subquestions=self.max_subquestions,
            max_variants=self.max_variants,
            timeout_seconds=self.timeout_seconds,
        )
