"""PostgreSQL lifecycle proof; invoke only in the owned S2 envelope."""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
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
    QuestionTraceTable,
    WorkspaceTable,
)
from knora.answering.stores import LexicalGeneration as RetrievedGeneration
from knora.answering.stores import QuestionTraceRecord
from knora.domain.errors import KnoraError
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalGenerationError,
    LexicalProfile,
    StageReceipt,
    StaleGenerationError,
)


def _manifest_row():
    generation = LexicalGeneration(
        "generation",
        "workspace",
        "document",
        "version",
        "set",
        LexicalProfile("fixture", "word", "1.19.2", 1.2, 0.75, 4, "b" * 64),
        1,
        (LexicalChunk("chunk", 0, "a" * 64),),
    )
    return generation, SimpleNamespace(
        id="generation",
        workspace_id="workspace",
        document_id="document",
        document_version_id="version",
        chunk_set_id="set",
        revision=1,
        profile_digest=generation.lexical_profile.digest(),
        content_digest=generation.content_digest(),
        expected_count=1,
        manifest=json.loads(json.dumps(asdict(generation))),
    )


def test_manifest_decode_preserves_json_roundtrip() -> None:
    generation, row = _manifest_row()
    assert PostgresSearchIndexStore._decode_generation(row) == generation


@pytest.mark.parametrize("corruption", ["identity", "profile", "chunk", "count", "shape"])
def test_manifest_decode_rejects_changed_persisted_provenance(corruption) -> None:
    _, row = _manifest_row()
    if corruption == "identity":
        row.manifest["workspace_id"] = "other-workspace"
    elif corruption == "profile":
        row.manifest["lexical_profile"]["tokenizer_version"] = "changed"
    elif corruption == "chunk":
        row.manifest["chunks"][0]["content_checksum"] = "c" * 64
    elif corruption == "count":
        row.expected_count = 2
    else:
        row.manifest["chunks"] = None
    with pytest.raises(LexicalGenerationError):
        PostgresSearchIndexStore._decode_generation(row)


@pytest.fixture
def lexical_generation():
    from backend.runtime_test.s2_runtime_guard import require_owned_s2_database

    require_owned_s2_database(SessionFactory.kw["bind"].url)
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


@pytest.mark.parametrize("change", ["document", "workspace", "revoke"])
def test_trace_commit_revalidates_after_pre_provider_transaction_closes(lexical_generation, change):
    population = VerifiedLexicalPopulation.from_mapping(
        json.loads(
            Path("evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json").read_text()
        )
    )
    content = "Refund requests are accepted within 30 days."
    checksum = hashlib.sha256(content.encode()).hexdigest()
    generation = replace(
        lexical_generation,
        lexical_profile=population.profile,
        chunks=(replace(lexical_generation.chunks[0], content_checksum=checksum),),
    )
    with SessionFactory.begin() as session:
        version = session.get(DocumentVersionTable, generation.document_version_id)
        version.raw_sha256 = population.documents[0].source_sha256
        version.media_type = "application/pdf"
        chunk = session.get(ChunkTable, generation.chunks[0].chunk_id)
        chunk.content, chunk.content_checksum, chunk.token_count = content, checksum, 8
        chunk.page_start = chunk.page_end = 1
        chunk.start_offset, chunk.end_offset = 0, len(content)
    index_store = PostgresSearchIndexStore(SessionFactory)
    index_store.request_generation(generation, expected_revision=0)
    index_store.activate_ready(
        generation,
        StageReceipt(generation.generation_id, len(generation.chunks), generation.content_digest()),
    )
    snapshot = RetrievedGeneration(
        generation.workspace_id,
        generation.document_id,
        generation.document_version_id,
        generation.chunk_set_id,
        generation.generation_id,
        generation.lexical_profile.id,
    )
    answering = PostgresAnsweringStore(SessionFactory, lexical_population=population)
    answering.revalidate_lexical_snapshot(
        generation.workspace_id, generation.lexical_profile.id, (snapshot,)
    )
    # A separate transaction must obtain the lifecycle lock after the pre-provider call returns.
    with SessionFactory.begin() as session:
        session.execute(text("SET LOCAL lock_timeout = '1s'"))
        if change == "revoke":
            index_store.revoke_in_transaction(
                session, workspace_id=generation.workspace_id, document_id=generation.document_id
            )
        else:
            table, identity = (
                (DocumentTable, generation.document_id)
                if change == "document"
                else (WorkspaceTable, generation.workspace_id)
            )
            row = session.get(table, identity)
            row.archived = True
            row.revision += 1
    trace = QuestionTraceRecord(
        workspace_id=generation.workspace_id,
        question="Lifecycle fixture?",
        retrieval_configuration_id="bm25-fixture",
        embedding_configuration_id=None,
        candidate_decisions=(),
        retrieved_chunk_ids=(),
        embedding_set_ids=(),
        chunk_set_ids=(generation.chunk_set_id,),
        decision="REFUSAL",
        answer=None,
        refusal_reason="INSUFFICIENT_EVIDENCE",
        generation_status="not_called",
        trace_schema_version=3,
        provider_metadata={
            "retrieval": {"mode": "bm25-only", "lexical_generations": [asdict(snapshot)]}
        },
    )
    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        answering.persist_trace(trace)
    with SessionFactory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(QuestionTraceTable)
                .where(QuestionTraceTable.workspace_id == generation.workspace_id)
            )
            == 0
        )
