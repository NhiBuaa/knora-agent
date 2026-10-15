from __future__ import annotations

import math
from copy import deepcopy

import pytest

from knora.adapters.qdrant.search_index import (
    AuthorizedLexicalSnapshot,
    ProjectionResponseError,
    QdrantSearchIndex,
)
from knora.ingestion.search_indexing import LexicalGenerationError, LexicalProfile, lexical_point_id


def snapshot() -> AuthorizedLexicalSnapshot:
    return AuthorizedLexicalSnapshot(
        workspace_id="workspace-1",
        generation_ids=("generation-1", "generation-2"),
        profile_id="bm25-unicode-word-v1",
        profile_digest=index().profile.digest(),
    )


def index() -> QdrantSearchIndex:
    return QdrantSearchIndex(
        collection_name="knora_s2",
        profile=LexicalProfile(
            id="bm25-unicode-word-v1",
            tokenizer="word",
            tokenizer_version="qdrant-1.19.2-rust1.98.1",
            k1=1.2,
            b=0.75,
            avg_len=128.0,
            statistics_digest="stats-1",
        ),
    )


def test_query_has_raw_bm25_and_separate_authorized_idf_scope() -> None:
    body = index().query_body(snapshot(), "hạn mức", limit=200)

    assert body["limit"] == 200
    assert body["using"] == "bm25"
    assert "score_threshold" not in body
    assert body["query"] == {
        "text": "hạn mức",
        "model": "qdrant/bm25",
        "options": {
            "k": 1.2,
            "b": 0.75,
            "avg_len": 128.0,
            "tokenizer": "word",
            "lowercase": True,
            "ascii_folding": False,
            "stemmer": {"type": "none"},
            "stopwords": {},
        },
    }
    assert body["filter"] == body["params"]["idf"]["corpus"]
    assert body["filter"]["must"][0] == {
        "key": "workspace_id",
        "match": {"value": "workspace-1"},
    }
    assert body["params"]["idf"]["corpus"]["must"][0]["key"] == "workspace_id"


def test_query_normalizes_compatibility_characters_without_dropping_accents() -> None:
    body = index().query_body(snapshot(), "ＰＤＦ HẠN MỨC")
    assert body["query"]["text"] == "pdf hạn mức"


def test_parse_preserves_raw_scores_and_rejects_foreign_or_nonfinite_points() -> None:
    response = {
        "points": [
            {
                "id": lexical_point_id("generation-1", "chunk-1"),
                "score": 3.25,
                "payload": {
                    "workspace_id": "workspace-1",
                    "generation_id": "generation-1",
                    "chunk_id": "chunk-1",
                    "profile_digest": index().profile.digest(),
                },
            }
        ]
    }

    assert index().parse_response(snapshot(), response) == (
        {
            "point_id": lexical_point_id("generation-1", "chunk-1"),
            "score_policy_digest": index().profile.digest(),
            "score": 3.25,
            "rank": 1,
            "generation_id": "generation-1",
            "chunk_id": "chunk-1",
        },
    )

    foreign = {
        "points": [
            {
                "id": "point-2",
                "score": 2.0,
                "payload": {
                    "workspace_id": "other",
                    "generation_id": "generation-1",
                    "chunk_id": "chunk-2",
                },
            }
        ]
    }
    with pytest.raises(ProjectionResponseError):
        index().parse_response(snapshot(), foreign)

    nonfinite = {
        "points": [
            {
                "id": "point-3",
                "score": math.nan,
                "payload": {
                    "workspace_id": "workspace-1",
                    "generation_id": "generation-1",
                    "chunk_id": "chunk-3",
                },
            }
        ]
    }
    with pytest.raises(ProjectionResponseError):
        index().parse_response(snapshot(), nonfinite)


def test_profile_requires_measured_native_token_counts() -> None:
    with pytest.raises(LexicalGenerationError):
        LexicalProfile.from_native_token_counts(
            id="bm25-unicode-word-v1",
            tokenizer="word",
            tokenizer_version="qdrant-1.19.2-rust1.98.1",
            k1=1.2,
            b=0.75,
            token_counts=(),
            statistics_digest="stats-1",
        )

    profile = LexicalProfile.from_native_token_counts(
        id="bm25-unicode-word-v1",
        tokenizer="word",
        tokenizer_version="qdrant-1.19.2-rust1.98.1",
        k1=1.2,
        b=0.75,
        token_counts=(120, 136),
        statistics_digest="stats-1",
    )
    assert profile.avg_len == 128.0


def test_snapshot_profile_must_match_before_query_or_response() -> None:
    from dataclasses import replace

    wrong = replace(snapshot(), profile_digest="stale")
    with pytest.raises(ProjectionResponseError):
        index().query_body(wrong, "hạn mức")
    with pytest.raises(ProjectionResponseError):
        index().parse_response(wrong, {"points": []})


@pytest.mark.parametrize("mutation", ["profile", "point_id", "duplicate", "too_many", "order"])
def test_malformed_projection_fails_closed(mutation: str) -> None:
    from knora.ingestion.search_indexing import lexical_point_id

    point = {
        "id": lexical_point_id("generation-1", "chunk-1"),
        "score": 3.25,
        "payload": {
            "workspace_id": "workspace-1",
            "generation_id": "generation-1",
            "chunk_id": "chunk-1",
            "profile_digest": index().profile.digest(),
        },
    }
    response = {"points": [point]}
    if mutation == "profile":
        point["payload"]["profile_digest"] = "stale"
    elif mutation == "point_id":
        point["id"] = "arbitrary-id"
    elif mutation == "duplicate":
        response["points"].append(deepcopy(point))
    elif mutation == "too_many":
        response["points"] *= 201
    else:
        second = deepcopy(point)
        second["score"] = 4
        response["points"].append(second)
    with pytest.raises(ProjectionResponseError):
        index().parse_response(snapshot(), response)
