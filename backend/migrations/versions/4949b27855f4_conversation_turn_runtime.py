"""Add idempotency and fenced worker state to Conversation Turns.

Revision ID: 4949b27855f4
Revises: e032cc86f4ca
Create Date: 2026-09-26 12:10:54.897560
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4949b27855f4"
down_revision: str | None = "e032cc86f4ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_turns = bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM conversation_turns)"))
    if existing_turns:
        raise RuntimeError(
            "cannot add durable Turn idempotency without a verified request binding"
        )

    op.add_column(
        "conversation_turns",
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
    )
    op.add_column(
        "conversation_turns",
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
    )
    op.add_column(
        "conversation_turns", sa.Column("worker_id", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "conversation_turns", sa.Column("claim_token", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "conversation_turns",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversation_turns",
        sa.Column("execution_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_conversation_turns_idempotency_scope",
        "conversation_turns",
        ["workspace_id", "conversation_id", "idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_conversation_turns_claim_token", "conversation_turns", ["claim_token"]
    )
    op.create_check_constraint(
        "ck_conversation_turns_request_fingerprint",
        "conversation_turns",
        "length(request_fingerprint) = 64",
    )
    op.create_check_constraint(
        "ck_conversation_turns_processing_lease",
        "conversation_turns",
        "(status = 'processing' AND worker_id IS NOT NULL AND claim_token IS NOT NULL "
        "AND lease_expires_at IS NOT NULL AND execution_deadline_at IS NOT NULL) OR "
        "(status <> 'processing' AND worker_id IS NULL AND claim_token IS NULL "
        "AND lease_expires_at IS NULL AND execution_deadline_at IS NULL)",
    )
    op.create_index(
        "uq_conversation_turns_one_active_per_conversation",
        "conversation_turns",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    retained_turns = bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM conversation_turns)"))
    if retained_turns:
        raise RuntimeError("refusing downgrade while Conversation Turns are retained")

    op.drop_index(
        "uq_conversation_turns_one_active_per_conversation", table_name="conversation_turns"
    )
    op.drop_constraint(
        "ck_conversation_turns_processing_lease", "conversation_turns", type_="check"
    )
    op.drop_constraint(
        "ck_conversation_turns_request_fingerprint", "conversation_turns", type_="check"
    )
    op.drop_constraint(
        "uq_conversation_turns_claim_token", "conversation_turns", type_="unique"
    )
    op.drop_constraint(
        "uq_conversation_turns_idempotency_scope", "conversation_turns", type_="unique"
    )
    op.drop_column("conversation_turns", "execution_deadline_at")
    op.drop_column("conversation_turns", "lease_expires_at")
    op.drop_column("conversation_turns", "claim_token")
    op.drop_column("conversation_turns", "worker_id")
    op.drop_column("conversation_turns", "request_fingerprint")
    op.drop_column("conversation_turns", "idempotency_key")
