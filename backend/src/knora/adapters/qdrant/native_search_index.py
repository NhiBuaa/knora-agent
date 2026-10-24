"""Thin native Qdrant HTTP adapter; PostgreSQL remains the authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from knora.ingestion.search_indexing import (
    LexicalGeneration,
    LexicalProjectionUnavailable,
    StageReceipt,
)

from .search_index import (
    AuthorizedLexicalSnapshot,
    ProjectionResponseError,
    QdrantSearchIndex,
)


class NativeQdrantSearchIndex:
    """Use only the pinned server's REST wire; no inference or local model calls."""

    def __init__(
        self,
        *,
        index: QdrantSearchIndex,
        client: httpx.Client,
    ) -> None:

        self.index = index

        self._client = client

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:

        try:
            response = self._client.request(method, path, json=body, follow_redirects=False)

        except (httpx.InvalidURL, httpx.UnsupportedProtocol, httpx.LocalProtocolError) as exc:
            raise ProjectionResponseError("Qdrant transport configuration is invalid") from exc

        except httpx.DecodingError as exc:
            raise ProjectionResponseError("Qdrant response encoding is invalid") from exc

        except httpx.TransportError as exc:
            raise LexicalProjectionUnavailable("Qdrant transport unavailable") from exc

        if response.status_code in (408, 429) or 500 <= response.status_code < 600:
            raise LexicalProjectionUnavailable("Qdrant storage temporarily unavailable")

        if response.status_code < 200 or response.status_code >= 300:
            raise ProjectionResponseError("Qdrant request was rejected")

        try:
            decoded = response.json()

        except ValueError as exc:
            raise ProjectionResponseError("Qdrant response is not JSON") from exc

        if not isinstance(decoded, dict) or decoded.get("status") != "ok":
            raise ProjectionResponseError("Qdrant response status is invalid")

        return decoded

    def stage_generation(
        self,
        generation: LexicalGeneration,
        chunk_texts: Mapping[str, str],
        chunk_vectors: Mapping[str, tuple[float, ...] | list[float]] | None = None,
    ) -> StageReceipt:

        response = self._request(
            "PUT",
            f"/collections/{self.index.collection_name}/points?wait=true",
            self.index.stage_body(generation, chunk_texts, chunk_vectors),
        )

        self._require_completed(response)

        response = self._request(
            "POST",
            f"/collections/{self.index.collection_name}/points",
            self.index.persisted_points_body(generation),
        )

        result = response.get("result")

        if not isinstance(result, list):
            raise ProjectionResponseError("Qdrant persisted-point readback is incomplete")

        return self.index.parse_stage_response(
            generation, result, expected_chunk_vectors=chunk_vectors
        )

    def remove_generation(self, generation: LexicalGeneration) -> None:
        """Delete only this generation's deterministic point IDs, waiting for completion."""

        response = self._request(
            "POST",
            f"/collections/{self.index.collection_name}/points/delete?wait=true",
            {"points": list(generation.point_ids())},
        )

        self._require_completed(response)

    @staticmethod
    def _require_completed(response: dict[str, Any]) -> None:

        result = response.get("result")

        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ProjectionResponseError("Qdrant mutation did not complete")

    def ensure_collection(self) -> None:

        path = f"/collections/{self.index.collection_name}"

        existence = self._request("GET", f"{path}/exists").get("result")

        if not isinstance(existence, dict) or type(existence.get("exists")) is not bool:
            raise ProjectionResponseError("Qdrant collection existence response is invalid")

        if not existence["exists"]:
            created = self._request("PUT", path, self.index.collection_body())

            if created.get("result") is not True:
                raise ProjectionResponseError("Qdrant collection creation was not confirmed")

        result = self._request("GET", path).get("result")

        config = result.get("config") if isinstance(result, dict) else None

        params = config.get("params") if isinstance(config, dict) else None

        sparse = params.get("sparse_vectors") if isinstance(params, dict) else None

        bm25 = sparse.get("bm25") if isinstance(sparse, dict) else None

        expected_body = self.index.collection_body()

        expected_vectors = expected_body.get("vectors", {})

        if (
            not isinstance(params, dict)
            or params.get("shard_number") != 1
            or not isinstance(sparse, dict)
            or set(sparse) != {"bm25"}
            or not isinstance(bm25, dict)
            or bm25.get("modifier") != "idf"
        ):
            raise ProjectionResponseError("Qdrant collection configuration is incompatible")

        vectors = params.get("vectors")

        if not expected_vectors:
            if vectors != {}:
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

        else:
            if not isinstance(vectors, dict) or "dense" not in vectors:
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

            dense_params = vectors["dense"]

            if not isinstance(dense_params, dict):
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

            expected_dense = expected_vectors["dense"]

            if dense_params.get("size") != expected_dense.get("size"):
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

            if (
                "distance" in dense_params
                and str(dense_params.get("distance")).lower()
                != str(expected_dense.get("distance")).lower()
            ):
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

            datatype = dense_params.get("datatype")
            if datatype is not None and datatype not in ("float32", None):
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

            if dense_params.get("on_disk") is False:
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

            hnsw = dense_params.get("hnsw_config")

            if isinstance(hnsw, dict) and (
                hnsw.get("m", 16) < 16 or hnsw.get("ef_construct", 100) < 100
            ):
                raise ProjectionResponseError("Qdrant collection configuration is incompatible")

            if self.index.turbo_quant:
                quant = dense_params.get("quantization_config")

                if not isinstance(quant, dict):
                    raise ProjectionResponseError("Qdrant collection configuration is incompatible")

                turbo = quant.get("turbo")
                if not isinstance(turbo, dict):
                    raise ProjectionResponseError("Qdrant collection configuration is incompatible")

                if turbo.get("bits") != "bits4" or turbo.get("always_ram") is not True:
                    raise ProjectionResponseError("Qdrant collection configuration is incompatible")

        for body in self.index.payload_index_bodies():
            response = self._request(
                "PUT",
                f"{path}/index?wait=true",
                body,
            )

            self._require_completed(response)

    def query(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        query_text: str,
        *,
        limit: int = 200,
    ) -> tuple[dict[str, Any], ...]:

        response = self._request(
            "POST",
            f"/collections/{self.index.collection_name}/points/query",
            self.index.query_body(snapshot, query_text, limit=limit),
        )

        result = response.get("result")

        if not isinstance(result, dict) or not isinstance(result.get("points"), list):
            raise ProjectionResponseError("Qdrant query result is incomplete")

        return self.index.parse_response(snapshot, result, limit=limit)

    def query_dense(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        query_vector: tuple[float, ...] | list[float],
        *,
        limit: int = 200,
        hnsw_ef: int = 256,
        rescore: bool = True,
        oversampling: float = 2.0,
    ) -> tuple[dict[str, Any], ...]:

        response = self._request(
            "POST",
            f"/collections/{self.index.collection_name}/points/query",
            self.index.dense_query_body(
                snapshot,
                query_vector,
                limit=limit,
                hnsw_ef=hnsw_ef,
                rescore=rescore,
                oversampling=oversampling,
            ),
        )

        result = response.get("result")

        if not isinstance(result, dict) or not isinstance(result.get("points"), list):
            raise ProjectionResponseError("Qdrant dense query result is incomplete")

        return self.index.parse_response(
            snapshot, result, limit=limit, score_kind="cosine_similarity"
        )

    def query_hybrid(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        query_text: str,
        query_vector: tuple[float, ...] | list[float],
        *,
        dense_limit: int = 200,
        sparse_limit: int = 200,
        final_limit: int = 100,
        hnsw_ef: int = 256,
        rescore: bool = True,
        oversampling: float = 2.0,
    ) -> tuple[dict[str, Any], ...]:

        response = self._request(
            "POST",
            f"/collections/{self.index.collection_name}/points/query",
            self.index.hybrid_query_body(
                snapshot,
                query_text,
                query_vector,
                dense_limit=dense_limit,
                sparse_limit=sparse_limit,
                final_limit=final_limit,
                hnsw_ef=hnsw_ef,
                rescore=rescore,
                oversampling=oversampling,
            ),
        )

        result = response.get("result")

        if not isinstance(result, dict) or not isinstance(result.get("points"), list):
            raise ProjectionResponseError("Qdrant hybrid query result is incomplete")

        return self.index.parse_response(snapshot, result, limit=final_limit, score_kind="dbsf")
