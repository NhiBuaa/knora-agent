import re
from dataclasses import dataclass

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


def validate_generation(
    result: GenerationResult,
    *,
    available_evidence_ids: tuple[str, ...],
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
