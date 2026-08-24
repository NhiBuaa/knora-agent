"""Add M4 generation-1 tool execution, admission, observation and epoch state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260824_0038"
down_revision: str | None = "20260822_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tool_proposals", sa.Column("execution_stale_reason", sa.String(60)))
    op.drop_constraint("ck_tool_proposal_state", "tool_proposals", type_="check")
    op.drop_constraint("ck_tool_proposal_revision", "tool_proposals", type_="check")
    op.drop_constraint("ck_tool_proposal_decision_projection", "tool_proposals", type_="check")
    op.create_check_constraint(
        "ck_tool_proposal_state",
        "tool_proposals",
        "state IN ('proposed','approved','rejected','executing','succeeded','failed')",
    )
    op.create_check_constraint(
        "ck_tool_proposal_revision",
        "tool_proposals",
        "(state = 'proposed' AND revision = 0) OR "
        "(state IN ('approved','rejected') AND revision = 1) OR "
        "(state = 'executing' AND revision = 2) OR "
        "(state IN ('succeeded','failed') AND revision = 3)",
    )
    op.create_check_constraint(
        "ck_tool_proposal_decision_projection",
        "tool_proposals",
        "(state = 'proposed' AND decision_actor_id IS NULL AND decision_actor_kind IS NULL "
        "AND decision_authority_id IS NULL AND decision_authority_version IS NULL "
        "AND decision_authority_digest IS NULL AND decision_reason IS NULL "
        "AND decision_at IS NULL) "
        "OR (state = 'rejected' AND decision_actor_kind = 'human' "
        "AND decision_actor_id IS NOT NULL AND decision_authority_id IS NOT NULL "
        "AND decision_authority_version IS NOT NULL AND decision_authority_digest IS NOT NULL "
        "AND decision_reason IN ('not_approved','incorrect_target','incorrect_parameters','other') "
        "AND decision_at IS NOT NULL) OR "
        "(state IN ('approved','executing','succeeded','failed') AND decision_actor_kind = 'human' "
        "AND decision_actor_id IS NOT NULL AND decision_authority_id IS NOT NULL "
        "AND decision_authority_version IS NOT NULL AND decision_authority_digest IS NOT NULL "
        "AND decision_reason IS NULL AND decision_at IS NOT NULL)",
    )
    op.drop_constraint("ck_tool_action_audit_event_type", "tool_action_audit_events", type_="check")
    op.create_check_constraint(
        "ck_tool_action_audit_event_type",
        "tool_action_audit_events",
        "event_type IN ('proposed','approved','rejected','approval_invalidated',"
        "'execution_acquired',"
        "'dispatch_admitted','execution_observed','succeeded','failed')",
    )

    op.create_table(
        "tool_executions",
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("tool_proposals.id"),
            primary_key=True,
        ),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("logical_execution_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_fingerprint", sa.String(200), nullable=False),
        sa.Column("lifecycle", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("lease_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("binding_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("acquisition_identity", sa.String(36), nullable=False, unique=True),
        sa.Column("acquisition_digest", sa.String(200), nullable=False),
        sa.Column("acquisition_audit_identity", sa.String(36), nullable=False, unique=True),
        sa.Column("acquisition_audit_digest", sa.String(200), nullable=False),
        sa.Column("rejection_code", sa.String(40)),
        sa.Column("external_resource_reference", sa.Text()),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("generation = 1", name="ck_tool_execution_generation_one"),
        sa.CheckConstraint(
            "lifecycle IN ('executing','succeeded','failed')", name="ck_tool_execution_lifecycle"
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^sha256:[0-9a-f]{64}$' "
            "AND acquisition_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND acquisition_audit_digest ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_tool_execution_digests",
        ),
    )
    op.create_index("ix_tool_executions_workspace_id", "tool_executions", ["workspace_id"])

    admission_columns = [
        sa.Column("logical_execution_id", sa.String(36), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("tool_proposals.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("admission_schema_version", sa.Integer(), nullable=False),
        sa.Column("admission_identity", sa.String(36), nullable=False, unique=True),
        sa.Column("admission_digest", sa.String(200), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("request_fingerprint", sa.String(200), nullable=False),
    ]
    for name, length in (
        ("capability_identity", 100),
        ("capability_version", 100),
        ("capability_digest", 200),
        ("binding_identity", 200),
        ("binding_version", 100),
        ("binding_digest", 200),
        ("policy_identity", 200),
        ("policy_version", 100),
        ("policy_digest", 200),
        ("reference_identity", 100),
        ("reference_version", 20),
        ("reference_digest", 200),
        ("reference_claims_digest", 200),
        ("resource_identity_digest", 200),
        ("canonical_target_digest", 200),
        ("canonical_parameter_digest", 200),
        ("complete_intent_digest", 200),
        ("authority_decision_digest", 200),
        ("authority_witness_digest", 200),
        ("owner", 200),
        ("envelope_signing_key_identity", 200),
        ("envelope_signing_key_version", 100),
        ("routing_snapshot_digest", 200),
        ("canonical_envelope_digest", 200),
        ("admission_audit_identity", 36),
        ("admission_audit_digest", 200),
    ):
        admission_columns.append(sa.Column(name, sa.String(length), nullable=False))
    admission_columns.extend(
        [
            sa.Column("reference_key_epoch", sa.Integer(), nullable=False),
            sa.Column("workspace_dispatch_epoch", sa.Integer(), nullable=False),
            sa.Column("generation", sa.Integer(), nullable=False),
            sa.Column("database_issue_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lease_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lease_deadline", sa.DateTime(timezone=True), nullable=False),
            sa.Column("envelope_token", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "admission_audit_identity", name="uq_tool_admission_audit_identity"
            ),
            sa.CheckConstraint("generation = 1", name="ck_tool_admission_generation_one"),
        ]
    )
    op.create_table("tool_dispatch_admissions", *admission_columns)
    op.create_index(
        "ix_tool_dispatch_admissions_workspace_id",
        "tool_dispatch_admissions",
        ["workspace_id"],
    )
    op.create_table(
        "tool_execution_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("tool_proposals.id"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("observation_type", sa.String(60), nullable=False),
        sa.Column("rejection_code", sa.String(40)),
        sa.Column("external_resource_reference", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "proposal_id", "sequence", name="uq_tool_execution_observation_sequence"
        ),
    )
    op.create_index(
        "ix_tool_execution_observations_workspace_id",
        "tool_execution_observations",
        ["workspace_id"],
    )
    op.create_table(
        "tool_dispatch_global_epochs",
        sa.Column("singleton_id", sa.Integer(), primary_key=True),
        sa.Column("reference_key_epoch", sa.Integer(), nullable=False),
        sa.CheckConstraint("singleton_id = 1", name="ck_tool_dispatch_global_singleton"),
        sa.CheckConstraint("reference_key_epoch >= 1", name="ck_tool_reference_key_epoch"),
    )
    op.execute("INSERT INTO tool_dispatch_global_epochs VALUES (1, 1)")
    op.create_table(
        "tool_workspace_dispatch_epochs",
        sa.Column(
            "workspace_id",
            sa.String(100),
            sa.ForeignKey("workspaces.id"),
            primary_key=True,
        ),
        sa.Column("workspace_dispatch_epoch", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "workspace_dispatch_epoch >= 1", name="ck_tool_workspace_dispatch_epoch"
        ),
    )

    op.execute("DROP TRIGGER IF EXISTS tool_proposal_material_immutable ON tool_proposals")
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_proposal_material_update()")
    op.execute(
        """
        CREATE FUNCTION prevent_tool_proposal_material_update()
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
             OR NEW.resource_kind <> OLD.resource_kind
             OR NEW.parameters <> OLD.parameters
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
          IF OLD.execution_stale_reason IS NOT NULL
             AND NEW.execution_stale_reason IS DISTINCT FROM OLD.execution_stale_reason
          THEN RAISE EXCEPTION 'tool proposal stale projection is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER tool_proposal_material_immutable BEFORE UPDATE ON tool_proposals
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_proposal_material_update();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tool_proposal_material_immutable ON tool_proposals")
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_proposal_material_update()")
    op.execute("DROP TRIGGER IF EXISTS tool_action_audit_immutable ON tool_action_audit_events")
    op.execute(
        "DELETE FROM tool_action_audit_events WHERE event_type IN "
        "('approval_invalidated','execution_acquired','dispatch_admitted',"
        "'execution_observed','succeeded','failed')"
    )
    op.execute(
        "UPDATE tool_proposals SET state='approved', revision=1 "
        "WHERE state IN ('executing','succeeded','failed')"
    )
    op.execute("UPDATE tool_proposals SET execution_stale_reason=NULL")
    op.execute(
        "CREATE TRIGGER tool_action_audit_immutable "
        "BEFORE UPDATE OR DELETE ON tool_action_audit_events "
        "FOR EACH ROW EXECUTE FUNCTION prevent_tool_audit_mutation()"
    )
    op.drop_table("tool_workspace_dispatch_epochs")
    op.drop_table("tool_dispatch_global_epochs")
    op.drop_table("tool_execution_observations")
    op.drop_table("tool_dispatch_admissions")
    op.drop_table("tool_executions")
    op.drop_constraint("ck_tool_action_audit_event_type", "tool_action_audit_events", type_="check")
    op.create_check_constraint(
        "ck_tool_action_audit_event_type",
        "tool_action_audit_events",
        "event_type IN ('proposed','approved','rejected')",
    )
    op.drop_constraint("ck_tool_proposal_decision_projection", "tool_proposals", type_="check")
    op.drop_constraint("ck_tool_proposal_revision", "tool_proposals", type_="check")
    op.drop_constraint("ck_tool_proposal_state", "tool_proposals", type_="check")
    op.drop_column("tool_proposals", "execution_stale_reason")
    op.create_check_constraint(
        "ck_tool_proposal_state", "tool_proposals", "state IN ('proposed','approved','rejected')"
    )
    op.create_check_constraint("ck_tool_proposal_revision", "tool_proposals", "revision IN (0,1)")
    op.create_check_constraint(
        "ck_tool_proposal_decision_projection",
        "tool_proposals",
        "(state = 'proposed' AND revision = 0 "
        "AND decision_actor_id IS NULL AND decision_actor_kind IS NULL "
        "AND decision_authority_id IS NULL AND decision_authority_version IS NULL "
        "AND decision_authority_digest IS NULL AND decision_reason IS NULL "
        "AND decision_at IS NULL) OR "
        "(state = 'approved' AND revision = 1 "
        "AND decision_actor_id IS NOT NULL AND decision_actor_kind = 'human' "
        "AND decision_authority_id IS NOT NULL "
        "AND decision_authority_version IS NOT NULL "
        "AND decision_authority_digest IS NOT NULL AND decision_reason IS NULL "
        "AND decision_at IS NOT NULL) OR "
        "(state = 'rejected' AND revision = 1 "
        "AND decision_actor_id IS NOT NULL AND decision_actor_kind = 'human' "
        "AND decision_authority_id IS NOT NULL "
        "AND decision_authority_version IS NOT NULL "
        "AND decision_authority_digest IS NOT NULL "
        "AND decision_reason IS NOT NULL AND decision_reason IN "
        "('not_approved','incorrect_target','incorrect_parameters','other') "
        "AND decision_at IS NOT NULL)",
    )
    op.execute(
        """
        CREATE FUNCTION prevent_tool_proposal_material_update()
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
             OR NEW.resource_kind <> OLD.resource_kind
             OR NEW.parameters <> OLD.parameters
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
             NEW.state IS DISTINCT FROM OLD.state
             OR NEW.revision IS DISTINCT FROM OLD.revision
             OR NEW.decision_actor_id IS DISTINCT FROM OLD.decision_actor_id
             OR NEW.decision_actor_kind IS DISTINCT FROM OLD.decision_actor_kind
             OR NEW.decision_authority_id IS DISTINCT FROM OLD.decision_authority_id
             OR NEW.decision_authority_version IS DISTINCT FROM OLD.decision_authority_version
             OR NEW.decision_authority_digest IS DISTINCT FROM OLD.decision_authority_digest
             OR NEW.decision_reason IS DISTINCT FROM OLD.decision_reason
             OR NEW.decision_at IS DISTINCT FROM OLD.decision_at
          ) THEN RAISE EXCEPTION 'tool proposal decision projection is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER tool_proposal_material_immutable BEFORE UPDATE ON tool_proposals
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_proposal_material_update();
        """
    )
