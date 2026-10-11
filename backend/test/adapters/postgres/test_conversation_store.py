from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import ConversationTable, WorkspaceTable
from knora.domain.errors import KnoraError
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
        return import_module("knora.adapters.postgres.conversation_store").PostgresConversationStore
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
                column["name"] for column in inspect(connection).get_columns("conversation_turns")
            }
        engine.dispose()


def test_conversation_search_filters_before_pagination_and_keeps_workspace_archive_scope():
    workspace_id, other_workspace_id = str(uuid4()), str(uuid4())
    ids = [str(uuid4()) for _ in range(5)]
    with SessionFactory.begin() as session:
        session.add_all(
            [
                WorkspaceTable(id=workspace_id, name="Search"),
                WorkspaceTable(id=other_workspace_id, name="Other"),
            ]
        )
        session.flush()
        for index, (title, archived, workspace) in enumerate(
            [
                ("Unrelated", False, workspace_id),
                ("Budget 100%_ FINAL", False, workspace_id),
                ("Budget 100%_ second", False, workspace_id),
                ("Budget 100%_ archived", True, workspace_id),
                ("Budget 100%_ foreign", False, other_workspace_id),
            ]
        ):
            session.add(
                ConversationTable(
                    id=ids[index],
                    workspace_id=workspace,
                    title=title,
                    title_source="manual",
                    archived=archived,
                    revision=0,
                    updated_at=datetime(2026, 10, 5, tzinfo=UTC) - timedelta(minutes=index),
                )
            )
    store = conversation_store_class()(SessionFactory)
    page = store.list(workspace_id, False, None, 1, q="  100%_  ")
    assert [item.id for item in page.items] == [ids[1]]
    assert page.next_cursor is not None
    following = store.list(workspace_id, False, page.next_cursor, 1, q="100%_")
    assert [item.id for item in following.items] == [ids[2]]
    assert following.next_cursor is None
    assert [item.id for item in store.list(workspace_id, True, None, 20, q="budget").items] == [
        ids[3]
    ]
    assert store.list(workspace_id, False, None, 20, q="100%X").items == ()
    assert [item.id for item in store.list(workspace_id, False, None, 20, q="final").items] == [
        ids[1]
    ]
    for query, archived, workspace in (
        ("other", False, workspace_id),
        (None, False, workspace_id),
        ("100%_", True, workspace_id),
        ("100%_", False, other_workspace_id),
    ):
        with pytest.raises(KnoraError, match="INVALID_CONVERSATION_CURSOR"):
            store.list(workspace, archived, page.next_cursor, 20, q=query)


def test_conversation_store_rejects_overlong_search_and_normalizes_blank_query():
    store = conversation_store_class()(SessionFactory)
    workspace_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Search length"))
    store.create(workspace_id, "new")
    assert store.list(workspace_id, False, None, 20, q=" " + "\u0130" * 200 + " ").items == ()
    assert (
        store.list(workspace_id, False, None, 20, q="   ").items
        == store.list(workspace_id, False, None, 20).items
    )
    with pytest.raises(KnoraError, match="INVALID_CONVERSATION_QUERY"):
        store.list(workspace_id, False, None, 20, q="x" * 201)


@pytest.mark.parametrize("first_query, next_query", [("İ", "i"), ("i", "İ")])
def test_conversation_unicode_search_uses_postgres_case_semantics_for_matching_and_cursor(
    first_query, next_query
):
    workspace_id = str(uuid4())
    first_id, second_id = str(uuid4()), str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Unicode search"))
        session.flush()
        for index, conversation_id in enumerate((first_id, second_id)):
            session.add(
                ConversationTable(
                    id=conversation_id,
                    workspace_id=workspace_id,
                    title=f"İstanbul {index}",
                    title_source="manual",
                    archived=False,
                    revision=0,
                    updated_at=datetime(2026, 10, 5, tzinfo=UTC) - timedelta(minutes=index),
                )
            )
    store = conversation_store_class()(SessionFactory)
    page = store.list(workspace_id, False, None, 1, q=first_query)
    assert [item.id for item in page.items] == [first_id]
    assert page.next_cursor is not None
    following = store.list(workspace_id, False, page.next_cursor, 20, q=f" {next_query} ")
    assert [item.id for item in following.items] == [second_id]
