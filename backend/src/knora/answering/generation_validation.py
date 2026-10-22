from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult

MARKER_PATTERN = re.compile(r"\[\[([A-Za-z][A-Za-z0-9_-]*)\]\]")
_VALID_MARKER_PATTERN = re.compile(r"E[1-9][0-9]*\Z")


@dataclass(frozen=True, slots=True)
class ValidatedGeneration:
    result: GenerationResult
    parsed_markers: tuple[str, ...]


def _invalid() -> None:
    raise KnoraError("GENERATION_OUTPUT_INVALID")


def _matches_word_boundary(target: str, context: str) -> bool:
    cleaned = target.strip()
    if not cleaned:
        return False
    pattern = rf"(?<![a-zA-Z0-9_]){re.escape(cleaned)}(?![a-zA-Z0-9_])"
    return re.search(pattern, context, re.IGNORECASE) is not None


def _validate_answer_group_completeness(
    answer: str,
    required_subquestions: Sequence[Any],
    alias_to_candidate: Mapping[str, Any],
    cited_markers: Sequence[str],
) -> None:
    """Validates that all required subquestions are substantively represented.

    Checks both answer text presence, substantive factual facts, and evidence citations.
    """
    norm_answer = unicodedata.normalize("NFKC", answer).casefold()

    # 1. Reject stub answers that only list section headers/markers without substantive facts
    clean_answer = re.sub(r"\[\[[A-Za-z0-9_-]+\]\]", " ", norm_answer)
    for sq in required_subquestions:
        for s in getattr(sq, "protected_spans", ()):
            stext = unicodedata.normalize("NFKC", getattr(s, "text", "")).casefold().strip()
            if stext:
                clean_answer = re.sub(
                    rf"(?<![a-zA-Z0-9_]){re.escape(stext)}(?![a-zA-Z0-9_])", " ", clean_answer
                )
    stopwords = {
        "và",
        "với",
        "là",
        "của",
        "cho",
        "ở",
        "tại",
        "các",
        "những",
        "được",
        "có",
        "trong",
        "đến",
        "theo",
    }
    substantive_words = [
        w for w in re.findall(r"\w+", clean_answer) if len(w) >= 2 and w not in stopwords
    ]
    if len(substantive_words) < 5:
        _invalid()

    # 2. Check each required group has exact section and identifier representation
    for sq in required_subquestions:
        if not getattr(sq, "required", True):
            continue
        protected = getattr(sq, "protected_spans", ())
        section_spans = [
            unicodedata.normalize("NFKC", s.text).casefold()
            for s in protected
            if getattr(s, "category", "") == "section"
        ]
        if section_spans and not any(
            _matches_word_boundary(sec, norm_answer) for sec in section_spans
        ):
            _invalid()

        identifier_spans = [
            unicodedata.normalize("NFKC", s.text).casefold()
            for s in protected
            if getattr(s, "category", "") == "identifier"
        ]
        if identifier_spans and not any(
            _matches_word_boundary(ident, norm_answer) for ident in identifier_spans
        ):
            _invalid()

    # 3. Check citations match evidence for each required group
    if alias_to_candidate and len(required_subquestions) > 1:
        cited_cands = [alias_to_candidate[m] for m in cited_markers if m in alias_to_candidate]
        for sq in required_subquestions:
            if not getattr(sq, "required", True):
                continue
            section_spans = [
                s.text.casefold()
                for s in getattr(sq, "protected_spans", ())
                if getattr(s, "category", "") == "section"
            ]
            if section_spans:
                has_section_cand = any(
                    any(
                        _matches_word_boundary(
                            s, " ".join(c.heading_path).casefold() + " " + c.content.casefold()
                        )
                        for s in section_spans
                    )
                    for c in cited_cands
                )
                if not has_section_cand:
                    _invalid()


def validate_generation(
    result: GenerationResult,
    *,
    available_evidence_ids: tuple[str, ...],
    required_subquestions: Sequence[Any] | None = None,
    alias_to_candidate: Mapping[str, Any] | None = None,
) -> ValidatedGeneration:
    if result.decision == "REFUSAL":
        if (
            result.answer is not None
            or result.cited_evidence_ids != ()
            or result.refusal_reason != "INSUFFICIENT_EVIDENCE"
        ):
            _invalid()
        return ValidatedGeneration(result=result, parsed_markers=())

    if (
        result.decision != "ANSWER"
        or not isinstance(result.answer, str)
        or not result.answer.strip()
        or not isinstance(result.cited_evidence_ids, tuple)
        or not all(isinstance(item, str) and item for item in result.cited_evidence_ids)
        or result.refusal_reason is not None
    ):
        _invalid()

    markers = _parse_markers(result.answer)
    if not markers or len(markers) != len(set(markers)):
        _invalid()
    if len(result.cited_evidence_ids) != len(set(result.cited_evidence_ids)):
        _invalid()
    if any(marker not in available_evidence_ids for marker in markers):
        _invalid()
    if result.cited_evidence_ids != markers:
        _invalid()

    if required_subquestions and len(required_subquestions) > 1:
        _validate_answer_group_completeness(
            result.answer,
            required_subquestions,
            alias_to_candidate or {},
            markers,
        )

    return ValidatedGeneration(result=result, parsed_markers=markers)


def _parse_markers(answer: str) -> tuple[str, ...]:
    markers: list[str] = []
    cursor = 0
    while True:
        start = answer.find("[[", cursor)
        if start < 0:
            break
        end = answer.find("]]", start + 2)
        if end < 0:
            _invalid()
        marker = answer[start + 2 : end]
        if _VALID_MARKER_PATTERN.fullmatch(marker) is None:
            _invalid()
        markers.append(marker)
        cursor = end + 2
    return tuple(markers)
