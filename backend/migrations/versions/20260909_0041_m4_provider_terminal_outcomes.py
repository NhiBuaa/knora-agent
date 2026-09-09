"""Persist the closed provider-terminal execution outcome taxonomy."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260909_0041"
down_revision: str | None = "20260824_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_tool_execution_terminal_projection", "tool_executions", type_="check"
    )
    op.create_check_constraint(
        "ck_tool_execution_terminal_projection",
        "tool_executions",
        "(lifecycle = 'executing' AND rejection_code IS NULL "
        "AND external_resource_reference IS NULL AND finalized_at IS NULL) OR "
        "(lifecycle = 'succeeded' AND rejection_code IS NULL "
        "AND external_resource_reference IS NOT NULL AND finalized_at IS NOT NULL) OR "
        "(lifecycle = 'failed' AND rejection_code IN "
        "('target_not_found','validation_rejected','policy_rejected',"
        "'provider_request_rejected','provider_scope_denied') "
        "AND external_resource_reference IS NULL AND finalized_at IS NOT NULL)",
    )
    op.drop_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        "(observation_type IN ('succeeded','reconciled_succeeded') AND rejection_code IS NULL "
        "AND external_resource_reference IS NOT NULL) OR "
        "(observation_type IN ('failed','reconciled_failed') AND rejection_code IN "
        "('target_not_found','validation_rejected','policy_rejected') "
        "AND external_resource_reference IS NULL) OR "
        "(observation_type = 'provider_request_rejected' AND "
        "rejection_code = 'provider_request_rejected' AND external_resource_reference IS NULL) OR "
        "(observation_type = 'provider_scope_denied' AND "
        "rejection_code = 'provider_scope_denied' AND external_resource_reference IS NULL) OR "
        "(observation_type = 'reconciled_request_rejected' AND "
        "rejection_code = 'provider_request_rejected' AND external_resource_reference IS NULL) OR "
        "(observation_type IN ('indeterminate_external_outcome','provider_idempotency_conflict',"
        "'provider_outcome_not_found','provider_observation_unavailable',"
        "'provider_observation_timeout','provider_observation_malformed') "
        "AND rejection_code IS NULL AND external_resource_reference IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tool_execution_observation_projection",
        "tool_execution_observations",
        type_="check",
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
    op.drop_constraint(
        "ck_tool_execution_terminal_projection", "tool_executions", type_="check"
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
