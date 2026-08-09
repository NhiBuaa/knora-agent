"""Add typed terminal metadata for succeeded and superseded attempts.

Revision ID: 20260809_0013
Revises: 20260809_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0013"
down_revision: str | None = "20260809_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("terminal_outcome_code", sa.String(100)))
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "replacement_document_version_id",
            sa.String(36),
            sa.ForeignKey("document_versions.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "replacement_ingestion_job_id",
            sa.String(36),
            sa.ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column(
        "ingestion_job_attempts", sa.Column("terminal_outcome_code", sa.String(100))
    )
    op.add_column(
        "ingestion_job_attempts",
        sa.Column(
            "replacement_document_version_id",
            sa.String(36),
            sa.ForeignKey("document_versions.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column(
        "ingestion_job_attempts",
        sa.Column(
            "replacement_ingestion_job_id",
            sa.String(36),
            sa.ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"),
        ),
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
         AND safe_failure_code IS NULL
         AND terminal_outcome_code IS NULL
         AND replacement_document_version_id IS NULL
         AND replacement_ingestion_job_id IS NULL)
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
         AND safe_failure_code IS NULL
         AND terminal_outcome_code IS NULL
         AND replacement_document_version_id IS NULL
         AND replacement_ingestion_job_id IS NULL)
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
         AND safe_failure_code IS NULL
         AND terminal_outcome_code IS NULL
         AND replacement_document_version_id IS NULL
         AND replacement_ingestion_job_id IS NULL)
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
         AND safe_failure_code IS NOT NULL
         AND terminal_outcome_code IS NULL
         AND replacement_document_version_id IS NULL
         AND replacement_ingestion_job_id IS NULL)
        OR
        (status = 'succeeded'
         AND attempt_count >= 1
         AND worker_id IS NULL
         AND lease_expires_at IS NULL
         AND current_attempt_number IS NULL
         AND current_attempt_started_at IS NULL
         AND current_attempt_deadline_at IS NULL
         AND next_attempt_at IS NULL
         AND terminal_at IS NOT NULL
         AND failure_reason IS NULL
         AND safe_failure_code IS NULL
         AND terminal_outcome_code = 'succeeded'
         AND replacement_document_version_id IS NULL
         AND replacement_ingestion_job_id IS NULL)
        OR
        (status = 'superseded'
         AND attempt_count >= 1
         AND worker_id IS NULL
         AND lease_expires_at IS NULL
         AND current_attempt_number IS NULL
         AND current_attempt_started_at IS NULL
         AND current_attempt_deadline_at IS NULL
         AND next_attempt_at IS NULL
         AND terminal_at IS NOT NULL
         AND failure_reason IS NULL
         AND safe_failure_code IS NULL
         AND terminal_outcome_code = 'stale_document_version')
        """,
    )
    op.drop_constraint(
        "ck_ingestion_job_attempts_open_or_closed",
        "ingestion_job_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_job_attempts_open_or_closed",
        "ingestion_job_attempts",
        """
        (closed_at IS NULL
         AND disposition IS NULL
         AND closure_cause IS NULL
         AND failure_cause IS NULL
         AND failure_cause_version IS NULL
         AND cause_mapping_version IS NULL
         AND safe_failure_code IS NULL
         AND failure_reason IS NULL
         AND terminal_outcome_code IS NULL
         AND transition_operation_id IS NULL
         AND transition_operation_kind IS NULL
         AND transition_request_fingerprint IS NULL
         AND replacement_document_version_id IS NULL
         AND replacement_ingestion_job_id IS NULL)
        OR
        (closed_at IS NOT NULL AND disposition IS NOT NULL)
        """,
    )
    op.create_check_constraint(
        "ck_ingestion_job_attempts_superseded_audit",
        "ingestion_job_attempts",
        """
        disposition IS DISTINCT FROM 'superseded'
        OR
        (closed_at IS NOT NULL
         AND closure_cause = 'stale_document_version'
         AND failure_cause IS NULL
         AND failure_cause_version IS NULL
         AND cause_mapping_version IS NULL
         AND safe_failure_code IS NULL
         AND failure_reason IS NULL
         AND terminal_outcome_code = 'stale_document_version'
         AND transition_operation_id IS NOT NULL
         AND transition_operation_kind = 'superseded'
         AND transition_request_fingerprint IS NOT NULL)
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_job_attempts_superseded_audit",
        "ingestion_job_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_ingestion_job_attempts_open_or_closed",
        "ingestion_job_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ingestion_job_attempts_open_or_closed",
        "ingestion_job_attempts",
        """
        (closed_at IS NULL
         AND disposition IS NULL
         AND closure_cause IS NULL
         AND failure_cause IS NULL
         AND failure_cause_version IS NULL
         AND cause_mapping_version IS NULL
         AND safe_failure_code IS NULL
         AND failure_reason IS NULL
         AND transition_operation_id IS NULL
         AND transition_request_fingerprint IS NULL)
        OR
        (closed_at IS NOT NULL AND disposition IS NOT NULL)
        """,
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
    op.drop_column("ingestion_job_attempts", "replacement_ingestion_job_id")
    op.drop_column("ingestion_job_attempts", "replacement_document_version_id")
    op.drop_column("ingestion_job_attempts", "terminal_outcome_code")
    op.drop_column("ingestion_jobs", "replacement_ingestion_job_id")
    op.drop_column("ingestion_jobs", "replacement_document_version_id")
    op.drop_column("ingestion_jobs", "terminal_outcome_code")
