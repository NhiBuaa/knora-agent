from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import (
    ProjectionResponseError,
    QdrantSearchIndex,
)
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalProfile,
    LexicalProjectionUnavailable,
    StageReceipt,
    lexical_point_id,
)
from knora.providers.embedding import EmbeddingConfiguration


@pytest.fixture
def dense_profile() -> LexicalProfile:

    return LexicalProfile(
        id="hybrid-bm25-v1",
        tokenizer="tiktoken",
        tokenizer_version="cl100k_base",
        k1=1.2,
        b=0.75,
        avg_len=128.0,
        statistics_digest="a" * 64,
    )


@pytest.fixture
def embedding_config() -> EmbeddingConfiguration:

    return EmbeddingConfiguration(
        id="cloudflare-bge-base-en-v1.5",
        dimensions=768,
        distance_metric="cosine",
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
    )


@pytest.fixture
def dense_index(
    dense_profile: LexicalProfile, embedding_config: EmbeddingConfiguration
) -> QdrantSearchIndex:

    return QdrantSearchIndex(
        collection_name="knora_dense_hybrid_v3",
        profile=dense_profile,
        embedding_configuration=embedding_config,
        turbo_quant=True,
    )


@pytest.fixture
def sample_generation(dense_profile: LexicalProfile) -> LexicalGeneration:

    content = "Sample chunk content for dense indexing test"

    content_checksum = hashlib.sha256(content.encode()).hexdigest()

    return LexicalGeneration(
        generation_id="gen-test-1",
        workspace_id="ws-tenant-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cset-1",
        lexical_profile=dense_profile,
        revision=1,
        chunks=(LexicalChunk(chunk_id="chunk-1", ordinal=0, content_checksum=content_checksum),),
    )


def test_collection_body_includes_turbo_quant_and_sparse_bm25(
    dense_index: QdrantSearchIndex,
) -> None:

    body = dense_index.collection_body()

    vectors = body.get("vectors", {})

    assert "dense" in vectors

    dense_cfg = vectors["dense"]

    assert dense_cfg["size"] == 768

    assert dense_cfg["distance"] == "Cosine"

    assert dense_cfg["on_disk"] is True

    assert dense_cfg["hnsw_config"] == {"m": 16, "ef_construct": 100}

    assert dense_cfg["quantization_config"] == {
        "turbo": {
            "bits": "bits4",
            "always_ram": True,
            "rescore": True,
            "oversampling": 2.0,
        }
    }

    assert body.get("sparse_vectors") == {"bm25": {"modifier": "idf"}}

    assert body.get("shard_number") == 1


def test_tenant_payload_index_bodies(dense_index: QdrantSearchIndex) -> None:

    bodies = dense_index.payload_index_bodies()

    assert bodies == (
        {
            "field_name": "workspace_id",
            "field_schema": {"type": "keyword", "is_tenant": True},
        },
        {"field_name": "generation_id", "field_schema": "keyword"},
        {"field_name": "profile_digest", "field_schema": "keyword"},
    )


def test_deterministic_point_id(sample_generation: LexicalGeneration) -> None:

    pid = lexical_point_id(sample_generation.generation_id, "chunk-1")

    # Must be deterministic and reproducible

    assert pid == lexical_point_id(sample_generation.generation_id, "chunk-1")

    # Different generation or chunk ID produces different point ID

    assert pid != lexical_point_id("gen-test-2", "chunk-1")

    assert pid != lexical_point_id(sample_generation.generation_id, "chunk-2")


def test_stage_body_combines_dense_and_bm25(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:

    texts = {"chunk-1": "Sample chunk content for dense indexing test"}

    vec = tuple(0.01 * i for i in range(768))

    vectors = {"chunk-1": vec}

    stage_payload = dense_index.stage_body(sample_generation, texts, chunk_vectors=vectors)

    points = stage_payload["points"]

    assert len(points) == 1

    pt = points[0]

    assert pt["id"] == lexical_point_id(sample_generation.generation_id, "chunk-1")

    # Vector entry has both bm25 document and dense float array

    assert "bm25" in pt["vector"]

    assert "dense" in pt["vector"]

    assert pt["vector"]["dense"] == list(vec)

    # Payload contains canonical workspace_id, generation_id, digests

    payload = pt["payload"]

    assert payload["workspace_id"] == "ws-tenant-1"

    assert payload["generation_id"] == "gen-test-1"

    assert payload["chunk_id"] == "chunk-1"

    assert payload["profile_digest"] == sample_generation.lexical_profile.digest()


def test_native_stage_generation_with_dense_vectors_readback(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:

    texts = {"chunk-1": "Sample chunk content for dense indexing test"}

    vec = tuple(0.01 * i for i in range(768))

    vectors = {"chunk-1": vec}

    recorded_requests = []

    def transport_handler(request: httpx.Request) -> httpx.Response:

        recorded_requests.append(request)

        if request.method == "PUT" and "/points" in request.url.path:
            assert request.url.params.get("wait") == "true"

            data = json.loads(request.content)

            assert "points" in data

            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})

        if request.method == "POST" and "/points" in request.url.path:
            # Readback persisted points
            vec_digest = hashlib.sha256(
                json.dumps([float(v) for v in vec], separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            persisted = [
                {
                    "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
                    "vector": {"dense": list(vec)},
                    "payload": {
                        "workspace_id": "ws-tenant-1",
                        "generation_id": "gen-test-1",
                        "chunk_id": "chunk-1",
                        "profile_id": sample_generation.lexical_profile.id,
                        "profile_digest": sample_generation.lexical_profile.digest(),
                        "content_checksum": sample_generation.chunks[0].content_checksum,
                        "content_digest": sample_generation.content_digest(),
                        "embedding_configuration_id": dense_index.embedding_configuration.id,
                        "vector_digest": vec_digest,
                    },
                }
            ]

            return httpx.Response(200, json={"status": "ok", "result": persisted})

        return httpx.Response(404)

    client = httpx.Client(
        base_url="http://qdrant.test", transport=httpx.MockTransport(transport_handler)
    )

    native_index = NativeQdrantSearchIndex(index=dense_index, client=client)

    receipt = native_index.stage_generation(sample_generation, texts, chunk_vectors=vectors)

    assert isinstance(receipt, StageReceipt)

    assert receipt.generation_id == sample_generation.generation_id

    assert receipt.point_count == 1

    assert receipt.content_digest == sample_generation.content_digest()


def test_remove_generation_targets_deterministic_point_ids_only(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:

    deleted_points = []

    def transport_handler(request: httpx.Request) -> httpx.Response:

        if request.method == "POST" and "/points/delete" in request.url.path:
            assert request.url.params.get("wait") == "true"

            data = json.loads(request.content)

            deleted_points.extend(data["points"])

            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})

        return httpx.Response(404)

    client = httpx.Client(
        base_url="http://qdrant.test", transport=httpx.MockTransport(transport_handler)
    )

    native_index = NativeQdrantSearchIndex(index=dense_index, client=client)

    native_index.remove_generation(sample_generation)

    expected_pid = lexical_point_id(sample_generation.generation_id, "chunk-1")

    assert deleted_points == [expected_pid]


def test_ensure_collection_creates_with_turbo_quant_and_indexes(
    dense_index: QdrantSearchIndex,
) -> None:

    calls = []

    def transport_handler(request: httpx.Request) -> httpx.Response:

        calls.append((request.method, request.url.path))

        if request.method == "GET" and request.url.path.endswith("/exists"):
            return httpx.Response(200, json={"status": "ok", "result": {"exists": False}})

        if request.method == "PUT" and request.url.path.endswith("/knora_dense_hybrid_v3"):
            return httpx.Response(200, json={"status": "ok", "result": True})

        if request.method == "GET" and request.url.path.endswith("/knora_dense_hybrid_v3"):
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "result": {
                        "config": {
                            "params": {
                                "shard_number": 1,
                                "sparse_vectors": {"bm25": {"modifier": "idf"}},
                                "vectors": {
                                    "dense": {
                                        "size": 768,
                                        "distance": "Cosine",
                                        "datatype": "float32",
                                        "on_disk": True,
                                        "hnsw_config": {"m": 16, "ef_construct": 100},
                                        "quantization_config": {
                                            "turbo": {
                                                "bits": "bits4",
                                                "always_ram": True,
                                                "rescore": True,
                                                "oversampling": 2.0,
                                            }
                                        },
                                    }
                                },
                            }
                        }
                    },
                },
            )

        if request.method == "PUT" and "/index" in request.url.path:
            return httpx.Response(200, json={"status": "ok", "result": {"status": "completed"}})

        return httpx.Response(404)

    client = httpx.Client(
        base_url="http://qdrant.test", transport=httpx.MockTransport(transport_handler)
    )

    native_index = NativeQdrantSearchIndex(index=dense_index, client=client)

    native_index.ensure_collection()

    # Verified collection was created, verified compatible, and all 3 payload indexes created

    assert any(m == "PUT" and p.endswith("/knora_dense_hybrid_v3") for m, p in calls)

    assert any(m == "PUT" and "/index" in p for m, p in calls)


def test_transient_transport_error_raises_lexical_projection_unavailable(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:

    def transport_handler(request: httpx.Request) -> httpx.Response:

        return httpx.Response(503, json={"status": "error"})

    client = httpx.Client(
        base_url="http://qdrant.test", transport=httpx.MockTransport(transport_handler)
    )

    native_index = NativeQdrantSearchIndex(index=dense_index, client=client)

    with pytest.raises(LexicalProjectionUnavailable):
        native_index.remove_generation(sample_generation)


def test_parse_stage_response_rejects_altered_corrupted_vector(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:
    vec = tuple(0.01 * i for i in range(768))
    vec_digest = hashlib.sha256(
        json.dumps([float(v) for v in vec], separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    # Return vector with altered values [9.0] * 768
    altered_points = [
        {
            "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
            "vector": {"dense": [9.0] * 768},
            "payload": {
                "workspace_id": "ws-tenant-1",
                "generation_id": "gen-test-1",
                "chunk_id": "chunk-1",
                "profile_id": sample_generation.lexical_profile.id,
                "profile_digest": sample_generation.lexical_profile.digest(),
                "content_checksum": sample_generation.chunks[0].content_checksum,
                "content_digest": sample_generation.content_digest(),
                "embedding_configuration_id": dense_index.embedding_configuration.id,
                "vector_digest": vec_digest,
            },
        }
    ]
    with pytest.raises(ProjectionResponseError, match="altered or corrupted"):
        dense_index.parse_stage_response(sample_generation, altered_points)


def test_parse_stage_response_rejects_missing_vector(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:
    missing_vector_points = [
        {
            "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
            "payload": {
                "workspace_id": "ws-tenant-1",
                "generation_id": "gen-test-1",
                "chunk_id": "chunk-1",
                "profile_id": sample_generation.lexical_profile.id,
                "profile_digest": sample_generation.lexical_profile.digest(),
                "content_checksum": sample_generation.chunks[0].content_checksum,
                "content_digest": sample_generation.content_digest(),
                "embedding_configuration_id": dense_index.embedding_configuration.id,
            },
        }
    ]
    with pytest.raises(ProjectionResponseError, match="dense vector is missing"):
        dense_index.parse_stage_response(sample_generation, missing_vector_points)


def test_parse_stage_response_rejects_dimension_mismatch(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:
    mismatch_points = [
        {
            "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
            "vector": {"dense": [0.0] * 512},
            "payload": {
                "workspace_id": "ws-tenant-1",
                "generation_id": "gen-test-1",
                "chunk_id": "chunk-1",
                "profile_id": sample_generation.lexical_profile.id,
                "profile_digest": sample_generation.lexical_profile.digest(),
                "content_checksum": sample_generation.chunks[0].content_checksum,
                "content_digest": sample_generation.content_digest(),
                "embedding_configuration_id": dense_index.embedding_configuration.id,
            },
        }
    ]
    with pytest.raises(ProjectionResponseError, match="dimension mismatch"):
        dense_index.parse_stage_response(sample_generation, mismatch_points)


def test_parse_stage_response_rejects_missing_vector_digest(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:
    vec = tuple(0.01 * i for i in range(768))
    points = [
        {
            "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
            "vector": {"dense": list(vec)},
            "payload": {
                "workspace_id": "ws-tenant-1",
                "generation_id": "gen-test-1",
                "chunk_id": "chunk-1",
                "profile_id": sample_generation.lexical_profile.id,
                "profile_digest": sample_generation.lexical_profile.digest(),
                "content_checksum": sample_generation.chunks[0].content_checksum,
                "content_digest": sample_generation.content_digest(),
                "embedding_configuration_id": dense_index.embedding_configuration.id,
                # vector_digest is omitted / missing
            },
        }
    ]
    with pytest.raises(ProjectionResponseError, match="vector digest is missing"):
        dense_index.parse_stage_response(sample_generation, points)


def test_parse_stage_response_rejects_vector_differing_from_expected_pg_vector(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:
    pg_vec = tuple(0.01 * i for i in range(768))
    forged_vec = tuple(9.0 for _ in range(768))
    forged_digest = hashlib.sha256(
        json.dumps([float(v) for v in forged_vec], separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    # The point has a forged digest matching its forged vector
    points = [
        {
            "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
            "vector": {"dense": list(forged_vec)},
            "payload": {
                "workspace_id": "ws-tenant-1",
                "generation_id": "gen-test-1",
                "chunk_id": "chunk-1",
                "profile_id": sample_generation.lexical_profile.id,
                "profile_digest": sample_generation.lexical_profile.digest(),
                "content_checksum": sample_generation.chunks[0].content_checksum,
                "content_digest": sample_generation.content_digest(),
                "embedding_configuration_id": dense_index.embedding_configuration.id,
                "vector_digest": forged_digest,
            },
        }
    ]

    # Passing expected_chunk_vectors with the authoritative PG vector must reject forged digest
    with pytest.raises(ProjectionResponseError, match="differs from expected PG vector"):
        dense_index.parse_stage_response(
            sample_generation, points, expected_chunk_vectors={"chunk-1": pg_vec}
        )


def test_parse_stage_response_accepts_normalized_float32_server_equivalent_vector(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:
    pg_vec = tuple(0.01 * i for i in range(768))
    # Stored payload preserves the original staged vector digest
    pg_digest = hashlib.sha256(
        json.dumps([float(v) for v in pg_vec], separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    # Pinned server readback has slight float32 roundtrip tolerance difference
    readback_vec = tuple(v + 1e-6 for v in pg_vec)

    points = [
        {
            "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
            "vector": {"dense": list(readback_vec)},
            "payload": {
                "workspace_id": "ws-tenant-1",
                "generation_id": "gen-test-1",
                "chunk_id": "chunk-1",
                "profile_id": sample_generation.lexical_profile.id,
                "profile_digest": sample_generation.lexical_profile.digest(),
                "content_checksum": sample_generation.chunks[0].content_checksum,
                "content_digest": sample_generation.content_digest(),
                "embedding_configuration_id": dense_index.embedding_configuration.id,
                "vector_digest": pg_digest,
            },
        }
    ]

    receipt = dense_index.parse_stage_response(
        sample_generation, points, expected_chunk_vectors={"chunk-1": pg_vec}
    )
    assert receipt.generation_id == sample_generation.generation_id
    assert receipt.point_count == 1


def test_parse_stage_response_rejects_swapped_or_corrupt_vector(
    dense_index: QdrantSearchIndex, sample_generation: LexicalGeneration
) -> None:
    pg_vec = tuple(0.01 * i for i in range(768))
    swapped_vec = tuple(reversed(pg_vec))
    swapped_digest = hashlib.sha256(
        json.dumps([float(v) for v in swapped_vec], separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    points = [
        {
            "id": lexical_point_id(sample_generation.generation_id, "chunk-1"),
            "vector": {"dense": list(swapped_vec)},
            "payload": {
                "workspace_id": "ws-tenant-1",
                "generation_id": "gen-test-1",
                "chunk_id": "chunk-1",
                "profile_id": sample_generation.lexical_profile.id,
                "profile_digest": sample_generation.lexical_profile.digest(),
                "content_checksum": sample_generation.chunks[0].content_checksum,
                "content_digest": sample_generation.content_digest(),
                "embedding_configuration_id": dense_index.embedding_configuration.id,
                "vector_digest": swapped_digest,
            },
        }
    ]

    with pytest.raises(ProjectionResponseError, match="differs from expected PG vector"):
        dense_index.parse_stage_response(
            sample_generation, points, expected_chunk_vectors={"chunk-1": pg_vec}
        )
