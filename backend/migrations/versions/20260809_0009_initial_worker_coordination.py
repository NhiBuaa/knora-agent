"""Add the queued-to-terminal-failure worker coordination tracer.

Revision ID: 20260809_0009
Revises: 20260805_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0009"
down_revision: str | None = "20260805_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("worker_id", sa.String(100), nullable=True))
    op.add_column(
        "ingestion_jobs",
        sa.Column("lease_version", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column("ingestion_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("ingestion_jobs", sa.Column("current_attempt_number", sa.Integer()))
    op.add_column(
        "ingestion_jobs", sa.Column("current_attempt_started_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "ingestion_jobs", sa.Column("current_attempt_deadline_at", sa.DateTime(timezone=True))
    )
    op.add_column("ingestion_jobs", sa.Column("terminal_at", sa.DateTime(timezone=True)))
    op.add_column("ingestion_jobs", sa.Column("failure_reason", sa.String(50)))
    op.add_column("ingestion_jobs", sa.Column("safe_failure_code", sa.String(100)))

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM ingestion_jobs
                 WHERE status IS DISTINCT FROM 'queued'
                    OR attempt_count IS DISTINCT FROM 0
            ) THEN
                RAISE EXCEPTION
                    'worker coordination migration requires only queued zero-attempt legacy jobs'
                    USING ERRCODE = 'check_violation';
            END IF;
        END;
        $$;
        """
    )
    op.alter_column("ingestion_jobs", "lease_version", nullable=False, server_default="0")

    op.create_table(
        "ingestion_job_attempts",
        sa.Column(
            "ingestion_job_id",
            sa.String(36),
            sa.ForeignKey("ingestion_jobs.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("attempt_number", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.String(100), nullable=False),
        sa.Column("lease_version", sa.Integer(), nullable=False),
        sa.Column("attempt_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial_lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_operation_id", sa.String(36), nullable=False),
        sa.Column("claim_request_fingerprint", sa.Text(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("disposition", sa.String(50)),
        sa.Column("closure_cause", sa.String(100)),
        sa.Column("failure_cause", sa.String(100)),
        sa.Column("failure_cause_version", sa.String(50)),
        sa.Column("cause_mapping_version", sa.String(50)),
        sa.Column("safe_failure_code", sa.String(100)),
        sa.Column("failure_reason", sa.String(50)),
        sa.Column("transition_operation_id", sa.String(36)),
        sa.Column("transition_request_fingerprint", sa.Text()),
        sa.UniqueConstraint("claim_operation_id", name="uq_ingestion_job_attempts_claim_operation"),
        sa.UniqueConstraint(
            "transition_operation_id", name="uq_ingestion_job_attempts_transition_operation"
        ),
        sa.CheckConstraint(
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
            name="ck_ingestion_job_attempts_open_or_closed",
        ),
    )
    op.create_index(
        "uq_ingestion_job_attempts_one_open",
        "ingestion_job_attempts",
        ["ingestion_job_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_index(
        "ix_ingestion_jobs_queued_claim",
        "ingestion_jobs",
        ["created_at", "id"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_attempt_capacity",
        "ingestion_jobs",
        "attempt_count >= 0 AND attempt_count <= max_attempts",
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
    op.execute(
        """
        CREATE FUNCTION validate_ingestion_job_attempt_correspondence()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            checked_job_id varchar(36);
            job_row ingestion_jobs%ROWTYPE;
            open_count integer;
            attempt_row ingestion_job_attempts%ROWTYPE;
        BEGIN
            IF TG_TABLE_NAME = 'ingestion_jobs' THEN
                checked_job_id := NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                checked_job_id := OLD.ingestion_job_id;
            ELSE
                checked_job_id := NEW.ingestion_job_id;
            END IF;

            SELECT * INTO job_row FROM ingestion_jobs WHERE id = checked_job_id;
            IF NOT FOUND THEN
                RETURN NULL;
            END IF;

            SELECT count(*) INTO open_count
              FROM ingestion_job_attempts
             WHERE ingestion_job_id = checked_job_id
               AND closed_at IS NULL;

            IF job_row.status = 'processing' THEN
                IF open_count <> 1 THEN
                    RAISE EXCEPTION 'processing Ingestion Job must have exactly one open attempt'
                        USING ERRCODE = 'check_violation';
                END IF;
                SELECT * INTO attempt_row
                  FROM ingestion_job_attempts
                 WHERE ingestion_job_id = checked_job_id
                   AND closed_at IS NULL;
                IF attempt_row.attempt_number IS DISTINCT FROM job_row.current_attempt_number
                   OR attempt_row.attempt_number IS DISTINCT FROM job_row.attempt_count
                   OR attempt_row.worker_id IS DISTINCT FROM job_row.worker_id
                   OR attempt_row.lease_version IS DISTINCT FROM job_row.lease_version
                   OR attempt_row.attempt_started_at IS DISTINCT FROM
                      job_row.current_attempt_started_at
                   OR attempt_row.deadline_at IS DISTINCT FROM
                      job_row.current_attempt_deadline_at
                   OR attempt_row.initial_lease_expires_at IS DISTINCT FROM
                      job_row.lease_expires_at THEN
                    RAISE EXCEPTION 'current Ingestion Job projection does not match open attempt'
                        USING ERRCODE = 'check_violation';
                END IF;
            ELSIF open_count <> 0 THEN
                RAISE EXCEPTION 'non-processing Ingestion Job cannot have an open attempt'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NULL;
        END;
        $$;

        CREATE CONSTRAINT TRIGGER validate_ingestion_job_attempt_correspondence_on_job
        AFTER INSERT OR UPDATE ON ingestion_jobs
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_ingestion_job_attempt_correspondence();

        CREATE CONSTRAINT TRIGGER validate_ingestion_job_attempt_correspondence_on_attempt
        AFTER INSERT OR UPDATE OR DELETE ON ingestion_job_attempts
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_ingestion_job_attempt_correspondence();

        CREATE FUNCTION prevent_closed_ingestion_job_attempt_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.closed_at IS NOT NULL THEN
                RAISE EXCEPTION 'closed Ingestion Job Attempt is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$;

        CREATE TRIGGER prevent_closed_ingestion_job_attempt_mutation
        BEFORE UPDATE OR DELETE ON ingestion_job_attempts
        FOR EACH ROW EXECUTE FUNCTION prevent_closed_ingestion_job_attempt_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER prevent_closed_ingestion_job_attempt_mutation ON ingestion_job_attempts;
        DROP FUNCTION prevent_closed_ingestion_job_attempt_mutation();
        DROP TRIGGER validate_ingestion_job_attempt_correspondence_on_attempt
            ON ingestion_job_attempts;
        DROP TRIGGER validate_ingestion_job_attempt_correspondence_on_job ON ingestion_jobs;
        DROP FUNCTION validate_ingestion_job_attempt_correspondence();
        """
    )
    op.drop_constraint(
        "ck_ingestion_jobs_worker_coordination_projection",
        "ingestion_jobs",
        type_="check",
    )
    op.drop_constraint("ck_ingestion_jobs_attempt_capacity", "ingestion_jobs", type_="check")
    op.drop_index("ix_ingestion_jobs_queued_claim", table_name="ingestion_jobs")
    op.drop_table("ingestion_job_attempts")
    op.drop_column("ingestion_jobs", "safe_failure_code")
    op.drop_column("ingestion_jobs", "failure_reason")
    op.drop_column("ingestion_jobs", "terminal_at")
    op.drop_column("ingestion_jobs", "current_attempt_deadline_at")
    op.drop_column("ingestion_jobs", "current_attempt_started_at")
    op.drop_column("ingestion_jobs", "current_attempt_number")
    op.drop_column("ingestion_jobs", "lease_expires_at")
    op.drop_column("ingestion_jobs", "lease_version")
    op.drop_column("ingestion_jobs", "worker_id")
