"""Immutable lexical indexing inputs; lifecycle authority belongs to PostgreSQL."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from uuid import NAMESPACE_URL, uuid5


class LexicalGenerationError(ValueError):
    """The generation cannot be accepted at the lexical trust boundary."""


class StaleGenerationError(LexicalGenerationError):
    """A generation or revision is no longer the requested one."""


def lexical_point_id(generation_id: str, chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps(["knora-lexical-v1", generation_id, chunk_id])))


@dataclass(frozen=True, slots=True)
class LexicalProfile:
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
    ) -> LexicalProfile:
        if not token_counts or any(type(count) is not int or count < 1 for count in token_counts):
            raise LexicalGenerationError("native tokenizer counts are required for avg_len")
        return cls(
            id,
            tokenizer,
            tokenizer_version,
            k1,
            b,
            sum(token_counts) / len(token_counts),
            statistics_digest,
        )

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (
                self.id,
                self.tokenizer,
                self.tokenizer_version,
                self.statistics_digest,
            )
        ):
            raise LexicalGenerationError("lexical profile identifiers must be non-empty")
        if not isfinite(self.k1) or self.k1 <= 0:
            raise LexicalGenerationError("BM25 k1 must be finite and positive")
        if not isfinite(self.b) or not 0 <= self.b <= 1:
            raise LexicalGenerationError("BM25 b must be between zero and one")
        if not isfinite(self.avg_len) or self.avg_len <= 0:
            raise LexicalGenerationError("BM25 avg_len must be finite and positive")

    def digest(self) -> str:
        payload = {
            "b": self.b,
            "avg_len": self.avg_len,
            "id": self.id,
            "k1": self.k1,
            "statistics_digest": self.statistics_digest,
            "tokenizer": self.tokenizer,
            "tokenizer_version": self.tokenizer_version,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class LexicalChunk:
    chunk_id: str
    ordinal: int
    content_checksum: str

    def __post_init__(self) -> None:
        if not self.chunk_id or not self.content_checksum:
            raise LexicalGenerationError("chunk identity and checksum are required")
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise LexicalGenerationError("chunk ordinal must be non-negative")


@dataclass(frozen=True, slots=True)
class LexicalGeneration:
    generation_id: str
    workspace_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    lexical_profile: LexicalProfile
    revision: int
    chunks: tuple[LexicalChunk, ...]

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (
                self.generation_id,
                self.workspace_id,
                self.document_id,
                self.document_version_id,
                self.chunk_set_id,
            )
        ):
            raise LexicalGenerationError("generation identity fields are required")
        if type(self.revision) is not int or self.revision < 1:
            raise LexicalGenerationError("generation revision must be positive")
        if not self.chunks:
            raise LexicalGenerationError("lexical generation cannot be empty")
        chunk_ids = [chunk.chunk_id for chunk in self.chunks]
        ordinals = [chunk.ordinal for chunk in self.chunks]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise LexicalGenerationError("chunk IDs must be unique")
        if sorted(ordinals) != list(range(len(self.chunks))):
            raise LexicalGenerationError("chunk ordinals must be contiguous")

    def point_ids(self) -> tuple[str, ...]:
        """Return stable point IDs scoped to this generation."""

        return tuple(lexical_point_id(self.generation_id, chunk.chunk_id) for chunk in self.chunks)

    def content_digest(self) -> str:
        payload = {
            "chunk_set_id": self.chunk_set_id,
            "chunks": [
                {
                    "checksum": chunk.content_checksum,
                    "id": chunk.chunk_id,
                    "ordinal": chunk.ordinal,
                }
                for chunk in self.chunks
            ],
            "document_id": self.document_id,
            "document_version_id": self.document_version_id,
            "generation_id": self.generation_id,
            "lexical_profile": self.lexical_profile.digest(),
            "revision": self.revision,
            "workspace_id": self.workspace_id,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class StageReceipt:
    generation_id: str
    point_count: int
    content_digest: str

    def validate(self, generation: LexicalGeneration) -> None:
        if (
            self.generation_id != generation.generation_id
            or type(self.point_count) is not int
            or self.point_count != len(generation.chunks)
            or self.content_digest != generation.content_digest()
        ):
            raise LexicalGenerationError("generation acknowledgement does not match request")
