"""Pure native-BM25 request and response contracts.

Transport and runtime composition stay outside this module so request safety can be
verified without a Qdrant process or an inference provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from knora.ingestion.search_indexing import LexicalGenerationError


class ProjectionResponseError(LexicalGenerationError):
    """Qdrant returned data that cannot be trusted for this authorized snapshot."""


@dataclass(frozen=True, slots=True)
class AuthorizedLexicalSnapshot:
    workspace_id: str
    generation_ids: tuple[str, ...]
    profile_id: str

    def __post_init__(self) -> None:
        if not self.workspace_id or not self.profile_id or not self.generation_ids:
            raise ProjectionResponseError("authorized lexical snapshot is incomplete")
        if len(set(self.generation_ids)) != len(self.generation_ids) or any(
            not generation_id for generation_id in self.generation_ids
        ):
            raise ProjectionResponseError("authorized generation IDs must be unique")


@dataclass(frozen=True, slots=True)
class NativeBm25Profile:
    id: str
    tokenizer: str
    tokenizer_version: str
    k1: float
    b: float
    avg_len: float
    statistics_digest: str

    @classmethod
    def from_native_token_counts(
        cls,
        *,
        id: str,
        tokenizer: str,
        tokenizer_version: str,
        k1: float,
        b: float,
        token_counts: tuple[int, ...],
        statistics_digest: str,
    ) -> NativeBm25Profile:
        if not token_counts or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 1
            for count in token_counts
        ):
            raise ProjectionResponseError("native tokenizer counts are required for avg_len")
        return cls(
            id=id,
            tokenizer=tokenizer,
            tokenizer_version=tokenizer_version,
            k1=k1,
            b=b,
            avg_len=sum(token_counts) / len(token_counts),
            statistics_digest=statistics_digest,
        )

    def __post_init__(self) -> None:
        if not self.id or not self.tokenizer or not self.tokenizer_version:
            raise ProjectionResponseError("BM25 profile identity is incomplete")
        if not isfinite(self.k1) or self.k1 <= 0:
            raise ProjectionResponseError("BM25 k1 must be positive and finite")
        if not isfinite(self.b) or not 0 <= self.b <= 1:
            raise ProjectionResponseError("BM25 b must be between zero and one")
        if not isfinite(self.avg_len) or self.avg_len <= 0:
            raise ProjectionResponseError("BM25 avg_len must be positive and finite")
        if not self.statistics_digest:
            raise ProjectionResponseError("BM25 statistics digest is required")

    def inference_options(self) -> dict[str, Any]:
        return {
            "k": self.k1,
            "b": self.b,
            "avg_len": self.avg_len,
            "tokenizer": self.tokenizer,
            "lowercase": True,
            "ascii_folding": False,
            "stemmer": {"type": "none"},
            "stopwords": {},
        }


class QdrantSearchIndex:
    """Build and validate native BM25 wire data without performing I/O."""

    def __init__(self, *, collection_name: str, profile: NativeBm25Profile) -> None:
        if not collection_name:
            raise ValueError("Qdrant collection name is required")
        self._collection_name = collection_name
        self._profile = profile

    def query_body(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        query_text: str,
        *,
        limit: int = 200,
    ) -> dict[str, Any]:
        if snapshot.profile_id != self._profile.id:
            raise ProjectionResponseError("query profile differs from authorized snapshot")
        if not isinstance(query_text, str) or not query_text.strip():
            raise ValueError("query text is required")
        if isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError("native BM25 limit must be between one and two hundred")

        retrieval_filter = {
            "must": [
                {"key": "workspace_id", "match": {"value": snapshot.workspace_id}},
                {
                    "key": "generation_id",
                    "match": {"any": list(snapshot.generation_ids)},
                },
            ]
        }
        idf_corpus_filter = {
            "must": [
                {
                    "key": "generation_id",
                    "match": {"any": list(snapshot.generation_ids)},
                }
            ]
        }
        return {
            "query": {
                "text": query_text,
                "model": "qdrant/bm25",
                "options": self._profile.inference_options(),
            },
            "filter": retrieval_filter,
            "params": {"idf": {"corpus": idf_corpus_filter}},
            "limit": limit,
            "with_payload": True,
        }

    def parse_response(
        self,
        snapshot: AuthorizedLexicalSnapshot,
        response: dict[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        points = response.get("points")
        if not isinstance(points, list):
            raise ProjectionResponseError("Qdrant response has no points list")

        parsed: list[dict[str, Any]] = []
        for rank, point in enumerate(points, start=1):
            if not isinstance(point, dict):
                raise ProjectionResponseError("Qdrant point is not an object")
            point_id = point.get("id")
            score = point.get("score")
            payload = point.get("payload")
            if (
                not isinstance(point_id, (str, int))
                or isinstance(point_id, bool)
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not isfinite(float(score))
                or not isinstance(payload, dict)
            ):
                raise ProjectionResponseError("Qdrant point has invalid identity, score or payload")
            if payload.get("workspace_id") != snapshot.workspace_id:
                raise ProjectionResponseError("Qdrant point crossed workspace boundary")
            generation_id = payload.get("generation_id")
            chunk_id = payload.get("chunk_id")
            if (
                generation_id not in snapshot.generation_ids
                or not isinstance(chunk_id, str)
                or not chunk_id
            ):
                raise ProjectionResponseError("Qdrant point is stale or incomplete")
            parsed.append(
                {
                    "point_id": str(point_id),
                    "score": float(score),
                    "rank": rank,
                    "generation_id": generation_id,
                    "chunk_id": chunk_id,
                }
            )
        return tuple(parsed)
