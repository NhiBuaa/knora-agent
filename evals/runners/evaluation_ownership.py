"""Durable cross-process ownership for the M3 evaluation control plane."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalise_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _encode_time(value: datetime) -> str:
    return _normalise_time(value).isoformat()


def _decode_time(value: str | None) -> datetime | None:
    return None if value is None else _normalise_time(datetime.fromisoformat(value))


class EvaluationOwnershipError(ValueError):
    """A durable ownership operation was rejected at its linearization point."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class EvaluationOwnershipCapability:
    """The owner/fencing capability required for every sealed-run mutation."""

    run_id: str
    owner_id: str
    fencing_version: int
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationOwnershipSnapshot:
    """Durable owner state used for observable acceptance evidence."""

    run_id: str
    owner_id: str | None
    fencing_version: int
    lease_expires_at: datetime | None


class EvaluationOwnershipStore(Protocol):
    def acquire(
        self, *, run_id: str, owner_id: str, lease_duration: timedelta
    ) -> EvaluationOwnershipCapability: ...

    def assert_current(self, capability: EvaluationOwnershipCapability) -> None: ...

    def renew(
        self, capability: EvaluationOwnershipCapability, *, lease_duration: timedelta
    ) -> EvaluationOwnershipCapability: ...

    def release(self, capability: EvaluationOwnershipCapability) -> None: ...

    def snapshot(self, *, run_id: str) -> EvaluationOwnershipSnapshot: ...


class SqliteEvaluationOwnershipStore:
    """A durable SQLite lease shared by independent M3 worker/process contexts.

    SQLite's write transaction serializes acquisition/release decisions. The persisted fencing
    version is retained after release and incremented on every new acquisition, including recovery
    after expiry. No process-local flag is used as an ownership guarantee.
    """

    def __init__(
        self,
        *,
        path: str | Path,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if str(path) == ":memory:":
            raise ValueError("evaluation ownership requires a shared durable path")
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._initialise()

    def acquire(
        self, *, run_id: str, owner_id: str, lease_duration: timedelta
    ) -> EvaluationOwnershipCapability:
        if not run_id or not owner_id or lease_duration <= timedelta(0):
            raise EvaluationOwnershipError("EVALUATION_SEAL_ACQUIRE_FAILED")
        now = _normalise_time(self._clock())
        expires_at = now + lease_duration
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT owner_id, fencing_version, lease_expires_at
                FROM evaluation_ownership
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is not None:
                current_owner, fencing_version, raw_expiry = row
                current_expiry = _decode_time(raw_expiry)
                if (
                    current_owner is not None
                    and current_expiry is not None
                    and current_expiry > now
                ):
                    raise EvaluationOwnershipError("EVALUATION_SEAL_ACQUIRE_FAILED")
                next_version = int(fencing_version) + 1
                connection.execute(
                    """
                    UPDATE evaluation_ownership
                    SET owner_id = ?, fencing_version = ?, lease_expires_at = ?, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (owner_id, next_version, _encode_time(expires_at), _encode_time(now), run_id),
                )
            else:
                next_version = 1
                connection.execute(
                    """
                    INSERT INTO evaluation_ownership
                        (run_id, owner_id, fencing_version, lease_expires_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, owner_id, next_version, _encode_time(expires_at), _encode_time(now)),
                )
        return EvaluationOwnershipCapability(run_id, owner_id, next_version, expires_at)

    def assert_current(self, capability: EvaluationOwnershipCapability) -> None:
        now = _normalise_time(self._clock())
        with self._transaction() as connection:
            row = self._row(connection, capability.run_id)
            if not self._matches(row, capability, now):
                raise EvaluationOwnershipError("EVALUATION_SEAL_FENCED")

    def renew(
        self, capability: EvaluationOwnershipCapability, *, lease_duration: timedelta
    ) -> EvaluationOwnershipCapability:
        if lease_duration <= timedelta(0):
            raise EvaluationOwnershipError("EVALUATION_SEAL_RENEW_FAILED")
        now = _normalise_time(self._clock())
        expires_at = now + lease_duration
        with self._transaction() as connection:
            row = self._row(connection, capability.run_id)
            if not self._matches(row, capability, now):
                raise EvaluationOwnershipError("EVALUATION_SEAL_FENCED")
            connection.execute(
                """
                UPDATE evaluation_ownership
                SET lease_expires_at = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (_encode_time(expires_at), _encode_time(now), capability.run_id),
            )
        return EvaluationOwnershipCapability(
            capability.run_id,
            capability.owner_id,
            capability.fencing_version,
            expires_at,
        )

    def release(self, capability: EvaluationOwnershipCapability) -> None:
        now = _normalise_time(self._clock())
        with self._transaction() as connection:
            row = self._row(connection, capability.run_id)
            if not self._matches(row, capability, now):
                raise EvaluationOwnershipError("EVALUATION_SEAL_FENCED")
            connection.execute(
                """
                UPDATE evaluation_ownership
                SET owner_id = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE run_id = ?
                """,
                (_encode_time(now), capability.run_id),
            )

    def snapshot(self, *, run_id: str) -> EvaluationOwnershipSnapshot:
        with self._connection() as connection:
            row = self._row(connection, run_id)
        if row is None:
            raise EvaluationOwnershipError("EVALUATION_SEAL_NOT_FOUND")
        return EvaluationOwnershipSnapshot(
            run_id=run_id,
            owner_id=row[0],
            fencing_version=int(row[1]),
            lease_expires_at=_decode_time(row[2]),
        )

    def _initialise(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_ownership (
                    run_id TEXT PRIMARY KEY,
                    owner_id TEXT,
                    fencing_version INTEGER NOT NULL,
                    lease_expires_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._path), timeout=5, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _transaction(self):
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")

        class Transaction:
            def __enter__(_self):
                return connection

            def __exit__(_self, exception_type, exception, traceback):
                try:
                    connection.execute("ROLLBACK" if exception_type else "COMMIT")
                finally:
                    connection.close()
                return False

        return Transaction()

    @staticmethod
    def _row(connection: sqlite3.Connection, run_id: str):
        return connection.execute(
            """
            SELECT owner_id, fencing_version, lease_expires_at
            FROM evaluation_ownership
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

    @staticmethod
    def _matches(
        row: tuple[object, ...] | None,
        capability: EvaluationOwnershipCapability,
        now: datetime,
    ) -> bool:
        if row is None:
            return False
        owner_id, fencing_version, raw_expiry = row
        expiry = _decode_time(raw_expiry)
        return (
            owner_id == capability.owner_id
            and int(fencing_version) == capability.fencing_version
            and expiry is not None
            and expiry > now
        )
