from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import WorkspaceTable
from knora.infrastructure.settings import settings


@contextmanager
def disposable_database() -> Iterator[str]:
    database_name = f"knora_conversation_migration_{uuid4().hex}"
    database_url = make_url(settings.database_url).set(database=database_name)
    admin_engine = create_engine(
        database_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {database_name}"))
    try:
        yield database_url.render_as_string(hide_password=False)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name"
                ),
                {"name": database_name},
            )
            connection.execute(text(f"DROP DATABASE {database_name}"))
        admin_engine.dispose()


def alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def conversation_store_class():
    try:
        return import_module(
            "knora.adapters.postgres.conversation_store"
        ).PostgresConversationStore
    except ModuleNotFoundError as error:
        pytest.fail(f"Postgres Conversation store is not implemented: {error}", pytrace=False)


def test_conversation_history_tables_are_migrated() -> None:
    inspector = inspect(SessionFactory.kw["bind"])

    assert inspector.has_table("conversations")
    assert inspector.has_table("conversation_turns")


def test_conversation_turns_require_the_original_question() -> None:
    inspector = inspect(SessionFactory.kw["bind"])

    assert inspector.has_table("conversation_turns")
    columns = {column["name"]: column for column in inspector.get_columns("conversation_turns")}

    assert "question" in columns
    assert columns["question"]["nullable"] is False


def test_question_traces_support_one_optional_conversation_turn_link() -> None:
    inspector = inspect(SessionFactory.kw["bind"])

    assert inspector.has_table("question_traces")
    columns = {column["name"]: column for column in inspector.get_columns("question_traces")}
    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("question_traces")
    }

    assert "conversation_turn_id" in columns
    assert columns["conversation_turn_id"]["nullable"] is True
    assert ("conversation_turn_id",) in unique_columns


def test_postgres_conversation_store_persists_creation_and_manual_rename() -> None:
    workspace_id = f"conversation-store-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Conversation Store Test"))

    store = conversation_store_class()(SessionFactory)
    created = store.create(workspace_id, "create-conversation-1")
    replayed = store.create(workspace_id, "create-conversation-1")
    renamed = store.mutate(workspace_id, created.id, 0, title="My title")
    loaded = store.get(workspace_id, created.id)

    assert replayed.id == created.id
    assert created.title == "New conversation"
    assert loaded.title == "My title"
    assert loaded.title_source == "manual"
    assert renamed.revision == 1


def test_runtime_migration_refuses_to_fabricate_bindings_for_existing_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with disposable_database() as database_url:
        monkeypatch.setenv("KNORA_DATABASE_URL", database_url)
        config = alembic_config(database_url)
        command.upgrade(config, "e032cc86f4ca")
        engine = create_engine(database_url)
        workspace_id = f"legacy-turn-workspace-{uuid4()}"
        conversation_id = str(uuid4())
        turn_id = str(uuid4())
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO workspaces (id, name) VALUES (:id, 'Legacy Turn Test')"),
                {"id": workspace_id},
            )
            connection.execute(
                text(
                    """INSERT INTO conversations
                    (id, workspace_id, title, title_source, archived, revision)
                    VALUES (:id, :workspace, 'New conversation', 'auto', false, 0)"""
                ),
                {"id": conversation_id, "workspace": workspace_id},
            )
            connection.execute(
                text(
                    """INSERT INTO conversation_turns
                    (id, workspace_id, conversation_id, sequence, question, status)
                    VALUES (:id, :workspace, :conversation, 1, 'legacy question', 'queued')"""
                ),
                {
                    "id": turn_id,
                    "workspace": workspace_id,
                    "conversation": conversation_id,
                },
            )

        with pytest.raises(RuntimeError, match="cannot add durable Turn idempotency"):
            command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "e032cc86f4ca"
            )
            assert "idempotency_key" not in {
                column["name"]
                for column in inspect(connection).get_columns("conversation_turns")
            }
        engine.dispose()
