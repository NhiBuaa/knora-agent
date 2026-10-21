"""Fence queued lexical rollback extraction with its reserved head revision.

Revision ID: 20261018_0156
Revises: 20261016_0155
"""

import sqlalchemy as sa
from alembic import op

revision = "20261018_0156"
down_revision = "20261016_0155"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("lexical_head_revision", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_ingestion_jobs_rollback_revision",
        "ingestion_jobs",
        "lexical_head_revision IS NULL OR "
        "(derivation_kind = 'pdf_extraction' AND lexical_head_revision > 0)",
    )
    op.execute("""
        CREATE FUNCTION validate_ingestion_rollback_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.lexical_head_revision IS DISTINCT FROM OLD.lexical_head_revision THEN
                RAISE EXCEPTION 'rollback request revision is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER validate_ingestion_rollback_revision
        BEFORE UPDATE OF lexical_head_revision ON ingestion_jobs
        FOR EACH ROW EXECUTE FUNCTION validate_ingestion_rollback_revision();
    """)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM ingestion_jobs WHERE lexical_head_revision IS NOT NULL)"
        )
    ):
        raise RuntimeError("rollback downgrade requires no retained rollback jobs")
    op.execute("""
        DROP TRIGGER validate_ingestion_rollback_revision ON ingestion_jobs;
        DROP FUNCTION validate_ingestion_rollback_revision();
    """)
    op.drop_constraint("ck_ingestion_jobs_rollback_revision", "ingestion_jobs", type_="check")
    op.drop_column("ingestion_jobs", "lexical_head_revision")
