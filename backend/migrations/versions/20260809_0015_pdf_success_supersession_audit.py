"""Allow the PDF success operation to record a stale-target supersession."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_0015"
down_revision: str | None = "20260809_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_job_attempts_superseded_audit",
        "ingestion_job_attempts",
        type_="check",
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
         AND transition_operation_kind IN ('superseded', 'pdf_success')
         AND transition_request_fingerprint IS NOT NULL)
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_job_attempts_superseded_audit",
        "ingestion_job_attempts",
        type_="check",
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
