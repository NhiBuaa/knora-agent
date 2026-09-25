"""Make embedding dimensions and Embedding Set profile links immutable."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260925_0048"
down_revision: str | None = "20260925_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION enforce_immutable_embedding_dimensions()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.dimensions IS DISTINCT FROM OLD.dimensions THEN
                RAISE EXCEPTION 'embedding configuration dimensions are immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER zz_enforce_immutable_embedding_dimensions
        BEFORE UPDATE OF dimensions ON embedding_configurations
        FOR EACH ROW EXECUTE FUNCTION enforce_immutable_embedding_dimensions()
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_immutable_embedding_set_profile()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.embedding_configuration_id
               IS DISTINCT FROM OLD.embedding_configuration_id THEN
                RAISE EXCEPTION 'embedding set configuration identity is immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER zz_enforce_immutable_embedding_set_profile
        BEFORE UPDATE OF embedding_configuration_id ON embedding_sets
        FOR EACH ROW EXECUTE FUNCTION enforce_immutable_embedding_set_profile()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER zz_enforce_immutable_embedding_set_profile ON embedding_sets")
    op.execute("DROP FUNCTION enforce_immutable_embedding_set_profile()")
    op.execute(
        "DROP TRIGGER zz_enforce_immutable_embedding_dimensions ON embedding_configurations"
    )
    op.execute("DROP FUNCTION enforce_immutable_embedding_dimensions()")
