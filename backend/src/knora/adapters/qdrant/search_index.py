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

    def __post_init__(self) -> None:
        if not all((self.workspace_id, self.profile_id, self.profile_digest, self.generation_ids)):
            raise ProjectionResponseError("authorized lexical snapshot is incomplete")
        if len(set(self.generation_ids)) != len(self.generation_ids) or any(
            not generation_id for generation_id in self.generation_ids
        ):
            raise ProjectionResponseError("authorized generation IDs must be unique")


@dataclass(frozen=True, slots=True)
class QdrantSearchIndex:
    """Build and validate wire data; runtime compatibility is a separate gate."""

    collection_name: str
    profile: LexicalProfile

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
        return {
            "vectors": {},
            "sparse_vectors": {"bm25": {"modifier": "idf"}},
            "shard_number": 1,
        }

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
        self, generation: LexicalGeneration, chunk_texts: Mapping[str, str]
    ) -> dict[str, Any]:
        """Build one native batch from PostgreSQL-authoritative chunk text."""
        self._validate_generation(generation)
        if not isinstance(chunk_texts, Mapping) or set(chunk_texts) != {
            chunk.chunk_id for chunk in generation.chunks
        }:
            raise LexicalGenerationError("authoritative texts differ from generation manifest")
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
            points.append(
                {
                    "id": lexical_point_id(generation.generation_id, chunk.chunk_id),
                    "vector": {"bm25": self._document(text)},
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
        scope = {
            "must": [
                {"key": "workspace_id", "match": {"value": snapshot.workspace_id}},
                {"key": "generation_id", "match": {"any": list(snapshot.generation_ids)}},
                {"key": "profile_digest", "match": {"value": snapshot.profile_digest}},
            ]
        }
        return {
            "using": "bm25",
            "query": self._document(query_text),
            "filter": scope,
            "params": {"idf": {"corpus": scope}},
            "limit": limit,
            "with_payload": True,
        }

    def parse_response(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        response: dict[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        self._validate_snapshot(snapshot)
        points = response.get("points")
        if not isinstance(points, list) or len(points) > 200:
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
            parsed.append(
                {
                    "point_id": point_id,
                    "score": float(score),
                    "rank": rank,
                    "generation_id": generation_id,
                    "chunk_id": chunk_id,
                    "score_policy_digest": snapshot.profile_digest,
                }
            )
        return tuple(parsed)
