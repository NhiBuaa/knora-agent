"""Unit tests for positional derivation and lexical positions in chunks."""

from __future__ import annotations

import hashlib

import pytest

from knora.ingestion.lexical_positions import (
    build_corpus_statistics_from_chunks,
    extract_chunk_positions,
)


def test_extract_chunk_positions_monotonic_and_offsets():
    """Verify deterministic token positions with valid character offsets and checksum validation."""
    content = "AUTH_403: phiên bản 3.1 không tìm thấy lỗi 404 (Việt-Anh)"
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

    derivation = extract_chunk_positions("chunk-1", content, checksum)
    assert derivation.chunk_id == "chunk-1"
    assert derivation.content_checksum == checksum
    assert derivation.token_count == 11

    # Verify monotonic position index and non-overlapping valid character offsets
    prev_pos = -1
    prev_end = 0
    for tok in derivation.tokens:
        assert tok.position == prev_pos + 1
        assert tok.start_offset >= prev_end or prev_pos == -1
        assert tok.end_offset > tok.start_offset
        assert (
            content[tok.start_offset : tok.end_offset].lower().replace(":", "").replace("-", "")
            in tok.token
            or tok.token in content[tok.start_offset : tok.end_offset].lower()
        )
        prev_pos = tok.position
        prev_end = tok.end_offset


def test_extract_chunk_positions_rejects_checksum_mismatch():
    """Content checksum mismatch must raise ValueError."""
    content = "Sample content"
    wrong_checksum = "0" * 64
    with pytest.raises(ValueError, match="content checksum mismatch"):
        extract_chunk_positions("chunk-1", content, wrong_checksum)


def test_build_corpus_statistics_from_chunks():
    """Verify collection unigram frequencies and totals aggregated across chunks."""
    doc1 = "quick brown fox"
    doc2 = "brown fox jumps high"
    chk1 = hashlib.sha256(doc1.encode("utf-8")).hexdigest()
    chk2 = hashlib.sha256(doc2.encode("utf-8")).hexdigest()

    deriv1 = extract_chunk_positions("c1", doc1, chk1)
    deriv2 = extract_chunk_positions("c2", doc2, chk2)

    stats = build_corpus_statistics_from_chunks([deriv1, deriv2])
    assert stats.total_tokens == 7
    assert stats.total_chunks == 2
    assert stats.unigram_frequencies["quick"] == 1
    assert stats.unigram_frequencies["brown"] == 2
    assert stats.unigram_frequencies["fox"] == 2
    assert stats.unigram_frequencies["jumps"] == 1
    assert stats.unigram_frequencies["high"] == 1
    assert stats.average_chunk_length == 3.5
