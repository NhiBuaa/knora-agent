import concurrent.futures
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from knora.access.identity_access import BASELINE_CAPABILITIES
from knora.adapters.postgres.identity_access_store import PostgresIdentityAccessStore
from knora.infrastructure.settings import settings


@pytest.fixture(scope="module")
def disposable_db():
    assert settings.database_url, "KNORA_DATABASE_URL must be configured"
    base_url = make_url(settings.database_url)
    assert base_url.get_backend_name() == "postgresql", "Test database must be PostgreSQL"

    db_name = f"knora_test_id_{uuid.uuid4().hex[:12]}"
    assert db_name.startswith("knora_test_"), "Disposable database must have knora_test_ prefix"

    admin_url = base_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    # Verify admin connection before running DDL
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    target_url = base_url.set(database=db_name)
    engine = create_engine(target_url, pool_pre_ping=True)

    try:
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
    finally:
        engine.dispose()
        # Clean up only disposable DB owned by this test run
        if db_name.startswith("knora_test_"):
            with admin_engine.connect() as conn:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": db_name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
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


def test_db_error_raises_auth_provider_unavailable():
    from knora.domain.errors import KnoraError

    broken_url = make_url(settings.database_url).set(
        password="wrong_password",
        database="nonexistent_db_12345",
        query={"connect_timeout": "1"},
    )
    broken_engine = create_engine(broken_url)
    broken_factory = sessionmaker(bind=broken_engine)
    broken_store = PostgresIdentityAccessStore(broken_factory)
    with pytest.raises(KnoraError) as exc:
        broken_store.get_or_create_baseline("https://demo.supabase.co/auth/v1", "user-1")
    assert exc.value.code == "AUTH_PROVIDER_UNAVAILABLE"
