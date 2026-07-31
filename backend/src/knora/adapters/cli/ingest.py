from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingConfiguration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest a Markdown or plain-text document into Knora"
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--source-name")
    return parser


def media_type_for_path(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    if suffix in {"", ".txt", ".text"}:
        return "text/plain"
    raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")


def run_ingestion(args: argparse.Namespace) -> dict:
    path: Path = args.path
    media_type = media_type_for_path(path)
    source_name = args.source_name or path.name
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    )
    result = use_case.execute(
        IngestDocumentCommand(
            workspace_id=args.workspace,
            source_key=args.source_key,
            source_name=source_name,
            media_type=media_type,
            raw_content=path.read_bytes(),
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        WorkspacePrincipal(workspace_id=args.workspace, key_id="cli"),
    )
    return {
        "outcome": result.outcome,
        "activation_changed": result.activation_changed,
        "document_id": result.document_id,
        "document_version_id": result.document_version_id,
        "chunk_set_id": result.chunk_set_id,
        "embedding_set_id": result.embedding_set_id,
        "chunking_configuration_id": result.chunking_configuration_id,
        "embedding_configuration_id": result.embedding_configuration_id,
        "chunk_count": result.chunk_count,
    }


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(json.dumps(run_ingestion(args), ensure_ascii=False))
    except KnoraError as error:
        print(json.dumps({"error": error.code}), file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
