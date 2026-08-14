"""Internal control-plane seam for isolated evaluation environments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import WorkspaceTable
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration


class WorkspaceGateway(Protocol):
    def provision_or_reuse(self, *, workspace_id: str, name: str) -> str: ...


@dataclass(slots=True)
class PostgresEvaluationWorkspaceGateway:
    session_factory: sessionmaker

    def provision_or_reuse(self, *, workspace_id: str, name: str) -> str:
        with self.session_factory.begin() as session:
            workspace = session.scalar(
                select(WorkspaceTable).where(WorkspaceTable.id == workspace_id)
            )
            if workspace is None:
                session.add(WorkspaceTable(id=workspace_id, name=name))
            return workspace_id


@dataclass(slots=True)
class ApplicationEvaluationCorpusGateway:
    ingest_document: IngestDocument
    embedding_configuration: EmbeddingConfiguration

    def ingest(
        self, *, workspace_id: str, source_key: str, source_name: str,
        media_type: str, raw_content: bytes,
    ) -> object:
        return self.ingest_document.execute(
            IngestDocumentCommand(
                workspace_id=workspace_id,
                source_key=source_key,
                source_name=source_name,
                media_type=media_type,
                raw_content=raw_content,
                chunking_configuration=ChunkingConfiguration.milestone_one(),
                embedding_configuration=self.embedding_configuration,
            ),
            WorkspacePrincipal(workspace_id=workspace_id, key_id="evaluation-bootstrap"),
        )
