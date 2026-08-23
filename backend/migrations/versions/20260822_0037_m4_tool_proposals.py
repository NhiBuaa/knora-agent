"""Add immutable M4 tool proposal, decision and audit tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260822_0037"
down_revision: str | None = "20260816_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capability_id", sa.String(100), nullable=False),
        sa.Column("capability_version", sa.String(100), nullable=False),
        sa.Column("capability_digest", sa.String(200), nullable=False),
        sa.Column("binding_id", sa.String(200), nullable=False),
        sa.Column("binding_version", sa.String(100), nullable=False),
        sa.Column("binding_digest", sa.String(200), nullable=False),
        sa.Column("policy_id", sa.String(200), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("policy_digest", sa.String(200), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("target_reference", sa.Text(), nullable=False),
        sa.Column("target_reference_digest", sa.String(200), nullable=False),
        sa.Column("target_reference_id", sa.String(100), nullable=False),
        sa.Column("target_resource_identity_digest", sa.String(200), nullable=False),
        sa.Column("target_resource_claims_digest", sa.String(200), nullable=False),
        sa.Column("resource_kind", sa.String(100), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("parameters_digest", sa.String(200), nullable=False),
        sa.Column("request_fingerprint", sa.String(200), nullable=False),
        sa.Column("caller_principal_id", sa.String(200), nullable=False),
        sa.Column("caller_key_id", sa.String(200), nullable=False),
        sa.Column("proposal_actor_id", sa.String(200), nullable=False),
        sa.Column("proposal_actor_kind", sa.String(20), nullable=False),
        sa.Column("proposal_actor_authority_id", sa.String(200), nullable=False),
        sa.Column("proposal_actor_authority_version", sa.String(100), nullable=False),
        sa.Column("proposal_actor_authority_digest", sa.String(200), nullable=False),
        sa.Column("logical_execution_id", sa.String(36), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_at", sa.DateTime(timezone=True)),
        sa.Column("decision_actor_id", sa.String(200)),
        sa.Column("decision_actor_kind", sa.String(20)),
        sa.Column("decision_authority_id", sa.String(200)),
        sa.Column("decision_authority_version", sa.String(100)),
        sa.Column("decision_authority_digest", sa.String(200)),
        sa.Column("decision_reason", sa.String(40)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "state IN ('proposed', 'approved', 'rejected')",
            name="ck_tool_proposal_state",
        ),
        sa.CheckConstraint("revision IN (0, 1)", name="ck_tool_proposal_revision"),
        sa.CheckConstraint(
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
            name="ck_tool_proposal_decision_projection",
        ),
        sa.CheckConstraint(
            "proposal_actor_kind IN ('human','model','system')",
            name="ck_tool_proposal_actor_kind",
        ),
        sa.CheckConstraint(
            "capability_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND binding_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND policy_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND target_reference_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND target_resource_identity_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND target_resource_claims_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND parameters_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND request_fingerprint ~ '^sha256:[0-9a-f]{64}$' "
            "AND proposal_actor_authority_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND (decision_authority_digest IS NULL OR "
            "decision_authority_digest ~ '^sha256:[0-9a-f]{64}$')",
            name="ck_tool_proposal_digests",
        ),
    )
    op.create_index("ix_tool_proposals_workspace_id", "tool_proposals", ["workspace_id"])
    op.create_table(
        "tool_proposal_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("tool_proposals.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False),
        sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("actor_kind", sa.String(20), nullable=False),
        sa.Column("authority_id", sa.String(200), nullable=False),
        sa.Column("authority_version", sa.String(100), nullable=False),
        sa.Column("authority_digest", sa.String(200), nullable=False),
        sa.Column("reason_code", sa.String(40)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("proposal_id", name="uq_tool_proposal_decision_proposal"),
        sa.CheckConstraint(
            "decision IN ('approved','rejected')",
            name="ck_tool_proposal_decision_value",
        ),
        sa.CheckConstraint(
            "expected_revision >= 0 AND resulting_revision = expected_revision + 1",
            name="ck_tool_proposal_decision_revision",
        ),
        sa.CheckConstraint("actor_kind = 'human'", name="ck_tool_proposal_decision_actor"),
        sa.CheckConstraint(
            "authority_digest ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_tool_proposal_decision_authority_digest",
        ),
        sa.CheckConstraint(
            "(decision = 'approved' AND reason_code IS NULL) OR "
            "(decision = 'rejected' AND reason_code IS NOT NULL AND reason_code IN "
            "('not_approved','incorrect_target','incorrect_parameters','other'))",
            name="ck_tool_proposal_decision_reason",
        ),
    )
    op.create_index(
        "ix_tool_proposal_decisions_workspace_id", "tool_proposal_decisions", ["workspace_id"]
    )
    op.create_table(
        "tool_action_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("tool_proposals.id"), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("actor_kind", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("proposal_id", "sequence", name="uq_tool_action_audit_sequence"),
        sa.CheckConstraint("sequence >= 1", name="ck_tool_action_audit_sequence"),
        sa.CheckConstraint(
            "event_type IN ('proposed','approved','rejected')",
            name="ck_tool_action_audit_event_type",
        ),
        sa.CheckConstraint(
            "actor_kind IN ('human','model','system')",
            name="ck_tool_action_audit_actor_kind",
        ),
    )
    op.create_index(
        "ix_tool_action_audit_events_workspace_id", "tool_action_audit_events", ["workspace_id"]
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
             OR NEW.created_at <> OLD.created_at
             OR NEW.expires_at <> OLD.expires_at
             THEN RAISE EXCEPTION 'tool proposal material fields are immutable';
          END IF;
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
          ) THEN RAISE EXCEPTION 'tool proposal decision projection is immutable';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER tool_proposal_material_immutable
        BEFORE UPDATE ON tool_proposals
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_proposal_material_update();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_tool_decision_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'tool proposal decision is immutable'; END $$;
        CREATE TRIGGER tool_proposal_decision_immutable
        BEFORE UPDATE OR DELETE ON tool_proposal_decisions
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_decision_mutation();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_tool_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'tool action audit is append-only'; END $$;
        CREATE TRIGGER tool_action_audit_immutable
        BEFORE UPDATE OR DELETE ON tool_action_audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_tool_audit_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tool_action_audit_immutable ON tool_action_audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_audit_mutation()")
    op.execute("DROP TRIGGER IF EXISTS tool_proposal_decision_immutable ON tool_proposal_decisions")
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_decision_mutation()")
    op.execute("DROP TRIGGER IF EXISTS tool_proposal_material_immutable ON tool_proposals")
    op.execute("DROP FUNCTION IF EXISTS prevent_tool_proposal_material_update()")
    op.drop_table("tool_action_audit_events")
    op.drop_table("tool_proposal_decisions")
    op.drop_index("ix_tool_proposals_workspace_id", table_name="tool_proposals")
    op.drop_table("tool_proposals")
