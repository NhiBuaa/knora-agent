"""CLI utility to create missing lexical/search indexing jobs for existing documents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import func, select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.answering.retrieval_configuration import resolve_retrieval_configuration
from knora.infrastructure.lexical_configuration import load_lexical_population
from knora.infrastructure.settings import settings
from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration, LexicalProfile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reindex search projections for documents in a workspace"
    )
    parser.add_argument("--workspace-id", required=True, help="Workspace identifier to reindex")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan documents and report jobs that would be created without modifying the database",
    )
    parser.add_argument(
        "--checkpoint-file",
        type=Path,
        default=None,
        help="Path to JSON file used to save and resume scan progress across batches",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to inspect per batch",
    )
    return parser


def load_profile() -> LexicalProfile:
    configuration = resolve_retrieval_configuration(
        settings.retrieval_configuration_id,
        vector_min_similarity=settings.vector_min_similarity,
    )
    population = load_lexical_population(configuration, settings.lexical_population_manifest)
    if population is None:
        raise ValueError("reindex requires a reviewed lexical population profile")
    return population.profile


def run_reindex(
    *,
    workspace_id: str,
    dry_run: bool = False,
    checkpoint_file: Path | None = None,
    batch_size: int = 100,
    profile: LexicalProfile | None = None,
) -> dict[str, int | str | bool]:
    if profile is None:
        profile = load_profile()
    profile_digest = profile.digest()
    store = PostgresSearchIndexStore(SessionFactory)

    last_doc_id: str | None = None
    scanned_count = 0
    enqueued_count = 0

    if checkpoint_file is not None and checkpoint_file.exists():
        try:
            with open(checkpoint_file, encoding="utf-8") as f:
                ckpt_data = json.load(f)
                last_doc_id = ckpt_data.get("last_document_id")
                scanned_count = ckpt_data.get("scanned", 0)
                enqueued_count = ckpt_data.get("enqueued", 0)
        except Exception:
            pass

    while True:
        with SessionFactory() as session:
            workspace = session.get(WorkspaceTable, workspace_id)
            if workspace is None:
                raise ValueError(f"Workspace {workspace_id} not found")

            query = (
                select(DocumentTable)
                .where(
                    DocumentTable.workspace_id == workspace_id,
                    DocumentTable.archived.is_(False),
                    DocumentTable.current_document_version_id.is_not(None),
                )
                .order_by(DocumentTable.id)
                .limit(batch_size)
            )
            if last_doc_id is not None:
                query = query.where(DocumentTable.id > last_doc_id)

            batch = session.scalars(query).all()
            if not batch:
                break

            for document in batch:
                scanned_count += 1
                last_doc_id = document.id

                version_id = document.current_document_version_id
                version = session.get(DocumentVersionTable, version_id)
                if version is None:
                    continue

                # Check if document already has active or requested generation
                existing_gen = session.scalar(
                    select(LexicalGenerationTable).where(
                        LexicalGenerationTable.document_id == document.id,
                        LexicalGenerationTable.document_version_id == version.id,
                        LexicalGenerationTable.profile_digest == profile_digest,
                        LexicalGenerationTable.status.in_(("requested", "active")),
                    )
                )
                if existing_gen is not None:
                    continue

                # Find chunk_set_id
                chunk_set = session.scalar(
                    select(ChunkSetTable)
                    .where(ChunkSetTable.document_version_id == version.id)
                    .order_by(ChunkSetTable.id.desc())
                )
                if chunk_set is None:
                    continue

                chunks = session.scalars(
                    select(ChunkTable)
                    .where(ChunkTable.chunk_set_id == chunk_set.id)
                    .order_by(ChunkTable.ordinal)
                ).all()
                if not chunks:
                    continue

                if dry_run:
                    enqueued_count += 1
                    continue

                # Execute in an isolated transaction per document
                with session.begin_nested():
                    source_object = session.scalar(
                        select(OriginalSourceObjectTable).where(
                            OriginalSourceObjectTable.document_version_id == version.id
                        )
                    )
                    if source_object is None:
                        checksum = (
                            version.raw_sha256 or version.normalized_content_checksum or "0" * 64
                        )
                        content_bytes = (version.normalized_content or "").encode("utf-8")
                        source_object = OriginalSourceObjectTable(
                            id=str(uuid4()),
                            workspace_id=workspace_id,
                            document_version_id=version.id,
                            object_key=f"{workspace_id}/text/{version.id}",
                            raw_sha256=checksum,
                            byte_size=len(content_bytes),
                            media_type=version.media_type or "text/plain",
                        )
                        session.add(source_object)
                        session.flush()

                    # Find or create parent dense job
                    parent_job = session.scalar(
                        select(IngestionJobTable).where(
                            IngestionJobTable.workspace_id == workspace_id,
                            IngestionJobTable.target_document_version_id == version.id,
                            IngestionJobTable.derivation_kind == "dense",
                            IngestionJobTable.parent_ingestion_job_id.is_(None),
                        )
                    )
                    database_now = session.scalar(select(func.now()))
                    if parent_job is None:
                        # Find embedding config if available
                        emb_config_id = document.active_embedding_configuration_id
                        if emb_config_id is None:
                            emb_config = session.scalar(select(EmbeddingConfigurationTable))
                            emb_config_id = emb_config.id if emb_config else "default"

                        parent_fingerprint = (
                            f"text-dense-parent-v1\n{workspace_id}\n{version.id}\n{emb_config_id}"
                        )
                        parent_job = IngestionJobTable(
                            id=str(uuid4()),
                            workspace_id=workspace_id,
                            operation="ingest_document",
                            document_id=document.id,
                            target_document_version_id=version.id,
                            source_object_id=source_object.id,
                            content_fingerprint=parent_fingerprint,
                            parser_configuration_id="text-parser-m1",
                            normalizer_configuration_id="text-normalizer-m1",
                            chunking_configuration_id=chunk_set.chunking_configuration_id,
                            derivation_kind="dense",
                            embedding_configuration_id=emb_config_id,
                            source_revision=None,
                            workspace_revision=None,
                            status="succeeded",
                            attempt_count=1,
                            max_attempts=4,
                            created_at=database_now,
                            updated_at=database_now,
                            started_at=database_now,
                            terminal_at=database_now,
                            terminal_outcome_code="succeeded",
                        )
                        session.add(parent_job)
                        session.flush()

                    head = session.get(LexicalHeadTable, document.id)
                    expected_revision = head.revision if head is not None else 0

                    generation_id = str(
                        uuid5(NAMESPACE_URL, f"knora-text-lexical-{version.id}-{profile_digest}")
                    )
                    lexical_chunks = tuple(
                        LexicalChunk(c.id, c.ordinal, c.content_checksum) for c in chunks
                    )
                    generation = LexicalGeneration(
                        generation_id=generation_id,
                        workspace_id=workspace_id,
                        document_id=document.id,
                        document_version_id=version.id,
                        chunk_set_id=chunk_set.id,
                        lexical_profile=profile,
                        revision=expected_revision + 1,
                        chunks=lexical_chunks,
                    )
                    store.request_generation_in_transaction(
                        session, generation, expected_revision=expected_revision
                    )

                    child_job = session.scalar(
                        select(IngestionJobTable).where(
                            IngestionJobTable.parent_ingestion_job_id == parent_job.id,
                            IngestionJobTable.derivation_kind == "lexical_index",
                        )
                    )
                    if child_job is None:
                        child_fingerprint = (
                            f"lexical_index-v1\n{generation.generation_id}\n"
                            f"{generation.content_digest()}\n{profile_digest}"
                        )
                        child_job = IngestionJobTable(
                            id=str(uuid4()),
                            workspace_id=workspace_id,
                            operation="ingest_document",
                            document_id=document.id,
                            target_document_version_id=version.id,
                            source_object_id=source_object.id,
                            content_fingerprint=child_fingerprint,
                            parser_configuration_id="text-parser-m1",
                            normalizer_configuration_id="text-normalizer-m1",
                            chunking_configuration_id=chunk_set.chunking_configuration_id,
                            derivation_kind="lexical_index",
                            embedding_configuration_id=None,
                            lexical_profile=None,
                            lexical_generation_id=generation.generation_id,
                            parent_ingestion_job_id=parent_job.id,
                            source_revision=expected_revision + 1,
                            workspace_revision=workspace.revision,
                            status="queued",
                            attempt_count=0,
                            max_attempts=4,
                            created_at=database_now,
                            updated_at=database_now,
                        )
                        session.add(child_job)
                        session.flush()

                    session.commit()
                    enqueued_count += 1

            if checkpoint_file is not None:
                try:
                    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(checkpoint_file, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "last_document_id": last_doc_id,
                                "scanned": scanned_count,
                                "enqueued": enqueued_count,
                            },
                            f,
                        )
                except Exception:
                    pass

    return {
        "workspace_id": workspace_id,
        "scanned": scanned_count,
        "enqueued": enqueued_count,
        "dry_run": dry_run,
    }


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_reindex(
            workspace_id=args.workspace_id,
            dry_run=args.dry_run,
            checkpoint_file=args.checkpoint_file,
            batch_size=args.batch_size,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print(
            json.dumps(
                {
                    "error": error.__class__.__name__,
                    "detail": str(error),
                }
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
