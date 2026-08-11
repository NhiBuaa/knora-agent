from contextlib import contextmanager
from datetime import UTC, datetime

from knora.adapters.postgres.object_reconciliation import (
    PostgresClock,
    PostgresObjectReferenceResolver,
)


class FakeSession:
    def __init__(self, values):
        self.values = iter(values)

    def scalar(self, statement):
        del statement
        return next(self.values)

    def scalars(self, statement):
        del statement
        return self

    def all(self):
        return list(next(self.values))


class FakeSessionFactory:
    def __init__(self, values):
        self.values = values

    @contextmanager
    def __call__(self):
        yield FakeSession(self.values)


class FailingSessionFactory:
    @contextmanager
    def __call__(self):
        raise RuntimeError("database unavailable")
        yield  # pragma: no cover


def test_postgres_clock_reads_authoritative_database_time() -> None:
    expected = datetime(2026, 1, 1, tzinfo=UTC)
    assert PostgresClock(FakeSessionFactory([expected])).now() == expected


def test_reference_resolver_is_workspace_scoped() -> None:
    retained = PostgresObjectReferenceResolver(FakeSessionFactory(["source-id"]))
    unretained = PostgresObjectReferenceResolver(FakeSessionFactory([None]))

    assert retained.is_authoritatively_retained(workspace_id="w1", object_key="k1")
    assert not unretained.is_authoritatively_retained(workspace_id="w1", object_key="k1")


def test_reference_resolver_honors_durable_failed_upload_retention_work() -> None:
    diagnostic_work = PostgresObjectReferenceResolver(FakeSessionFactory(["diagnostic-work"]))

    assert diagnostic_work.is_authoritatively_retained(workspace_id="w1", object_key="k1")


def test_reference_resolver_reports_only_database_records_missing_from_inventory() -> None:
    resolver = PostgresObjectReferenceResolver(FakeSessionFactory([["k2", "k1", "k2"]]))

    assert resolver.inconsistent_object_keys(
        workspace_id="w1", observed_object_keys={"k1", "k3"}
    ) == ("k2",)


def test_reference_resolver_fails_closed_on_unexpected_authoritative_read_error() -> None:
    resolver = PostgresObjectReferenceResolver(FailingSessionFactory())

    assert resolver.is_authoritatively_retained(workspace_id="w1", object_key="k1")
    assert resolver.inconsistent_object_keys(
        workspace_id="w1", observed_object_keys=set()
    ) == ()
