from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from knora.adapters.cli.reindex_search import build_parser, run_reindex
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    IngestionJobTable,
    LexicalGenerationTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.ingestion.search_indexing import LexicalProfile
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration

SAMPLE_PROFILE = LexicalProfile(
    id="lexical-bm25-v1",
    tokenizer="tiktoken",
    tokenizer_version="cl100k_base",
    k1=1.2,
    b=0.75,
    avg_len=256.0,
    statistics_digest="0" * 64,
)


def _setup_workspace_and_text_doc(workspace_id: str, source_key: str) -> tuple[str, str]:
    with SessionFactory.begin() as session:
        workspace = session.get(WorkspaceTable, workspace_id)
        if workspace is None:
            workspace = WorkspaceTable(id=workspace_id, name="Test WS")
            session.add(workspace)

    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key=source_key,
        source_name=f"{source_key}.md",
        media_type="text/markdown",
        raw_content=f"# Title\n\nContent for {source_key}.\n".encode(),
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    principal = WorkspacePrincipal(workspace_id=workspace_id, key_id="cli")
    result = use_case.execute(command, principal)
    return result.document_id, result.document_version_id


def test_reindex_search_parser() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--workspace-id",
            "ws-123",
            "--dry-run",
            "--checkpoint-file",
            "ckpt.json",
            "--batch-size",
            "50",
        ]
    )
    assert args.workspace_id == "ws-123"
    assert args.dry_run is True
    assert args.checkpoint_file == Path("ckpt.json")
    assert args.batch_size == 50


def test_reindex_search_dry_run() -> None:
    workspace_id = f"test-reindex-dry-{uuid4()}"
    _setup_workspace_and_text_doc(workspace_id, "doc-1")

    res = run_reindex(workspace_id=workspace_id, dry_run=True, profile=SAMPLE_PROFILE)
    assert res["workspace_id"] == workspace_id
    assert res["scanned"] == 1
    assert res["enqueued"] == 1
    assert res["dry_run"] is True

    # In dry-run, no IngestionJobTable or LexicalGenerationTable should be created
    with SessionFactory() as session:
        jobs = session.scalars(
            select(IngestionJobTable).where(IngestionJobTable.workspace_id == workspace_id)
        ).all()
        assert len(jobs) == 0

        gens = session.scalars(
            select(LexicalGenerationTable).where(
                LexicalGenerationTable.workspace_id == workspace_id
            )
        ).all()
        assert len(gens) == 0


def test_reindex_search_real_run_and_idempotence() -> None:
    workspace_id = f"test-reindex-real-{uuid4()}"
    _setup_workspace_and_text_doc(workspace_id, "doc-1")
    _setup_workspace_and_text_doc(workspace_id, "doc-2")

    res = run_reindex(workspace_id=workspace_id, dry_run=False, profile=SAMPLE_PROFILE)
    assert res["workspace_id"] == workspace_id
    assert res["scanned"] == 2
    assert res["enqueued"] == 2
    assert res["dry_run"] is False

    with SessionFactory() as session:
        # Check parent and child jobs created for both documents
        parent_jobs = session.scalars(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.derivation_kind == "dense",
            )
        ).all()
        assert len(parent_jobs) == 2
        for p in parent_jobs:
            assert p.status == "succeeded"

        child_jobs = session.scalars(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.derivation_kind == "lexical_index",
            )
        ).all()
        assert len(child_jobs) == 2
        for c in child_jobs:
            assert c.status == "queued"
            assert c.parent_ingestion_job_id in {p.id for p in parent_jobs}

        gens = session.scalars(
            select(LexicalGenerationTable).where(
                LexicalGenerationTable.workspace_id == workspace_id
            )
        ).all()
        assert len(gens) == 2
        for g in gens:
            assert g.status == "requested"

        source_objs = session.scalars(
            select(OriginalSourceObjectTable).where(
                OriginalSourceObjectTable.workspace_id == workspace_id
            )
        ).all()
        assert len(source_objs) == 2

    # Run again: idempotent, nothing should be enqueued
    res2 = run_reindex(workspace_id=workspace_id, dry_run=False, profile=SAMPLE_PROFILE)
    assert res2["scanned"] == 2
    assert res2["enqueued"] == 0


def test_reindex_search_checkpoint_resume(tmp_path: Path) -> None:
    workspace_id = f"test-reindex-ckpt-{uuid4()}"
    doc_id_1, _ = _setup_workspace_and_text_doc(workspace_id, "doc-1")
    doc_id_2, _ = _setup_workspace_and_text_doc(workspace_id, "doc-2")

    sorted_docs = sorted([doc_id_1, doc_id_2])
    first_doc_id = sorted_docs[0]

    checkpoint_file = tmp_path / "checkpoint.json"
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "last_document_id": first_doc_id,
                "scanned": 1,
                "enqueued": 0,
            },
            f,
        )

    res = run_reindex(
        workspace_id=workspace_id,
        dry_run=True,
        checkpoint_file=checkpoint_file,
        profile=SAMPLE_PROFILE,
    )
    # Only the remaining document after first_doc_id was scanned
    assert res["scanned"] == 2
    assert res["enqueued"] == 1
