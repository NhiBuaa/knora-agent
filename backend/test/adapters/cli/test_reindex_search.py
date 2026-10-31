from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from knora.adapters.cli.reindex_search import build_parser, load_profile, run_reindex
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentTable,
    DocumentVersionTable,
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
            "--profile-file",
            "profile.json",
            "--batch-size",
            "50",
        ]
    )
    assert args.workspace_id == "ws-123"
    assert args.dry_run is True
    assert args.checkpoint_file == Path("ckpt.json")
    assert args.profile_file == Path("profile.json")
    assert args.batch_size == 50


def test_load_profile_with_explicit_file(tmp_path: Path) -> None:
    prof_file = tmp_path / "custom_profile.json"
    prof_file.write_text(
        json.dumps(
            {
                "id": "custom-bm25-v1",
                "tokenizer": "tiktoken",
                "tokenizer_version": "cl100k_base",
                "k1": 1.5,
                "b": 0.8,
                "avg_len": 300.0,
                "statistics_digest": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_profile(prof_file)
    assert loaded.id == "custom-bm25-v1"
    assert loaded.k1 == 1.5
    assert loaded.b == 0.8
    assert loaded.avg_len == 300.0
    assert loaded.statistics_digest == "b" * 64


@pytest.mark.parametrize(
    "configuration_id",
    ["retrieval-hybrid-top8-v3", "retrieval-hybrid-sdm-top8-v3", "retrieval-hybrid-rerank-top8-v3"],
)
def test_load_profile_v3_uses_live_corpus_without_s2_population(
    monkeypatch, configuration_id
) -> None:
    from knora.infrastructure.settings import settings

    monkeypatch.setattr(settings, "retrieval_configuration_id", configuration_id)
    workspace_id = f"test-reindex-profile-{uuid4()}"
    _setup_workspace_and_text_doc(workspace_id, "live-corpus")
    loaded = load_profile(workspace_id=workspace_id)
    assert loaded.id == "lexical-bm25-v1"
    assert loaded.avg_len > 0
    assert loaded.statistics_digest != "0" * 64
    assert run_reindex(workspace_id=workspace_id, profile=loaded)["enqueued"] == 1


def test_load_profile_v3_rejects_missing_corpus(monkeypatch) -> None:
    from knora.infrastructure.settings import settings

    monkeypatch.setattr(settings, "retrieval_configuration_id", "retrieval-hybrid-top8-v3")
    with pytest.raises(ValueError, match="non-empty corpus"):
        load_profile()


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


@pytest.mark.parametrize("existing_parent", [False, True])
def test_reindex_preserves_derivation_identity_and_current_revision(existing_parent: bool) -> None:
    workspace_id = f"test-reindex-parent-{uuid4()}"
    document_id, version_id = _setup_workspace_and_text_doc(workspace_id, "retained-source")
    with SessionFactory.begin() as session:
        document = session.get(DocumentTable, document_id)
        version = session.get(DocumentVersionTable, version_id)
        workspace = session.get(WorkspaceTable, workspace_id)
        chunk_set = session.scalar(
            select(ChunkSetTable).where(ChunkSetTable.document_version_id == version_id)
        )
        document.revision = 7
        workspace.revision = 3
        chunk_set.parser_configuration_id = "pdf-parser-retained-v1"
        chunk_set.normalizer_configuration_id = "pdf-normalizer-retained-v1"
        if existing_parent:
            source = OriginalSourceObjectTable(
                id=str(uuid4()),
                workspace_id=workspace_id,
                document_version_id=version_id,
                object_key=f"{workspace_id}/source",
                raw_sha256=version.normalized_content_checksum,
                byte_size=len(version.normalized_content.encode("utf-8")),
                media_type=version.media_type or "text/plain",
            )
            session.add(source)
            session.flush()
            session.add(
                IngestionJobTable(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    operation="submit_pdf",
                    document_id=document_id,
                    target_document_version_id=version_id,
                    source_object_id=source.id,
                    content_fingerprint=f"retained-parent-{version_id}",
                    parser_configuration_id=chunk_set.parser_configuration_id,
                    normalizer_configuration_id=chunk_set.normalizer_configuration_id,
                    chunking_configuration_id=chunk_set.chunking_configuration_id,
                    derivation_kind="dense",
                    embedding_configuration_id=document.active_embedding_configuration_id,
                    status="succeeded",
                    attempt_count=1,
                    started_at=datetime.now(UTC),
                    terminal_at=datetime.now(UTC),
                    terminal_outcome_code="succeeded",
                )
            )

    result = run_reindex(workspace_id=workspace_id, profile=SAMPLE_PROFILE)
    assert result["enqueued"] == 1
    with SessionFactory() as session:
        child = session.scalar(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == workspace_id,
                IngestionJobTable.derivation_kind == "lexical_index",
            )
        )
        parent = session.get(IngestionJobTable, child.parent_ingestion_job_id)
        assert child.source_revision == 7
        assert child.workspace_revision == 3
        assert (
            child.parser_configuration_id
            == parent.parser_configuration_id
            == "pdf-parser-retained-v1"
        )
        assert (
            child.normalizer_configuration_id
            == parent.normalizer_configuration_id
            == "pdf-normalizer-retained-v1"
        )
        assert (
            child.operation
            == parent.operation
            == ("submit_pdf" if existing_parent else "ingest_document")
        )
        assert child.source_object_id == parent.source_object_id
    assert run_reindex(workspace_id=workspace_id, profile=SAMPLE_PROFILE)["enqueued"] == 0


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
