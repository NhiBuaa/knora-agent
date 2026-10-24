from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import (
    AuthorizedLexicalSnapshot,
    ProjectionResponseError,
    QdrantSearchIndex,
)
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalProfile,
    LexicalProjectionUnavailable,
    lexical_point_id,
)


@pytest.fixture
def wire() -> QdrantSearchIndex:
    return QdrantSearchIndex(
        "knora_s2",
        LexicalProfile("word-v1", "word", "qdrant-1.19.2", 1.2, 0.75, 2.0, "stats"),
    )


@pytest.fixture
def generation(wire) -> LexicalGeneration:
    return LexicalGeneration(
        "generation",
        "workspace",
        "document",
        "version",
        "chunkset",
        wire.profile,
        1,
        (LexicalChunk("chunk", 0, hashlib.sha256("hạn mức".encode()).hexdigest()),),
    )


def test_stage_requires_completed_upsert_and_full_persisted_readback(wire, generation) -> None:
    requests = []

    def serve(request):
        requests.append(request)
        if request.method == "PUT":
            assert request.url.params["wait"] == "true"
            assert json.loads(request.content) == wire.stage_body(generation, {"chunk": "hạn mức"})
            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})
        assert request.method == "POST"
        assert json.loads(request.content) == wire.persisted_points_body(generation)
        points = wire.stage_body(generation, {"chunk": "hạn mức"})["points"]
        for point in points:
            point.pop("vector")
        return httpx.Response(200, json={"status": "ok", "result": points})

    client = httpx.Client(base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve))
    try:
        receipt = NativeQdrantSearchIndex(index=wire, client=client).stage_generation(
            generation, {"chunk": "hạn mức"}
        )
        receipt.validate(generation)
        assert len(requests) == 2
    finally:
        client.close()


@pytest.mark.parametrize("result", [{"status": "acknowledged"}, {"status": "failed"}, {}, None])
def test_stage_never_reads_back_or_receipts_an_incomplete_upsert(wire, generation, result) -> None:
    requests = []

    def serve(request):
        requests.append(request)
        if request.method == "PUT":
            return httpx.Response(200, json={"status": "ok", "result": result})
        points = wire.stage_body(generation, {"chunk": "hạn mức"})["points"]
        return httpx.Response(200, json={"status": "ok", "result": points})

    with (
        httpx.Client(
            base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
        ) as client,
        pytest.raises(ProjectionResponseError),
    ):
        NativeQdrantSearchIndex(index=wire, client=client).stage_generation(
            generation, {"chunk": "hạn mức"}
        )
    assert len(requests) == 1


@pytest.mark.parametrize("status", [307, 400, 401, 404, 408, 409, 429, 500, 503, 600])
def test_query_classifies_status_without_retry_or_empty_evidence(wire, status) -> None:
    requests = []

    def serve(request):
        requests.append(request)
        return httpx.Response(status, json={"status": {"error": "sensitive detail"}})

    client = httpx.Client(base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve))
    adapter = NativeQdrantSearchIndex(index=wire, client=client)
    snapshot = AuthorizedLexicalSnapshot(
        "workspace", ("generation",), wire.profile.id, wire.profile.digest()
    )
    expected = (
        LexicalProjectionUnavailable
        if status in {408, 429} or 500 <= status < 600
        else ProjectionResponseError
    )
    try:
        with pytest.raises(expected) as error:
            adapter.query(snapshot, "hạn mức")
        assert "sensitive" not in str(error.value)
        assert len(requests) == 1
    finally:
        client.close()


@pytest.mark.parametrize(
    "fault",
    ["timeout", "connect", "protocol", "proxy", "gzip", "json", "result", "status", "error-null"],
)
def test_transport_and_malformed_responses_stay_distinct(wire, fault) -> None:
    requests = []

    def serve(request):
        requests.append(request)
        if fault == "timeout":
            raise httpx.ReadTimeout("private", request=request)
        if fault == "connect":
            raise httpx.ConnectError("private", request=request)
        if fault == "protocol":
            raise httpx.RemoteProtocolError("private", request=request)
        if fault == "proxy":
            raise httpx.ProxyError("private", request=request)
        if fault == "gzip":
            return httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                stream=httpx.ByteStream(b"private invalid gzip"),
            )
        if fault == "json":
            return httpx.Response(200, text="private non-json")
        if fault == "status":
            return httpx.Response(
                200, json={"status": {"error": "private"}, "result": {"points": []}}
            )
        if fault == "error-null":
            return httpx.Response(200, json={"status": {"error": None}, "result": {"points": []}})
        return httpx.Response(200, json={"status": "ok", "result": []})

    client = httpx.Client(base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve))
    snapshot = AuthorizedLexicalSnapshot(
        "workspace", ("generation",), wire.profile.id, wire.profile.digest()
    )
    expected = (
        LexicalProjectionUnavailable
        if fault in {"timeout", "connect", "protocol", "proxy"}
        else ProjectionResponseError
    )
    try:
        with pytest.raises(expected) as error:
            NativeQdrantSearchIndex(index=wire, client=client).query(snapshot, "hạn mức")
        assert "private" not in str(error.value)
        assert len(requests) == 1
    finally:
        client.close()


def test_query_uses_native_wire_and_preserves_the_single_returned_population(wire) -> None:
    snapshot = AuthorizedLexicalSnapshot(
        "workspace", ("generation",), wire.profile.id, wire.profile.digest()
    )
    requests = []

    def serve(request):
        requests.append(request)
        assert request.url.path == "/collections/knora_s2/points/query"
        assert json.loads(request.content) == wire.query_body(snapshot, "ＰＤＦ HẠN MỨC", limit=8)
        return httpx.Response(200, json={"status": "ok", "result": {"points": []}})

    client = httpx.Client(base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve))
    try:
        assert (
            NativeQdrantSearchIndex(index=wire, client=client).query(
                snapshot, "ＰＤＦ HẠN MỨC", limit=8
            )
            == ()
        )
        assert len(requests) == 1
    finally:
        client.close()


def test_collection_setup_is_replayable_and_marks_only_workspace_as_tenant(wire) -> None:
    requests = []
    exists = False

    def serve(request):
        nonlocal exists
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.url.path.endswith("/exists"):
            result = {"exists": exists}
        elif request.method == "GET":
            result = {"config": {"params": wire.collection_body()}}
        elif request.url.path.endswith("/index"):
            assert request.url.params["wait"] == "true"
            result = {"status": "completed", "operation_id": 1}
        elif exists:
            return httpx.Response(409, json={"status": {"error": "already exists"}})
        else:
            exists = True
            result = True
        return httpx.Response(200, json={"status": "ok", "result": result})

    client = httpx.Client(base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve))
    try:
        adapter = NativeQdrantSearchIndex(index=wire, client=client)
        adapter.ensure_collection()
        assert len(requests) == 6
        adapter.ensure_collection()
        assert len(requests) == 11
    finally:
        client.close()
    creates = [item for item in requests if item[0:2] == ("PUT", "/collections/knora_s2")]
    assert len(creates) == 1
    indexes = [item[2] for item in requests if item[1].endswith("/index")]
    assert len(indexes) == 6
    assert indexes[0] == {
        "field_name": "workspace_id",
        "field_schema": {"type": "keyword", "is_tenant": True},
    }
    assert indexes[1:3] == [
        {"field_name": "generation_id", "field_schema": "keyword"},
        {"field_name": "profile_digest", "field_schema": "keyword"},
    ]


@pytest.mark.parametrize(
    "params",
    [
        None,
        {},
        {
            "vectors": {"dense": {"size": 3, "distance": "Cosine"}},
            "sparse_vectors": {"bm25": {"modifier": "idf"}},
            "shard_number": 1,
        },
        {"vectors": {}, "sparse_vectors": {"bm25": {}}, "shard_number": 1},
        {"vectors": {}, "sparse_vectors": {"bm25": {"modifier": "idf"}}, "shard_number": 2},
    ],
)
def test_collection_setup_rejects_incompatible_config_before_index_writes(wire, params) -> None:
    writes = []

    def serve(request):
        if request.method != "GET":
            writes.append(request)
            result = {"status": "completed"}
        elif request.url.path.endswith("/exists"):
            result = {"exists": True}
        else:
            result = {"config": {"params": params}}
        return httpx.Response(200, json={"status": "ok", "result": result})

    with (
        httpx.Client(
            base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
        ) as client,
        pytest.raises(ProjectionResponseError),
    ):
        NativeQdrantSearchIndex(index=wire, client=client).ensure_collection()
    assert writes == []


@pytest.mark.parametrize(
    "error_type", [httpx.UnsupportedProtocol, httpx.LocalProtocolError, httpx.InvalidURL]
)
def test_invalid_transport_configuration_is_terminal(wire, error_type) -> None:
    def serve(request):
        raise error_type("private configuration")

    snapshot = AuthorizedLexicalSnapshot(
        "workspace", ("generation",), wire.profile.id, wire.profile.digest()
    )
    with (
        httpx.Client(
            base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
        ) as client,
        pytest.raises(ProjectionResponseError) as error,
    ):
        NativeQdrantSearchIndex(index=wire, client=client).query(snapshot, "hạn mức")
    assert "private" not in str(error.value)


@pytest.mark.parametrize("fault", ["exists", "creation", "index"])
def test_collection_setup_requires_valid_acknowledgements(wire, fault) -> None:
    requests = []

    def serve(request):
        requests.append(request)
        if request.url.path.endswith("/exists"):
            result = {"exists": "false"} if fault == "exists" else {"exists": False}
        elif request.method == "GET":
            result = {"config": {"params": wire.collection_body()}}
        elif request.url.path.endswith("/index"):
            result = {"status": "acknowledged"}
        else:
            result = fault != "creation"
        return httpx.Response(200, json={"status": "ok", "result": result})

    with (
        httpx.Client(
            base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
        ) as client,
        pytest.raises(ProjectionResponseError),
    ):
        NativeQdrantSearchIndex(index=wire, client=client).ensure_collection()
    assert len(requests) == {"exists": 1, "creation": 2, "index": 4}[fault]


@pytest.mark.parametrize("fault", ["outage", "missing", "foreign"])
def test_stage_receipt_requires_trusted_persisted_readback(wire, generation, fault) -> None:
    requests = []

    def serve(request):
        requests.append(request)
        if request.method == "PUT":
            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})
        if fault == "outage":
            return httpx.Response(503)
        points = wire.stage_body(generation, {"chunk": "hạn mức"})["points"]
        if fault == "foreign":
            points[0]["payload"]["workspace_id"] = "foreign-workspace"
        return httpx.Response(
            200, json={"status": "ok", "result": [] if fault == "missing" else points}
        )

    with httpx.Client(
        base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
    ) as client:
        expected = LexicalProjectionUnavailable if fault == "outage" else ProjectionResponseError
        with pytest.raises(expected):
            NativeQdrantSearchIndex(index=wire, client=client).stage_generation(
                generation, {"chunk": "hạn mức"}
            )
    assert len(requests) == 2


def test_query_rejects_redirect_without_following_it(wire) -> None:
    requests = []

    def serve(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(307, headers={"location": "http://other-host/points"})
        return httpx.Response(200, json={"status": "ok", "result": {"points": []}})

    snapshot = AuthorizedLexicalSnapshot(
        "workspace", ("generation",), wire.profile.id, wire.profile.digest()
    )
    with (
        httpx.Client(
            base_url="http://127.0.0.1:16433",
            transport=httpx.MockTransport(serve),
            follow_redirects=True,
        ) as client,
        pytest.raises(ProjectionResponseError),
    ):
        NativeQdrantSearchIndex(index=wire, client=client).query(snapshot, "hạn mức")
    assert len(requests) == 1


def test_remove_generation_deletes_only_its_point_ids_idempotently(wire, generation):
    requests = []

    def serve(request):
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/collections/knora_s2/points/delete"
        assert request.url.params["wait"] == "true"
        assert json.loads(request.content) == {"points": list(generation.point_ids())}
        return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})

    with httpx.Client(
        base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
    ) as client:
        index = NativeQdrantSearchIndex(index=wire, client=client)
        index.remove_generation(generation)
        index.remove_generation(generation)
    assert len(requests) == 2


@pytest.mark.parametrize("status", ["acknowledged", "wait_timeout", None])
def test_remove_generation_requires_completed_response(wire, generation, status):
    with httpx.Client(
        base_url="http://127.0.0.1:16433",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "ok", "result": {"status": status}})
        ),
    ) as client:
        index = NativeQdrantSearchIndex(index=wire, client=client)
        with pytest.raises(ProjectionResponseError):
            index.remove_generation(generation)


def test_query_dense_calls_native_wire_and_parses_cosine_scores(wire) -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    dense_wire = QdrantSearchIndex(
        "knora_v3_dense",
        wire.profile,
        embedding_configuration=cf_config,
    )
    snapshot = AuthorizedLexicalSnapshot(
        "workspace", ("generation",), wire.profile.id, wire.profile.digest()
    )
    requests = []

    def serve(request):
        requests.append(request)
        assert request.url.path == "/collections/knora_v3_dense/points/query"
        body = json.loads(request.content)
        assert body["using"] == "dense"
        assert body["limit"] == 200
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "result": {
                    "points": [
                        {
                            "id": lexical_point_id("generation", "chunk"),
                            "score": 0.88,
                            "payload": {
                                "workspace_id": "workspace",
                                "generation_id": "generation",
                                "chunk_id": "chunk",
                                "profile_digest": wire.profile.digest(),
                            },
                        }
                    ]
                },
            },
        )

    with httpx.Client(
        base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
    ) as client:
        adapter = NativeQdrantSearchIndex(index=dense_wire, client=client)
        points = adapter.query_dense(snapshot, [0.05] * 1024, limit=200)
        assert len(points) == 1
        assert points[0]["score"] == 0.88
        assert points[0]["score_kind"] == "cosine_similarity"
    assert len(requests) == 1


def test_query_hybrid_calls_native_wire_with_dbsf_fusion(wire) -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    hybrid_wire = QdrantSearchIndex(
        "knora_v3_hybrid",
        wire.profile,
        embedding_configuration=cf_config,
    )
    snapshot = AuthorizedLexicalSnapshot(
        "workspace", ("generation",), wire.profile.id, wire.profile.digest()
    )
    requests = []

    def serve(request):
        requests.append(request)
        assert request.url.path == "/collections/knora_v3_hybrid/points/query"
        body = json.loads(request.content)
        assert body["query"] == {"fusion": "dbsf"}
        assert len(body["prefetch"]) == 2
        assert body["prefetch"][0]["using"] == "bm25"
        assert body["prefetch"][1]["using"] == "dense"
        assert body["limit"] == 100
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "result": {
                    "points": [
                        {
                            "id": lexical_point_id("generation", "chunk"),
                            "score": 0.95,
                            "payload": {
                                "workspace_id": "workspace",
                                "generation_id": "generation",
                                "chunk_id": "chunk",
                                "profile_digest": wire.profile.digest(),
                            },
                        }
                    ]
                },
            },
        )

    with httpx.Client(
        base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
    ) as client:
        adapter = NativeQdrantSearchIndex(index=hybrid_wire, client=client)
        points = adapter.query_hybrid(snapshot, "hạn mức", [0.05] * 1024, final_limit=100)
        assert len(points) == 1
        assert points[0]["score"] == 0.95
        assert points[0]["score_kind"] == "dbsf"
    assert len(requests) == 1


def test_ensure_collection_validates_dense_named_vector(wire) -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    dense_wire = QdrantSearchIndex(
        "knora_v3_dense",
        wire.profile,
        embedding_configuration=cf_config,
    )

    def serve_compatible(request):
        if request.url.path == "/collections/knora_v3_dense/exists":
            return httpx.Response(200, json={"status": "ok", "result": {"exists": True}})
        if request.url.path == "/collections/knora_v3_dense":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "result": {
                        "config": {
                            "params": {
                                "shard_number": 1,
                                "vectors": {
                                    "dense": {
                                        "size": 1024,
                                        "distance": "Cosine",
                                        "datatype": "float32",
                                        "on_disk": True,
                                        "hnsw_config": {"m": 16, "ef_construct": 100},
                                        "quantization_config": {
                                            "turbo": {"bits": "bits4", "always_ram": True}
                                        },
                                    }
                                },
                                "sparse_vectors": {"bm25": {"modifier": "idf"}},
                            }
                        }
                    },
                },
            )
        if "/index" in request.url.path:
            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with httpx.Client(
        base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve_compatible)
    ) as client:
        adapter = NativeQdrantSearchIndex(index=dense_wire, client=client)
        adapter.ensure_collection()

    # Incompatible: missing dense vector in server response
    def serve_missing_dense(request):
        if request.url.path == "/collections/knora_v3_dense/exists":
            return httpx.Response(200, json={"status": "ok", "result": {"exists": True}})
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "result": {
                    "config": {
                        "params": {
                            "shard_number": 1,
                            "vectors": {},
                            "sparse_vectors": {"bm25": {"modifier": "idf"}},
                        }
                    }
                },
            },
        )

    with (
        httpx.Client(
            base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve_missing_dense)
        ) as client,
        pytest.raises(ProjectionResponseError, match="incompatible"),
    ):
        adapter = NativeQdrantSearchIndex(index=dense_wire, client=client)
        adapter.ensure_collection()


def test_stage_generation_with_dense_vectors(wire, generation) -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    cf_config = EmbeddingConfiguration.cloudflare_qwen3_06b()
    hybrid_wire = QdrantSearchIndex(
        "knora_v3_hybrid",
        wire.profile,
        embedding_configuration=cf_config,
    )
    requests = []

    def serve(request):
        requests.append(request)
        if request.method == "PUT":
            assert request.url.params["wait"] == "true"
            body = json.loads(request.content)
            assert "dense" in body["points"][0]["vector"]
            assert len(body["points"][0]["vector"]["dense"]) == 1024
            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})
        assert request.method == "POST"
        points = hybrid_wire.stage_body(generation, {"chunk": "hạn mức"}, {"chunk": [0.01] * 1024})[
            "points"
        ]
        for point in points:
            point["vector"] = {"dense": point["vector"]["dense"]}
        return httpx.Response(200, json={"status": "ok", "result": points})

    with httpx.Client(
        base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(serve)
    ) as client:
        adapter = NativeQdrantSearchIndex(index=hybrid_wire, client=client)
        receipt = adapter.stage_generation(
            generation, {"chunk": "hạn mức"}, {"chunk": [0.01] * 1024}
        )
        receipt.validate(generation)
        assert len(requests) == 2


@pytest.mark.parametrize(
    "actual_dense",
    [
        {
            "size": 768,
            "distance": "Dot",
            "datatype": "float16",
            "on_disk": False,
            "hnsw_config": {"m": 0, "ef_construct": 4},
            "quantization_config": None,
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float16",
            "on_disk": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            "quantization_config": {"turbo": {"bits": "bits4", "always_ram": True}},
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "uint8",
            "on_disk": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            "quantization_config": {"turbo": {"bits": "bits4", "always_ram": True}},
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float32",
            "on_disk": False,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            "quantization_config": {"turbo": {"bits": "bits4", "always_ram": True}},
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float32",
            "on_disk": True,
            "hnsw_config": {"m": 0, "ef_construct": 4},
            "quantization_config": {"turbo": {"bits": "bits4", "always_ram": True}},
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float32",
            "on_disk": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            "quantization_config": None,
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float32",
            "on_disk": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            # missing quantization_config entirely
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float32",
            "on_disk": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            "quantization_config": {"scalar": {"type": "int8", "always_ram": False}},
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float32",
            "on_disk": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            "quantization_config": {"turbo": {"bits": None, "always_ram": True}},
        },
        {
            "size": 768,
            "distance": "Cosine",
            "datatype": "float32",
            "on_disk": True,
            "hnsw_config": {"m": 16, "ef_construct": 100},
            "quantization_config": {"turbo": {"bits": "bits4", "always_ram": False}},
        },
    ],
)
def test_ensure_collection_rejects_incompatible_dense_readback(wire, actual_dense) -> None:
    from knora.providers.embedding import EmbeddingConfiguration

    dense_wire = QdrantSearchIndex(
        "review",
        wire.profile,
        embedding_configuration=EmbeddingConfiguration.cloudflare_bge_base_en(),
        turbo_quant=True,
    )

    def handler(request):
        if request.method == "GET" and request.url.path.endswith("/exists"):
            result = {"exists": True}
        elif request.method == "GET":
            result = {
                "config": {
                    "params": {
                        "shard_number": 1,
                        "sparse_vectors": {"bm25": {"modifier": "idf"}},
                        "vectors": {"dense": actual_dense},
                    }
                }
            }
        else:
            result = {"status": "completed"}
        return httpx.Response(200, json={"status": "ok", "result": result})

    with (
        httpx.Client(
            base_url="http://127.0.0.1:16433", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(ProjectionResponseError, match="incompatible"),
    ):
        NativeQdrantSearchIndex(index=dense_wire, client=client).ensure_collection()
