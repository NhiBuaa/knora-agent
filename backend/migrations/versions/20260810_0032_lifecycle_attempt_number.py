"""Enforce valid Object Lifecycle Attempt numbers."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0032"
down_revision: str | None = "20260810_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_object_lifecycle_attempt_number",
        "object_lifecycle_attempts",
        "attempt_number >= 1 AND attempt_number <= 4",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_object_lifecycle_attempt_number",
        "object_lifecycle_attempts",
        type_="check",
    )
