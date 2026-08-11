"""Persist lifecycle operation bindings and exact retry-policy decisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0028"
down_revision: str | None = "20260810_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "object_lifecycle_attempts",
        sa.Column("prepare_operation_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "object_lifecycle_attempts",
        sa.Column("deletion_generation", sa.String(36), nullable=True),
    )
    op.add_column(
        "object_lifecycle_attempts",
        sa.Column("completion_operation_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "object_lifecycle_attempts",
        sa.Column("failure_operation_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "object_lifecycle_attempts",
        sa.Column("retry_policy_version", sa.String(50), nullable=True),
    )
    op.add_column(
        "object_lifecycle_attempts",
        sa.Column("retry_window_upper_bound_microseconds", sa.Integer, nullable=True),
    )
    op.create_unique_constraint(
        "uq_object_lifecycle_attempt_prepare_operation",
        "object_lifecycle_attempts",
        ["prepare_operation_id"],
    )
    op.create_unique_constraint(
        "uq_object_lifecycle_attempt_completion_operation",
        "object_lifecycle_attempts",
        ["completion_operation_id"],
    )
    op.create_unique_constraint(
        "uq_object_lifecycle_attempt_failure_operation",
        "object_lifecycle_attempts",
        ["failure_operation_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_object_lifecycle_attempt_failure_operation",
        "object_lifecycle_attempts",
        type_="unique",
    )
    op.drop_constraint(
        "uq_object_lifecycle_attempt_completion_operation",
        "object_lifecycle_attempts",
        type_="unique",
    )
    op.drop_constraint(
        "uq_object_lifecycle_attempt_prepare_operation",
        "object_lifecycle_attempts",
        type_="unique",
    )
    for name in (
        "retry_window_upper_bound_microseconds",
        "retry_policy_version",
        "failure_operation_id",
        "completion_operation_id",
        "deletion_generation",
        "prepare_operation_id",
    ):
        op.drop_column("object_lifecycle_attempts", name)
