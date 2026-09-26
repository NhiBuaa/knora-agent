from importlib import import_module
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import WorkspaceTable


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
