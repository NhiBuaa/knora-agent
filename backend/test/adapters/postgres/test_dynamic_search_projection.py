"""Dynamic uploads must become searchable without an operator reindex command."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import DocumentTable, LexicalGenerationTable, WorkspaceTable
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.ingestion.search_indexing import (
    DynamicSearchIndexHandler,
    StageReceipt,
    StaleGenerationError,
)
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


class Projection:
    def __init__(self):
        self.calls = []
        self.fail_after = None

    def stage_generation(self, generation, chunk_texts, chunk_vectors=None):
        self.calls.append(generation.generation_id)
        assert set(chunk_texts) == set(chunk_vectors)
        if self.fail_after == len(self.calls):
            raise OSError("projection unavailable")
        return StageReceipt(
            generation.generation_id,
            len(generation.chunks),
            generation.content_digest(),
        )


def harness():
    workspace_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Dynamic projection test"))
    embedding = EmbeddingConfiguration.milestone_one_local()
    ingestion = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )

    def upload(key):
        return ingestion.execute(
            IngestDocumentCommand(
                workspace_id=workspace_id,
                source_key=key,
                source_name=key,
                media_type="text/plain",
                raw_content=b"Reports contain seven chapters.",
                chunking_configuration=ChunkingConfiguration.milestone_one(),
                embedding_configuration=embedding,
            ),
            WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
        )

    store = PostgresSearchIndexStore(SessionFactory)
    projection = Projection()
    handler = DynamicSearchIndexHandler(
        store=store,
        index=projection,
        lexical_policy_id="lexical-bm25-v1",
        embedding_configuration_id=embedding.id,
    )
    return workspace_id, upload, store, projection, handler


def test_upload_is_indexed_and_repeated_reconciliation_is_noop():
    workspace, upload, store, projection, handler = harness()
    uploaded = upload("first.txt")
    assert handler.reconcile_workspace(workspace) == 1
    generations = store.read_active_generations(workspace, "lexical-bm25-v1")
    assert [g.document_id for g in generations] == [uploaded.document_id]
    assert handler.reconcile_workspace(workspace) == 0
    assert len(projection.calls) == 1


def test_new_document_reprofiles_whole_corpus_and_recovers_partial_projection():
    workspace, upload, store, projection, handler = harness()
    first = upload("first.txt")
    handler.reconcile_workspace(workspace)
    old = store.read_active_generations(workspace, "lexical-bm25-v1")
    second = upload("same-content-different-source.txt")
    projection.fail_after = len(projection.calls) + 2
    with pytest.raises(OSError):
        handler.reconcile_workspace(workspace)
    assert store.read_active_generations(workspace, "lexical-bm25-v1") == old
    with SessionFactory() as session:
        pending = session.scalars(
            select(LexicalGenerationTable.id).where(
                LexicalGenerationTable.workspace_id == workspace,
                LexicalGenerationTable.status == "requested",
            )
        ).all()
    assert len(pending) == 2
    projection.fail_after = None
    assert handler.reconcile_workspace(workspace) == 2
    current = store.read_active_generations(workspace, "lexical-bm25-v1")
    assert {g.document_id for g in current} == {first.document_id, second.document_id}
    assert len({g.lexical_profile.digest() for g in current}) == 1
    assert {g.generation_id for g in current} == set(pending)


def test_source_revision_change_during_projection_prevents_activation():
    workspace, upload, store, projection, handler = harness()
    document = upload("source.txt")
    pending = store.prepare_dynamic_corpus(
        workspace, "lexical-bm25-v1", EmbeddingConfiguration.milestone_one_local().id
    )
    receipts = tuple(
        (
            i.generation,
            projection.stage_generation(i.generation, dict(i.chunk_texts), dict(i.chunk_vectors)),
        )
        for i in pending
    )
    with SessionFactory.begin() as session:
        session.get(DocumentTable, document.document_id).revision += 1
    with pytest.raises(StaleGenerationError):
        store.commit_corpus_transition(receipts)
    assert handler.reconcile_workspace(workspace) == 1


def test_workspace_waits_for_current_dense_derivation_and_never_mixes_configurations():
    workspace, upload, store, projection, handler = harness()
    document = upload("pending.txt")
    assert store.prepare_dynamic_corpus(workspace, "lexical-bm25-v1", "foreign-config") == ()
    with SessionFactory.begin() as session:
        row = session.get(DocumentTable, document.document_id)
        row.active_embedding_set_id = None
        row.active_embedding_configuration_id = None
        row.revision += 1
    assert handler.reconcile_workspace(workspace) == 0
    assert projection.calls == []


def test_membership_change_during_projection_rejects_partial_corpus_activation():
    workspace, upload, store, projection, handler = harness()
    upload("first.txt")
    pending = store.prepare_dynamic_corpus(
        workspace, "lexical-bm25-v1", EmbeddingConfiguration.milestone_one_local().id
    )
    receipts = tuple(
        (
            i.generation,
            projection.stage_generation(i.generation, dict(i.chunk_texts), dict(i.chunk_vectors)),
        )
        for i in pending
    )
    upload("second.txt")
    with pytest.raises(StaleGenerationError, match="all canonical"):
        store.commit_corpus_transition(receipts)
    assert handler.reconcile_workspace(workspace) == 2


def test_reconciliation_continues_other_workspaces_after_one_projection_failure(monkeypatch):
    workspace, upload, store, projection, handler = harness()
    upload("first.txt")
    processed = []
    monkeypatch.setattr(store, "dynamic_workspace_ids", lambda _id: ("unavailable", workspace))
    reconcile = handler.reconcile_workspace

    def attempt(workspace_id):
        processed.append(workspace_id)
        if workspace_id == "unavailable":
            raise OSError("offline")
        return reconcile(workspace_id)

    monkeypatch.setattr(handler, "reconcile_workspace", attempt)
    handler.run_once()
    assert processed == ["unavailable", workspace]
    assert len(store.read_active_generations(workspace, "lexical-bm25-v1")) == 1
