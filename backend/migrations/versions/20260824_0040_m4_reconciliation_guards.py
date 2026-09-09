"""Allow fenced M4 reconciliation transitions without weakening intent immutability."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260824_0040"
down_revision: str | None = "20260824_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tool_action_audit_events "
        "DROP CONSTRAINT IF EXISTS ck_tool_action_audit_event_type"
    )
    op.create_check_constraint(
        "ck_tool_action_audit_event_type",
        "tool_action_audit_events",
        "event_type IN ('proposed','approved','rejected','approval_invalidated',"
        "'execution_acquired','execution_taken_over','dispatch_admitted',"
        "'execution_observed','succeeded','failed')",
    )
    op.execute(
        "ALTER TABLE tool_proposals DROP CONSTRAINT IF EXISTS ck_tool_proposal_revision"
    )
    op.create_check_constraint(
        "ck_tool_proposal_revision",
        "tool_proposals",
        "(state = 'proposed' AND revision = 0) OR "
        "(state IN ('approved','rejected') AND revision = 1) OR "
        "(state = 'executing' AND revision >= 2) OR "
        "(state IN ('succeeded','failed') AND revision >= 3)",
    )
    op.execute(
        "ALTER TABLE tool_executions "
        "DROP CONSTRAINT IF EXISTS ck_tool_execution_generation_one"
    )
    op.execute(
        "ALTER TABLE tool_executions "
        "DROP CONSTRAINT IF EXISTS ck_tool_execution_generation_positive"
    )
    op.create_check_constraint(
        "ck_tool_execution_generation_positive",
        "tool_executions",
        "generation >= 1",
    )
    op.execute(
        "ALTER TABLE tool_execution_observations "
        "DROP CONSTRAINT IF EXISTS ck_tool_execution_observation_projection"
    )
    op.create_check_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        "(observation_type IN ('succeeded','reconciled_succeeded') AND rejection_code IS NULL "
        "AND external_resource_reference IS NOT NULL) OR "
        "(observation_type IN ('failed','reconciled_failed') AND rejection_code IN "
        "('target_not_found','validation_rejected','policy_rejected') "
        "AND external_resource_reference IS NULL) OR "
        "(observation_type IN ('indeterminate_external_outcome','provider_idempotency_conflict',"
        "'provider_outcome_not_found','provider_observation_unavailable',"
        "'provider_observation_timeout','provider_observation_malformed') "
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
                          AND e.lifecycle = 'executing' AND e.revision = NEW.revision) THEN NULL;
            ELSIF OLD.state = 'executing' AND NEW.state = 'executing'
              AND NEW.revision = OLD.revision + 1
              AND EXISTS (SELECT 1 FROM tool_executions e WHERE e.proposal_id = OLD.id
                          AND e.lifecycle = 'executing' AND e.revision = NEW.revision) THEN NULL;
            ELSIF OLD.state = 'executing' AND NEW.state IN ('succeeded','failed')
              AND EXISTS (SELECT 1 FROM tool_executions e WHERE e.proposal_id = OLD.id
                          AND e.lifecycle = NEW.state AND e.revision = NEW.revision) THEN NULL;
            ELSE RAISE EXCEPTION 'tool proposal decision projection is immutable'; END IF;
          END IF;
          IF OLD.execution_stale_reason IS NOT NULL
             AND NEW.execution_stale_reason IS DISTINCT FROM OLD.execution_stale_reason
          THEN RAISE EXCEPTION 'tool proposal stale projection is immutable'; END IF;
          RETURN NEW;
        END $$;

        CREATE OR REPLACE FUNCTION prevent_tool_execution_material_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'tool execution is retained'; END IF;
          IF NEW.proposal_id <> OLD.proposal_id
             OR NEW.workspace_id <> OLD.workspace_id
             OR NEW.logical_execution_id <> OLD.logical_execution_id
             OR NEW.request_fingerprint <> OLD.request_fingerprint
             OR NEW.binding_snapshot <> OLD.binding_snapshot
             OR NEW.acquisition_identity <> OLD.acquisition_identity
             OR NEW.acquisition_digest <> OLD.acquisition_digest
             OR NEW.acquisition_audit_identity <> OLD.acquisition_audit_identity
             OR NEW.acquisition_audit_digest <> OLD.acquisition_audit_digest
             OR NEW.created_at <> OLD.created_at
          THEN RAISE EXCEPTION 'tool execution material fields are immutable'; END IF;
          IF OLD.lifecycle <> 'executing' THEN
            IF ROW(NEW.lifecycle, NEW.revision, NEW.owner, NEW.generation, NEW.lease_started_at,
               NEW.lease_expires_at, NEW.rejection_code, NEW.external_resource_reference,
               NEW.finalized_at) IS DISTINCT FROM
               ROW(OLD.lifecycle, OLD.revision, OLD.owner, OLD.generation, OLD.lease_started_at,
               OLD.lease_expires_at, OLD.rejection_code, OLD.external_resource_reference,
               OLD.finalized_at)
            THEN RAISE EXCEPTION 'tool execution terminal outcome is immutable'; END IF;
          ELSIF NEW.lifecycle = 'executing' THEN
            IF NEW.generation = OLD.generation + 1
               AND NEW.revision = OLD.revision + 1
               AND NEW.lease_started_at > OLD.lease_expires_at
               AND NEW.lease_expires_at > NEW.lease_started_at
               AND NEW.rejection_code IS NULL
               AND NEW.external_resource_reference IS NULL
               AND NEW.finalized_at IS NULL
            THEN NULL;
            ELSIF ROW(NEW.revision, NEW.owner, NEW.generation, NEW.lease_started_at,
               NEW.lease_expires_at, NEW.rejection_code, NEW.external_resource_reference,
               NEW.finalized_at) IS DISTINCT FROM
               ROW(OLD.revision, OLD.owner, OLD.generation, OLD.lease_started_at,
               OLD.lease_expires_at, OLD.rejection_code, OLD.external_resource_reference,
               OLD.finalized_at)
            THEN RAISE EXCEPTION 'tool execution transition is fenced'; END IF;
          ELSIF NEW.lifecycle IN ('succeeded','failed') THEN
            IF NEW.owner <> OLD.owner OR NEW.generation <> OLD.generation
               OR NEW.lease_started_at <> OLD.lease_started_at
               OR NEW.lease_expires_at <> OLD.lease_expires_at
               OR NEW.revision <> OLD.revision + 1
            THEN RAISE EXCEPTION 'tool execution finalization is fenced'; END IF;
          ELSE RAISE EXCEPTION 'tool execution lifecycle is invalid'; END IF;
          RETURN NEW;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tool_action_audit_immutable ON tool_action_audit_events")
    op.execute(
        "DROP TRIGGER IF EXISTS tool_execution_observation_immutable "
        "ON tool_execution_observations"
    )
    op.execute("DROP TRIGGER IF EXISTS tool_execution_material_immutable ON tool_executions")
    op.execute("DROP TRIGGER IF EXISTS tool_proposal_material_immutable ON tool_proposals")
    op.execute(
        "DELETE FROM tool_action_audit_events WHERE event_type = 'execution_taken_over'"
    )
    op.execute(
        "DELETE FROM tool_execution_observations WHERE observation_type IN "
        "('reconciled_succeeded','reconciled_failed','provider_outcome_not_found',"
        "'provider_observation_unavailable','provider_observation_timeout',"
        "'provider_observation_malformed')"
    )
    op.execute(
        "UPDATE tool_executions SET generation = 1, revision = CASE "
        "WHEN lifecycle = 'executing' THEN 2 ELSE 3 END "
        "WHERE generation <> 1 OR revision <> CASE "
        "WHEN lifecycle = 'executing' THEN 2 ELSE 3 END"
    )
    op.execute(
        "UPDATE tool_proposals SET revision = CASE "
        "WHEN state = 'executing' THEN 2 "
        "WHEN state IN ('succeeded','failed') THEN 3 "
        "ELSE revision END "
        "WHERE state IN ('executing','succeeded','failed')"
    )
    op.drop_constraint(
        "ck_tool_action_audit_event_type", "tool_action_audit_events", type_="check"
    )
    op.create_check_constraint(
        "ck_tool_action_audit_event_type",
        "tool_action_audit_events",
        "event_type IN ('proposed','approved','rejected','approval_invalidated',"
        "'execution_acquired','dispatch_admitted','execution_observed','succeeded','failed')",
    )
    op.drop_constraint("ck_tool_proposal_revision", "tool_proposals", type_="check")
    op.create_check_constraint(
        "ck_tool_proposal_revision",
        "tool_proposals",
        "(state = 'proposed' AND revision = 0) OR "
        "(state IN ('approved','rejected') AND revision = 1) OR "
        "(state = 'executing' AND revision = 2) OR "
        "(state IN ('succeeded','failed') AND revision = 3)",
    )
    op.execute(
        "ALTER TABLE tool_executions "
        "DROP CONSTRAINT IF EXISTS ck_tool_execution_generation_positive"
    )
    op.execute(
        "ALTER TABLE tool_executions "
        "DROP CONSTRAINT IF EXISTS ck_tool_execution_generation_one"
    )
    op.create_check_constraint(
        "ck_tool_execution_generation_one", "tool_executions", "generation = 1"
    )
    op.drop_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        "(observation_type = 'succeeded' AND rejection_code IS NULL "
        "AND external_resource_reference IS NOT NULL) OR "
        "(observation_type = 'failed' AND rejection_code IN "
        "('target_not_found','validation_rejected','policy_rejected') "
        "AND external_resource_reference IS NULL) OR "
        "(observation_type IN ('indeterminate_external_outcome','provider_idempotency_conflict') "
        "AND rejection_code IS NULL AND external_resource_reference IS NULL)",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_tool_execution_material_mutation()
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
        """
    )
    op.execute(
        """
        CREATE TRIGGER tool_action_audit_immutable
        BEFORE UPDATE OR DELETE ON tool_action_audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_audit_mutation();

        CREATE TRIGGER tool_execution_observation_immutable
        BEFORE UPDATE OR DELETE ON tool_execution_observations
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_observation_mutation();

        CREATE TRIGGER tool_execution_material_immutable
        BEFORE UPDATE OR DELETE ON tool_executions
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_execution_material_mutation();

        CREATE TRIGGER tool_proposal_material_immutable
        BEFORE UPDATE ON tool_proposals
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_proposal_material_update();
        """
    )
