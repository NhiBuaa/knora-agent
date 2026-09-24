"""Add persisted issuer/subject ownership to Workspaces."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0043"
down_revision: tuple[str, str] = ("20260914_0042", "20260909_0041")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_identities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("issuer", "subject", name="uq_workspace_identities_issuer_subject"),
    )
    op.add_column("workspaces", sa.Column("owner_identity_id", sa.String(length=36), nullable=True))
    op.add_column(
        "workspaces", sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column(
        "workspaces", sa.Column("revision", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_index("ix_workspaces_owner_identity_id", "workspaces", ["owner_identity_id"])
    op.create_foreign_key(
        "fk_workspaces_owner_identity_id",
        "workspaces",
        "workspace_identities",
        ["owner_identity_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    connection = op.get_bind()
    owned = connection.execute(
        sa.text("SELECT 1 FROM workspaces WHERE owner_identity_id IS NOT NULL LIMIT 1")
    ).first()
    if owned is not None:
        raise RuntimeError("refusing to discard persisted Workspace ownership")
    op.drop_constraint("fk_workspaces_owner_identity_id", "workspaces", type_="foreignkey")
    op.drop_index("ix_workspaces_owner_identity_id", table_name="workspaces")
    op.drop_column("workspaces", "revision")
    op.drop_column("workspaces", "archived")
    op.drop_column("workspaces", "owner_identity_id")
    op.drop_table("workspace_identities")
