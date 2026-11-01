"""Tests for dynamic corpus-statistics snapshot generation and validation."""

import hashlib

import pytest

from knora.ingestion.lexical_population import (
    CorpusStatisticsSnapshot,
    LexicalPopulationError,
    count_qdrant_word_tokens,
)

ALPHA = hashlib.sha256(b"alpha content text").hexdigest()
BETA = hashlib.sha256(b"beta content text").hexdigest()
GAMMA = hashlib.sha256(b"gamma content text").hexdigest()
DOC_A = "a" * 64
DOC_B = "b" * 64
DOC_C = "c" * 64


def test_count_qdrant_word_tokens_parity() -> None:
    # 7 tokens from upload fixture
    assert count_qdrant_word_tokens("Refund requests are accepted within 30 days.") == 7
    # 3 tokens from accented Vietnamese compatibility characters
    assert count_qdrant_word_tokens("ＰＤＦ HẠN MỨC") == 3
    # 3 tokens from English words
    assert count_qdrant_word_tokens("running run the") == 3
    # Punctuation and whitespace handling
    assert count_qdrant_word_tokens("  hello,  world! 123 ") == 3
    # Non-empty fallback min count
    assert count_qdrant_word_tokens("") == 1
    assert count_qdrant_word_tokens("   ") == 1


def test_corpus_statistics_snapshot_build_and_invariants() -> None:
    docs = [
        (DOC_B, [(BETA, 5)]),
        (DOC_A, [(ALPHA, 3)]),
    ]
    snapshot = CorpusStatisticsSnapshot.build(
        population_id="dynamic-test-v1",
        documents=docs,
    )

    assert snapshot.total_documents == 2
    assert snapshot.total_chunks == 2
    assert snapshot.total_tokens == 8
    assert snapshot.avg_len == 4.0
    assert snapshot.tokenizer == "word"
    assert snapshot.tokenizer_version == "qdrant-1.19.2"
    assert snapshot.k1 == 1.2
    assert snapshot.b == 0.75
    assert snapshot.profile.id == "dynamic-test-v1"
    assert snapshot.profile.avg_len == 4.0
    assert snapshot.profile.statistics_digest == snapshot.statistics_digest

    # Deterministic ordering by source_sha256: DOC_A before DOC_B
    assert snapshot.documents[0].source_sha256 == DOC_A
    assert snapshot.documents[1].source_sha256 == DOC_B

    # Re-building with same documents produces identical statistics_digest
    rebuilt = CorpusStatisticsSnapshot.build(
        population_id="dynamic-test-v1",
        documents=[(DOC_A, [(ALPHA, 3)]), (DOC_B, [(BETA, 5)])],
    )
    assert rebuilt.statistics_digest == snapshot.statistics_digest
    assert rebuilt.profile.digest() == snapshot.profile.digest()


def test_membership_change_mutates_statistics_digest_and_avg_len() -> None:
    initial_docs = [
        (DOC_A, [(ALPHA, 3)]),
        (DOC_B, [(BETA, 5)]),
    ]
    initial = CorpusStatisticsSnapshot.build(
        population_id="dynamic-test-v1",
        documents=initial_docs,
    )

    # Adding a 3rd document (unseen in S2 frozen manifests)
    extended_docs = [
        (DOC_A, [(ALPHA, 3)]),
        (DOC_B, [(BETA, 5)]),
        (DOC_C, [(GAMMA, 10)]),
    ]
    extended = CorpusStatisticsSnapshot.build(
        population_id="dynamic-test-v1",
        documents=extended_docs,
    )
    assert extended.total_documents == 3
    assert extended.total_chunks == 3
    assert extended.total_tokens == 18
    assert extended.avg_len == 6.0
    assert extended.statistics_digest != initial.statistics_digest
    assert extended.profile.digest() != initial.profile.digest()

    # Deleting a document
    reduced_docs = [
        (DOC_A, [(ALPHA, 3)]),
    ]
    reduced = CorpusStatisticsSnapshot.build(
        population_id="dynamic-test-v1",
        documents=reduced_docs,
    )
    assert reduced.total_documents == 1
    assert reduced.avg_len == 3.0
    assert reduced.statistics_digest != initial.statistics_digest


def test_as_verified_population_compatibility() -> None:
    docs = [
        (DOC_A, [(ALPHA, 3), (BETA, 5)]),
        (DOC_B, [(GAMMA, 7)]),
    ]
    snapshot = CorpusStatisticsSnapshot.build(
        population_id="dynamic-test-v1",
        documents=docs,
    )
    verified = snapshot.as_verified_population()

    assert verified.id == snapshot.snapshot_id
    assert verified.profile.digest() == snapshot.profile.digest()
    assert verified.validate_document(
        DOC_A, ("alpha content text", "beta content text"), verified.profile
    ) == (3, 5)
    assert verified.validate_document(DOC_B, ("gamma content text",), verified.profile) == (7,)

    verified.validate_corpus(
        [
            (DOC_A, ("alpha content text", "beta content text")),
            (DOC_B, ("gamma content text",)),
        ],
        verified.profile,
    )


@pytest.mark.parametrize(
    "bad_docs,match_err",
    [
        ([], "cannot be empty"),
        ([(DOC_A, [])], "cannot be empty"),
        ([(DOC_A, [(ALPHA, 0)])], "positive integer"),
        ([(DOC_A, [(ALPHA, -1)])], "positive integer"),
        ([(DOC_A, [(ALPHA, 2.5)])], "positive integer"),
        ([(DOC_A, [("invalid-sha", 5)])], "invalid chunk content checksum"),
        ([("invalid-source", [(ALPHA, 3)])], "invalid source sha256"),
        ([(DOC_A, [(ALPHA, 3)]), (DOC_A, [(BETA, 5)])], "duplicate source"),
    ],
)
def test_corpus_statistics_snapshot_validation_failures(bad_docs: list, match_err: str) -> None:
    with pytest.raises(LexicalPopulationError, match=match_err):
        CorpusStatisticsSnapshot.build(
            population_id="test-fail",
            documents=bad_docs,
        )
