"""Persist Workspace mutation admissions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0045"
down_revision: str | None = "20260924_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_admissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("operation_id", sa.String(length=255), nullable=False),
        sa.Column("ingestion_job_id", sa.String(length=36), nullable=True),
        sa.Column("admitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ingestion_job_id"], ["ingestion_jobs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("workspace_id", "operation", "operation_id"),
    )
    op.create_index(
        "ix_workspace_admissions_workspace_id", "workspace_admissions", ["workspace_id"]
    )
    op.create_index(
        "ix_workspace_admissions_ingestion_job_id", "workspace_admissions", ["ingestion_job_id"]
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM workspace_admissions LIMIT 1")).first():
        raise RuntimeError("refusing to discard Workspace admission history")
    op.drop_index("ix_workspace_admissions_workspace_id", table_name="workspace_admissions")
    op.drop_index("ix_workspace_admissions_ingestion_job_id", table_name="workspace_admissions")
    op.drop_table("workspace_admissions")
