"""Builder draft, retained PDF source, and immutable extraction snapshots."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from knora.adapters.postgres.database import Base


class DatasetDraftTable(Base):
    __tablename__ = "evaluation_dataset_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cases: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    reviews: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    proposal_batches: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetSourceTable(Base):
    __tablename__ = "evaluation_dataset_sources"
    __table_args__ = (UniqueConstraint("dataset_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_dataset_drafts.id", ondelete="RESTRICT"), index=True
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"))
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True
    )
    original_source_object_id: Mapped[str] = mapped_column(
        ForeignKey("original_source_objects.id", ondelete="RESTRICT"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROCESSING")
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtractionSnapshotTable(Base):
    __tablename__ = "evaluation_extraction_snapshots"
    __table_args__ = (UniqueConstraint("source_id", "configuration_sha256", "extraction_sha256"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_dataset_sources.id", ondelete="RESTRICT"), index=True
    )
    configuration_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    extraction_options_version: Mapped[str] = mapped_column(String(100), nullable=False)
    normalizer_version: Mapped[str] = mapped_column(String(100), nullable=False)
    pages: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvaluationGoldVersionTable(Base):
    __tablename__ = "evaluation_gold_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version"),
        UniqueConstraint("dataset_id", "digest"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_dataset_drafts.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    frozen_json: Mapped[str] = mapped_column(String, nullable=False)
    reviews: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
