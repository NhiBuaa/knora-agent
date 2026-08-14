"""Persist the complete immutable embedding configuration contract."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0035"
down_revision: str | None = "20260812_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "embedding_configurations", sa.Column("deployment_identity", sa.String(200), nullable=True)
    )
    op.add_column(
        "embedding_configurations", sa.Column("api_contract_version", sa.String(200), nullable=True)
    )
    op.add_column(
        "embedding_configurations", sa.Column("input_normalization", sa.String(100), nullable=True)
    )
    op.add_column(
        "embedding_configurations", sa.Column("input_policy_id", sa.String(100), nullable=True)
    )
    op.add_column(
        "embedding_configurations", sa.Column("output_dimensionality", sa.Integer(), nullable=True)
    )
    op.add_column(
        "embedding_configurations", sa.Column("vector_normalization", sa.String(200), nullable=True)
    )
    op.create_table(
        "retrieval_v2_cutovers",
        sa.Column(
            "workspace_id",
            sa.String(100),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "embedding_configuration_id",
            sa.String(100),
            sa.ForeignKey("embedding_configurations.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("population_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("status = 'completed'", name="ck_retrieval_v2_cutover_completed"),
    )


def downgrade() -> None:
    op.drop_table("retrieval_v2_cutovers")
    for name in (
        "vector_normalization",
        "output_dimensionality",
        "input_policy_id",
        "input_normalization",
        "api_contract_version",
        "deployment_identity",
    ):
        op.drop_column("embedding_configurations", name)
