from __future__ import annotations

from dataclasses import replace

import pytest

from knora.ingestion.search_indexing import (
    GenerationLedger,
    LexicalChunk,
    LexicalGeneration,
    LexicalProfile,
    StaleGenerationError,
)


def profile() -> LexicalProfile:
    return LexicalProfile(
        id="bm25-unicode-multilingual-v1",
        tokenizer="multilingual",
        tokenizer_version="qdrant-native-v1",
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

    assert first.point_ids() == ("generation-1:chunk-1", "generation-1:chunk-2")
    assert first.content_digest() == second.content_digest()
    assert first.content_digest() == (
        "e9721cdf2c7ebec60e2ae4bcc4b193c622dda5263357330f374ca05e57e16236"
    )


def test_ledger_is_idempotent_and_activates_with_compare_and_set() -> None:
    ledger = GenerationLedger()
    requested = ledger.request(generation())
    assert requested.status == "requested"

    staged = ledger.acknowledge(
        generation_id=requested.generation_id,
        revision=requested.revision,
        point_count=2,
        content_digest=generation().content_digest(),
    )
    assert staged.status == "ready"
    assert (
        ledger.acknowledge(
            generation_id=requested.generation_id,
            revision=requested.revision,
            point_count=2,
            content_digest=generation().content_digest(),
        )
        == staged
    )

    active = ledger.activate(
        workspace_id="workspace-1",
        document_id="document-1",
        expected_revision=1,
        generation_id="generation-1",
    )
    assert active.generation_id == "generation-1"
    assert ledger.active("workspace-1", "document-1") == active


def test_activation_rejects_stale_revision_and_revoke_is_fail_closed() -> None:
    ledger = GenerationLedger()
    ledger.request(generation())
    ledger.acknowledge(
        generation_id="generation-1",
        revision=1,
        point_count=2,
        content_digest=generation().content_digest(),
    )

    with pytest.raises(StaleGenerationError):
        ledger.activate(
            workspace_id="workspace-1",
            document_id="document-1",
            expected_revision=2,
            generation_id="generation-1",
        )

    ledger.activate(
        workspace_id="workspace-1",
        document_id="document-1",
        expected_revision=1,
        generation_id="generation-1",
    )
    ledger.revoke("generation-1")
    assert ledger.active("workspace-1", "document-1") is None
