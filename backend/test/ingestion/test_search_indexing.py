from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalGenerationError,
    LexicalProfile,
    StageReceipt,
)


def profile() -> LexicalProfile:
    return LexicalProfile(
        id="bm25-unicode-word-v1",
        tokenizer="word",
        tokenizer_version="qdrant-1.19.2-rust1.98.1",
        k1=1.2,
        b=0.75,
        avg_len=128.0,
        statistics_digest="stats-1",
    )


def generation(*, revision: int = 1) -> LexicalGeneration:
    return LexicalGeneration(
        generation_id="generation-1",
        workspace_id="workspace-1",
        document_id="document-1",
        document_version_id="version-1",
        chunk_set_id="chunk-set-1",
        lexical_profile=profile(),
        revision=revision,
        chunks=(
            LexicalChunk(
                chunk_id="chunk-1",
                ordinal=0,
                content_checksum="checksum-1",
            ),
            LexicalChunk(
                chunk_id="chunk-2",
                ordinal=1,
                content_checksum="checksum-2",
            ),
        ),
    )


def test_generation_identity_and_digest_are_stable() -> None:
    first = generation()
    second = replace(first)

    assert len(set(first.point_ids())) == 2
    assert all(str(UUID(value)) == value for value in first.point_ids())
    assert first.point_ids() == second.point_ids()
    assert first.point_ids() != replace(first, generation_id="generation-2").point_ids()
    assert first.content_digest() == second.content_digest()
    assert first.content_digest() != replace(first, revision=2).content_digest()


@pytest.mark.parametrize(
    "changes",
    [
        {"point_count": 1},
        {"point_count": True},
        {"content_digest": "other"},
        {"generation_id": "other"},
    ],
)
def test_partial_or_mismatched_receipt_is_rejected(changes: dict) -> None:
    requested = generation()
    receipt = StageReceipt(
        requested.generation_id, len(requested.chunks), requested.content_digest()
    )
    receipt.validate(requested)
    with pytest.raises(LexicalGenerationError):
        replace(receipt, **changes).validate(requested)
