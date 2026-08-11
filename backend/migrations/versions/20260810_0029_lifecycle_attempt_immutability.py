"""Enforce immutable closed Object Lifecycle Attempts."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0029"
down_revision: str | None = "20260810_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_closed_object_lifecycle_attempt_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.closed_at IS NOT NULL THEN
                RAISE EXCEPTION 'closed Object Lifecycle Attempt is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$;

        CREATE TRIGGER prevent_closed_object_lifecycle_attempt_mutation
        BEFORE UPDATE OR DELETE ON object_lifecycle_attempts
        FOR EACH ROW EXECUTE FUNCTION prevent_closed_object_lifecycle_attempt_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER prevent_closed_object_lifecycle_attempt_mutation
            ON object_lifecycle_attempts;
        DROP FUNCTION prevent_closed_object_lifecycle_attempt_mutation();
        """
    )
