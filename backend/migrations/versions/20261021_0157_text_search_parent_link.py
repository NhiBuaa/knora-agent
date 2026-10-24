"""Allow dense derivation parents for text search indexing.

Revision ID: 20261021_0157
Revises: 20261022_0158
"""

from alembic import op

revision = "20261021_0157"
down_revision = "20261022_0158"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_ingestion_index_parent()
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
               AND OLD.derivation_kind IN ('pdf_extraction', 'dense')
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
               OR parent.derivation_kind NOT IN ('pdf_extraction', 'dense')
               OR parent.workspace_id IS DISTINCT FROM NEW.workspace_id
               OR parent.document_id IS DISTINCT FROM NEW.document_id
               OR parent.target_document_version_id IS DISTINCT FROM NEW.target_document_version_id
               OR parent.source_object_id IS DISTINCT FROM NEW.source_object_id
               OR parent.operation IS DISTINCT FROM NEW.operation
               OR parent.parser_configuration_id IS DISTINCT FROM NEW.parser_configuration_id
               OR parent.normalizer_configuration_id IS DISTINCT FROM
                  NEW.normalizer_configuration_id
               OR parent.chunking_configuration_id IS DISTINCT FROM NEW.chunking_configuration_id
               OR (parent.derivation_kind = 'pdf_extraction' AND (
                   parent.source_revision IS DISTINCT FROM NEW.source_revision
                   OR parent.workspace_revision IS DISTINCT FROM NEW.workspace_revision
               )) THEN
                RAISE EXCEPTION 'invalid lexical index parent'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_ingestion_job_lexical_binding()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            generation_workspace_id varchar(100);
            generation_document_id varchar(36);
            generation_version_id varchar(36);
            generation_source_revision integer;
            generation_workspace_revision integer;
            chunk_version_id varchar(36);
            chunk_configuration_id varchar(100);
            chunk_parser_id varchar(100);
            chunk_normalizer_id varchar(100);
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NEW.derivation_kind IS DISTINCT FROM OLD.derivation_kind
                   OR NEW.lexical_profile::jsonb IS DISTINCT FROM OLD.lexical_profile::jsonb
                   OR NEW.lexical_generation_id IS DISTINCT FROM OLD.lexical_generation_id
                   OR NEW.source_revision IS DISTINCT FROM OLD.source_revision
                   OR NEW.workspace_revision IS DISTINCT FROM OLD.workspace_revision THEN
                    RAISE EXCEPTION 'ingestion derivation identity is immutable'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF NEW.derivation_kind <> 'lexical_index' THEN
                RETURN NEW;
            END IF;
            SELECT generation.workspace_id, generation.document_id,
                   generation.document_version_id, generation.source_revision,
                   generation.workspace_revision, chunk_set.document_version_id,
                   chunk_set.chunking_configuration_id, chunk_set.parser_configuration_id,
                   chunk_set.normalizer_configuration_id
              INTO generation_workspace_id, generation_document_id,
                   generation_version_id, generation_source_revision,
                   generation_workspace_revision, chunk_version_id, chunk_configuration_id,
                   chunk_parser_id, chunk_normalizer_id
              FROM lexical_generations AS generation
              JOIN chunk_sets AS chunk_set ON chunk_set.id = generation.chunk_set_id
             WHERE generation.id = NEW.lexical_generation_id
             FOR SHARE OF generation, chunk_set;
            IF generation_workspace_id IS NULL
               OR generation_workspace_id IS DISTINCT FROM NEW.workspace_id
               OR generation_document_id IS DISTINCT FROM NEW.document_id
               OR generation_version_id IS DISTINCT FROM NEW.target_document_version_id
               OR generation_source_revision IS DISTINCT FROM NEW.source_revision
               OR generation_workspace_revision IS DISTINCT FROM NEW.workspace_revision
               OR chunk_version_id IS DISTINCT FROM NEW.target_document_version_id
               OR chunk_configuration_id IS DISTINCT FROM NEW.chunking_configuration_id
               OR (chunk_parser_id IS DISTINCT FROM NEW.parser_configuration_id
                   AND NOT (chunk_parser_id IS NULL
                            AND NEW.parser_configuration_id = 'text-parser-m1'))
               OR (chunk_normalizer_id IS DISTINCT FROM NEW.normalizer_configuration_id
                   AND NOT (chunk_normalizer_id IS NULL
                            AND NEW.normalizer_configuration_id = 'text-normalizer-m1')) THEN
                RAISE EXCEPTION 'invalid lexical Ingestion Job ownership'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_ingestion_index_parent()
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
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_ingestion_job_lexical_binding()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            generation_workspace_id varchar(100);
            generation_document_id varchar(36);
            generation_version_id varchar(36);
            generation_source_revision integer;
            generation_workspace_revision integer;
            chunk_version_id varchar(36);
            chunk_configuration_id varchar(100);
            chunk_parser_id varchar(100);
            chunk_normalizer_id varchar(100);
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NEW.derivation_kind IS DISTINCT FROM OLD.derivation_kind
                   OR NEW.lexical_profile::jsonb IS DISTINCT FROM OLD.lexical_profile::jsonb
                   OR NEW.lexical_generation_id IS DISTINCT FROM OLD.lexical_generation_id
                   OR NEW.source_revision IS DISTINCT FROM OLD.source_revision
                   OR NEW.workspace_revision IS DISTINCT FROM OLD.workspace_revision THEN
                    RAISE EXCEPTION 'ingestion derivation identity is immutable'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF NEW.derivation_kind <> 'lexical_index' THEN
                RETURN NEW;
            END IF;
            SELECT generation.workspace_id, generation.document_id,
                   generation.document_version_id, generation.source_revision,
                   generation.workspace_revision, chunk_set.document_version_id,
                   chunk_set.chunking_configuration_id, chunk_set.parser_configuration_id,
                   chunk_set.normalizer_configuration_id
              INTO generation_workspace_id, generation_document_id,
                   generation_version_id, generation_source_revision,
                   generation_workspace_revision, chunk_version_id, chunk_configuration_id,
                   chunk_parser_id, chunk_normalizer_id
              FROM lexical_generations AS generation
              JOIN chunk_sets AS chunk_set ON chunk_set.id = generation.chunk_set_id
             WHERE generation.id = NEW.lexical_generation_id
             FOR SHARE OF generation, chunk_set;
            IF generation_workspace_id IS NULL
               OR generation_workspace_id IS DISTINCT FROM NEW.workspace_id
               OR generation_document_id IS DISTINCT FROM NEW.document_id
               OR generation_version_id IS DISTINCT FROM NEW.target_document_version_id
               OR generation_source_revision IS DISTINCT FROM NEW.source_revision
               OR generation_workspace_revision IS DISTINCT FROM NEW.workspace_revision
               OR chunk_version_id IS DISTINCT FROM NEW.target_document_version_id
               OR chunk_configuration_id IS DISTINCT FROM NEW.chunking_configuration_id
               OR chunk_parser_id IS DISTINCT FROM NEW.parser_configuration_id
               OR chunk_normalizer_id IS DISTINCT FROM NEW.normalizer_configuration_id THEN
                RAISE EXCEPTION 'invalid lexical Ingestion Job ownership'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
