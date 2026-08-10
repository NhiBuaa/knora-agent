"""Add public lifecycle timestamps, reprocess linkage, and audit projection."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0016"
down_revision: str | None = "20260809_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "reprocess_of_job_id",
            sa.String(36),
            sa.ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_ingestion_jobs_reprocess_of_job_id",
        "ingestion_jobs",
        ["reprocess_of_job_id"],
    )
    op.create_table(
        "reprocess_audit_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(100),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_key_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column(
            "target_document_version_id",
            sa.String(36),
            sa.ForeignKey("document_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requested_config_mode", sa.String(30), nullable=False),
        sa.Column("resolved_config_mode", sa.String(30), nullable=False),
        sa.Column(
            "config_source_job_id",
            sa.String(36),
            sa.ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "ingestion_job_id",
            sa.String(36),
            sa.ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_reprocess_audit_records_workspace_id",
        "reprocess_audit_records",
        ["workspace_id"],
    )
    op.create_index(
        "ix_reprocess_audit_records_target_document_version_id",
        "reprocess_audit_records",
        ["target_document_version_id"],
    )
    op.create_index(
        "ix_reprocess_audit_records_ingestion_job_id",
        "reprocess_audit_records",
        ["ingestion_job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reprocess_audit_records_ingestion_job_id",
        table_name="reprocess_audit_records",
    )
    op.drop_index(
        "ix_reprocess_audit_records_target_document_version_id",
        table_name="reprocess_audit_records",
    )
    op.drop_index(
        "ix_reprocess_audit_records_workspace_id",
        table_name="reprocess_audit_records",
    )
    op.drop_table("reprocess_audit_records")
    op.drop_index("ix_ingestion_jobs_reprocess_of_job_id", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "reprocess_of_job_id")
    op.drop_column("ingestion_jobs", "started_at")
