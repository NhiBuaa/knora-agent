"""Finite lexical populations are checked against authoritative source text."""

import hashlib
import json
from copy import deepcopy

import pytest

from knora.ingestion.lexical_population import LexicalPopulationError, VerifiedLexicalPopulation
from knora.ingestion.search_indexing import LexicalProfile

ALPHA = "8ed3f6ad685b959ead7022518e1af76cd816f8e8ec7ccdda1ed4018e8f2223f8"
BETA = "f44e64e75f3948e9f73f8dfa94721c4ce8cbb4f265c4790c702b2d41cfbf2753"
GAMMA = "be9d587defa1f0c09ef49eb17e206983a5f8f8289e4281860bd0ee5a19592c67"
STATS = "8200d1af8e17ccacf053ddaea1c27e62113ca6af86de0716e80e9ace682ac670"


def manifest_data() -> dict:
    profile = LexicalProfile("finite-v1", "word", "qdrant-1.19.2", 1.2, 0.75, 5.0, STATS)
    return {
        "schema_version": "lexical-population-v1",
        "id": "fixture-two-sources",
        "native_evidence_sha256": "c" * 64,
        "profile": {
            "id": profile.id,
            "tokenizer": profile.tokenizer,
            "tokenizer_version": profile.tokenizer_version,
            "k1": profile.k1,
            "b": profile.b,
            "avg_len": profile.avg_len,
            "statistics_digest": profile.statistics_digest,
        },
        "profile_digest": profile.digest(),
        "documents": [
            {
                "source_sha256": "a" * 64,
                "chunks": [
                    {"content_checksum": ALPHA, "native_token_count": 3},
                    {"content_checksum": BETA, "native_token_count": 5},
                ],
            },
            {
                "source_sha256": "b" * 64,
                "chunks": [{"content_checksum": GAMMA, "native_token_count": 7}],
            },
        ],
    }


def test_validates_document_and_exact_corpus_without_database_ids() -> None:
    manifest = VerifiedLexicalPopulation.from_mapping(manifest_data())

    assert manifest.validate_document("a" * 64, ("alpha", "beta"), manifest.profile) == (3, 5)
    manifest.validate_corpus(
        (("b" * 64, ("gamma",)), ("a" * 64, ("alpha", "beta"))),
        manifest.profile,
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "v2"),
        (("native_evidence_sha256",), "not-a-hash"),
        (("profile_digest",), "0" * 64),
        (("profile", "statistics_digest"), "0" * 64),
        (("profile", "avg_len"), 4.0),
        (("profile", "tokenizer_version"), "other"),
        (("documents", 0, "source_sha256"), "not-a-hash"),
        (("documents", 0, "chunks", 0, "content_checksum"), "not-a-hash"),
        (("documents", 0, "chunks", 0, "native_token_count"), 0),
        (("documents", 0, "chunks", 0, "native_token_count"), True),
    ],
)
def test_rejects_malformed_or_inconsistent_manifest(path: tuple, value: object) -> None:
    data = manifest_data()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(LexicalPopulationError):
        VerifiedLexicalPopulation.from_mapping(data)


def test_rejects_unknown_fields_duplicate_sources_and_unpinned_chunks() -> None:
    data = manifest_data()
    data["extra"] = "untrusted"
    with pytest.raises(LexicalPopulationError):
        VerifiedLexicalPopulation.from_mapping(data)

    data = manifest_data()
    data["documents"].append(deepcopy(data["documents"][0]))
    with pytest.raises(LexicalPopulationError):
        VerifiedLexicalPopulation.from_mapping(data)

    data = manifest_data()
    data["documents"][0]["chunks"].append(deepcopy(data["documents"][0]["chunks"][0]))
    with pytest.raises(LexicalPopulationError):
        VerifiedLexicalPopulation.from_mapping(data)


def test_parsed_manifest_does_not_follow_mutation_of_input() -> None:
    data = manifest_data()
    manifest = VerifiedLexicalPopulation.from_mapping(data)
    data["documents"][0]["chunks"][0]["native_token_count"] = 99
    data["documents"].clear()

    assert manifest.validate_document("a" * 64, ("alpha", "beta"), manifest.profile) == (3, 5)


def test_repeated_content_at_distinct_positions_is_a_valid_pinned_population() -> None:
    data = manifest_data()
    data["documents"][0]["chunks"][1] = deepcopy(data["documents"][0]["chunks"][0])
    statistics = {
        "documents": data["documents"],
        "tokenizer": data["profile"]["tokenizer"],
        "tokenizer_version": data["profile"]["tokenizer_version"],
    }
    data["profile"]["statistics_digest"] = hashlib.sha256(
        json.dumps(statistics, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    data["profile"]["avg_len"] = 13 / 3
    data["profile_digest"] = LexicalProfile(**data["profile"]).digest()
    manifest = VerifiedLexicalPopulation.from_mapping(data)

    assert manifest.validate_document("a" * 64, ("alpha", "alpha"), manifest.profile) == (3, 3)
    with pytest.raises(LexicalPopulationError):
        manifest.validate_document("a" * 64, ("alpha",), manifest.profile)
    with pytest.raises(LexicalPopulationError):
        manifest.validate_document("a" * 64, ("alpha", "alpha", "alpha"), manifest.profile)


@pytest.mark.parametrize(
    "source,chunks",
    [
        ("f" * 64, ("alpha", "beta")),
        ("a" * 64, ("alpha",)),
        ("a" * 64, ("alpha", "beta", "gamma")),
        ("a" * 64, ("beta", "alpha")),
        ("a" * 64, ("Alpha", "beta")),
    ],
)
def test_document_validation_rejects_unknown_missing_extra_or_changed_chunks(
    source: str, chunks: tuple[str, ...]
) -> None:
    with pytest.raises(LexicalPopulationError):
        manifest = VerifiedLexicalPopulation.from_mapping(manifest_data())
        manifest.validate_document(source, chunks, manifest.profile)


def test_document_validation_rejects_changed_profile_before_stage() -> None:
    manifest = VerifiedLexicalPopulation.from_mapping(manifest_data())
    with pytest.raises(LexicalPopulationError):
        manifest.validate_document(
            "a" * 64,
            ("alpha", "beta"),
            LexicalProfile("other", "word", "qdrant-1.19.2", 1.2, 0.75, 5.0, STATS),
        )


def test_corpus_validation_rejects_missing_extra_and_duplicate_sources() -> None:
    manifest = VerifiedLexicalPopulation.from_mapping(manifest_data())
    for documents in (
        (("a" * 64, ("alpha", "beta")),),
        (("a" * 64, ("alpha", "beta")), ("b" * 64, ("gamma",)), ("f" * 64, ("x",))),
        (("a" * 64, ("alpha", "beta")), ("a" * 64, ("alpha", "beta"))),
    ):
        with pytest.raises(LexicalPopulationError):
            manifest.validate_corpus(documents, manifest.profile)


def test_corpus_validation_rejects_changed_profile_or_content() -> None:
    manifest = VerifiedLexicalPopulation.from_mapping(manifest_data())
    with pytest.raises(LexicalPopulationError):
        manifest.validate_corpus(
            (("a" * 64, ("alpha", "beta")), ("b" * 64, ("gamma",))),
            LexicalProfile("other", "word", "qdrant-1.19.2", 1.2, 0.75, 5.0, STATS),
        )
    with pytest.raises(LexicalPopulationError):
        manifest.validate_corpus(
            (("a" * 64, ("alpha", "beta")), ("b" * 64, ("changed",))),
            manifest.profile,
        )


def test_malformed_corpus_source_fails_closed() -> None:
    manifest = VerifiedLexicalPopulation.from_mapping(manifest_data())
    with pytest.raises(LexicalPopulationError):
        manifest.validate_corpus(
            ((["a" * 64], ("alpha", "beta")), ("b" * 64, ("gamma",))),
            manifest.profile,
        )
