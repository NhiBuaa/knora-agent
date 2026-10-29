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
    r"(?<!\w)(?:chương|phần|mục|điều|khoản|chapter|section|article)\s+"
    r"(?:\d+(?:[._-]\d+)*|[ivxlcdm]+)(?!\w)",
    re.IGNORECASE,
)

_SECTION_WORDS = {
    "chương",
    "mục",
    "điều",
    "khoản",
    "phần",
    "chapter",
    "section",
    "article",
}

_SYNONYM_PAIRS: tuple[tuple[str, str], ...] = (
    ("khách hàng", "người mua"),
    ("khách hàng", "người tiêu dùng"),
    ("khách hàng", "khách"),
    ("thời hạn", "thời gian"),
    ("đổi trả", "hoàn trả"),
    ("đổi trả", "trả hàng"),
    ("hoàn tiền", "tiền hoàn lại"),
    ("hoàn tiền", "nhận lại tiền"),
    ("được hoàn tiền", "nhận được tiền hoàn lại"),
    ("chi phí", "giá cả"),
    ("chi phí", "giá"),
)

_UNIT_WORDS = {
    "ngày",
    "ngay",
    "tháng",
    "thang",
    "năm",
    "nam",
    "tuần",
    "tuan",
    "giờ",
    "gio",
    "phút",
    "phut",
    "giây",
    "giay",
    "triệu",
    "trieu",
    "tỷ",
    "ty",
    "đồng",
    "dong",
    "vnd",
    "usd",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
    "hour",
    "hours",
}

_NEGATION_WORDS = {"không", "chưa", "chẳng", "not", "never"}
_FRAMING_WORDS = {
    "thời",
    "hạn",
    "thời gian",
    "quy",
    "định",
    "chính",
    "sách",
    "áp",
    "dụng",
    "chi",
    "tiết",
    "thông",
    "tin",
    "vòng",
    "khoảng",
    "mức",
    "nội",
    "dung",
    "match",
    "matching",
    "result",
    "found",
    "nhận",
}

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
} | _SECTION_WORDS


def _find_uncited_sentences(answer: str) -> list[str]:
    matches = list(MARKER_PATTERN.finditer(answer))
    if not matches:
        raw_sents = re.split(r"(?:[.!?]\s+|\n+)", answer)
        return [s.strip() for s in raw_sents if s.strip()]

    uncited: list[str] = []
    prev_end = 0

    for m in matches:
        start = m.start()
        between = answer[prev_end:start]
        between_clean = re.sub(r"^[\s.;:,-]+", "", between)
        between_to_split = re.sub(r"[\s.;:,-]+$", "", between_clean)

        if between_to_split:
            parts = [
                p.strip() for p in re.split(r"(?:[.!?]\s+|\n+)", between_to_split) if p.strip()
            ]
            if len(parts) > 1:
                uncited.extend(parts[:-1])

        prev_end = m.end()

    trailing = answer[prev_end:]
    trailing_clean = re.sub(r"^[\s.;:,-]+", "", trailing)
    if trailing_clean:
        trailing_parts = [
            p.strip() for p in re.split(r"(?:[.!?]\s+|\n+)", trailing_clean) if p.strip()
        ]
        uncited.extend(trailing_parts)

    return uncited


def _grounding_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\\([^\w\s])", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\b(?:vào\s+)?ngày\s+(?=\d{1,2}/\d{1,2}/\d{4}\b)", "", text)
    return re.sub(r"\bchuong(?=\s+\d)", "chương", text)


def _section_count_support(statement: str, source: str) -> bool | None:
    labels = r"chương|phần|mục|chapter|section"
    count = re.fullmatch(
        rf"(?:(?:tổng cộng|tổng số)\s+)?(?:báo cáo\s+)?(?:được\s+)?(?:(?:gợi ý|đề xuất)\s+)?"
        rf"(?:(?:trình bày|bao gồm|gồm|có|chia thành)\s+)?"
        rf"(?P<count>\d+)\s+(?P<label>{labels})[.!?]?",
        statement.strip(),
    ) or re.fullmatch(
        rf"(?:tổng số|số lượng|số)\s+(?P<label>{labels})\s+"
        rf"(?:được\s+)?(?:(?:gợi ý|đề xuất)\s+)?(?:là\s+)?(?P<count>\d+)"
        rf"(?:\s+(?P=label))?[.!?]?",
        statement.strip(),
    )
    if count is None:
        return None
    label, expected = count["label"], count["count"].lstrip("0") or "0"
    if any(
        not any(re.search(rf"\b{neg}\b", clause) for neg in _NEGATION_WORDS)
        and re.search(
            rf"\b(?:gồm|có|bao gồm|trình bày)\s+{expected}\s+{re.escape(label)}\b", clause
        )
        is not None
        for clause in re.split(r"[.;\n]", source)
    ):
        return True
    members = list(
        re.finditer(
            rf"^\s*(?:[-*•]\s*)?{re.escape(label)}\s+(\d+)\s*[–—:.-]\s*\S.+$",
            source,
            re.MULTILINE,
        )
    )
    if members:
        # Count the complete ordered list; its largest identifier alone is not a total.
        return (
            bool(source[members[-1].end() :].strip())
            and expected == str(len(members))
            and all(
                (member[1].lstrip("0") or "0") == str(index)
                for index, member in enumerate(members, start=1)
            )
        )
    return False


def _validate_cited_statement(
    answer: str,
    alias_to_candidate: Mapping[str, Any],
    *,
    is_multi_group: bool = False,
) -> None:
    # 0. Check uncited factual sentences in body
    for sent in _find_uncited_sentences(answer):
        norm_s = unicodedata.normalize("NFKC", sent).casefold()
        subst = [w for w in re.findall(r"\w+", norm_s) if w not in _STOPWORDS and not w.isdigit()]
        if len(subst) >= 2:
            _invalid()

    matches = list(MARKER_PATTERN.finditer(answer))
    if not matches:
        return

    segments: list[tuple[str, str]] = []
    prev_boundary = 0

    for match in matches:
        marker = match.group(1)
        start = match.start()
        text_before = answer[prev_boundary:start].strip()

        # Strip trailing punctuation so citation placed after period (e.g. "Sentence. [[E1]]")
        # properly maps the preceding sentence to the marker
        text_to_search = re.sub(r"[\s.;:,-]+$", "", text_before)
        boundary_matches = list(re.finditer(r"\n|(?<=[.!?])\s+", text_to_search))
        if boundary_matches:
            seg_start_rel = boundary_matches[-1].end()
            seg_text = text_to_search[seg_start_rel:].strip()
        else:
            seg_text = text_to_search.strip()

        seg_text = re.sub(r"^[\s.;:,-]+", "", seg_text)
        if not seg_text and segments:
            seg_text = segments[-1][1]
        segments.append((marker, seg_text))
        prev_boundary = match.end()

    for marker, seg_text in segments:
        if marker not in alias_to_candidate:
            continue
        cand = alias_to_candidate[marker]
        cand_content = _grounding_text(cand.content)
        cand_heading = _grounding_text(" ".join(cand.heading_path))
        cand_full = f"{cand_heading} {cand_content}"

        norm_seg = _grounding_text(seg_text)
        for date in re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", norm_seg):
            if not _matches_word_boundary(date, cand_full):
                _invalid()
        count_support = _section_count_support(norm_seg, cand_content)
        if count_support is False:
            _invalid()
        if count_support is True:
            continue

        # 1. Section references inside segment must match candidate heading/content
        seg_sections = _SECTION_REF_PATTERN.findall(norm_seg)
        for sec in seg_sections:
            if not _matches_word_boundary(sec, cand_full):
                _invalid()

        # 2. Number constraints with whitelist conversion 7 days <-> 1 week
        non_section_text = _SECTION_REF_PATTERN.sub(" ", norm_seg)
        seg_numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", non_section_text)
        for num in seg_numbers:
            if not _matches_word_boundary(num, cand_full):
                if (
                    num == "7"
                    and any(d in norm_seg for d in ["ngày", "ngay", "day", "days"])
                    and any(w in cand_full for w in ["1 tuần", "một tuần", "1 week", "one week"])
                ):
                    continue
                if (
                    num == "1"
                    and any(w in norm_seg for w in ["tuần", "tuan", "week", "weeks"])
                    and any(d in cand_full for d in ["7 ngày", "bảy ngày", "7 day", "7 days"])
                ):
                    continue
                _invalid()

        # 3. Unit constraints: non-whitelisted unit words in segment must match evidence
        seg_units = [
            w
            for w in re.findall(r"\b\w+\b", norm_seg)
            if w in _UNIT_WORDS
            and not (
                (
                    w in {"ngày", "ngay", "day", "days"}
                    and any(x in cand_full for x in ["1 tuần", "một tuần", "1 week", "one week"])
                )
                or (
                    w in {"tuần", "tuan", "week", "weeks"}
                    and any(x in cand_full for x in ["7 ngày", "bảy ngày", "7 day", "7 days"])
                )
            )
        ]
        for u in seg_units:
            if not _matches_word_boundary(u, cand_full):
                _invalid()

        # 3b. Number-unit pairing check (F14: prevents fact swapping like "Phí 7 đồng; 30 ngày")
        num_unit_pairs = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹ]+)\b", norm_seg)
        for num, unit in num_unit_pairs:
            if unit in _UNIT_WORDS:
                if num == "7" and unit in {"ngày", "ngay", "day", "days"}:
                    if not any(
                        x in cand_full
                        for x in [
                            "7 ngày",
                            "bảy ngày",
                            "7 day",
                            "7 days",
                            "1 tuần",
                            "một tuần",
                            "1 week",
                            "one week",
                        ]
                    ):
                        _invalid()
                elif num == "1" and unit in {"tuần", "tuan", "week", "weeks"}:
                    if not any(
                        x in cand_full
                        for x in [
                            "1 tuần",
                            "một tuần",
                            "1 week",
                            "one week",
                            "7 ngày",
                            "bảy ngày",
                            "7 day",
                            "7 days",
                        ]
                    ):
                        _invalid()
                else:
                    pattern = (
                        rf"\b{re.escape(num)}\s*(?:\([^\)]*\)\s*)?(?:\w+\s+)?"
                        rf"{re.escape(unit)}\b"
                    )
                    if not re.search(pattern, cand_full):
                        _invalid()

        # 4. Polarity/negation check: ungrounded negation or dropped negation on critical terms
        seg_negs = [w for w in re.findall(r"\b\w+\b", norm_seg) if w in _NEGATION_WORDS]
        cand_negs = [w for w in re.findall(r"\b\w+\b", cand_full) if w in _NEGATION_WORDS]
        if seg_negs and not cand_negs:
            _invalid()
        for neg in ["không", "chưa", "not"]:
            if f"{neg} " in cand_full:
                words_after_neg = re.findall(rf"{neg}\s+(\w+)", cand_full)
                for w in words_after_neg:
                    if (
                        w not in _STOPWORDS
                        and _matches_word_boundary(w, norm_seg)
                        and not any(n in norm_seg for n in _NEGATION_WORDS)
                    ):
                        _invalid()

        # 5. Filler check: segment cannot be purely filler phrases
        filler_patterns = [
            r"đây\s+chỉ\s+là\s+phần\s+giới\s+thiệu",
            r"tổng\s+quan\s+chung",
            r"giới\s+thiệu\s+tổng\s+quan",
            r"chưa\s+có\s+thông\s+tin\s+chi\s+tiết",
            r"nội\s+dung\s+chung",
        ]
        if any(re.search(p, norm_seg) for p in filler_patterns):
            cand_words = set(re.findall(r"\w+", cand_content)) - _STOPWORDS
            cand_words = {w for w in cand_words if not w.isdigit()}
            seg_substantive = [
                w for w in re.findall(r"\w+", norm_seg) if w not in _STOPWORDS and not w.isdigit()
            ]
            if not any(w in cand_words for w in seg_substantive):
                _invalid()

        # 6. Substantive facts & statement-level support check (F14 / D5):
        cand_words = set(re.findall(r"\w+", cand_full)) - _STOPWORDS
        cand_words = {w for w in cand_words if len(w) >= 2 and not w.isdigit()}
        for a, b in _SYNONYM_PAIRS:
            if a in cand_full:
                for w in re.findall(r"\w+", b):
                    if w not in _STOPWORDS and not w.isdigit():
                        cand_words.add(w)
            if b in cand_full:
                for w in re.findall(r"\w+", a):
                    if w not in _STOPWORDS and not w.isdigit():
                        cand_words.add(w)

        # Split segment into individual statements/clauses
        statements = [s.strip() for s in re.split(r"[,;\n]|(?<=[.!?])\s+", seg_text) if s.strip()]
        cand_clauses = [
            c.strip()
            for c in re.split(r"[,;\n]|(?<=[.!?])\s+|(?:\s*,\s*(?:và|hoặc)\s*)", cand_full)
            if c.strip()
        ]
        for stmt in statements:
            norm_stmt = _grounding_text(stmt)
            stmt_words = [
                w for w in re.findall(r"\w+", norm_stmt) if w not in _STOPWORDS and not w.isdigit()
            ]
            non_unit_stmt = [w for w in stmt_words if w not in _UNIT_WORDS]
            if non_unit_stmt:
                matched_stmt = [w for w in non_unit_stmt if w in cand_words]
                if not matched_stmt:
                    _invalid()
                # Ungrounded substantive claims (e.g. "miễn phí", "sao hỏa", "phí vận chuyển")
                unsupported_stmt = [
                    w for w in non_unit_stmt if w not in cand_words and w not in _FRAMING_WORDS
                ]
                if unsupported_stmt:
                    _invalid()

            stmt_pairs = re.findall(r"\b(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹ]+)\b", norm_stmt)
            if stmt_pairs:
                stmt_content_words = {
                    w
                    for w in re.findall(r"\w+", norm_stmt)
                    if w not in _STOPWORDS
                    and not w.isdigit()
                    and w not in _UNIT_WORDS
                    and w not in _FRAMING_WORDS
                }
                for num, unit in stmt_pairs:
                    num_pattern = rf"\b{re.escape(num)}\b"
                    if num == "1" and unit in {"tuần", "tuan", "week", "weeks"}:
                        num_pattern = r"\b(?:1|7)\b"
                    elif num == "7" and unit in {"ngày", "ngay", "day", "days"}:
                        num_pattern = r"\b(?:7|1)\b"

                    matched_clause = False
                    for clause in cand_clauses:
                        if re.search(num_pattern, clause):
                            c_words = set(re.findall(r"\w+", clause))
                            for a, b in _SYNONYM_PAIRS:
                                if a in clause:
                                    c_words.update(re.findall(r"\w+", b))
                                if b in clause:
                                    c_words.update(re.findall(r"\w+", a))
                            diff = stmt_content_words - c_words
                            if not diff:
                                matched_clause = True
                                break
                    if not matched_clause and stmt_content_words:
                        _invalid()

        seg_words = [
            w for w in re.findall(r"\w+", norm_seg) if w not in _STOPWORDS and not w.isdigit()
        ]
        non_unit_seg = [w for w in seg_words if w not in _UNIT_WORDS]
        if non_unit_seg:
            unsupported_seg = [
                w for w in non_unit_seg if w not in cand_words and w not in _FRAMING_WORDS
            ]
            if unsupported_seg:
                _invalid()

        if is_multi_group and not seg_numbers:
            matched_words = [w for w in seg_words if w in cand_words]
            has_2gram = False
            for i in range(len(seg_words) - 1):
                bigram = f"{seg_words[i]} {seg_words[i + 1]}"
                if bigram in cand_content:
                    has_2gram = True
                    break
            if not has_2gram and len(matched_words) < 2:
                _invalid()


def _validate_citation_alignment(
    answer: str,
    alias_to_candidate: Mapping[str, Any],
    *,
    is_multi_group: bool = False,
) -> None:
    matches = list(MARKER_PATTERN.finditer(answer))
    cursor = 0
    index = 0
    while index < len(matches):
        first = matches[index]
        text = answer[cursor : first.start()]
        group = [first.group(1)]
        end = first.end()
        index += 1
        while index < len(matches) and re.fullmatch(
            r"[\s.,;:!?]*", answer[end : matches[index].start()]
        ):
            group.append(matches[index].group(1))
            end = matches[index].end()
            index += 1
        statements = [
            s.strip() for s in re.split(r"\n+|(?<=[.!?])\s+", text) if re.search(r"\w", s)
        ]
        if not statements:
            _invalid()
        for statement_index, statement in enumerate(statements):
            heading = re.fullmatch(
                r"(?:các|những)\s+(?P<label>chương|phần|mục)"
                r"(?:\s+của\s+báo cáo)?\s+(?:bao gồm|gồm)\s*:",
                _grounding_text(statement),
            )
            if heading and statement_index + 1 < len(statements):
                next_statement = _grounding_text(statements[statement_index + 1])
                if re.match(rf"^-\s+{heading['label']}\s+\d+\b", next_statement):
                    # A structural list lead asserts no fact; all list members are checked below.
                    continue
            # A unique citation can enclose blocks; every statement still needs source support.
            for alias in group:
                if alias not in alias_to_candidate:
                    _invalid()
                try:
                    _validate_cited_statement(
                        f"{statement} [[{alias}]]",
                        {alias: alias_to_candidate[alias]},
                        is_multi_group=is_multi_group,
                    )
                except KnoraError as exc:
                    if exc.code != "GENERATION_OUTPUT_INVALID":
                        raise
                else:
                    break
            else:
                _invalid()
        cursor = end
    if re.search(r"\w", answer[cursor:]):
        _invalid()


def validate_generation(
    result: GenerationResult,
    *,
    available_evidence_ids: tuple[str, ...],
    required_subquestions: Sequence[Any] | None = None,
    alias_to_candidate: Mapping[str, Any] | None = None,
    is_v3: bool = True,
) -> ValidatedGeneration:
    if result.decision == "REFUSAL":
        if (
            result.answer is not None
            or result.cited_evidence_ids != ()
            or result.refusal_reason not in {"INSUFFICIENT_EVIDENCE", "CLARIFICATION_REQUIRED"}
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

    if alias_to_candidate and (required_subquestions is not None or is_v3):
        is_multi = bool(required_subquestions and len(required_subquestions) > 1)
        _validate_citation_alignment(result.answer, alias_to_candidate, is_multi_group=is_multi)

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
