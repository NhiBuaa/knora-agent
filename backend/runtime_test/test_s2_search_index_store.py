"""PostgreSQL lifecycle proof; invoke only in the owned S2 envelope."""

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkingConfigurationTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    WorkspaceTable,
)
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalProfile,
    StageReceipt,
    StaleGenerationError,
)


@pytest.fixture
def lexical_generation():
    assert os.environ.get("KNORA_S2_ISOLATED_TESTS") == "1", "owned S2 runtime required"
    from sqlalchemy.engine import make_url

    from knora.infrastructure.settings import settings

    url = make_url(settings.database_url)
    assert url.host == "127.0.0.1" and url.port == 15433 and url.database == "knora_153_s2"
    ids = {
        key: str(uuid4())
        for key in ("workspace", "document", "version", "set", "chunk", "config", "generation")
    }
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=ids["workspace"], name="S2 isolated lifecycle"))
        session.flush()
        session.add(
            DocumentTable(
                id=ids["document"],
                workspace_id=ids["workspace"],
                source_key="isolated",
                source_name="isolated.pdf",
                revision=0,
            )
        )
        session.flush()
        session.add(
            DocumentVersionTable(id=ids["version"], document_id=ids["document"], version_number=1)
        )
        session.add(
            ChunkingConfigurationTable(
                id=ids["config"],
                parser_version="fixture",
                chunker_version="fixture",
                tokenizer_name="fixture",
                tokenizer_version="1",
                target_tokens=100,
                overlap_tokens=0,
                max_tokens=100,
            )
        )
        session.flush()
        session.get(DocumentTable, ids["document"]).current_document_version_id = ids["version"]
        session.add(
            ChunkSetTable(
                id=ids["set"],
                document_version_id=ids["version"],
                chunking_configuration_id=ids["config"],
                status="completed",
            )
        )
        session.flush()
        session.add(
            ChunkTable(
                id=ids["chunk"],
                chunk_set_id=ids["set"],
                ordinal=0,
                heading_path=[],
                start_line=1,
                end_line=1,
                content="hạn mức 42",
                content_checksum="a" * 64,
                token_count=4,
            )
        )
    return LexicalGeneration(
        ids["generation"],
        ids["workspace"],
        ids["document"],
        ids["version"],
        ids["set"],
        LexicalProfile("fixture-only", "word", "qdrant-1.19.2", 1.2, 0.75, 4, "b" * 64),
        1,
        (LexicalChunk(ids["chunk"], 0, "a" * 64),),
    )


def test_late_generation_and_partial_receipt_cannot_activate(lexical_generation) -> None:
    store = PostgresSearchIndexStore(SessionFactory)
    first = lexical_generation
    second = replace(first, generation_id=str(uuid4()), revision=2)
    store.request_generation(first, expected_revision=0)
    store.request_generation(second, expected_revision=1)
    receipt = StageReceipt(second.generation_id, len(second.chunks), second.content_digest())
    with pytest.raises(ValueError):
        store.activate_ready(second, replace(receipt, point_count=0))
    store.activate_ready(second, receipt)
    store.activate_ready(second, receipt)
    with pytest.raises(StaleGenerationError):
        store.activate_ready(
            first, StageReceipt(first.generation_id, len(first.chunks), first.content_digest())
        )
    with SessionFactory() as session:
        head = session.scalar(
            select(LexicalHeadTable).where(LexicalHeadTable.document_id == first.document_id)
        )
        assert head.active_generation_id == second.generation_id
        assert session.get(LexicalGenerationTable, first.generation_id).status == "requested"


def test_revoked_generation_cannot_be_replayed(lexical_generation) -> None:
    store = PostgresSearchIndexStore(SessionFactory)
    generation = lexical_generation
    store.request_generation(generation, expected_revision=0)
    receipt = StageReceipt(
        generation.generation_id, len(generation.chunks), generation.content_digest()
    )
    store.activate_ready(generation, receipt)
    store.revoke(workspace_id=generation.workspace_id, document_id=generation.document_id)
    store.revoke(workspace_id=generation.workspace_id, document_id=generation.document_id)
    with pytest.raises(StaleGenerationError):
        store.activate_ready(generation, receipt)


@pytest.mark.parametrize("scope", ["document", "workspace"])
def test_archive_fences_delayed_activation_and_still_allows_revoke(
    lexical_generation, scope
) -> None:
    store = PostgresSearchIndexStore(SessionFactory)
    generation = lexical_generation
    store.request_generation(generation, expected_revision=0)
    receipt = StageReceipt(
        generation.generation_id, len(generation.chunks), generation.content_digest()
    )
    table, identity = (
        (DocumentTable, generation.document_id)
        if scope == "document"
        else (WorkspaceTable, generation.workspace_id)
    )
    with SessionFactory.begin() as session:
        source = session.get(table, identity)
        source.archived = True
        source.revision += 1
    store.revoke(workspace_id=generation.workspace_id, document_id=generation.document_id)
    with SessionFactory.begin() as session:
        source = session.get(table, identity)
        source.archived = False
        source.revision += 1
    with pytest.raises(StaleGenerationError):
        store.activate_ready(generation, receipt)


def test_workspace_archive_cycle_fences_completion_without_explicit_revoke(
    lexical_generation,
) -> None:
    store = PostgresSearchIndexStore(SessionFactory)
    generation = lexical_generation
    store.request_generation(generation, expected_revision=0)
    for archived in (True, False):
        with SessionFactory.begin() as session:
            workspace = session.get(WorkspaceTable, generation.workspace_id)
            workspace.archived = archived
            workspace.revision += 1
    with pytest.raises(StaleGenerationError):
        store.activate_ready(
            generation,
            StageReceipt(
                generation.generation_id, len(generation.chunks), generation.content_digest()
            ),
        )
