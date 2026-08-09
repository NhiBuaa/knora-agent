"""Add durable retry scheduling audit and due-claim state.

Revision ID: 20260809_0010
Revises: 20260809_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0010"
down_revision: str | None = "20260809_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column(
        "ingestion_job_attempts",
        sa.Column("retry_policy_version", sa.String(50)),
    )
    op.add_column(
        "ingestion_job_attempts",
        sa.Column("retry_policy_result", sa.String(50)),
    )
    op.add_column(
        "ingestion_job_attempts",
        sa.Column("retry_jitter_version", sa.String(50)),
    )
    op.add_column(
        "ingestion_job_attempts",
        sa.Column("retry_window_upper_bound_microseconds", sa.Integer()),
    )
    op.add_column(
        "ingestion_job_attempts",
        sa.Column("retry_delay_microseconds", sa.Integer()),
    )
    op.add_column(
        "ingestion_job_attempts",
        sa.Column("retry_next_attempt_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_ingestion_jobs_retry_scheduled_claim",
        "ingestion_jobs",
        ["next_attempt_at", "id"],
        postgresql_where=sa.text("status = 'retry_scheduled'"),
    )

    op.drop_constraint(
        "ck_ingestion_jobs_worker_coordination_projection",
        "ingestion_jobs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_worker_coordination_projection",
        "ingestion_jobs",
        """
        (status = 'queued'
         AND attempt_count = 0
         AND worker_id IS NULL
         AND lease_expires_at IS NULL
         AND current_attempt_number IS NULL
         AND current_attempt_started_at IS NULL
         AND current_attempt_deadline_at IS NULL
         AND next_attempt_at IS NULL
         AND terminal_at IS NULL
         AND failure_reason IS NULL
         AND safe_failure_code IS NULL)
        OR
        (status = 'processing'
         AND attempt_count >= 1
         AND worker_id IS NOT NULL
         AND lease_expires_at IS NOT NULL
         AND current_attempt_number = attempt_count
         AND current_attempt_started_at IS NOT NULL
         AND current_attempt_deadline_at IS NOT NULL
         AND next_attempt_at IS NULL
         AND terminal_at IS NULL
         AND failure_reason IS NULL
         AND safe_failure_code IS NULL)
        OR
        (status = 'retry_scheduled'
         AND attempt_count >= 1
         AND attempt_count < max_attempts
         AND worker_id IS NULL
         AND lease_expires_at IS NULL
         AND current_attempt_number IS NULL
         AND current_attempt_started_at IS NULL
         AND current_attempt_deadline_at IS NULL
         AND next_attempt_at IS NOT NULL
         AND terminal_at IS NULL
         AND failure_reason IS NULL
         AND safe_failure_code IS NULL)
        OR
        (status = 'failed'
         AND attempt_count >= 1
         AND worker_id IS NULL
         AND lease_expires_at IS NULL
         AND current_attempt_number IS NULL
         AND current_attempt_started_at IS NULL
         AND current_attempt_deadline_at IS NULL
         AND next_attempt_at IS NULL
         AND terminal_at IS NOT NULL
         AND failure_reason IS NOT NULL
         AND safe_failure_code IS NOT NULL)
        OR status IN ('succeeded', 'superseded')
        """,
    )
    op.create_check_constraint(
        "ck_ingestion_job_attempts_retry_schedule_audit",
        "ingestion_job_attempts",
        """
        disposition IS DISTINCT FROM 'retry_scheduled'
        OR
        (closed_at IS NOT NULL
         AND closure_cause IS NOT NULL
         AND failure_cause IS NOT NULL
         AND failure_cause_version IS NOT NULL
         AND cause_mapping_version IS NOT NULL
         AND safe_failure_code IS NOT NULL
         AND failure_reason IS NULL
         AND transition_operation_id IS NOT NULL
         AND transition_request_fingerprint IS NOT NULL
         AND retry_policy_version IS NOT NULL
         AND retry_policy_result = 'schedule_retry'
         AND retry_jitter_version IS NOT NULL
         AND retry_window_upper_bound_microseconds IS NOT NULL
         AND retry_delay_microseconds IS NOT NULL
         AND retry_next_attempt_at IS NOT NULL)
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_job_attempts_retry_schedule_audit",
        "ingestion_job_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_ingestion_jobs_worker_coordination_projection",
        "ingestion_jobs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_worker_coordination_projection",
        "ingestion_jobs",
        """
        (status = 'queued'
         AND attempt_count = 0
         AND worker_id IS NULL
         AND lease_expires_at IS NULL
         AND current_attempt_number IS NULL
         AND current_attempt_started_at IS NULL
         AND current_attempt_deadline_at IS NULL
         AND terminal_at IS NULL
         AND failure_reason IS NULL
         AND safe_failure_code IS NULL)
        OR
        (status = 'processing'
         AND attempt_count >= 1
         AND worker_id IS NOT NULL
         AND lease_expires_at IS NOT NULL
         AND current_attempt_number = attempt_count
         AND current_attempt_started_at IS NOT NULL
         AND current_attempt_deadline_at IS NOT NULL
         AND terminal_at IS NULL
         AND failure_reason IS NULL
         AND safe_failure_code IS NULL)
        OR
        (status = 'failed'
         AND attempt_count >= 1
         AND worker_id IS NULL
         AND lease_expires_at IS NULL
         AND current_attempt_number IS NULL
         AND current_attempt_started_at IS NULL
         AND current_attempt_deadline_at IS NULL
         AND terminal_at IS NOT NULL
         AND failure_reason IS NOT NULL
         AND safe_failure_code IS NOT NULL)
        OR status IN ('retry_scheduled', 'succeeded', 'superseded')
        """,
    )
    op.drop_index("ix_ingestion_jobs_retry_scheduled_claim", table_name="ingestion_jobs")
    op.drop_column("ingestion_job_attempts", "retry_next_attempt_at")
    op.drop_column("ingestion_job_attempts", "retry_delay_microseconds")
    op.drop_column("ingestion_job_attempts", "retry_window_upper_bound_microseconds")
    op.drop_column("ingestion_job_attempts", "retry_jitter_version")
    op.drop_column("ingestion_job_attempts", "retry_policy_result")
    op.drop_column("ingestion_job_attempts", "retry_policy_version")
    op.drop_column("ingestion_jobs", "next_attempt_at")
