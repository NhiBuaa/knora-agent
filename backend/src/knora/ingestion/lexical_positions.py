"""Positional derivation and term position indexing for chunks."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from knora.answering.sequential_dependence import CorpusStatistics

_TOKEN_PATTERN = re.compile(r"\w+(?:\.\w+)*", re.UNICODE)


@dataclass(frozen=True, slots=True)
class PositionalToken:
    """A single token with its ordinal index and character offset bounds."""

    token: str
    position: int
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class ChunkPositionalDerivation:
    """Positional derivation for one chunk, pinned to content checksum and tokenizer."""

    chunk_id: str
    content_checksum: str
    token_count: int
    tokens: tuple[PositionalToken, ...]
    tokenizer: str = "tiktoken"
    tokenizer_version: str = "cl100k_base"


def extract_chunk_positions(
    chunk_id: str,
    content: str,
    content_checksum: str,
    *,
    tokenizer: str = "tiktoken",
    tokenizer_version: str = "cl100k_base",
) -> ChunkPositionalDerivation:
    """Extract positional tokens from content, validating checksum."""
    actual_checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if actual_checksum != content_checksum:
        raise ValueError("content checksum mismatch in positional derivation")

    normalized = unicodedata.normalize("NFKC", content).lower()
    tokens = []
    for idx, match in enumerate(_TOKEN_PATTERN.finditer(normalized)):
        tok = match.group()
        start = match.start()
        end = match.end()
        tokens.append(
            PositionalToken(
                token=tok,
                position=idx,
                start_offset=start,
                end_offset=end,
            )
        )

    return ChunkPositionalDerivation(
        chunk_id=chunk_id,
        content_checksum=content_checksum,
        token_count=len(tokens),
        tokens=tuple(tokens),
        tokenizer=tokenizer,
        tokenizer_version=tokenizer_version,
    )


def build_corpus_statistics_from_chunks(
    derivations: Sequence[ChunkPositionalDerivation],
    *,
    statistics_digest: str | None = None,
) -> CorpusStatistics:
    """Aggregate unigram frequencies and length totals from chunk derivations."""
    if not derivations:
        raise ValueError("derivations sequence must not be empty")

    frequencies: dict[str, int] = {}
    total_tokens = 0
    total_chunks = len(derivations)

    for deriv in derivations:
        total_tokens += deriv.token_count
        for tok in deriv.tokens:
            frequencies[tok.token] = frequencies.get(tok.token, 0) + 1

    avg_len = total_tokens / total_chunks if total_chunks > 0 else 0.0

    return CorpusStatistics(
        total_tokens=total_tokens,
        total_chunks=total_chunks,
        unigram_frequencies=frequencies,
        average_chunk_length=avg_len,
        statistics_digest=statistics_digest,
    )
