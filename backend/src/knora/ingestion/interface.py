from dataclasses import dataclass
from typing import Literal

from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration


@dataclass(frozen=True, slots=True)
class IngestDocumentCommand:
    workspace_id: str
    source_key: str
    source_name: str
    media_type: str
    raw_content: bytes
    chunking_configuration: ChunkingConfiguration
    embedding_configuration: EmbeddingConfiguration


@dataclass(frozen=True, slots=True)
class IngestionResult:
    outcome: Literal["created", "reused"]
    activation_changed: bool
    document_id: str
    document_version_id: str
    chunk_set_id: str
    embedding_set_id: str
    chunking_configuration_id: str
    embedding_configuration_id: str
    chunk_count: int
