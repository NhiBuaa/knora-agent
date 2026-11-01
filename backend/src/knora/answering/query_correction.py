"""Query correction, typo hypotheses generation and accent restoration.

Provides deterministic typo detection, transposed character correction,
letter-digit spacing normalization, and accent hypothesis generation while strictly
preserving protected identifiers, numbers, units, and negations.
Refs #153 (Retrieval V3 Stage 7).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from knora.answering.query_planning import (
    ProtectedSpan,
    QueryVariant,
    extract_protected_spans,
)

# Common Vietnamese vocabulary for typo correction and transposition repair
_CORE_VIETNAMESE_LEXICON: dict[str, str] = {
    "bao": "báo",
    "baos": "báo",
    "cao": "cáo",
    "chuong": "chương",
    "chươgn": "chương",
    "chuoqng": "chương",
    "muc": "mục",
    "mucj": "mục",
    "dieu": "điều",
    "khoan": "khoản",
    "khoanr": "khoản",
    "phan": "phần",
    "hop": "hợp",
    "dong": "đồng",
    "lao": "lao",
    "tien": "tiền",
    "luong": "lương",
    "luowng": "lương",
    "bao_hiem": "bảo hiểm",
    "xa_hoi": "xã hội",
    "thoi_han": "thời hạn",
    "quy_dinh": "quy định",
    "phap_luat": "pháp luật",
    "thu_viec": "thử việc",
    "nghi_phep": "nghỉ phép",
    "trinh_bay": "trình bày",
    "bao_nhieu": "bao nhiêu",
    "may": "mấy",
    "mays": "mấy",
    "la": "là",
    "gi": "gì",
}

# Regex to separate attached words and numbers: "chuong2" -> "chuong 2", "muc3.1" -> "muc 3.1"
_ATTACHED_DIGIT_PATTERN = re.compile(
    r"\b([a-zA-Zà-ỹÀ-Ỹ]+)(\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)

# Common telex typo suffixes
_TELEX_SUFFIXES = {
    "s": "sắc",
    "f": "huyền",
    "r": "hỏi",
    "x": "ngã",
    "j": "nặng",
    "w": "trăng/móc",
}


@dataclass(frozen=True, slots=True)
class TypoCorrectionResult:
    """Outcome of typo analysis on a query."""

    original_query: str
    has_typos: bool
    corrected_query: str | None
    correction_reason: str | None
    variants: tuple[QueryVariant, ...]


def separate_attached_digits(text: str, protected_spans: Sequence[ProtectedSpan]) -> str:
    """Separates words glued to numbers: 'chuong2' -> 'chuong 2', 'muc3.1' -> 'muc 3.1'.

    Never splits protected identifiers like 'AUTH_403' or 'ISO_27001'.
    """
    protected_texts = {s.text for s in protected_spans if s.category == "identifier"}

    def repl(m: re.Match[str]) -> str:
        full_match = m.group(0)
        if full_match in protected_texts:
            return full_match
        word_part = m.group(1)
        # Avoid splitting common acronyms or tokens with few letters (like P1, V2)
        if len(word_part) >= 3 or word_part.lower() in {"mục", "muc", "điều", "dieu"}:
            return f"{word_part} {m.group(2)}"
        return full_match

    return _ATTACHED_DIGIT_PATTERN.sub(repl, text)


def generate_typo_hypotheses(
    query: str,
    *,
    max_hypotheses: int = 2,
) -> TypoCorrectionResult:
    """Generates accurate typo-corrected variants while strictly protecting sensitive spans."""
    protected = extract_protected_spans(query)
    protected_tokens = {s.text.casefold() for s in protected}

    # Step 1: Normalize spacing around attached digits ('chuong2' -> 'chuong 2')
    spaced_query = separate_attached_digits(query, protected)
    has_spaced_change = spaced_query != query

    words = spaced_query.split()
    corrected_words: list[str] = []
    changes: list[str] = []

    for word in words:
        clean_word = word.strip(".,!?;:()[]{}")
        clean_lower = clean_word.casefold()

        # Never touch protected numbers, identifiers, or units
        if clean_lower in protected_tokens or clean_word in protected_tokens:
            corrected_words.append(word)
            continue

        # Transposition and common telex lookup
        if clean_lower in _CORE_VIETNAMESE_LEXICON:
            replacement = _CORE_VIETNAMESE_LEXICON[clean_lower]
            if clean_word[0].isupper():
                replacement = replacement.capitalize()
            # Preserve surrounding punctuation
            new_word = word.replace(clean_word, replacement)
            corrected_words.append(new_word)
            if replacement.casefold() != clean_lower:
                changes.append(f"{clean_word}->{replacement}")
        else:
            # Check single transposition (e.g. 'chươgn' -> 'chương')
            corrected = False
            for target_unaccent, target_accent in _CORE_VIETNAMESE_LEXICON.items():
                if _is_single_transposition(clean_lower, target_unaccent):
                    replacement = target_accent
                    if clean_word[0].isupper():
                        replacement = replacement.capitalize()
                    new_word = word.replace(clean_word, replacement)
                    corrected_words.append(new_word)
                    changes.append(f"{clean_word}->{replacement}")
                    corrected = True
                    break
            if not corrected:
                corrected_words.append(word)

    candidate_corrected = " ".join(corrected_words)
    has_word_changes = candidate_corrected.casefold() != query.casefold()

    variants: list[QueryVariant] = []
    if has_spaced_change or has_word_changes:
        reason = ", ".join(changes) if changes else "digit_spacing_normalization"
        variants.append(
            QueryVariant(
                query=candidate_corrected,
                reason=f"typo_correction: {reason}",
                variant_kind="typo_corrected",
            )
        )

        return TypoCorrectionResult(
            original_query=query,
            has_typos=True,
            corrected_query=candidate_corrected,
            correction_reason=reason,
            variants=tuple(variants[:max_hypotheses]),
        )

    return TypoCorrectionResult(
        original_query=query,
        has_typos=False,
        corrected_query=None,
        correction_reason=None,
        variants=(),
    )


def _is_single_transposition(a: str, b: str) -> bool:
    """Checks if string a differs from string b by exactly one adjacent character swap."""
    if len(a) != len(b) or len(a) < 2:
        return False
    diffs = [i for i in range(len(a)) if a[i] != b[i]]
    if len(diffs) == 2:
        i, j = diffs
        return j == i + 1 and a[i] == b[j] and a[j] == b[i]
    return False
