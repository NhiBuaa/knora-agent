"""Bind transition operation IDs to their mutation kind."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0012"
down_revision: str | None = "20260809_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_job_attempts",
        sa.Column("transition_operation_kind", sa.String(30), nullable=True),
    )
    op.execute(
        "ALTER TABLE ingestion_job_attempts "
        "DISABLE TRIGGER prevent_closed_ingestion_job_attempt_mutation"
    )
    op.execute(
        """
        UPDATE ingestion_job_attempts
        SET transition_operation_kind = CASE
            WHEN closure_cause = 'lease_expired' THEN 'expired_recovery'
            WHEN disposition = 'retry_scheduled' THEN 'schedule_retry'
            WHEN disposition = 'failed' THEN 'terminal_failure'
            ELSE NULL
        END
        WHERE transition_operation_id IS NOT NULL
        """
    )
    op.execute(
        "SET CONSTRAINTS ALL IMMEDIATE"
    )
    op.execute(
        "ALTER TABLE ingestion_job_attempts "
        "ENABLE TRIGGER prevent_closed_ingestion_job_attempt_mutation"
    )
    op.drop_constraint(
        "uq_ingestion_job_attempts_transition_operation",
        "ingestion_job_attempts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_ingestion_job_attempts_transition_operation_kind",
        "ingestion_job_attempts",
        ["transition_operation_kind", "transition_operation_id"],
    )
    op.create_check_constraint(
        "ck_ingestion_job_attempts_transition_binding",
        "ingestion_job_attempts",
        "(transition_operation_id IS NULL AND transition_operation_kind IS NULL) "
        "OR (transition_operation_id IS NOT NULL AND transition_operation_kind IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_job_attempts_transition_binding",
        "ingestion_job_attempts",
        type_="check",
    )
    op.drop_constraint(
        "uq_ingestion_job_attempts_transition_operation_kind",
        "ingestion_job_attempts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_ingestion_job_attempts_transition_operation",
        "ingestion_job_attempts",
        ["transition_operation_id"],
    )
    op.drop_column("ingestion_job_attempts", "transition_operation_kind")
