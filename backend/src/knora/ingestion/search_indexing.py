"""Pure lexical-generation contracts used before durable index integration.

The ledger is deliberately in-memory.  PostgreSQL is the production authority; this
small state machine makes the acknowledgement and CAS rules testable without a
database or a Qdrant process.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from math import isfinite
from typing import Literal


class LexicalGenerationError(ValueError):
    """The generation cannot be accepted at the lexical trust boundary."""


class StaleGenerationError(LexicalGenerationError):
    """A generation or revision is no longer the requested one."""


GenerationStatus = Literal["requested", "ready", "active", "revoked"]


@dataclass(frozen=True, slots=True)
class LexicalProfile:
    id: str
    tokenizer: str
    tokenizer_version: str
    k1: float
    b: float
    avg_len: float
    statistics_digest: str

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
        if isinstance(self.ordinal, bool) or self.ordinal < 0:
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
        if isinstance(self.revision, bool) or self.revision < 1:
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

        return tuple(f"{self.generation_id}:{chunk.chunk_id}" for chunk in self.chunks)

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
class GenerationRecord:
    generation_id: str
    workspace_id: str
    document_id: str
    revision: int
    status: GenerationStatus
    point_count: int | None = None
    content_digest: str | None = None


class GenerationLedger:
    """Offline reference state machine for request, acknowledgement and CAS activation."""

    def __init__(self) -> None:
        self._records: dict[str, GenerationRecord] = {}
        self._active: dict[tuple[str, str], str] = {}

    def request(self, generation: LexicalGeneration) -> GenerationRecord:
        existing = self._records.get(generation.generation_id)
        digest = generation.content_digest()
        if existing is not None:
            if existing.revision != generation.revision or existing.content_digest not in {
                None,
                digest,
            }:
                raise StaleGenerationError("generation identity was reused with different content")
            return existing
        record = GenerationRecord(
            generation_id=generation.generation_id,
            workspace_id=generation.workspace_id,
            document_id=generation.document_id,
            revision=generation.revision,
            status="requested",
            content_digest=digest,
        )
        self._records[generation.generation_id] = record
        return record

    def acknowledge(
        self,
        *,
        generation_id: str,
        revision: int,
        point_count: int,
        content_digest: str,
    ) -> GenerationRecord:
        record = self._records.get(generation_id)
        if record is None or record.revision != revision or record.status == "revoked":
            raise StaleGenerationError("generation acknowledgement is stale")
        if point_count < 1 or record.content_digest != content_digest:
            raise LexicalGenerationError("generation acknowledgement does not match request")
        if record.status == "active":
            return record
        ready = replace(record, status="ready", point_count=point_count)
        self._records[generation_id] = ready
        return ready

    def activate(
        self,
        *,
        workspace_id: str,
        document_id: str,
        expected_revision: int,
        generation_id: str,
    ) -> GenerationRecord:
        record = self._records.get(generation_id)
        if (
            record is None
            or record.workspace_id != workspace_id
            or record.document_id != document_id
            or record.revision != expected_revision
            or record.status != "ready"
        ):
            raise StaleGenerationError("generation activation compare-and-set failed")
        active = replace(record, status="active")
        self._records[generation_id] = active
        self._active[(workspace_id, document_id)] = generation_id
        return active

    def revoke(self, generation_id: str) -> None:
        record = self._records.get(generation_id)
        if record is None:
            raise StaleGenerationError("unknown generation cannot be revoked")
        self._records[generation_id] = replace(record, status="revoked")
        key = (record.workspace_id, record.document_id)
        if self._active.get(key) == generation_id:
            del self._active[key]

    def active(self, workspace_id: str, document_id: str) -> GenerationRecord | None:
        generation_id = self._active.get((workspace_id, document_id))
        return self._records.get(generation_id) if generation_id is not None else None
