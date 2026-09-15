"""Add reversible document archive state and asynchronous deletion requests."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0042"
down_revision: str | None = "20260909_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("documents")}
    if "archived" not in columns:
        op.add_column("documents", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column("documents", "archived", server_default=None)
    inspector = sa.inspect(op.get_bind())
    if "document_deletion_requests" not in inspector.get_table_names():
        op.create_table(
            "document_deletion_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace_id", sa.String(100), sa.ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("idempotency_key", sa.String(255), nullable=False),
            sa.Column("state", sa.String(20), nullable=False, server_default="requested"),
            sa.Column("failure_reason", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("workspace_id", "document_id", "idempotency_key"),
        )
        op.create_index("ix_document_deletion_requests_workspace_id", "document_deletion_requests", ["workspace_id"])
        op.create_index("ix_document_deletion_requests_document_id", "document_deletion_requests", ["document_id"])
    elif "failure_reason" not in {
        c["name"] for c in inspector.get_columns("document_deletion_requests")
    }:
        op.add_column(
            "document_deletion_requests",
            sa.Column("failure_reason", sa.String(100), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "document_deletion_requests" in inspector.get_table_names():
        if "failure_reason" in {
            c["name"] for c in inspector.get_columns("document_deletion_requests")
        }:
            op.drop_column("document_deletion_requests", "failure_reason")
        op.drop_table("document_deletion_requests")
    if "archived" in {c["name"] for c in inspector.get_columns("documents")}:
        op.drop_column("documents", "archived")
