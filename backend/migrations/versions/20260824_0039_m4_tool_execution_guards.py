"""Harden M4 execution lifecycle and append-only persistence guards."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260824_0039"
down_revision: str | None = "20260824_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tool_action_audit_immutable ON tool_action_audit_events")
    op.execute(
        "CREATE TRIGGER tool_action_audit_immutable "
        "BEFORE UPDATE OR DELETE ON tool_action_audit_events "
        "FOR EACH ROW EXECUTE FUNCTION prevent_tool_audit_mutation()"
    )
    op.create_check_constraint(
        "ck_tool_proposal_execution_stale_reason",
        "tool_proposals",
        "execution_stale_reason IS NULL OR execution_stale_reason IN ("
        "'capability_identity_mismatch','capability_version_mismatch',"
        "'capability_digest_mismatch','binding_identity_mismatch',"
        "'binding_version_mismatch','binding_digest_mismatch',"
        "'policy_identity_mismatch','policy_version_mismatch','policy_digest_mismatch')",
    )
    op.create_check_constraint(
        "ck_tool_execution_terminal_projection",
        "tool_executions",
        "(lifecycle = 'executing' AND rejection_code IS NULL "
        "AND external_resource_reference IS NULL AND finalized_at IS NULL) OR "
        "(lifecycle = 'succeeded' AND rejection_code IS NULL "
        "AND external_resource_reference IS NOT NULL AND finalized_at IS NOT NULL) OR "
        "(lifecycle = 'failed' AND rejection_code IN "
        "('target_not_found','validation_rejected','policy_rejected') "
        "AND external_resource_reference IS NULL AND finalized_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        "(observation_type = 'succeeded' AND rejection_code IS NULL "
        "AND external_resource_reference IS NOT NULL) OR "
        "(observation_type = 'failed' AND rejection_code IN "
        "('target_not_found','validation_rejected','policy_rejected') "
        "AND external_resource_reference IS NULL) OR "
        "(observation_type IN "
        "('indeterminate_external_outcome','provider_idempotency_conflict') "
        "AND rejection_code IS NULL AND external_resource_reference IS NULL)",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_tool_proposal_material_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.workspace_id <> OLD.workspace_id
             OR NEW.capability_id <> OLD.capability_id
             OR NEW.capability_version <> OLD.capability_version
             OR NEW.capability_digest <> OLD.capability_digest
             OR NEW.binding_id <> OLD.binding_id
             OR NEW.binding_version <> OLD.binding_version
             OR NEW.binding_digest <> OLD.binding_digest
             OR NEW.policy_id <> OLD.policy_id
             OR NEW.policy_version <> OLD.policy_version
             OR NEW.policy_digest <> OLD.policy_digest
             OR NEW.policy_snapshot <> OLD.policy_snapshot
             OR NEW.target_reference <> OLD.target_reference
             OR NEW.target_reference_digest <> OLD.target_reference_digest
             OR NEW.target_reference_id <> OLD.target_reference_id
             OR NEW.target_resource_identity_digest <> OLD.target_resource_identity_digest
             OR NEW.target_resource_claims_digest <> OLD.target_resource_claims_digest
             OR NEW.resource_kind <> OLD.resource_kind OR NEW.parameters <> OLD.parameters
             OR NEW.parameters_digest <> OLD.parameters_digest
             OR NEW.request_fingerprint <> OLD.request_fingerprint
             OR NEW.caller_principal_id <> OLD.caller_principal_id
             OR NEW.caller_key_id <> OLD.caller_key_id
             OR NEW.proposal_actor_id <> OLD.proposal_actor_id
             OR NEW.proposal_actor_kind <> OLD.proposal_actor_kind
             OR NEW.proposal_actor_authority_id <> OLD.proposal_actor_authority_id
             OR NEW.proposal_actor_authority_version <> OLD.proposal_actor_authority_version
             OR NEW.proposal_actor_authority_digest <> OLD.proposal_actor_authority_digest
             OR NEW.logical_execution_id <> OLD.logical_execution_id
             OR NEW.created_at <> OLD.created_at OR NEW.expires_at <> OLD.expires_at
          THEN RAISE EXCEPTION 'tool proposal material fields are immutable'; END IF;
          IF OLD.state <> 'proposed' AND (
             NEW.decision_actor_id IS DISTINCT FROM OLD.decision_actor_id
             OR NEW.decision_actor_kind IS DISTINCT FROM OLD.decision_actor_kind
             OR NEW.decision_authority_id IS DISTINCT FROM OLD.decision_authority_id
             OR NEW.decision_authority_version IS DISTINCT FROM OLD.decision_authority_version
             OR NEW.decision_authority_digest IS DISTINCT FROM OLD.decision_authority_digest
             OR NEW.decision_reason IS DISTINCT FROM OLD.decision_reason
             OR NEW.decision_at IS DISTINCT FROM OLD.decision_at
          ) THEN RAISE EXCEPTION 'tool proposal decision projection is immutable'; END IF;
          IF NEW.state IS DISTINCT FROM OLD.state OR NEW.revision IS DISTINCT FROM OLD.revision THEN
            IF OLD.state = 'proposed' THEN NULL;
            ELSIF OLD.state = 'approved' AND NEW.state = 'executing' AND NEW.revision = 2
              AND EXISTS (SELECT 1 FROM tool_executions e WHERE e.proposal_id = OLD.id
                          AND e.lifecycle = 'executing' AND e.revision = 2) THEN NULL;
            ELSIF OLD.state = 'executing' AND NEW.state IN ('succeeded','failed')
              AND NEW.revision = 3
              AND EXISTS (SELECT 1 FROM tool_executions e WHERE e.proposal_id = OLD.id
                          AND e.lifecycle = NEW.state AND e.revision = 3) THEN NULL;
            ELSE RAISE EXCEPTION 'tool proposal decision projection is immutable'; END IF;
          END IF;
          IF OLD.execution_stale_reason IS NOT NULL
             AND NEW.execution_stale_reason IS DISTINCT FROM OLD.execution_stale_reason
          THEN RAISE EXCEPTION 'tool proposal stale projection is immutable'; END IF;
          RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_tool_execution_material_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'tool execution is retained'; END IF;
          IF NEW.proposal_id <> OLD.proposal_id
             OR NEW.workspace_id <> OLD.workspace_id
             OR NEW.logical_execution_id <> OLD.logical_execution_id
             OR NEW.request_fingerprint <> OLD.request_fingerprint
             OR NEW.owner <> OLD.owner OR NEW.generation <> OLD.generation
             OR NEW.lease_started_at <> OLD.lease_started_at
             OR NEW.lease_expires_at <> OLD.lease_expires_at
             OR NEW.binding_snapshot <> OLD.binding_snapshot
             OR NEW.acquisition_identity <> OLD.acquisition_identity
             OR NEW.acquisition_digest <> OLD.acquisition_digest
             OR NEW.acquisition_audit_identity <> OLD.acquisition_audit_identity
             OR NEW.acquisition_audit_digest <> OLD.acquisition_audit_digest
             OR NEW.created_at <> OLD.created_at
          THEN RAISE EXCEPTION 'tool execution material fields are immutable'; END IF;
          IF OLD.lifecycle <> 'executing' AND ROW(NEW.lifecycle, NEW.revision, NEW.rejection_code,
             NEW.external_resource_reference, NEW.finalized_at) IS DISTINCT FROM
             ROW(OLD.lifecycle, OLD.revision, OLD.rejection_code,
             OLD.external_resource_reference, OLD.finalized_at)
          THEN RAISE EXCEPTION 'tool execution terminal outcome is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER tool_execution_material_immutable
        BEFORE UPDATE OR DELETE ON tool_executions
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_execution_material_mutation();

        CREATE FUNCTION prevent_tool_admission_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'tool dispatch admission is immutable'; END $$;
        CREATE TRIGGER tool_dispatch_admission_immutable
        BEFORE UPDATE OR DELETE ON tool_dispatch_admissions
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_admission_mutation();

        CREATE FUNCTION prevent_tool_observation_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'tool execution observation is immutable'; END $$;
        CREATE TRIGGER tool_execution_observation_immutable
        BEFORE UPDATE OR DELETE ON tool_execution_observations
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_observation_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS tool_execution_observation_immutable ON tool_execution_observations"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_observation_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS tool_dispatch_admission_immutable ON tool_dispatch_admissions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_admission_mutation()")
    op.execute("DROP TRIGGER IF EXISTS tool_execution_material_immutable ON tool_executions")
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_execution_material_mutation()")
    op.drop_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        type_="check",
    )
    op.drop_constraint("ck_tool_execution_terminal_projection", "tool_executions", type_="check")
    op.drop_constraint("ck_tool_proposal_execution_stale_reason", "tool_proposals", type_="check")
