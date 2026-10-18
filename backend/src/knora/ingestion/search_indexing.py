"""Immutable lexical indexing inputs; lifecycle authority belongs to PostgreSQL."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Protocol
from uuid import NAMESPACE_URL, uuid5

from knora.ingestion.job_processing import (
    CancellationToken,
    HandlerFailureKindV1,
    IngestionWork,
    PdfDerivationSuccess,
    PdfExtractionSuccess,
    WorkFailed,
    WorkHandler,
    WorkOutcome,
    WorkSucceeded,
    WorkSuperseded,
)

if TYPE_CHECKING:
    from knora.ingestion.lexical_population import VerifiedLexicalPopulation


class LexicalGenerationError(ValueError):
    """The generation cannot be accepted at the lexical trust boundary."""


class StaleGenerationError(LexicalGenerationError):
    """A generation or revision is no longer the requested one."""


class LexicalProjectionUnavailable(RuntimeError):
    """A transport-classified transient projection storage failure."""


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


@dataclass(frozen=True, slots=True)
class LexicalIndexInput:
    generation: LexicalGeneration
    chunk_texts: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class LexicalIndexSuccess:
    generation: LexicalGeneration
    receipt: StageReceipt

    def __post_init__(self) -> None:
        self.receipt.validate(self.generation)


class LexicalIndexStore(Protocol):
    def load_generation(self, work: IngestionWork) -> LexicalIndexInput:
        """Load authoritative text and reject a stale enqueue snapshot."""
        ...


class LexicalIndexPort(Protocol):
    def stage_generation(
        self, generation: LexicalGeneration, chunk_texts: Mapping[str, str]
    ) -> StageReceipt: ...


class LexicalIndexHandler:
    """Stage one durable generation; fenced activation belongs to finalization."""

    def __init__(
        self,
        *,
        store: LexicalIndexStore,
        index: LexicalIndexPort,
        lexical_population: VerifiedLexicalPopulation | None = None,
    ) -> None:
        self._store = store
        self._index = index
        self._lexical_population = lexical_population

    def execute(
        self, work: IngestionWork, cancellation: CancellationToken
    ) -> WorkOutcome[LexicalIndexSuccess]:
        from knora.ingestion.lexical_population import LexicalPopulationError

        del cancellation
        if work.derivation_kind != "lexical_index":
            return WorkFailed(HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid")
        try:
            loaded = self._store.load_generation(work)
            generation = loaded.generation
            if (
                generation.generation_id != work.lexical_generation_id
                or generation.workspace_id != work.workspace_id
                or generation.document_id != work.document_id
                or generation.document_version_id != work.document_version_id
                or (
                    work.lexical_profile_digest is not None
                    and generation.lexical_profile.digest() != work.lexical_profile_digest
                )
            ):
                raise LexicalGenerationError("generation does not match claimed work")
            texts = dict(loaded.chunk_texts)
            if len(texts) != len(loaded.chunk_texts) or set(texts) != {
                chunk.chunk_id for chunk in generation.chunks
            }:
                raise LexicalGenerationError("authoritative texts differ from generation")
            for chunk in generation.chunks:
                text = texts[chunk.chunk_id]
                if (
                    not isinstance(text, str)
                    or not text.strip()
                    or hashlib.sha256(text.encode("utf-8")).hexdigest() != chunk.content_checksum
                ):
                    raise LexicalGenerationError("authoritative text checksum is invalid")
            if self._lexical_population is None:
                raise LexicalGenerationError("verified lexical population is required")
            self._lexical_population.validate_document(
                work.source_sha256,
                tuple(
                    texts[chunk.chunk_id]
                    for chunk in sorted(generation.chunks, key=lambda c: c.ordinal)
                ),
                generation.lexical_profile,
            )
            receipt = self._index.stage_generation(generation, texts)
            if not isinstance(receipt, StageReceipt):
                raise LexicalGenerationError("projection receipt is missing")
            return WorkSucceeded(LexicalIndexSuccess(generation, receipt))
        except StaleGenerationError:
            return WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot")
        except (LexicalGenerationError, LexicalPopulationError):
            return WorkFailed(HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid")
        except LexicalProjectionUnavailable:
            return WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")


class DerivationJobHandler:
    """Dispatch durable kinds through the existing ingestion attempt runtime."""

    def __init__(
        self,
        *,
        pdf_handler: WorkHandler[PdfDerivationSuccess | PdfExtractionSuccess],
        index_handler: WorkHandler[LexicalIndexSuccess],
    ) -> None:
        self._pdf_handler = pdf_handler
        self._index_handler = index_handler

    def execute(
        self, work: IngestionWork, cancellation: CancellationToken
    ) -> WorkOutcome[PdfDerivationSuccess | PdfExtractionSuccess | LexicalIndexSuccess]:
        if work.derivation_kind == "lexical_index":
            return self._index_handler.execute(work, cancellation)
        return self._pdf_handler.execute(work, cancellation)
