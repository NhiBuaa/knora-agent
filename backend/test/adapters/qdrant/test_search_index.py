from __future__ import annotations

import math

import pytest

from knora.adapters.qdrant.search_index import (
    AuthorizedLexicalSnapshot,
    NativeBm25Profile,
    ProjectionResponseError,
    QdrantSearchIndex,
)


def snapshot() -> AuthorizedLexicalSnapshot:
    return AuthorizedLexicalSnapshot(
        workspace_id="workspace-1",
        generation_ids=("generation-1", "generation-2"),
        profile_id="bm25-unicode-multilingual-v1",
    )


def index() -> QdrantSearchIndex:
    return QdrantSearchIndex(
        collection_name="knora_s2",
        profile=NativeBm25Profile(
            id="bm25-unicode-multilingual-v1",
            tokenizer="multilingual",
            tokenizer_version="qdrant-native-v1",
            k1=1.2,
            b=0.75,
            avg_len=128.0,
            statistics_digest="stats-1",
        ),
    )


def test_query_has_raw_bm25_and_separate_authorized_idf_scope() -> None:
    body = index().query_body(snapshot(), "hạn mức", limit=200)

    assert body["limit"] == 200
    assert "score_threshold" not in body
    assert body["query"] == {
        "text": "hạn mức",
        "model": "qdrant/bm25",
        "options": {
            "k": 1.2,
            "b": 0.75,
            "avg_len": 128.0,
            "tokenizer": "multilingual",
            "lowercase": True,
            "ascii_folding": False,
            "stemmer": {"type": "none"},
            "stopwords": {},
        },
    }
    assert body["filter"] != body["params"]["idf"]["corpus"]
    assert body["filter"]["must"][0] == {
        "key": "workspace_id",
        "match": {"value": "workspace-1"},
    }
    assert body["params"]["idf"]["corpus"]["must"][0]["key"] == "generation_id"


def test_parse_preserves_raw_scores_and_rejects_foreign_or_nonfinite_points() -> None:
    response = {
        "points": [
            {
                "id": "point-1",
                "score": 3.25,
                "payload": {
                    "workspace_id": "workspace-1",
                    "generation_id": "generation-1",
                    "chunk_id": "chunk-1",
                },
            }
        ]
    }

    assert index().parse_response(snapshot(), response) == (
        {
            "point_id": "point-1",
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
    with pytest.raises(ProjectionResponseError):
        NativeBm25Profile.from_native_token_counts(
            id="bm25-unicode-multilingual-v1",
            tokenizer="multilingual",
            tokenizer_version="qdrant-native-v1",
            k1=1.2,
            b=0.75,
            token_counts=(),
            statistics_digest="stats-1",
        )

    profile = NativeBm25Profile.from_native_token_counts(
        id="bm25-unicode-multilingual-v1",
        tokenizer="multilingual",
        tokenizer_version="qdrant-native-v1",
        k1=1.2,
        b=0.75,
        token_counts=(120, 136),
        statistics_digest="stats-1",
    )
    assert profile.avg_len == 128.0
