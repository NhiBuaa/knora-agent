"""Tests for typo correction, transposition repair, and protected entity preservation."""

from __future__ import annotations

from knora.answering.query_correction import (
    generate_typo_hypotheses,
    separate_attached_digits,
)
from knora.answering.query_planning import extract_protected_spans


def test_separate_attached_digits():
    spans = extract_protected_spans("Tra cứu chuong2 và muc3.1 theo AUTH_403")
    res = separate_attached_digits("Tra cứu chuong2 và muc3.1 theo AUTH_403", spans)

    assert "chuong 2" in res
    assert "muc 3.1" in res
    # Protected identifier AUTH_403 is NOT split
    assert "AUTH_403" in res


def test_typo_correction_transposition():
    query = "báo cáo có mấy chươgn"
    result = generate_typo_hypotheses(query)

    assert result.has_typos is True
    assert result.corrected_query == "báo cáo có mấy chương"
    assert len(result.variants) == 1
    assert result.variants[0].variant_kind == "typo_corrected"


def test_typo_correction_telex_and_spacing():
    query = "baos cao muc3.1"
    result = generate_typo_hypotheses(query)

    assert result.has_typos is True
    assert "báo cáo" in result.corrected_query
    assert "mục 3.1" in result.corrected_query


def test_typo_correction_preserves_identifiers_and_negation():
    query = "Mã lỗi AUTH_403 không quá 14 ngày tại chuong2"
    result = generate_typo_hypotheses(query)

    assert result.has_typos is True
    # AUTH_403, không quá, 14 ngày must all remain intact
    assert "AUTH_403" in result.corrected_query
    assert "không quá" in result.corrected_query
    assert "14" in result.corrected_query
    assert "chương 2" in result.corrected_query


def test_clean_query_produces_no_hypotheses():
    clean_query = "Điều kiện hưởng bảo hiểm xã hội một lần là gì?"
    result = generate_typo_hypotheses(clean_query)

    assert result.has_typos is False
    assert result.corrected_query is None
    assert len(result.variants) == 0
