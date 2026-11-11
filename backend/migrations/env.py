import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, engine_from_config, pool

from knora.adapters.postgres import (  # noqa: F401
    evaluation_datasets_tables,
    evaluation_runs_tables,
    tables,  # noqa: F401
)
from knora.adapters.postgres.database import Base

config = context.config
database_url = os.environ.get("KNORA_DATABASE_URL")
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url or config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = (
        create_engine(database_url, poolclass=pool.NullPool)
        if database_url
        else engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
