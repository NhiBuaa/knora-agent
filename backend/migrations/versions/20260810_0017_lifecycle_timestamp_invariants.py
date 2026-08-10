"""Enforce lifecycle timestamp invariants for public Ingestion Job projections."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0017"
down_revision: str | None = "20260810_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE ingestion_jobs "
        "SET started_at = COALESCE(current_attempt_started_at, updated_at, created_at) "
        "WHERE status <> 'queued' AND started_at IS NULL"
    )
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.create_check_constraint(
        "ck_ingestion_jobs_lifecycle_timestamps",
        "ingestion_jobs",
        "((status = 'queued' AND started_at IS NULL) "
        "OR (status IN ('processing', 'retry_scheduled', 'succeeded', 'superseded', 'failed') "
        "AND started_at IS NOT NULL))",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_jobs_lifecycle_timestamps",
        "ingestion_jobs",
        type_="check",
    )
