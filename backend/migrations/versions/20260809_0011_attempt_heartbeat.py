"""Add heartbeat replay fields to the mutable ingestion-job projection.

Revision ID: 20260809_0011
Revises: 20260809_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0011"
down_revision: str | None = "20260809_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("last_heartbeat_operation_id", sa.String(36)))
    op.add_column("ingestion_jobs", sa.Column("last_heartbeat_request_fingerprint", sa.Text()))
    op.add_column(
        "ingestion_jobs",
        sa.Column("last_heartbeat_resulting_lease_expires_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_ingestion_job_attempt_correspondence()
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
            IF NOT FOUND THEN RETURN NULL; END IF;
            SELECT count(*) INTO open_count FROM ingestion_job_attempts
             WHERE ingestion_job_id = checked_job_id AND closed_at IS NULL;
            IF job_row.status = 'processing' THEN
                IF open_count <> 1 THEN
                    RAISE EXCEPTION 'processing Ingestion Job must have exactly one open attempt'
                        USING ERRCODE = 'check_violation';
                END IF;
                SELECT * INTO attempt_row FROM ingestion_job_attempts
                 WHERE ingestion_job_id = checked_job_id AND closed_at IS NULL;
                IF attempt_row.attempt_number IS DISTINCT FROM job_row.current_attempt_number
                   OR attempt_row.attempt_number IS DISTINCT FROM job_row.attempt_count
                   OR attempt_row.worker_id IS DISTINCT FROM job_row.worker_id
                   OR attempt_row.lease_version IS DISTINCT FROM job_row.lease_version
                   OR attempt_row.attempt_started_at IS DISTINCT FROM
                      job_row.current_attempt_started_at
                   OR attempt_row.deadline_at IS DISTINCT FROM
                      job_row.current_attempt_deadline_at THEN
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
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_ingestion_job_attempt_correspondence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            checked_job_id varchar(36); job_row ingestion_jobs%ROWTYPE;
            open_count integer; attempt_row ingestion_job_attempts%ROWTYPE;
        BEGIN
            IF TG_TABLE_NAME = 'ingestion_jobs' THEN checked_job_id := NEW.id;
            ELSIF TG_OP = 'DELETE' THEN checked_job_id := OLD.ingestion_job_id;
            ELSE checked_job_id := NEW.ingestion_job_id; END IF;
            SELECT * INTO job_row FROM ingestion_jobs WHERE id = checked_job_id;
            IF NOT FOUND THEN RETURN NULL; END IF;
            SELECT count(*) INTO open_count FROM ingestion_job_attempts
             WHERE ingestion_job_id = checked_job_id AND closed_at IS NULL;
            IF job_row.status = 'processing' THEN
                IF open_count <> 1 THEN
                    RAISE EXCEPTION 'processing Ingestion Job must have exactly one open attempt'
                        USING ERRCODE = 'check_violation';
                END IF;
                SELECT * INTO attempt_row FROM ingestion_job_attempts
                 WHERE ingestion_job_id = checked_job_id AND closed_at IS NULL;
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
        """
    )
    op.drop_column("ingestion_jobs", "last_heartbeat_resulting_lease_expires_at")
    op.drop_column("ingestion_jobs", "last_heartbeat_request_fingerprint")
    op.drop_column("ingestion_jobs", "last_heartbeat_operation_id")
