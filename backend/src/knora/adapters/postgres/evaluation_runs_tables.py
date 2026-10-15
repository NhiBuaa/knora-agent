"""Durable evaluation run admission and case checkpoints."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from knora.adapters.postgres.database import Base


class EvaluationRunTable(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    selection: Mapped[dict] = mapped_column(JSON, nullable=False)
    profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    binding: Mapped[dict] = mapped_column(JSON, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)
    observations: Mapped[dict] = mapped_column(JSON, nullable=False)
    report: Mapped[dict | None] = mapped_column(JSON)
    scoring_batches: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    attempt_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationPreflightTable(Base):
    __tablename__ = "evaluation_run_preflights"

    preflight_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
