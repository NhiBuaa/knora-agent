"""Offline native BM25 wire validation; no transport or provider calls."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any
from unicodedata import normalize

from knora.ingestion.search_indexing import (
    LexicalGenerationError,
    LexicalProfile,
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
            "query": {
                "text": normalized_lexical_text(query_text),
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
            },
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
