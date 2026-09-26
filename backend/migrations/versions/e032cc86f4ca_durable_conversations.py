"""Add durable Conversations, Turns and optional trace correlation.

Revision ID: e032cc86f4ca
Revises: 20260925_0048
Create Date: 2026-09-26 11:07:03.932441
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e032cc86f4ca"
down_revision: str | None = "20260925_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("title_source", sa.String(length=10), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 120", name="ck_conversations_title_length"),
        sa.CheckConstraint(
            "title_source IN ('auto', 'manual')", name="ck_conversations_title_source"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_conversations_workspace_id_id"),
    )
    op.create_index("ix_conversations_workspace_id", "conversations", ["workspace_id"])

    op.create_table(
        "conversation_create_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_create_requests_workspace_conversation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "key", name="uq_conversation_create_requests_key"),
    )
    op.create_index(
        "ix_conversation_create_requests_workspace_id",
        "conversation_create_requests",
        ["workspace_id"],
    )

    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence > 0", name="ck_conversation_turns_sequence_positive"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'answered', 'refused', 'failed', 'interrupted')",
            name="ck_conversation_turns_status",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_turns_workspace_conversation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "sequence", name="uq_conversation_turns_conversation_sequence"
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_conversation_turns_workspace_id_id"),
    )

    op.add_column(
        "question_traces", sa.Column("conversation_turn_id", sa.String(length=36), nullable=True)
    )
    op.create_unique_constraint(
        "uq_question_traces_conversation_turn_id", "question_traces", ["conversation_turn_id"]
    )
    op.create_foreign_key(
        "fk_question_traces_workspace_turn",
        "question_traces",
        "conversation_turns",
        ["workspace_id", "conversation_turn_id"],
        ["workspace_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_question_traces_workspace_turn", "question_traces", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_question_traces_conversation_turn_id", "question_traces", type_="unique"
    )
    op.drop_column("question_traces", "conversation_turn_id")
    op.drop_table("conversation_turns")
    op.drop_index(
        "ix_conversation_create_requests_workspace_id", table_name="conversation_create_requests"
    )
    op.drop_table("conversation_create_requests")
    op.drop_index("ix_conversations_workspace_id", table_name="conversations")
    op.drop_table("conversations")
