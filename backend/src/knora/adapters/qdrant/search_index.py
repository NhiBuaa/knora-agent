"""Offline native BM25 wire validation; no transport or provider calls."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any
from unicodedata import normalize

from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalGenerationError,
    LexicalProfile,
    StageReceipt,
    lexical_point_id,
)
from knora.providers.embedding import EmbeddingConfiguration


class ProjectionResponseError(LexicalGenerationError):
    """The projection cannot be trusted for this authorized snapshot."""


def normalized_lexical_text(text: str) -> str:
    return normalize("NFKC", text).lower()


@dataclass(frozen=True, slots=True)
class AuthorizedLexicalSnapshot:
    workspace_id: str
    generation_ids: tuple[str, ...]
    profile_id: str
    profile_digest: str
    embedding_configuration_id: str | None = None
    embedding_set_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.workspace_id, self.profile_id, self.profile_digest, self.generation_ids)):
            raise ProjectionResponseError("authorized lexical snapshot is incomplete")
        if len(set(self.generation_ids)) != len(self.generation_ids) or any(
            not generation_id for generation_id in self.generation_ids
        ):
            raise ProjectionResponseError("authorized generation IDs must be unique")


AuthorizedSearchSnapshot = AuthorizedLexicalSnapshot


@dataclass(frozen=True, slots=True)
class QdrantSearchIndex:
    """Build and validate wire data; runtime compatibility is a separate gate."""

    collection_name: str
    profile: LexicalProfile
    embedding_configuration: EmbeddingConfiguration | None = None
    turbo_quant: bool = True

    def _document(self, text: str) -> dict[str, Any]:
        return {
            "text": normalized_lexical_text(text),
            "model": "qdrant/bm25",
            "options": {
                "k": self.profile.k1,
                "b": self.profile.b,
                "avg_len": self.profile.avg_len,
                "tokenizer": self.profile.tokenizer,
                "lowercase": True,
                "ascii_folding": False,
                "stemmer": {"type": "none"},
                "stopwords": {},
            },
        }

    def collection_body(self) -> dict[str, Any]:
        vectors: dict[str, Any] = {}
        if self.embedding_configuration is not None:
            dense_cfg: dict[str, Any] = {
                "size": self.embedding_configuration.dimensions,
                "distance": self.embedding_configuration.distance_metric.capitalize(),
                "on_disk": True,
                "hnsw_config": {
                    "m": 16,
                    "ef_construct": 100,
                },
            }
            if self.turbo_quant:
                dense_cfg["quantization_config"] = {
                    "turbo": {
                        "bits": "bits4",
                        "always_ram": True,
                        "rescore": True,
                        "oversampling": 2.0,
                    }
                }
            vectors["dense"] = dense_cfg
        return {
            "vectors": vectors,
            "sparse_vectors": {"bm25": {"modifier": "idf"}},
            "shard_number": 1,
        }

    def payload_index_bodies(self) -> tuple[dict[str, Any], ...]:
        """Build separate PUT /collections/{collection}/index request bodies."""
        return (
            {
                "field_name": "workspace_id",
                "field_schema": {"type": "keyword", "is_tenant": True},
            },
            {"field_name": "generation_id", "field_schema": "keyword"},
            {"field_name": "profile_digest", "field_schema": "keyword"},
        )

    def _validate_generation(self, generation: LexicalGeneration) -> None:
        if generation.lexical_profile.digest() != self.profile.digest():
            raise LexicalGenerationError("generation profile differs from index profile")
        if not 1 <= len(generation.chunks) <= 64:
            raise LexicalGenerationError("native staging requires one batch of at most 64 points")

    @staticmethod
    def _point_payload(
        generation: LexicalGeneration, chunk: LexicalChunk, content_digest: str
    ) -> dict[str, str]:
        return {
            "workspace_id": generation.workspace_id,
            "generation_id": generation.generation_id,
            "chunk_id": chunk.chunk_id,
            "profile_id": generation.lexical_profile.id,
            "profile_digest": generation.lexical_profile.digest(),
            "content_checksum": chunk.content_checksum,
            "content_digest": content_digest,
        }

    def stage_body(
        self,
        generation: LexicalGeneration,
        chunk_texts: Mapping[str, str],
        chunk_vectors: Mapping[str, tuple[float, ...] | list[float]] | None = None,
    ) -> dict[str, Any]:
        """Build one native batch from authoritative chunk text and optional dense vectors."""
        self._validate_generation(generation)
        if not isinstance(chunk_texts, Mapping) or set(chunk_texts) != {
            chunk.chunk_id for chunk in generation.chunks
        }:
            raise LexicalGenerationError("authoritative texts differ from generation manifest")
        if chunk_vectors is not None and (
            not isinstance(chunk_vectors, Mapping)
            or set(chunk_vectors) != {chunk.chunk_id for chunk in generation.chunks}
        ):
            raise LexicalGenerationError("authoritative vectors differ from generation manifest")
        points = []
        content_digest = generation.content_digest()
        for chunk in generation.chunks:
            text = chunk_texts[chunk.chunk_id]
            if (
                not isinstance(text, str)
                or not text.strip()
                or hashlib.sha256(text.encode("utf-8")).hexdigest() != chunk.content_checksum
            ):
                raise LexicalGenerationError("authoritative chunk text checksum is invalid")
            vector_entry: dict[str, Any] = {"bm25": self._document(text)}
            if chunk_vectors is not None:
                vec = chunk_vectors[chunk.chunk_id]
                if (
                    not isinstance(vec, (tuple, list))
                    or not vec
                    or not all(
                        isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v)
                        for v in vec
                    )
                ):
                    raise LexicalGenerationError(
                        "chunk vector contains invalid or nonfinite values"
                    )
                if (
                    self.embedding_configuration
                    and len(vec) != self.embedding_configuration.dimensions
                ):
                    raise LexicalGenerationError("chunk vector dimension mismatch")
                vector_entry["dense"] = list(vec)
            points.append(
                {
                    "id": lexical_point_id(generation.generation_id, chunk.chunk_id),
                    "vector": vector_entry,
                    "payload": self._point_payload(generation, chunk, content_digest),
                }
            )
        return {"points": points}

    def persisted_points_body(self, generation: LexicalGeneration) -> dict[str, Any]:
        self._validate_generation(generation)
        return {"ids": list(generation.point_ids()), "with_payload": True, "with_vector": False}

    def parse_stage_response(
        self, generation: LexicalGeneration, points: list[dict[str, Any]]
    ) -> StageReceipt:
        """Verify retrieved persisted points, never an upsert operation response."""
        self._validate_generation(generation)
        if not isinstance(points, list) or len(points) != len(generation.chunks):
            raise ProjectionResponseError("persisted generation point count is incomplete")
        content_digest = generation.content_digest()
        expected = {
            lexical_point_id(generation.generation_id, chunk.chunk_id): self._point_payload(
                generation, chunk, content_digest
            )
            for chunk in generation.chunks
        }
        seen = set()
        for point in points:
            if not isinstance(point, dict):
                raise ProjectionResponseError("persisted point is not an object")
            point_id = point.get("id")
            if (
                not isinstance(point_id, str)
                or point_id not in expected
                or point_id in seen
                or point.get("payload") != expected[point_id]
            ):
                raise ProjectionResponseError(
                    "persisted point identity or digest differs from manifest"
                )
            seen.add(point_id)
        return StageReceipt(generation.generation_id, len(seen), content_digest)

    def _validate_snapshot(self, snapshot: AuthorizedLexicalSnapshot) -> None:
        if (snapshot.profile_id, snapshot.profile_digest) != (
            self.profile.id,
            self.profile.digest(),
        ):
            raise ProjectionResponseError("profile differs from authorized snapshot")

    @staticmethod
    def _build_scope(snapshot: AuthorizedLexicalSnapshot) -> dict[str, Any]:
        return {
            "must": [
                {"key": "workspace_id", "match": {"value": snapshot.workspace_id}},
                {"key": "generation_id", "match": {"any": list(snapshot.generation_ids)}},
                {"key": "profile_digest", "match": {"value": snapshot.profile_digest}},
            ]
        }

    def query_body(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        query_text: str,
        *,
        limit: int = 200,
    ) -> dict[str, Any]:
        self._validate_snapshot(snapshot)
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("query text is required")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("native BM25 limit must be between one and two hundred")
        scope = self._build_scope(snapshot)
        return {
            "using": "bm25",
            "query": self._document(query_text),
            "filter": scope,
            "params": {"idf": {"corpus": scope}},
            "limit": limit,
            "with_payload": True,
        }

    def dense_query_body(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        query_vector: tuple[float, ...] | list[float],
        *,
        limit: int = 200,
        hnsw_ef: int = 256,
        rescore: bool = True,
        oversampling: float = 2.0,
    ) -> dict[str, Any]:
        self._validate_snapshot(snapshot)
        if not query_vector or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v)
            for v in query_vector
        ):
            raise ValueError("query vector is required and must contain finite numbers")
        if (
            self.embedding_configuration
            and len(query_vector) != self.embedding_configuration.dimensions
        ):
            raise ValueError("query vector dimension differs from embedding configuration")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("native dense limit must be between one and two hundred")
        scope = self._build_scope(snapshot)
        return {
            "using": "dense",
            "query": list(query_vector),
            "filter": scope,
            "params": {
                "hnsw_ef": hnsw_ef,
                "quantization": {
                    "rescore": rescore,
                    "oversampling": oversampling,
                },
            },
            "limit": limit,
            "with_payload": True,
        }

    def hybrid_query_body(
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
    ) -> dict[str, Any]:
        self._validate_snapshot(snapshot)
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("query text is required")
        if not query_vector or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v)
            for v in query_vector
        ):
            raise ValueError("query vector is required and must contain finite numbers")
        if (
            self.embedding_configuration
            and len(query_vector) != self.embedding_configuration.dimensions
        ):
            raise ValueError("query vector dimension differs from embedding configuration")
        if type(final_limit) is not int or not 1 <= final_limit <= 100:
            raise ValueError("hybrid final limit must be between one and one hundred")
        if type(dense_limit) is not int or not 1 <= dense_limit <= 200:
            raise ValueError("dense prefetch limit must be between one and two hundred")
        if type(sparse_limit) is not int or not 1 <= sparse_limit <= 200:
            raise ValueError("sparse prefetch limit must be between one and two hundred")
        scope = self._build_scope(snapshot)
        return {
            "prefetch": [
                {
                    "using": "bm25",
                    "query": self._document(query_text),
                    "filter": scope,
                    "params": {"idf": {"corpus": scope}},
                    "limit": sparse_limit,
                },
                {
                    "using": "dense",
                    "query": list(query_vector),
                    "filter": scope,
                    "params": {
                        "hnsw_ef": hnsw_ef,
                        "quantization": {
                            "rescore": rescore,
                            "oversampling": oversampling,
                        },
                    },
                    "limit": dense_limit,
                },
            ],
            "query": {"fusion": "dbsf"},
            "filter": scope,
            "limit": final_limit,
            "with_payload": True,
        }

    def parse_response(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        response: dict[str, Any],
        *,
        limit: int = 200,
        score_kind: str = "bm25",
    ) -> tuple[dict[str, Any], ...]:
        self._validate_snapshot(snapshot)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("native BM25 limit must be between one and two hundred")
        points = response.get("points")
        if not isinstance(points, list) or len(points) > limit:
            raise ProjectionResponseError("Qdrant points list is missing or exceeds limit")
        parsed = []
        seen = set()
        previous_score = float("inf")
        for rank, point in enumerate(points, start=1):
            if not isinstance(point, dict):
                raise ProjectionResponseError("Qdrant point is not an object")
            score, payload = point.get("score"), point.get("payload")
            if (
                type(score) not in (int, float)
                or not isfinite(score)
                or not isinstance(payload, dict)
            ):
                raise ProjectionResponseError("Qdrant point has invalid score or payload")
            generation_id, chunk_id = payload.get("generation_id"), payload.get("chunk_id")
            if (
                payload.get("workspace_id") != snapshot.workspace_id
                or payload.get("profile_digest") != snapshot.profile_digest
                or generation_id not in snapshot.generation_ids
                or not isinstance(chunk_id, str)
                or not chunk_id
            ):
                raise ProjectionResponseError("Qdrant point is stale, foreign or incomplete")
            point_id = lexical_point_id(generation_id, chunk_id)
            if point.get("id") != point_id or chunk_id in seen or score > previous_score:
                raise ProjectionResponseError("Qdrant identity, uniqueness or rank is invalid")
            seen.add(chunk_id)
            previous_score = score
            item: dict[str, Any] = {
                "point_id": point_id,
                "score": float(score),
                "rank": rank,
                "generation_id": generation_id,
                "chunk_id": chunk_id,
                "score_policy_digest": snapshot.profile_digest,
            }
            if score_kind != "bm25":
                item["score_kind"] = score_kind
            parsed.append(item)
        if len(parsed) < limit:
            parsed.sort(key=lambda hit: (-hit["score"], hit["chunk_id"]))
            for rank, hit in enumerate(parsed, start=1):
                hit["rank"] = rank
        return tuple(parsed)
