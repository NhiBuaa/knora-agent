"""Persist the authoritative eligibility timestamp for lifecycle deletion."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0027"
down_revision: str | None = "20260810_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "object_lifecycle_work",
        "id",
        existing_type=sa.String(36),
        type_=sa.String(255),
    )
    op.alter_column(
        "object_lifecycle_attempts",
        "object_lifecycle_work_id",
        existing_type=sa.String(36),
        type_=sa.String(255),
    )
    op.alter_column(
        "object_lifecycle_work",
        "lifecycle_generation",
        existing_type=sa.String(36),
        type_=sa.String(255),
    )
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("object_lifecycle_work")
    }
    if "eligible_at" not in columns:
        op.add_column(
            "object_lifecycle_work",
            sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("object_lifecycle_work")
    }
    if "eligible_at" in columns:
        op.drop_column("object_lifecycle_work", "eligible_at")
    op.alter_column(
        "object_lifecycle_attempts",
        "object_lifecycle_work_id",
        existing_type=sa.String(255),
        type_=sa.String(36),
    )
    op.alter_column(
        "object_lifecycle_work",
        "lifecycle_generation",
        existing_type=sa.String(255),
        type_=sa.String(36),
    )
    op.alter_column(
        "object_lifecycle_work",
        "id",
        existing_type=sa.String(255),
        type_=sa.String(36),
    )
