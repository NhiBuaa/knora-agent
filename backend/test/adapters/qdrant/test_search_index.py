from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from dataclasses import replace

import pytest

from knora.adapters.qdrant.search_index import (
    AuthorizedLexicalSnapshot,
    ProjectionResponseError,
    QdrantSearchIndex,
)
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalGenerationError,
    LexicalProfile,
    StageReceipt,
    lexical_point_id,
)


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


def _query_point(chunk_id: str, score: float) -> dict:
    return {
        "id": lexical_point_id("generation-1", chunk_id),
        "score": score,
        "payload": {
            "workspace_id": "workspace-1",
            "generation_id": "generation-1",
            "chunk_id": chunk_id,
            "profile_digest": index().profile.digest(),
        },
    }


def test_complete_native_population_canonicalizes_ties_after_score_validation() -> None:
    parsed = index().parse_response(
        snapshot(),
        {
            "points": [
                _query_point("chunk-z", 2),
                _query_point("chunk-a", 2),
                _query_point("chunk-m", 1),
            ]
        },
    )

    assert [(hit["chunk_id"], hit["rank"]) for hit in parsed] == [
        ("chunk-a", 1),
        ("chunk-z", 2),
        ("chunk-m", 3),
    ]


def test_full_native_population_preserves_tie_order_at_unknown_boundary() -> None:
    chunk_ids = [f"chunk-{i:03d}" for i in range(200, 0, -1)]
    parsed = index().parse_response(
        snapshot(), {"points": [_query_point(chunk_id, 2) for chunk_id in chunk_ids]}
    )

    assert len(parsed) == 200
    assert [(hit["chunk_id"], hit["rank"]) for hit in parsed[:2]] == [
        ("chunk-200", 1),
        ("chunk-199", 2),
    ]
    assert [(hit["chunk_id"], hit["rank"]) for hit in parsed[-2:]] == [
        ("chunk-002", 199),
        ("chunk-001", 200),
    ]


@pytest.mark.parametrize(
    "limit,expected", [(2, ["chunk-z", "chunk-a"]), (3, ["chunk-a", "chunk-z"])]
)
def test_tie_completeness_uses_requested_window(limit, expected) -> None:
    parsed = index().parse_response(
        snapshot(),
        {"points": [_query_point("chunk-z", 2), _query_point("chunk-a", 2)]},
        limit=limit,
    )
    assert [hit["chunk_id"] for hit in parsed] == expected


def test_response_cannot_exceed_requested_window() -> None:
    with pytest.raises(ProjectionResponseError):
        index().parse_response(
            snapshot(),
            {"points": [_query_point("chunk-z", 2), _query_point("chunk-a", 2)]},
            limit=1,
        )


@pytest.mark.parametrize(
    "points",
    [
        [_query_point("chunk-z", 1), _query_point("chunk-a", 2)],
        [_query_point("chunk-a", 2), _query_point("chunk-a", 1)],
    ],
)
def test_native_population_rejects_score_disorder_and_duplicate_chunks(points) -> None:
    with pytest.raises(ProjectionResponseError):
        index().parse_response(snapshot(), {"points": points})


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


def generation() -> LexicalGeneration:
    return LexicalGeneration(
        generation_id="generation-1",
        workspace_id="workspace-1",
        document_id="document-1",
        document_version_id="version-1",
        chunk_set_id="chunk-set-1",
        lexical_profile=index().profile,
        revision=1,
        chunks=(
            LexicalChunk("chunk-1", 0, hashlib.sha256("ＰＤＦ HẠN MỨC".encode()).hexdigest()),
            LexicalChunk("chunk-2", 1, hashlib.sha256(b"running run the").hexdigest()),
        ),
    )


def chunk_texts() -> dict[str, str]:
    return {"chunk-1": "ＰＤＦ HẠN MỨC", "chunk-2": "running run the"}


def persisted_points() -> list[dict]:
    requested = generation()
    return [
        {
            "id": lexical_point_id("generation-1", chunk.chunk_id),
            "payload": {
                "workspace_id": "workspace-1",
                "generation_id": "generation-1",
                "chunk_id": chunk.chunk_id,
                "profile_id": "bm25-unicode-word-v1",
                "profile_digest": index().profile.digest(),
                "content_checksum": chunk.content_checksum,
                "content_digest": requested.content_digest(),
            },
        }
        for chunk in requested.chunks
    ]


def test_stage_emits_native_documents_with_query_profile_and_identity_only_payload() -> None:
    requested = generation()
    body = index().stage_body(requested, chunk_texts())

    assert len(body["points"]) == 2
    for point, expected, text in zip(
        body["points"], persisted_points(), ("pdf hạn mức", "running run the"), strict=True
    ):
        assert point["id"] == expected["id"]
        assert point["payload"] == expected["payload"]
        document = point["vector"]["bm25"]
        assert document == index().query_body(snapshot(), text)["query"]
        assert document["text"] == text


def test_collection_and_persisted_point_readback_have_bounded_native_wire_shapes() -> None:
    assert index().collection_body() == {
        "vectors": {},
        "sparse_vectors": {"bm25": {"modifier": "idf"}},
        "shard_number": 1,
    }
    assert index().persisted_points_body(generation()) == {
        "ids": list(generation().point_ids()),
        "with_payload": True,
        "with_vector": False,
    }


def test_payload_keyword_indexes_cover_query_and_idf_filters_without_shared_mutation() -> None:
    adapter = index()
    expected = (
        {
            "field_name": "workspace_id",
            "field_schema": {"type": "keyword", "is_tenant": True},
        },
        {"field_name": "generation_id", "field_schema": "keyword"},
        {"field_name": "profile_digest", "field_schema": "keyword"},
    )
    bodies = adapter.payload_index_bodies()

    assert bodies == expected
    query = adapter.query_body(snapshot(), "hạn mức")
    index_fields = sorted(body["field_name"] for body in bodies)
    for scope in (query["filter"], query["params"]["idf"]["corpus"]):
        assert index_fields == sorted(condition["key"] for condition in scope["must"])

    bodies[0]["field_schema"]["is_tenant"] = False
    bodies[1]["field_name"] = "foreign"
    bodies[2]["field_schema"] = "integer"
    assert adapter.payload_index_bodies() == expected


@pytest.mark.parametrize(
    "texts",
    [
        {},
        {"chunk-1": "ＰＤＦ HẠN MỨC"},
        {**chunk_texts(), "foreign": "extra"},
        {**chunk_texts(), "chunk-1": "pdf hạn mức"},
        {**chunk_texts(), "chunk-1": ""},
        {**chunk_texts(), "chunk-1": None},
        None,
    ],
)
def test_stage_rejects_missing_foreign_or_checksum_mismatched_authoritative_text(
    texts: dict,
) -> None:
    with pytest.raises(LexicalGenerationError):
        index().stage_body(generation(), texts)


@pytest.mark.parametrize("mutation", ["profile", "65_points"])
def test_stage_and_readback_reject_profile_mismatch_or_oversized_generation(mutation: str) -> None:
    requested = generation()
    if mutation == "profile":
        requested = replace(requested, lexical_profile=replace(index().profile, avg_len=256.0))
    else:
        requested = replace(
            requested,
            chunks=tuple(LexicalChunk(f"chunk-{i}", i, "checksum") for i in range(65)),
        )
    with pytest.raises(LexicalGenerationError):
        index().stage_body(requested, chunk_texts())
    with pytest.raises(LexicalGenerationError):
        index().persisted_points_body(requested)
    with pytest.raises(LexicalGenerationError):
        index().parse_stage_response(requested, persisted_points())


def test_stage_receipt_requires_complete_persisted_identity_and_digest_readback() -> None:
    requested = generation()
    receipt = index().parse_stage_response(requested, list(reversed(persisted_points())))

    assert receipt == StageReceipt("generation-1", 2, requested.content_digest())
    receipt.validate(requested)


@pytest.mark.parametrize(
    "mutation",
    [
        "http_success",
        "empty",
        "partial",
        "duplicate",
        "extra",
        "malformed_point",
        "malformed_id",
        "missing_payload",
        "workspace_id",
        "generation_id",
        "chunk_id",
        "profile_id",
        "profile_digest",
        "content_checksum",
        "content_digest",
        "id",
    ],
)
def test_stage_readback_fails_closed_without_complete_persisted_manifest(mutation: str) -> None:
    points = persisted_points()
    if mutation == "http_success":
        points = {"status": "ok", "result": {"status": "completed", "operation_id": 1}}
    elif mutation == "empty":
        points = []
    elif mutation == "partial":
        points.pop()
    elif mutation == "duplicate":
        points[1] = deepcopy(points[0])
    elif mutation == "extra":
        points.append(deepcopy(points[0]))
    elif mutation == "malformed_point":
        points[0] = None
    elif mutation == "malformed_id":
        points[0]["id"] = []
    elif mutation == "missing_payload":
        points[0].pop("payload")
    elif mutation == "id":
        points[0]["id"] = lexical_point_id("other", "chunk-1")
    else:
        points[0]["payload"][mutation] = "foreign"
    with pytest.raises(ProjectionResponseError):
        index().parse_stage_response(generation(), points)
