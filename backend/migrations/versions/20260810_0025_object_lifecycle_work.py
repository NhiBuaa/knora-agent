"""Add durable object lifecycle work and attempts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0025"
down_revision: str | None = "20260810_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "object_lifecycle_work",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(100),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("artifact_class", sa.String(40), nullable=False),
        sa.Column("lifecycle_generation", sa.String(36), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="4"),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("lease_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("terminal_at", sa.DateTime(timezone=True)),
        sa.Column("deletion_generation", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "workspace_id",
            "object_key",
            "artifact_class",
            "lifecycle_generation",
            name="uq_object_lifecycle_work_identity",
        ),
        sa.CheckConstraint(
            "state IN ('queued', 'processing', 'retry_scheduled', 'succeeded', 'failed')",
            name="ck_object_lifecycle_work_state",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts = 4", name="ck_object_lifecycle_work_attempts"
        ),
    )
    op.create_index(
        "ix_object_lifecycle_work_eligible",
        "object_lifecycle_work",
        ["state", "next_attempt_at", "created_at"],
    )
    op.create_table(
        "object_lifecycle_attempts",
        sa.Column(
            "object_lifecycle_work_id",
            sa.String(36),
            sa.ForeignKey("object_lifecycle_work.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("attempt_number", sa.Integer, primary_key=True),
        sa.Column("worker_id", sa.String(100), nullable=False),
        sa.Column("lease_version", sa.Integer, nullable=False),
        sa.Column("claim_operation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("attempt_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("disposition", sa.String(50)),
        sa.Column("retry_delay_microseconds", sa.Integer),
        sa.Column("retry_next_attempt_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_object_lifecycle_attempt_open",
        "object_lifecycle_attempts",
        ["object_lifecycle_work_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_object_lifecycle_attempt_open", table_name="object_lifecycle_attempts")
    op.drop_table("object_lifecycle_attempts")
    op.drop_index("ix_object_lifecycle_work_eligible", table_name="object_lifecycle_work")
    op.drop_table("object_lifecycle_work")
