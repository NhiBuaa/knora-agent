from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from knora.infrastructure.database import Base


class WorkspaceTable(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentTable(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    source: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChunkTable(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(220), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class QuestionTraceTable(Base):
    __tablename__ = "question_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[str] = mapped_column(Text)
    refused: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

