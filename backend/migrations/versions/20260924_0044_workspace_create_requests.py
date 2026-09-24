"""Persist per-identity Workspace creation idempotency."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0044"
down_revision: str | None = "20260924_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_create_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["identity_id"], ["workspace_identities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("identity_id", "operation", "key"),
    )
    op.create_index(
        "ix_workspace_create_requests_identity_id", "workspace_create_requests", ["identity_id"]
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM workspace_create_requests LIMIT 1")).first():
        raise RuntimeError("refusing to discard Workspace creation idempotency history")
    op.drop_index(
        "ix_workspace_create_requests_identity_id", table_name="workspace_create_requests"
    )
    op.drop_table("workspace_create_requests")
