"""Link lexical index jobs to their exact extraction job.

Revision ID: 20261016_0155
Revises: 20261016_0154
"""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0155"
down_revision = "20261016_0154"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM ingestion_jobs WHERE derivation_kind = 'lexical_index'")
    ):
        raise RuntimeError(
            "legacy lexical_index jobs have no parent; resolve their lineage before migration"
        )
    op.add_column(
        "ingestion_jobs",
        sa.Column("parent_ingestion_job_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_ingestion_jobs_parent",
        "ingestion_jobs",
        "ingestion_jobs",
        ["parent_ingestion_job_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_ingestion_jobs_parent_ingestion_job",
        "ingestion_jobs",
        ["parent_ingestion_job_id"],
        unique=True,
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_index_parent",
        "ingestion_jobs",
        "(derivation_kind = 'lexical_index' AND parent_ingestion_job_id IS NOT NULL) "
        "OR (derivation_kind <> 'lexical_index' AND parent_ingestion_job_id IS NULL)",
    )
    op.execute(
        """
        CREATE FUNCTION validate_ingestion_index_parent()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            parent ingestion_jobs%ROWTYPE;
        BEGIN
            IF TG_OP = 'UPDATE'
               AND NEW.parent_ingestion_job_id IS DISTINCT FROM OLD.parent_ingestion_job_id THEN
                RAISE EXCEPTION 'ingestion index parent is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF TG_OP = 'UPDATE'
               AND OLD.derivation_kind = 'pdf_extraction'
               AND (NEW.derivation_kind, NEW.workspace_id, NEW.document_id,
                    NEW.target_document_version_id, NEW.source_object_id, NEW.operation,
                    NEW.parser_configuration_id, NEW.normalizer_configuration_id,
                    NEW.chunking_configuration_id, NEW.source_revision, NEW.workspace_revision)
                   IS DISTINCT FROM
                   (OLD.derivation_kind, OLD.workspace_id, OLD.document_id,
                    OLD.target_document_version_id, OLD.source_object_id, OLD.operation,
                    OLD.parser_configuration_id, OLD.normalizer_configuration_id,
                    OLD.chunking_configuration_id, OLD.source_revision, OLD.workspace_revision)
               AND EXISTS (SELECT 1 FROM ingestion_jobs
                            WHERE parent_ingestion_job_id = OLD.id) THEN
                RAISE EXCEPTION 'linked extraction identity is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.derivation_kind <> 'lexical_index' THEN
                RETURN NEW;
            END IF;
            SELECT * INTO parent FROM ingestion_jobs
             WHERE id = NEW.parent_ingestion_job_id FOR SHARE;
            IF parent.id IS NULL
               OR parent.derivation_kind IS DISTINCT FROM 'pdf_extraction'
               OR parent.workspace_id IS DISTINCT FROM NEW.workspace_id
               OR parent.document_id IS DISTINCT FROM NEW.document_id
               OR parent.target_document_version_id IS DISTINCT FROM NEW.target_document_version_id
               OR parent.source_object_id IS DISTINCT FROM NEW.source_object_id
               OR parent.operation IS DISTINCT FROM NEW.operation
               OR parent.parser_configuration_id IS DISTINCT FROM NEW.parser_configuration_id
               OR parent.normalizer_configuration_id IS DISTINCT FROM
                  NEW.normalizer_configuration_id
               OR parent.chunking_configuration_id IS DISTINCT FROM NEW.chunking_configuration_id
               OR parent.source_revision IS DISTINCT FROM NEW.source_revision
               OR parent.workspace_revision IS DISTINCT FROM NEW.workspace_revision THEN
                RAISE EXCEPTION 'invalid lexical index parent'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER validate_ingestion_index_parent
        BEFORE INSERT OR UPDATE OF parent_ingestion_job_id, derivation_kind,
                                   workspace_id, document_id, target_document_version_id,
                                   source_object_id, operation, parser_configuration_id,
                                   normalizer_configuration_id, chunking_configuration_id,
                                   source_revision, workspace_revision
        ON ingestion_jobs
        FOR EACH ROW
        EXECUTE FUNCTION validate_ingestion_index_parent();
        """
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM ingestion_jobs WHERE derivation_kind = 'lexical_index'")
    ):
        raise RuntimeError("ingestion parent downgrade requires no lexical_index jobs")
    op.execute(
        """
        DROP TRIGGER validate_ingestion_index_parent ON ingestion_jobs;
        DROP FUNCTION validate_ingestion_index_parent();
        """
    )
    op.drop_constraint("ck_ingestion_jobs_index_parent", "ingestion_jobs", type_="check")
    op.drop_index("uq_ingestion_jobs_parent_ingestion_job", table_name="ingestion_jobs")
    op.drop_constraint("fk_ingestion_jobs_parent", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "parent_ingestion_job_id")
