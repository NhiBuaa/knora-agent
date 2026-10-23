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

    filler_patterns = [
        r"đây\s+chỉ\s+là\s+phần\s+giới\s+thiệu",
        r"tổng\s+quan\s+chung",
        r"giới\s+thiệu\s+tổng\s+quan",
        r"chưa\s+có\s+thông\s+tin\s+chi\s+tiết",
        r"nội\s+dung\s+chung",
    ]
    has_filler = any(re.search(p, norm_answer) for p in filler_patterns)

    # 1. Check each required group has exact section and identifier representation
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

    # 2. Check each required group has substantive factual evidence in answer
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
        "chương",
        "mục",
        "điều",
        "khoản",
        "phần",
        "chapter",
        "section",
        "article",
    }
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
            matching_cands = []
            if section_spans:
                matching_cands = [
                    c
                    for c in cited_cands
                    if any(
                        _matches_word_boundary(
                            s, " ".join(c.heading_path).casefold() + " " + c.content.casefold()
                        )
                        for s in section_spans
                    )
                ]
                if not matching_cands:
                    _invalid()
            else:
                matching_cands = cited_cands

            section_words = {w for s in section_spans for w in re.findall(r"\w+", s)}
            identifier_words = {
                w
                for s in getattr(sq, "protected_spans", ())
                if getattr(s, "category", "") == "identifier"
                for w in re.findall(r"\w+", s.text.casefold())
            }
            excluded_words = stopwords | section_words | identifier_words

            found_factual = False
            for cand in matching_cands:
                cand_words = [
                    w
                    for w in re.findall(r"\w+", cand.content.casefold())
                    if w not in excluded_words
                ]
                matched = [w for w in cand_words if _matches_word_boundary(w, norm_answer)]
                if len(matched) >= 1:
                    found_factual = True
                    break

            if not found_factual:
                _invalid()

        if has_filler:
            _invalid()


_SECTION_REF_PATTERN = re.compile(
    r"(?<!\w)(?:chương|phần|mục|điều|khoản|chapter|section|article)\s+[0-9a-zA-Z._-]+(?!\w)",
    re.IGNORECASE,
)

_STOPWORDS = {
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
    "chương",
    "mục",
    "điều",
    "khoản",
    "phần",
    "chapter",
    "section",
    "article",
    "đây",
    "chỉ",
    "nội",
    "dung",
    "về",
    "thông",
    "tin",
    "quy",
    "định",
    "tổng",
    "quan",
    "chung",
    "giới",
    "thiệu",
    "chi",
    "tiết",
    "khác",
    "nào",
    "một",
    "hai",
    "ba",
    "bốn",
    "năm",
    "sáu",
    "bảy",
    "tám",
    "chín",
    "mười",
    "này",
    "kia",
    "đó",
    "thì",
    "sẽ",
    "đã",
    "đang",
    "cũng",
    "khi",
    "như",
    "nhưng",
    "hoặc",
    "hay",
    "đều",
    "phải",
    "bị",
    "bởi",
    "do",
    "bằng",
}


def _validate_citation_alignment(
    answer: str,
    alias_to_candidate: Mapping[str, Any],
) -> None:
    matches = list(MARKER_PATTERN.finditer(answer))
    if not matches:
        return

    segments: list[tuple[str, str]] = []
    prev_boundary = 0

    for match in matches:
        marker = match.group(1)
        start = match.start()
        text_before = answer[prev_boundary:start]
        boundary_matches = list(re.finditer(r"[.;\n]", text_before))
        if boundary_matches:
            seg_start = prev_boundary + boundary_matches[-1].end()
        else:
            seg_start = prev_boundary

        seg_text = answer[seg_start:start].strip()
        if not seg_text and segments:
            seg_text = segments[-1][1]
        segments.append((marker, seg_text))
        prev_boundary = match.end()

    for marker, seg_text in segments:
        if marker not in alias_to_candidate:
            continue
        cand = alias_to_candidate[marker]
        cand_content = unicodedata.normalize("NFKC", cand.content).casefold()
        cand_heading = unicodedata.normalize("NFKC", " ".join(cand.heading_path)).casefold()
        cand_full = f"{cand_heading} {cand_content}"

        norm_seg = unicodedata.normalize("NFKC", seg_text).casefold()

        # 1. Section references inside segment must match candidate heading/content
        seg_sections = _SECTION_REF_PATTERN.findall(norm_seg)
        for sec in seg_sections:
            if not _matches_word_boundary(sec, cand_full):
                _invalid()

        # 2. Number constraints: every non-section number must exist in candidate context
        non_section_text = _SECTION_REF_PATTERN.sub(" ", norm_seg)
        seg_numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", non_section_text)
        for num in seg_numbers:
            if not _matches_word_boundary(num, cand_full):
                _invalid()

        # 3. Factual substance check: must not be completely factless or only filler
        cand_words = set(re.findall(r"\w+", cand_content)) - _STOPWORDS
        cand_words = {w for w in cand_words if len(w) >= 2 and not w.isdigit()}

        seg_words = [
            w for w in re.findall(r"\w+", norm_seg) if w not in _STOPWORDS and not w.isdigit()
        ]
        matched_words = [w for w in seg_words if w in cand_words]

        if seg_numbers:
            if seg_words and not matched_words:
                _invalid()
        else:
            has_2gram = False
            content_words_in_seg = [
                w for w in re.findall(r"\w+", norm_seg) if w not in _STOPWORDS and not w.isdigit()
            ]
            for i in range(len(content_words_in_seg) - 1):
                w1, w2 = content_words_in_seg[i], content_words_in_seg[i + 1]
                bigram = f"{w1} {w2}"
                if bigram in cand_content:
                    has_2gram = True
                    break

            if not has_2gram and len(matched_words) < 2:
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

    if alias_to_candidate and required_subquestions:
        _validate_citation_alignment(result.answer, alias_to_candidate)

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
