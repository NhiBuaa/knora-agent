"""Add Knora identity_access capability table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261115_identity_access"
down_revision: str | Sequence[str] | None = "20261021_0157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "identity_access" not in inspector.get_table_names():
        op.create_table(
            "identity_access",
            sa.Column("issuer", sa.String(length=500), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("issuer", "subject", name="pk_identity_access"),
        )
        op.execute(sa.text("ALTER TABLE identity_access ENABLE ROW LEVEL SECURITY;"))
        op.execute(
            sa.text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL ON identity_access FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL ON identity_access FROM authenticated;
                END IF;
            END $$;
            """)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "identity_access" in inspector.get_table_names():
        op.drop_table("identity_access")
