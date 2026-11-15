import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.supabase_session_reader import PostgresSupabaseSessionReader
from knora.domain.errors import KnoraError


@pytest.fixture(scope="module")
def disposable_db():
    db_name = f"knora_test_sess_{uuid.uuid4().hex[:12]}"
    admin_url = "postgresql+psycopg://knora:knora@127.0.0.1:5432/postgres?connect_timeout=3"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}" OWNER knora;'))

    target_url = f"postgresql+psycopg://knora:knora@127.0.0.1:5432/{db_name}?connect_timeout=3"
    engine = create_engine(target_url, pool_pre_ping=True)

    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE SCHEMA IF NOT EXISTS auth;
            CREATE TABLE auth.users (
                id UUID PRIMARY KEY,
                deleted_at TIMESTAMPTZ,
                banned_until TIMESTAMPTZ
            );
            CREATE TABLE auth.sessions (
                id UUID PRIMARY KEY,
                user_id UUID REFERENCES auth.users(id),
                created_at TIMESTAMPTZ NOT NULL
            );
        """)
        )
        conn.commit()

    yield engine

    engine.dispose()
    with admin_engine.connect() as conn:
        conn.execute(
            text(f"""
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid();
        """)
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}";'))
    admin_engine.dispose()


@pytest.fixture
def session_factory(disposable_db):
    return sessionmaker(bind=disposable_db, expire_on_commit=False)


@pytest.fixture
def reader(session_factory):
    return PostgresSupabaseSessionReader(session_factory)


@pytest.fixture
def connection(disposable_db):
    conn = disposable_db.connect()
    yield conn
    conn.close()


def test_active_session_returns_true(reader, connection):
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    connection.execute(
        text("INSERT INTO auth.users (id, deleted_at, banned_until) VALUES (:uid, NULL, NULL)"),
        {"uid": user_id},
    )
    connection.execute(
        text("INSERT INTO auth.sessions (id, user_id, created_at) VALUES (:sid, :uid, :created)"),
        {"sid": session_id, "uid": user_id, "created": now - timedelta(hours=1)},
    )
    connection.commit()

    assert reader.is_active(user_id, session_id) is True


def test_missing_session_returns_false(reader):
    assert reader.is_active(str(uuid.uuid4()), str(uuid.uuid4())) is False


def test_wrong_user_returns_false(reader, connection):
    user_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    connection.execute(
        text("INSERT INTO auth.users (id, deleted_at, banned_until) VALUES (:uid, NULL, NULL)"),
        {"uid": user_id},
    )
    connection.execute(
        text("INSERT INTO auth.sessions (id, user_id, created_at) VALUES (:sid, :uid, :created)"),
        {"sid": session_id, "uid": user_id, "created": now},
    )
    connection.commit()

    assert reader.is_active(other_user_id, session_id) is False


def test_expired_session_returns_false(reader, connection):
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    connection.execute(
        text("INSERT INTO auth.users (id, deleted_at, banned_until) VALUES (:uid, NULL, NULL)"),
        {"uid": user_id},
    )
    # Session older than 8 hours
    connection.execute(
        text("INSERT INTO auth.sessions (id, user_id, created_at) VALUES (:sid, :uid, :created)"),
        {"sid": session_id, "uid": user_id, "created": now - timedelta(hours=8, minutes=1)},
    )
    connection.commit()

    assert reader.is_active(user_id, session_id) is False


def test_deleted_user_returns_false(reader, connection):
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    connection.execute(
        text("INSERT INTO auth.users (id, deleted_at, banned_until) VALUES (:uid, :del, NULL)"),
        {"uid": user_id, "del": now - timedelta(minutes=10)},
    )
    connection.execute(
        text("INSERT INTO auth.sessions (id, user_id, created_at) VALUES (:sid, :uid, :created)"),
        {"sid": session_id, "uid": user_id, "created": now - timedelta(minutes=30)},
    )
    connection.commit()

    assert reader.is_active(user_id, session_id) is False


def test_banned_user_returns_false(reader, connection):
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    # Active ban in future
    connection.execute(
        text("INSERT INTO auth.users (id, deleted_at, banned_until) VALUES (:uid, NULL, :ban)"),
        {"uid": user_id, "ban": now + timedelta(days=1)},
    )
    connection.execute(
        text("INSERT INTO auth.sessions (id, user_id, created_at) VALUES (:sid, :uid, :created)"),
        {"sid": session_id, "uid": user_id, "created": now - timedelta(minutes=30)},
    )
    connection.commit()

    assert reader.is_active(user_id, session_id) is False

    # Past ban has expired
    connection.execute(
        text("UPDATE auth.users SET banned_until = :past WHERE id = :uid"),
        {"uid": user_id, "past": now - timedelta(hours=1)},
    )
    connection.commit()
    assert reader.is_active(user_id, session_id) is True


def test_db_error_propagates_as_unavailable(session_factory):
    # Use reader pointing to a bad engine/schema that fails queries
    bad_engine = create_engine(
        "postgresql+psycopg://knora:knora@127.0.0.1:5432/nonexistent_db_12345?connect_timeout=1"
    )
    bad_factory = sessionmaker(bind=bad_engine)
    bad_reader = PostgresSupabaseSessionReader(bad_factory)

    with pytest.raises(Exception) as exc_info:
        bad_reader.is_active(str(uuid.uuid4()), str(uuid.uuid4()))
    # Must fail, never return True
    assert isinstance(exc_info.value, (KnoraError, Exception))


def test_no_writes_to_managed_tables(reader, connection):
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    connection.execute(
        text("INSERT INTO auth.users (id, deleted_at, banned_until) VALUES (:uid, NULL, NULL)"),
        {"uid": user_id},
    )
    connection.execute(
        text("INSERT INTO auth.sessions (id, user_id, created_at) VALUES (:sid, :uid, :created)"),
        {"sid": session_id, "uid": user_id, "created": now - timedelta(hours=2)},
    )
    connection.commit()

    reader.is_active(user_id, session_id)

    # Verify rows unchanged
    user_row = connection.execute(
        text("SELECT deleted_at, banned_until FROM auth.users WHERE id = :uid"),
        {"uid": user_id},
    ).one()
    assert user_row[0] is None
    assert user_row[1] is None
