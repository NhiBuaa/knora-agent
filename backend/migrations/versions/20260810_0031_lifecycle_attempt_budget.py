"""Enforce the four-attempt Object Lifecycle Work budget."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0031"
down_revision: str | None = "20260810_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_object_lifecycle_work_attempts",
        "object_lifecycle_work",
        type_="check",
    )
    op.create_check_constraint(
        "ck_object_lifecycle_work_attempts",
        "object_lifecycle_work",
        "attempt_count >= 0 AND attempt_count <= max_attempts AND max_attempts = 4",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_object_lifecycle_work_attempts",
        "object_lifecycle_work",
        type_="check",
    )
    op.create_check_constraint(
        "ck_object_lifecycle_work_attempts",
        "object_lifecycle_work",
        "attempt_count >= 0 AND max_attempts = 4",
    )
