import concurrent.futures
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from knora.access.identity_access import BASELINE_CAPABILITIES
from knora.adapters.postgres.identity_access_store import PostgresIdentityAccessStore


@pytest.fixture(scope="module")
def disposable_db():
    db_name = f"knora_test_id_{uuid.uuid4().hex[:12]}"
    admin_url = "postgresql+psycopg://knora:knora@127.0.0.1:5432/postgres?connect_timeout=3"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}" OWNER knora;'))

    target_url = f"postgresql+psycopg://knora:knora@127.0.0.1:5432/{db_name}?connect_timeout=3"
    engine = create_engine(target_url, pool_pre_ping=True)

    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE identity_access (
                issuer VARCHAR(500) NOT NULL,
                subject VARCHAR(255) NOT NULL,
                capabilities JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT pk_identity_access PRIMARY KEY (issuer, subject)
            );
            ALTER TABLE identity_access ENABLE ROW LEVEL SECURITY;
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
def store(session_factory):
    return PostgresIdentityAccessStore(session_factory)


@pytest.fixture
def connection(disposable_db):
    conn = disposable_db.connect()
    yield conn
    conn.close()


def test_first_access_grants_baseline(store):
    issuer = "https://demo.supabase.co/auth/v1"
    subject = f"user-{uuid.uuid4()}"
    grants = store.get_or_create_baseline(issuer, subject)
    assert set(grants) == set(BASELINE_CAPABILITIES)
    assert set(grants) == {"documents:read", "documents:write", "questions:ask"}


def test_existing_empty_grant_is_not_reenrolled(store, connection):
    issuer, subject = "https://demo.supabase.co/auth/v1", f"test-user-{uuid.uuid4()}"
    assert set(store.get_or_create_baseline(issuer, subject)) == {
        "documents:read",
        "documents:write",
        "questions:ask",
    }
    connection.execute(
        text(
            "UPDATE identity_access SET capabilities = '[]'::jsonb "
            "WHERE issuer = :issuer AND subject = :subject"
        ),
        {"issuer": issuer, "subject": subject},
    )
    connection.commit()
    assert store.get_or_create_baseline(issuer, subject) == ()


def test_existing_changed_grant_is_retained(store, connection):
    issuer, subject = "https://demo.supabase.co/auth/v1", f"test-user-{uuid.uuid4()}"
    store.get_or_create_baseline(issuer, subject)
    connection.execute(
        text(
            "UPDATE identity_access SET capabilities = '[\"documents:read\"]'::jsonb "
            "WHERE issuer = :issuer AND subject = :subject"
        ),
        {"issuer": issuer, "subject": subject},
    )
    connection.commit()
    assert store.get_or_create_baseline(issuer, subject) == ("documents:read",)


def test_concurrent_enrollments_create_one_row(session_factory, connection):
    issuer = "https://demo.supabase.co/auth/v1"
    subject = f"concurrent-user-{uuid.uuid4()}"

    def enroll():
        s = PostgresIdentityAccessStore(session_factory)
        return s.get_or_create_baseline(issuer, subject)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: enroll(), range(10)))

    for res in results:
        assert set(res) == set(BASELINE_CAPABILITIES)

    row_count = connection.execute(
        text("SELECT COUNT(*) FROM identity_access WHERE issuer = :issuer AND subject = :subject"),
        {"issuer": issuer, "subject": subject},
    ).scalar()
    assert row_count == 1
