"""Finite lexical populations pinned to measured native token-count evidence.

``statistics_digest`` is SHA-256 of canonical JSON containing ordered documents,
their ordered checksum/count pairs, and tokenizer name/version. The separate
``native_evidence_sha256`` pins an externally reviewed measurement artifact; a
caller-supplied hash alone does not establish that native measurement occurred.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from knora.ingestion.search_indexing import LexicalGenerationError, LexicalProfile


class LexicalPopulationError(ValueError):
    """A finite lexical population or observed document does not match its pin."""


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PROFILE_KEYS = {
    "id",
    "tokenizer",
    "tokenizer_version",
    "k1",
    "b",
    "avg_len",
    "statistics_digest",
}


def _object(raw: object, keys: set[str]) -> Mapping[str, object]:
    if not isinstance(raw, Mapping) or set(raw) != keys:
        raise LexicalPopulationError("unexpected population manifest fields")
    return raw


def _sha256(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise LexicalPopulationError("population SHA-256 must be lowercase hex")
    return value


def _items(value: object) -> Sequence[object]:
    if not isinstance(value, (list, tuple)) or not value:
        raise LexicalPopulationError("population list must be non-empty")
    return value


@dataclass(frozen=True, slots=True)
class _Chunk:
    content_checksum: str
    native_token_count: int


@dataclass(frozen=True, slots=True)
class _Document:
    source_sha256: str
    chunks: tuple[_Chunk, ...]


@dataclass(frozen=True, slots=True)
class VerifiedLexicalPopulation:
    id: str
    profile: LexicalProfile
    native_evidence_sha256: str
    documents: tuple[_Document, ...]

    @classmethod
    def from_mapping(cls, raw: object) -> VerifiedLexicalPopulation:
        data = _object(
            raw,
            {
                "schema_version",
                "id",
                "native_evidence_sha256",
                "profile",
                "profile_digest",
                "documents",
            },
        )
        if data["schema_version"] != "lexical-population-v1":
            raise LexicalPopulationError("unsupported population schema")
        if not isinstance(data["id"], str) or not data["id"].strip():
            raise LexicalPopulationError("population ID is required")
        evidence_sha = _sha256(data["native_evidence_sha256"])
        profile_data = _object(data["profile"], _PROFILE_KEYS)
        if any(
            not isinstance(profile_data[key], (int, float)) or isinstance(profile_data[key], bool)
            for key in ("k1", "b", "avg_len")
        ):
            raise LexicalPopulationError("BM25 parameters must be numbers")
        _sha256(profile_data["statistics_digest"])
        try:
            profile = LexicalProfile(**profile_data)
        except (LexicalGenerationError, TypeError, ValueError) as error:
            raise LexicalPopulationError("invalid lexical profile") from error
        if _sha256(data["profile_digest"]) != profile.digest():
            raise LexicalPopulationError("lexical profile digest mismatch")

        documents = []
        source_hashes: set[str] = set()
        for raw_document in _items(data["documents"]):
            document = _object(raw_document, {"source_sha256", "chunks"})
            source_sha = _sha256(document["source_sha256"])
            if source_sha in source_hashes:
                raise LexicalPopulationError("duplicate population source")
            source_hashes.add(source_sha)
            chunks = []
            for raw_chunk in _items(document["chunks"]):
                chunk = _object(raw_chunk, {"content_checksum", "native_token_count"})
                checksum = _sha256(chunk["content_checksum"])
                count = chunk["native_token_count"]
                if type(count) is not int or count < 1:
                    raise LexicalPopulationError("invalid native token count")
                chunks.append(_Chunk(checksum, count))
            documents.append(_Document(source_sha, tuple(chunks)))

        pinned = tuple(documents)
        statistics = {
            "documents": [
                {
                    "source_sha256": document.source_sha256,
                    "chunks": [
                        {
                            "content_checksum": chunk.content_checksum,
                            "native_token_count": chunk.native_token_count,
                        }
                        for chunk in document.chunks
                    ],
                }
                for document in pinned
            ],
            "tokenizer": profile.tokenizer,
            "tokenizer_version": profile.tokenizer_version,
        }
        digest = hashlib.sha256(
            json.dumps(statistics, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        counts = tuple(chunk.native_token_count for document in pinned for chunk in document.chunks)
        if profile.statistics_digest != digest or profile.avg_len != sum(counts) / len(counts):
            raise LexicalPopulationError("population statistics mismatch")
        return cls(data["id"], profile, evidence_sha, pinned)

    def validate_document(
        self, source_sha256: str, chunk_texts: Sequence[str], profile: LexicalProfile
    ) -> tuple[int, ...]:
        """Return pinned native counts only after exact source/content comparison."""

        if not isinstance(profile, LexicalProfile) or profile.digest() != self.profile.digest():
            raise LexicalPopulationError("population profile mismatch")
        document = next(
            (item for item in self.documents if item.source_sha256 == source_sha256), None
        )
        if document is None or not isinstance(chunk_texts, (list, tuple)):
            raise LexicalPopulationError("unrecognized population source")
        if len(chunk_texts) != len(document.chunks):
            raise LexicalPopulationError("population chunk count mismatch")
        for text, chunk in zip(chunk_texts, document.chunks, strict=True):
            if (
                type(text) is not str
                or hashlib.sha256(text.encode("utf-8")).hexdigest() != chunk.content_checksum
            ):
                raise LexicalPopulationError("population chunk content mismatch")
        return tuple(chunk.native_token_count for chunk in document.chunks)

    def validate_corpus(
        self, documents: Sequence[tuple[str, Sequence[str]]], profile: LexicalProfile
    ) -> None:
        """Require every authorized source exactly once, with the pinned profile."""

        if (
            not isinstance(profile, LexicalProfile)
            or profile.digest() != self.profile.digest()
            or not isinstance(documents, (list, tuple))
            or len(documents) != len(self.documents)
        ):
            raise LexicalPopulationError("population profile or source count mismatch")
        seen: set[str] = set()
        for document in documents:
            if not isinstance(document, (list, tuple)) or len(document) != 2:
                raise LexicalPopulationError("malformed population document")
            source_sha, chunk_texts = document
            if not isinstance(source_sha, str):
                raise LexicalPopulationError("malformed population source")
            if source_sha in seen:
                raise LexicalPopulationError("duplicate population source")
            seen.add(source_sha)
            self.validate_document(source_sha, chunk_texts, profile)
