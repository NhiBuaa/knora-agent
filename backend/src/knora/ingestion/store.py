from dataclasses import dataclass
from typing import Protocol

from knora.ingestion.interface import IngestionResult
from knora.ingestion.processing import ChunkingConfiguration, ProcessedDocument
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


@dataclass(frozen=True, slots=True)
class DocumentHead:
    document_id: str
    revision: int
    active_embedding_set_id: str | None


@dataclass(frozen=True, slots=True)
class PreparedDerivation:
    workspace_id: str
    source_key: str
    source_name: str
    processed: ProcessedDocument
    chunking_configuration: ChunkingConfiguration
    embedding_configuration: EmbeddingConfiguration
    embedding_batch: EmbeddingBatch


class IngestionStore(Protocol):
    def authorize_workspace(self, *, workspace_id: str) -> None: ...

    def read_document_head(self, *, workspace_id: str, source_key: str) -> DocumentHead | None: ...

    def commit_derivation(
        self,
        *,
        prepared: PreparedDerivation,
        expected_revision: int,
    ) -> IngestionResult: ...
