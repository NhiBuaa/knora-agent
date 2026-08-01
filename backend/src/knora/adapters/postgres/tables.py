from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from knora.adapters.postgres.database import Base


class WorkspaceTable(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentTable(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("workspace_id", "source_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(500), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active_embedding_set_id: Mapped[str | None] = mapped_column(
        ForeignKey("embedding_sets.id", ondelete="RESTRICT"), nullable=True
    )
    active_embedding_configuration_id: Mapped[str | None] = mapped_column(
        ForeignKey("embedding_configurations.id", ondelete="RESTRICT"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentVersionTable(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "normalized_content_checksum"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), index=True
    )
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChunkingConfigurationTable(Base):
    __tablename__ = "chunking_configurations"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(100), nullable=False)
    tokenizer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tokenizer_version: Mapped[str] = mapped_column(String(100), nullable=False)
    target_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    overlap_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)


class ChunkSetTable(Base):
    __tablename__ = "chunk_sets"
    __table_args__ = (UniqueConstraint("document_version_id", "chunking_configuration_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True
    )
    chunking_configuration_id: Mapped[str] = mapped_column(
        ForeignKey("chunking_configurations.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class ChunkTable(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("chunk_set_id", "ordinal"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chunk_set_id: Mapped[str] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="RESTRICT"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list] = mapped_column(JSON, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)


class EmbeddingConfigurationTable(Base):
    __tablename__ = "embedding_configurations"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(30), nullable=False)


class EmbeddingSetTable(Base):
    __tablename__ = "embedding_sets"
    __table_args__ = (UniqueConstraint("chunk_set_id", "embedding_configuration_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chunk_set_id: Mapped[str] = mapped_column(
        ForeignKey("chunk_sets.id", ondelete="RESTRICT"), index=True
    )
    embedding_configuration_id: Mapped[str] = mapped_column(
        ForeignKey("embedding_configurations.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class ChunkEmbeddingTable(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (UniqueConstraint("embedding_set_id", "chunk_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    embedding_set_id: Mapped[str] = mapped_column(
        ForeignKey("embedding_sets.id", ondelete="RESTRICT"), index=True
    )
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="RESTRICT"), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)


class QuestionTraceTable(Base):
    __tablename__ = "question_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    trace_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retrieval_configuration_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_configuration_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_set_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    chunk_set_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    candidate_decisions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False)
    refusal_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    alias_mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    parsed_markers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    validation_outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
