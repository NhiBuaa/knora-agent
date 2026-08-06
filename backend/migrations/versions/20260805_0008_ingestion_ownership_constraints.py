"""Enforce Workspace and Document ownership across PDF ingestion records."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260805_0008"
down_revision: str | None = "20260805_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION validate_original_source_object_ownership()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            owner_workspace_id varchar(100);
        BEGIN
            SELECT documents.workspace_id
              INTO owner_workspace_id
              FROM document_versions
              JOIN documents ON documents.id = document_versions.document_id
             WHERE document_versions.id = NEW.document_version_id
             FOR SHARE OF documents;
            IF owner_workspace_id IS NULL
               OR owner_workspace_id IS DISTINCT FROM NEW.workspace_id THEN
                RAISE EXCEPTION 'invalid Original Source Object ownership'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER validate_original_source_object_ownership
        BEFORE INSERT OR UPDATE OF workspace_id, document_version_id
        ON original_source_objects
        FOR EACH ROW
        EXECUTE FUNCTION validate_original_source_object_ownership();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_ingestion_job_ownership()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            document_workspace_id varchar(100);
            target_document_id varchar(36);
            source_workspace_id varchar(100);
            source_document_id varchar(36);
            source_version_id varchar(36);
        BEGIN
            SELECT workspace_id INTO document_workspace_id
              FROM documents
             WHERE id = NEW.document_id
             FOR SHARE;
            SELECT document_id INTO target_document_id
              FROM document_versions
             WHERE id = NEW.target_document_version_id
             FOR SHARE;
            SELECT original_source_objects.workspace_id,
                   document_versions.document_id,
                   document_versions.id
              INTO source_workspace_id, source_document_id, source_version_id
              FROM original_source_objects
              JOIN document_versions
                ON document_versions.id = original_source_objects.document_version_id
             WHERE original_source_objects.id = NEW.source_object_id
             FOR SHARE OF original_source_objects;
            IF document_workspace_id IS NULL
               OR target_document_id IS NULL
               OR source_workspace_id IS NULL
               OR source_document_id IS NULL
               OR document_workspace_id IS DISTINCT FROM NEW.workspace_id
               OR target_document_id IS DISTINCT FROM NEW.document_id
               OR source_workspace_id IS DISTINCT FROM NEW.workspace_id
               OR source_document_id IS DISTINCT FROM NEW.document_id
               OR source_version_id IS DISTINCT FROM NEW.target_document_version_id THEN
                RAISE EXCEPTION 'invalid Ingestion Job ownership'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER validate_ingestion_job_ownership
        BEFORE INSERT OR UPDATE OF workspace_id, document_id,
                                   target_document_version_id, source_object_id
        ON ingestion_jobs
        FOR EACH ROW
        EXECUTE FUNCTION validate_ingestion_job_ownership();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_idempotency_record_ownership()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            job_workspace_id varchar(100);
        BEGIN
            SELECT workspace_id INTO job_workspace_id
              FROM ingestion_jobs
             WHERE id = NEW.ingestion_job_id
             FOR SHARE;
            IF job_workspace_id IS NULL
               OR job_workspace_id IS DISTINCT FROM NEW.workspace_id THEN
                RAISE EXCEPTION 'invalid Idempotency Record ownership'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER validate_idempotency_record_ownership
        BEFORE INSERT OR UPDATE OF workspace_id, ingestion_job_id
        ON idempotency_records
        FOR EACH ROW
        EXECUTE FUNCTION validate_idempotency_record_ownership();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER validate_idempotency_record_ownership ON idempotency_records;
        DROP FUNCTION validate_idempotency_record_ownership();
        DROP TRIGGER validate_ingestion_job_ownership ON ingestion_jobs;
        DROP FUNCTION validate_ingestion_job_ownership();
        DROP TRIGGER validate_original_source_object_ownership ON original_source_objects;
        DROP FUNCTION validate_original_source_object_ownership();
        """
    )
