"""Add explicit extraction and lexical-index ingestion derivations.

Revision ID: 20261016_0154
Revises: 20261016_0153

DRAFT FOR HUNK ACK: not applied; this revision does not execute projection work.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0154"
down_revision = "20261016_0153"
branch_labels = None
depends_on = None

_DERIVATION_CONFIGURATION = (
    "(derivation_kind = 'dense' AND embedding_configuration_id IS NOT NULL "
    "AND lexical_profile IS NULL AND lexical_generation_id IS NULL) OR "
    "(derivation_kind = 'pdf_extraction' AND embedding_configuration_id IS NULL "
    "AND lexical_profile IS NOT NULL AND lexical_generation_id IS NULL) OR "
    "(derivation_kind = 'lexical_index' AND embedding_configuration_id IS NULL "
    "AND lexical_profile IS NULL AND lexical_generation_id IS NOT NULL)"
)


_LEGACY_WORKER_COORDINATION = """
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
"""

_WORKER_COORDINATION = """
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
 AND (terminal_outcome_code = 'stale_document_version'
      OR (terminal_outcome_code = 'stale_derivation_snapshot'
          AND derivation_kind IN ('pdf_extraction', 'lexical_index'))))
"""

_LEGACY_SUPERSEDED_AUDIT = """
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
"""

_SUPERSEDED_AUDIT = """
disposition IS DISTINCT FROM 'superseded'
OR
(closed_at IS NOT NULL
 AND closure_cause IN ('stale_document_version', 'stale_derivation_snapshot')
 AND failure_cause IS NULL
 AND failure_cause_version IS NULL
 AND cause_mapping_version IS NULL
 AND safe_failure_code IS NULL
 AND failure_reason IS NULL
 AND terminal_outcome_code = closure_cause
 AND transition_operation_id IS NOT NULL
 AND ((closure_cause = 'stale_document_version'
       AND transition_operation_kind IN ('superseded', 'pdf_success'))
      OR (closure_cause = 'stale_derivation_snapshot'
          AND transition_operation_kind IN
              ('superseded', 'pdf_extraction_success', 'lexical_index_success')))
 AND transition_request_fingerprint IS NOT NULL)
"""


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("derivation_kind", sa.String(30), nullable=False, server_default="dense"),
    )
    op.add_column(
        "ingestion_jobs", sa.Column("lexical_profile", sa.JSON(none_as_null=True), nullable=True)
    )
    op.add_column(
        "ingestion_jobs", sa.Column("lexical_generation_id", sa.String(36), nullable=True)
    )
    op.add_column("ingestion_jobs", sa.Column("source_revision", sa.Integer(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("workspace_revision", sa.Integer(), nullable=True))
    op.alter_column(
        "ingestion_jobs",
        "embedding_configuration_id",
        existing_type=sa.String(100),
        nullable=True,
    )
    op.create_foreign_key(
        "fk_ingestion_jobs_lexical_generation",
        "ingestion_jobs",
        "lexical_generations",
        ["lexical_generation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_ingestion_jobs_lexical_generation", "ingestion_jobs", ["lexical_generation_id"]
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_derivation_configuration",
        "ingestion_jobs",
        _DERIVATION_CONFIGURATION,
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_lexical_revisions",
        "ingestion_jobs",
        "(derivation_kind = 'dense' AND source_revision IS NULL "
        "AND workspace_revision IS NULL) OR "
        "(derivation_kind IN ('pdf_extraction', 'lexical_index') "
        "AND source_revision IS NOT NULL AND source_revision >= 0 "
        "AND workspace_revision IS NOT NULL AND workspace_revision >= 0)",
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_lexical_profile_object",
        "ingestion_jobs",
        "lexical_profile IS NULL OR json_typeof(lexical_profile) = 'object'",
    )
    op.drop_constraint(
        "ck_ingestion_jobs_worker_coordination_projection", "ingestion_jobs", type_="check"
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_worker_coordination_projection", "ingestion_jobs", _WORKER_COORDINATION
    )
    op.drop_constraint(
        "ck_ingestion_job_attempts_superseded_audit", "ingestion_job_attempts", type_="check"
    )
    op.create_check_constraint(
        "ck_ingestion_job_attempts_superseded_audit", "ingestion_job_attempts", _SUPERSEDED_AUDIT
    )
    op.execute(
        """
        CREATE FUNCTION validate_ingestion_attempt_lexical_supersession()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            job_kind varchar(30);
        BEGIN
            IF NEW.terminal_outcome_code = 'stale_derivation_snapshot'
               OR NEW.closure_cause = 'stale_derivation_snapshot' THEN
                SELECT derivation_kind INTO job_kind FROM ingestion_jobs
                 WHERE id = NEW.ingestion_job_id FOR SHARE;
                IF job_kind IS NULL OR job_kind NOT IN ('pdf_extraction', 'lexical_index')
                   OR NEW.disposition IS DISTINCT FROM 'superseded'
                   OR NEW.terminal_outcome_code IS DISTINCT FROM 'stale_derivation_snapshot'
                   OR NEW.closure_cause IS DISTINCT FROM 'stale_derivation_snapshot'
                   OR COALESCE(NEW.transition_operation_kind, '')
                      NOT IN ('superseded', job_kind || '_success') THEN
                    RAISE EXCEPTION 'invalid lexical supersession audit'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER validate_ingestion_attempt_lexical_supersession
        BEFORE INSERT OR UPDATE OF ingestion_job_id, disposition,
                                   terminal_outcome_code, closure_cause
        ON ingestion_job_attempts
        FOR EACH ROW
        EXECUTE FUNCTION validate_ingestion_attempt_lexical_supersession();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_ingestion_job_lexical_binding()
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

        CREATE TRIGGER validate_ingestion_job_lexical_binding
        BEFORE INSERT OR UPDATE OF derivation_kind, lexical_profile, lexical_generation_id,
                                   workspace_id, document_id, target_document_version_id,
                                   source_object_id, chunking_configuration_id,
                                   parser_configuration_id, normalizer_configuration_id,
                                   source_revision, workspace_revision
        ON ingestion_jobs
        FOR EACH ROW
        EXECUTE FUNCTION validate_ingestion_job_lexical_binding();
        """
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM ingestion_jobs) "
            "OR EXISTS (SELECT 1 FROM lexical_generations)"
        )
    ):
        raise RuntimeError("ingestion derivation downgrade requires an empty owned database")
    op.execute(
        """
        DROP TRIGGER validate_ingestion_attempt_lexical_supersession ON ingestion_job_attempts;
        DROP FUNCTION validate_ingestion_attempt_lexical_supersession();
        """
    )
    op.drop_constraint(
        "ck_ingestion_job_attempts_superseded_audit", "ingestion_job_attempts", type_="check"
    )
    op.create_check_constraint(
        "ck_ingestion_job_attempts_superseded_audit",
        "ingestion_job_attempts",
        _LEGACY_SUPERSEDED_AUDIT,
    )
    op.drop_constraint(
        "ck_ingestion_jobs_worker_coordination_projection", "ingestion_jobs", type_="check"
    )
    op.create_check_constraint(
        "ck_ingestion_jobs_worker_coordination_projection",
        "ingestion_jobs",
        _LEGACY_WORKER_COORDINATION,
    )
    op.execute(
        """
        DROP TRIGGER validate_ingestion_job_lexical_binding ON ingestion_jobs;
        DROP FUNCTION validate_ingestion_job_lexical_binding();
        """
    )
    op.drop_constraint("ck_ingestion_jobs_lexical_profile_object", "ingestion_jobs", type_="check")
    op.drop_constraint(
        "ck_ingestion_jobs_derivation_configuration", "ingestion_jobs", type_="check"
    )
    op.drop_constraint("ck_ingestion_jobs_lexical_revisions", "ingestion_jobs", type_="check")
    op.drop_constraint("uq_ingestion_jobs_lexical_generation", "ingestion_jobs", type_="unique")
    op.drop_constraint("fk_ingestion_jobs_lexical_generation", "ingestion_jobs", type_="foreignkey")
    op.alter_column(
        "ingestion_jobs",
        "embedding_configuration_id",
        existing_type=sa.String(100),
        nullable=False,
    )
    op.drop_column("ingestion_jobs", "workspace_revision")
    op.drop_column("ingestion_jobs", "source_revision")
    op.drop_column("ingestion_jobs", "lexical_generation_id")
    op.drop_column("ingestion_jobs", "lexical_profile")
    op.drop_column("ingestion_jobs", "derivation_kind")
