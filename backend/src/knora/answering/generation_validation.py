import re
from dataclasses import dataclass

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult

MARKER_PATTERN = re.compile(r"\[\[([A-Za-z][A-Za-z0-9_-]*)\]\]")


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
            or result.cited_evidence_ids
            or result.refusal_reason != "INSUFFICIENT_EVIDENCE"
        ):
            _invalid()
        return ValidatedGeneration(result=result, parsed_markers=())

    if result.decision != "ANSWER" or not result.answer or result.refusal_reason is not None:
        _invalid()

    markers = tuple(MARKER_PATTERN.findall(result.answer))
    if not markers or len(markers) != len(set(markers)):
        _invalid()
    if len(result.cited_evidence_ids) != len(set(result.cited_evidence_ids)):
        _invalid()
    if any(marker not in available_evidence_ids for marker in markers):
        _invalid()
    if result.cited_evidence_ids != markers:
        _invalid()
    return ValidatedGeneration(result=result, parsed_markers=markers)
