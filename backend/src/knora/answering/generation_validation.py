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


def _validate_answer_group_completeness(
    answer: str,
    required_subquestions: Sequence[Any],
    alias_to_candidate: Mapping[str, Any],
    cited_markers: Sequence[str],
) -> None:
    """Validates that all required subquestions are substantively represented.

    Checks both answer text presence and evidence citations.
    """
    norm_answer = unicodedata.normalize("NFKC", answer).casefold()

    for sq in required_subquestions:
        if not getattr(sq, "required", True):
            continue
        protected = getattr(sq, "protected_spans", ())
        section_spans = [
            unicodedata.normalize("NFKC", s.text).casefold()
            for s in protected
            if getattr(s, "category", "") == "section"
        ]
        if section_spans and not any(sec in norm_answer for sec in section_spans):
            _invalid()

        identifier_spans = [
            unicodedata.normalize("NFKC", s.text).casefold()
            for s in protected
            if getattr(s, "category", "") == "identifier"
        ]
        if identifier_spans and not any(ident in norm_answer for ident in identifier_spans):
            _invalid()

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
                        s in " ".join(c.heading_path).casefold() or s in c.content.casefold()
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
