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


def test_collection_body_with_dense_turboquant() -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    dense_index = QdrantSearchIndex(
        collection_name="knora_v3_hybrid",
        profile=index().profile,
        embedding_configuration=cf_config,
        turbo_quant=True,
    )
    body = dense_index.collection_body()

    assert body["shard_number"] == 1
    assert body["sparse_vectors"] == {"bm25": {"modifier": "idf"}}
    assert "dense" in body["vectors"]
    dense = body["vectors"]["dense"]
    assert dense["size"] == 1024
    assert dense["distance"] == "Cosine"
    assert dense["on_disk"] is True
    assert dense["hnsw_config"] == {"m": 16, "ef_construct": 100}
    assert dense["quantization_config"] == {
        "turbo": {
            "bits": "bits4",
            "always_ram": True,
            "rescore": True,
            "oversampling": 2.0,
        }
    }
    assert "datatype" not in dense


def test_collection_body_float32_rollback() -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    float32_index = QdrantSearchIndex(
        collection_name="knora_v3_float32",
        profile=index().profile,
        embedding_configuration=cf_config,
        turbo_quant=False,
    )
    body = float32_index.collection_body()
    assert "dense" in body["vectors"]
    assert "quantization_config" not in body["vectors"]["dense"]


def test_dense_query_body_structure_and_validation() -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    dense_index = QdrantSearchIndex(
        collection_name="knora_v3_dense",
        profile=index().profile,
        embedding_configuration=cf_config,
    )
    query_vector = [0.05] * 1024
    body = dense_index.dense_query_body(snapshot(), query_vector, limit=200)

    assert body["using"] == "dense"
    assert body["query"] == query_vector
    assert body["limit"] == 200
    assert body["with_payload"] is True
    assert body["params"] == {
        "hnsw_ef": 256,
        "quantization": {
            "rescore": True,
            "oversampling": 2.0,
        },
    }
    assert body["filter"]["must"][0] == {
        "key": "workspace_id",
        "match": {"value": "workspace-1"},
    }

    # Rejects dimension mismatch
    with pytest.raises(ValueError, match="dimension differs"):
        dense_index.dense_query_body(snapshot(), [0.1] * 768)

    # Rejects nonfinite / invalid vector
    with pytest.raises(ValueError, match="finite numbers"):
        dense_index.dense_query_body(snapshot(), [float("nan")] * 1024)

    with pytest.raises(ValueError, match="finite numbers"):
        dense_index.dense_query_body(snapshot(), [])

    # Rejects invalid limit
    with pytest.raises(ValueError, match="between one and two hundred"):
        dense_index.dense_query_body(snapshot(), query_vector, limit=0)

    with pytest.raises(ValueError, match="between one and two hundred"):
        dense_index.dense_query_body(snapshot(), query_vector, limit=201)


def test_hybrid_query_body_structure_and_validation() -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    hybrid_index = QdrantSearchIndex(
        collection_name="knora_v3_hybrid",
        profile=index().profile,
        embedding_configuration=cf_config,
    )
    query_vector = [0.05] * 1024
    body = hybrid_index.hybrid_query_body(snapshot(), "hạn mức tín dụng", query_vector)

    assert body["limit"] == 100
    assert body["with_payload"] is True
    assert body["query"] == {"fusion": "dbsf"}
    assert len(body["prefetch"]) == 2

    sparse_pf = body["prefetch"][0]
    assert sparse_pf["using"] == "bm25"
    assert sparse_pf["limit"] == 200
    assert sparse_pf["query"]["text"] == "hạn mức tín dụng"
    assert sparse_pf["filter"] == body["filter"]
    assert sparse_pf["params"] == {"idf": {"corpus": body["filter"]}}

    dense_pf = body["prefetch"][1]
    assert dense_pf["using"] == "dense"
    assert dense_pf["limit"] == 200
    assert dense_pf["query"] == query_vector
    assert dense_pf["filter"] == body["filter"]
    assert dense_pf["params"] == {
        "hnsw_ef": 256,
        "quantization": {
            "rescore": True,
            "oversampling": 2.0,
        },
    }

    # Rejects blank query text
    with pytest.raises(ValueError, match="query text is required"):
        hybrid_index.hybrid_query_body(snapshot(), "", query_vector)

    # Rejects invalid vector
    with pytest.raises(ValueError, match="finite numbers"):
        hybrid_index.hybrid_query_body(snapshot(), "hạn mức", [float("inf")] * 1024)

    # Rejects final limit > 100
    with pytest.raises(ValueError, match="between one and one hundred"):
        hybrid_index.hybrid_query_body(snapshot(), "hạn mức", query_vector, final_limit=101)


def test_stage_body_with_dense_vectors_and_validation() -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    hybrid_index = QdrantSearchIndex(
        collection_name="knora_v3_hybrid",
        profile=index().profile,
        embedding_configuration=cf_config,
    )
    gen = generation()
    texts = chunk_texts()
    vectors = {
        "chunk-1": [0.01] * 1024,
        "chunk-2": [0.02] * 1024,
    }
    body = hybrid_index.stage_body(gen, texts, vectors)
    assert len(body["points"]) == 2
    for pt in body["points"]:
        assert "bm25" in pt["vector"]
        assert "dense" in pt["vector"]
        assert len(pt["vector"]["dense"]) == 1024

    # Dimension mismatch rejected
    bad_vectors = {
        "chunk-1": [0.01] * 512,
        "chunk-2": [0.02] * 512,
    }
    with pytest.raises(LexicalGenerationError, match="dimension mismatch"):
        hybrid_index.stage_body(gen, texts, bad_vectors)

    # Nonfinite values rejected
    nan_vectors = {
        "chunk-1": [float("nan")] * 1024,
        "chunk-2": [0.02] * 1024,
    }
    with pytest.raises(LexicalGenerationError, match="invalid or nonfinite"):
        hybrid_index.stage_body(gen, texts, nan_vectors)


def test_parse_response_with_score_kind_preserves_contract() -> None:
    response = {
        "points": [
            {
                "id": lexical_point_id("generation-1", "chunk-1"),
                "score": 0.89,
                "payload": {
                    "workspace_id": "workspace-1",
                    "generation_id": "generation-1",
                    "chunk_id": "chunk-1",
                    "profile_digest": index().profile.digest(),
                },
            }
        ]
    }
    dense_res = index().parse_response(snapshot(), response, score_kind="cosine_similarity")
    assert len(dense_res) == 1
    assert dense_res[0]["score"] == 0.89
    assert dense_res[0]["score_kind"] == "cosine_similarity"

    dbsf_res = index().parse_response(snapshot(), response, score_kind="dbsf")
    assert len(dbsf_res) == 1
    assert dbsf_res[0]["score"] == 0.89
    assert dbsf_res[0]["score_kind"] == "dbsf"


def test_vectors_equivalent_rejects_degenerate_and_corrupted() -> None:
    # All zeros / degenerate vectors
    expected_tiny = [1e-6] + [0.0] * 767
    actual_zero = [0.0] * 768
    assert not QdrantSearchIndex._vectors_equivalent(actual_zero, expected_tiny)
    assert not QdrantSearchIndex._vectors_equivalent(actual_zero, actual_zero)

    # Opposite direction
    v1 = [1.0] + [0.0] * 767
    v2 = [-1.0] + [0.0] * 767
    assert not QdrantSearchIndex._vectors_equivalent(v1, v2)

    # Norm / magnitude mismatch
    v3 = [1.0] + [0.0] * 767
    v4 = [1.05] + [0.0] * 767
    assert not QdrantSearchIndex._vectors_equivalent(v3, v4)

    # Non-finite values
    v_nan = [float("nan")] + [0.0] * 767
    assert not QdrantSearchIndex._vectors_equivalent(v_nan, v1)
    assert not QdrantSearchIndex._vectors_equivalent(v1, v_nan)

    # Length mismatch
    assert not QdrantSearchIndex._vectors_equivalent([1.0] * 10, [1.0] * 11)

    # Valid normalized unit vector with float32 roundtrip error within tolerance
    norm_vec = [1.0 / math.sqrt(768)] * 768
    slight_diff = [(1.0 / math.sqrt(768)) + 1e-6] * 768
    assert QdrantSearchIndex._vectors_equivalent(norm_vec, slight_diff)
