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


_NO_REPLAY = object()


class EvaluationOwnershipStore(Protocol):
    def acquire(
        self, *, run_id: str, owner_id: str, lease_duration: timedelta, operation_id: str
    ) -> EvaluationOwnershipCapability: ...

    def assert_current(self, capability: EvaluationOwnershipCapability) -> None: ...

    def renew(
        self,
        capability: EvaluationOwnershipCapability,
        *,
        lease_duration: timedelta,
        operation_id: str,
    ) -> EvaluationOwnershipCapability: ...

    def release(self, capability: EvaluationOwnershipCapability, *, operation_id: str) -> None: ...

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
        self, *, run_id: str, owner_id: str, lease_duration: timedelta, operation_id: str
    ) -> EvaluationOwnershipCapability:
        self._validate_operation_id(operation_id)
        now = _normalise_time(self._clock())
        expires_at = now + max(lease_duration, timedelta(0))
        capability: EvaluationOwnershipCapability | None = None
        error_code: str | None = None
        with self._transaction() as connection:
            replay = self._replay(
                connection,
                operation_id=operation_id,
                operation="acquire",
                run_id=run_id,
                owner_id=owner_id,
                fencing_version=None,
                lease_duration=lease_duration,
            )
            if replay is not _NO_REPLAY:
                replayed = self._capability_from_operation(replay, run_id, owner_id)
                if not self._matches(self._row(connection, run_id), replayed, now):
                    raise EvaluationOwnershipError("EVALUATION_SEAL_FENCED")
                return replayed
            if not run_id or not owner_id or lease_duration <= timedelta(0):
                error_code = "EVALUATION_SEAL_ACQUIRE_FAILED"
            row = connection.execute(
                """
                SELECT owner_id, fencing_version, lease_expires_at
                FROM evaluation_ownership
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if error_code is None and row is not None:
                current_owner, fencing_version, raw_expiry = row
                current_expiry = _decode_time(raw_expiry)
                if (
                    current_owner is not None
                    and current_expiry is not None
                    and current_expiry > now
                ):
                    error_code = "EVALUATION_SEAL_ACQUIRE_FAILED"
                else:
                    next_version = int(fencing_version) + 1
                    connection.execute(
                        """
                        UPDATE evaluation_ownership
                        SET owner_id = ?, fencing_version = ?, lease_expires_at = ?, updated_at = ?
                        WHERE run_id = ?
                        """,
                        (
                            owner_id,
                            next_version,
                            _encode_time(expires_at),
                            _encode_time(now),
                            run_id,
                        ),
                    )
            elif error_code is None:
                next_version = 1
                connection.execute(
                    """
                    INSERT INTO evaluation_ownership
                        (run_id, owner_id, fencing_version, lease_expires_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, owner_id, next_version, _encode_time(expires_at), _encode_time(now)),
                )
            if error_code is None:
                capability = EvaluationOwnershipCapability(
                    run_id, owner_id, next_version, expires_at
                )
            self._record_operation(
                connection,
                operation_id=operation_id,
                operation="acquire",
                run_id=run_id,
                owner_id=owner_id,
                fencing_version=capability.fencing_version if capability else None,
                lease_expires_at=capability.lease_expires_at if capability else None,
                lease_duration=lease_duration,
                result_code=error_code or "OK",
                recorded_at=now,
            )
        if error_code is not None:
            raise EvaluationOwnershipError(error_code)
        assert capability is not None
        return capability

    def assert_current(self, capability: EvaluationOwnershipCapability) -> None:
        now = _normalise_time(self._clock())
        with self._transaction() as connection:
            row = self._row(connection, capability.run_id)
            if not self._matches(row, capability, now):
                raise EvaluationOwnershipError("EVALUATION_SEAL_FENCED")

    def renew(
        self,
        capability: EvaluationOwnershipCapability,
        *,
        lease_duration: timedelta,
        operation_id: str,
    ) -> EvaluationOwnershipCapability:
        self._validate_operation_id(operation_id)
        now = _normalise_time(self._clock())
        expires_at = now + max(lease_duration, timedelta(0))
        renewed: EvaluationOwnershipCapability | None = None
        error_code: str | None = None
        with self._transaction() as connection:
            replay = self._replay(
                connection,
                operation_id=operation_id,
                operation="renew",
                run_id=capability.run_id,
                owner_id=capability.owner_id,
                fencing_version=capability.fencing_version,
                lease_duration=lease_duration,
            )
            if replay is not _NO_REPLAY:
                replayed = self._capability_from_operation(
                    replay, capability.run_id, capability.owner_id
                )
                if not self._matches(
                    self._row(connection, capability.run_id), replayed, now
                ):
                    raise EvaluationOwnershipError("EVALUATION_SEAL_FENCED")
                return replayed
            if lease_duration <= timedelta(0):
                error_code = "EVALUATION_SEAL_RENEW_FAILED"
            row = self._row(connection, capability.run_id)
            if error_code is None and not self._matches(row, capability, now):
                error_code = "EVALUATION_SEAL_FENCED"
            if error_code is None:
                connection.execute(
                    """
                    UPDATE evaluation_ownership
                    SET lease_expires_at = ?, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (_encode_time(expires_at), _encode_time(now), capability.run_id),
                )
                renewed = EvaluationOwnershipCapability(
                    capability.run_id,
                    capability.owner_id,
                    capability.fencing_version,
                    expires_at,
                )
            self._record_operation(
                connection,
                operation_id=operation_id,
                operation="renew",
                run_id=capability.run_id,
                owner_id=capability.owner_id,
                fencing_version=capability.fencing_version,
                lease_expires_at=renewed.lease_expires_at if renewed else None,
                lease_duration=lease_duration,
                result_code=error_code or "OK",
                recorded_at=now,
            )
        if error_code is not None:
            raise EvaluationOwnershipError(error_code)
        assert renewed is not None
        return renewed

    def release(self, capability: EvaluationOwnershipCapability, *, operation_id: str) -> None:
        self._validate_operation_id(operation_id)
        now = _normalise_time(self._clock())
        error_code: str | None = None
        with self._transaction() as connection:
            replay = self._replay(
                connection,
                operation_id=operation_id,
                operation="release",
                run_id=capability.run_id,
                owner_id=capability.owner_id,
                fencing_version=capability.fencing_version,
                lease_duration=None,
            )
            if replay is not _NO_REPLAY:
                return None
            row = self._row(connection, capability.run_id)
            if not self._matches(row, capability, now):
                error_code = "EVALUATION_SEAL_FENCED"
            else:
                connection.execute(
                    """
                    UPDATE evaluation_ownership
                    SET owner_id = NULL, lease_expires_at = NULL, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (_encode_time(now), capability.run_id),
                )
            self._record_operation(
                connection,
                operation_id=operation_id,
                operation="release",
                run_id=capability.run_id,
                owner_id=capability.owner_id,
                fencing_version=capability.fencing_version,
                lease_expires_at=None,
                lease_duration=None,
                result_code=error_code or "OK",
                recorded_at=now,
            )
        if error_code is not None:
            raise EvaluationOwnershipError(error_code)

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_ownership_operations (
                    operation_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    fencing_version INTEGER,
                    lease_expires_at TEXT,
                    lease_duration_seconds REAL,
                    result_code TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _validate_operation_id(operation_id: str) -> None:
        if not isinstance(operation_id, str) or not operation_id:
            raise EvaluationOwnershipError("EVALUATION_OPERATION_INVALID")

    @staticmethod
    def _operation_row(connection: sqlite3.Connection, operation_id: str):
        return connection.execute(
            """
            SELECT operation_id, operation, run_id, owner_id, fencing_version,
                   lease_expires_at, lease_duration_seconds, result_code, recorded_at
            FROM evaluation_ownership_operations
            WHERE operation_id = ?
            """,
            (operation_id,),
        ).fetchone()

    def _replay(
        self,
        connection: sqlite3.Connection,
        *,
        operation_id: str,
        operation: str,
        run_id: str,
        owner_id: str,
        fencing_version: int | None,
        lease_duration: timedelta | None,
    ):
        row = self._operation_row(connection, operation_id)
        if row is None:
            return _NO_REPLAY
        stored_duration = row[6]
        requested_duration = (
            lease_duration.total_seconds() if lease_duration is not None else None
        )
        if (
            row[1] != operation
            or row[2] != run_id
            or row[3] != owner_id
            or (fencing_version is not None and row[4] != fencing_version)
            or stored_duration != requested_duration
        ):
            raise EvaluationOwnershipError("EVALUATION_OPERATION_REPLAY_MISMATCH")
        if row[7] != "OK":
            raise EvaluationOwnershipError(str(row[7]))
        return row

    @staticmethod
    def _capability_from_operation(
        row: tuple[object, ...], run_id: str, owner_id: str
    ) -> EvaluationOwnershipCapability:
        fencing_version = row[4]
        lease_expires_at = _decode_time(row[5])
        if fencing_version is None or lease_expires_at is None:
            raise EvaluationOwnershipError("EVALUATION_OPERATION_RESULT_INVALID")
        return EvaluationOwnershipCapability(
            run_id, owner_id, int(fencing_version), lease_expires_at
        )

    @staticmethod
    def _record_operation(
        connection: sqlite3.Connection,
        *,
        operation_id: str,
        operation: str,
        run_id: str,
        owner_id: str,
        fencing_version: int | None,
        lease_expires_at: datetime | None,
        lease_duration: timedelta | None,
        result_code: str,
        recorded_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO evaluation_ownership_operations
                (operation_id, operation, run_id, owner_id, fencing_version,
                 lease_expires_at, lease_duration_seconds, result_code, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                operation_id,
                operation,
                run_id,
                owner_id,
                fencing_version,
                _encode_time(lease_expires_at) if lease_expires_at is not None else None,
                lease_duration.total_seconds() if lease_duration is not None else None,
                result_code,
                _encode_time(recorded_at),
            ),
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
