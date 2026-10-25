from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from knora.ingestion.job_processing import (
    HandlerFailureKindV1,
    IngestionWork,
    WorkFailed,
    WorkSucceeded,
)
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalGenerationError,
    LexicalIndexHandler,
    LexicalIndexInput,
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


def test_lexical_index_handler_permits_dynamic_v3_without_population() -> None:
    gen = generation()
    text_1 = "valid text one"
    text_2 = "valid text two"
    import hashlib

    hash_1 = hashlib.sha256(text_1.encode("utf-8")).hexdigest()
    hash_2 = hashlib.sha256(text_2.encode("utf-8")).hexdigest()
    gen = replace(
        gen,
        chunks=(
            LexicalChunk(chunk_id="chunk-1", ordinal=0, content_checksum=hash_1),
            LexicalChunk(chunk_id="chunk-2", ordinal=1, content_checksum=hash_2),
        ),
    )

    class StubStore:
        def load_generation(self, work):
            return LexicalIndexInput(
                generation=gen,
                chunk_texts=(("chunk-1", text_1), ("chunk-2", text_2)),
            )

    class StubIndex:
        def stage_generation(self, g, texts, chunk_vectors=None):
            return StageReceipt(g.generation_id, len(g.chunks), g.content_digest())

    handler = LexicalIndexHandler(
        store=StubStore(),
        index=StubIndex(),
        lexical_population=None,
    )
    work = IngestionWork(
        workspace_id="workspace-1",
        document_id="document-1",
        document_version_id="version-1",
        source_object_id="source-1",
        source_object_key="key-1",
        source_media_type="text/plain",
        parser_configuration_id="p-1",
        normalizer_configuration_id="n-1",
        chunking_configuration_id="chunk-set-1",
        embedding_configuration_id=None,
        source_sha256="s" * 64,
        source_byte_size=100,
        derivation_kind="lexical_index",
        lexical_generation_id="generation-1",
        lexical_profile_digest=gen.lexical_profile.digest(),
        source_revision=1,
        workspace_revision=1,
        ingestion_job_id="job-1",
    )

    class DummyToken:
        def is_cancelled(self) -> bool:
            return False

        def cancel(self) -> None:
            pass

    outcome = handler.execute(work, DummyToken())
    assert isinstance(outcome, WorkSucceeded)
    assert outcome.payload.receipt.point_count == 2


def test_lexical_index_handler_requires_population_for_s2_finite_profiles() -> None:
    s2_profile = LexicalProfile(
        id="bm25-word-frozen47-population-v1",
        tokenizer="word",
        tokenizer_version="qdrant-1.19.2",
        k1=1.2,
        b=0.75,
        avg_len=128.0,
        statistics_digest="s" * 64,
    )
    gen = replace(generation(), lexical_profile=s2_profile)
    text_1 = "valid text one"
    text_2 = "valid text two"
    import hashlib

    hash_1 = hashlib.sha256(text_1.encode("utf-8")).hexdigest()
    hash_2 = hashlib.sha256(text_2.encode("utf-8")).hexdigest()
    gen = replace(
        gen,
        chunks=(
            LexicalChunk(chunk_id="chunk-1", ordinal=0, content_checksum=hash_1),
            LexicalChunk(chunk_id="chunk-2", ordinal=1, content_checksum=hash_2),
        ),
    )

    class StubStore:
        def load_generation(self, work):
            return LexicalIndexInput(
                generation=gen,
                chunk_texts=(("chunk-1", text_1), ("chunk-2", text_2)),
            )

    class StubIndex:
        def stage_generation(self, g, texts, chunk_vectors=None):
            return StageReceipt(g.generation_id, len(g.chunks), g.content_digest())

    handler = LexicalIndexHandler(
        store=StubStore(),
        index=StubIndex(),
        lexical_population=None,
    )
    work = IngestionWork(
        workspace_id="workspace-1",
        document_id="document-1",
        document_version_id="version-1",
        source_object_id="source-1",
        source_object_key="key-1",
        source_media_type="text/plain",
        parser_configuration_id="p-1",
        normalizer_configuration_id="n-1",
        chunking_configuration_id="chunk-set-1",
        embedding_configuration_id=None,
        source_sha256="s" * 64,
        source_byte_size=100,
        derivation_kind="lexical_index",
        lexical_generation_id="generation-1",
        lexical_profile_digest=gen.lexical_profile.digest(),
        source_revision=1,
        workspace_revision=1,
        ingestion_job_id="job-1",
    )

    class DummyToken:
        def is_cancelled(self) -> bool:
            return False

        def cancel(self) -> None:
            pass

    outcome = handler.execute(work, DummyToken())
    assert isinstance(outcome, WorkFailed)
    assert outcome.failure_kind == HandlerFailureKindV1.CONFIGURATION_INVALID
