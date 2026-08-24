from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

from knora.tools.contracts import format_timestamp, parse_timestamp
from knora.tools.references import ReferenceRecord


class SQLiteReferenceProvider:
    """Independent reference/provider state boundary for deterministic release evidence."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS tool_references ("
            "reference_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, "
            "capability_id TEXT NOT NULL, capability_version TEXT NOT NULL, "
            "binding_id TEXT NOT NULL, binding_version TEXT NOT NULL, "
            "binding_digest TEXT NOT NULL, resource_kind TEXT NOT NULL, "
            "resource_identity_digest TEXT NOT NULL, resource_claims_digest TEXT NOT NULL, "
            "provider_routing_handle TEXT NOT NULL UNIQUE, provider_resource_id TEXT NOT NULL, "
            "issued_at TEXT NOT NULL, expires_at TEXT NOT NULL, key_version TEXT NOT NULL)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS tickets ("
            "scope TEXT NOT NULL, provider_resource_id TEXT NOT NULL, title TEXT NOT NULL, "
            "status TEXT NOT NULL, summary TEXT NOT NULL, PRIMARY KEY(scope, provider_resource_id))"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS provider_idempotency ("
            "logical_execution_id TEXT PRIMARY KEY, scope TEXT NOT NULL, "
            "request_fingerprint TEXT NOT NULL, admission_digest TEXT NOT NULL, "
            "outcome_type TEXT NOT NULL, outcome_value TEXT NOT NULL)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS provider_created_tickets ("
            "logical_execution_id TEXT PRIMARY KEY, scope TEXT NOT NULL, "
            "target_provider_resource_id TEXT NOT NULL, provider_ticket_id TEXT NOT NULL UNIQUE, "
            "external_resource_reference TEXT NOT NULL UNIQUE, title TEXT NOT NULL, "
            "description TEXT NOT NULL)"
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def register_reference(self, record: ReferenceRecord, *, provider_resource_id: str) -> None:
        if not provider_resource_id:
            raise ValueError("provider_resource_id is required")
        values = (
            record.reference_id,
            record.workspace_id,
            record.capability_id,
            record.capability_version,
            record.binding_id,
            record.binding_version,
            record.binding_digest,
            record.resource_kind,
            record.resource_identity_digest,
            record.resource_claims_digest,
            record.provider_routing_handle,
            provider_resource_id,
            format_timestamp(record.issued_at),
            format_timestamp(record.expires_at),
            record.key_version,
        )
        inserted = self._connection.execute(
            "INSERT OR IGNORE INTO tool_references VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
        )
        if inserted.rowcount == 0:
            current = self._connection.execute(
                "SELECT reference_id, workspace_id, capability_id, capability_version, "
                "binding_id, binding_version, binding_digest, resource_kind, "
                "resource_identity_digest, resource_claims_digest, provider_routing_handle, "
                "provider_resource_id, issued_at, expires_at, key_version "
                "FROM tool_references WHERE reference_id = ?",
                (record.reference_id,),
            ).fetchone()
            if current != values:
                self._connection.rollback()
                raise ValueError("reference identity conflict")
        self._connection.commit()

    register = register_reference

    def get_reference(self, reference_id: str) -> ReferenceRecord | None:
        row = self._connection.execute(
            "SELECT reference_id, workspace_id, capability_id, capability_version, binding_id, "
            "binding_version, binding_digest, resource_kind, resource_identity_digest, "
            "resource_claims_digest, provider_routing_handle, issued_at, expires_at, key_version "
            "FROM tool_references WHERE reference_id = ?",
            (reference_id,),
        ).fetchone()
        if row is None:
            return None
        return ReferenceRecord(
            reference_id=row[0],
            workspace_id=row[1],
            capability_id=row[2],
            capability_version=row[3],
            binding_id=row[4],
            binding_version=row[5],
            binding_digest=row[6],
            resource_kind=row[7],
            resource_identity_digest=row[8],
            resource_claims_digest=row[9],
            provider_routing_handle=row[10],
            issued_at=parse_timestamp(row[11], "issued_at"),
            expires_at=parse_timestamp(row[12], "expires_at"),
            key_version=row[13],
        )

    def register_ticket(
        self, *, scope: str, provider_resource_id: str, title: str, status: str, summary: str
    ) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO tickets VALUES (?, ?, ?, ?, ?)",
            (scope, provider_resource_id, title, status, summary),
        )
        self._connection.commit()

    def lookup_ticket(
        self, *, scope: str, provider_routing_handle: str
    ) -> tuple[object, object, object] | None:
        row = self._connection.execute(
            "SELECT tickets.title, tickets.status, tickets.summary "
            "FROM tool_references JOIN tickets "
            "ON tickets.provider_resource_id = tool_references.provider_resource_id "
            "WHERE tool_references.provider_routing_handle = ? AND tickets.scope = ?",
            (provider_routing_handle, scope),
        ).fetchone()
        return None if row is None else (row[0], row[1], row[2])

    def create_ticket(
        self,
        *,
        scope: str,
        provider_routing_handle: str,
        logical_execution_id: str,
        request_fingerprint: str,
        admission_digest: str,
        title: str,
        description: str,
        external_resource_reference: str,
        forced_rejection: str | None = None,
    ) -> tuple[str, str]:
        """Commit one effect or closed rejection with its idempotency row."""
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self._connection.execute(
                "SELECT request_fingerprint, outcome_type, outcome_value "
                "FROM provider_idempotency WHERE logical_execution_id = ?",
                (logical_execution_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] != request_fingerprint:
                    self._connection.rollback()
                    return ("conflict", "provider_idempotency_conflict")
                self._connection.commit()
                return (existing[1], existing[2])
            target = self._connection.execute(
                "SELECT tool_references.provider_resource_id FROM tool_references "
                "JOIN tickets ON tickets.provider_resource_id = "
                "tool_references.provider_resource_id "
                "WHERE tool_references.provider_routing_handle = ? AND tickets.scope = ?",
                (provider_routing_handle, scope),
            ).fetchone()
            rejection = forced_rejection
            if target is None:
                rejection = "target_not_found"
            if rejection is not None:
                if rejection not in {
                    "target_not_found",
                    "validation_rejected",
                    "policy_rejected",
                }:
                    raise ValueError("unsupported provider rejection")
                self._connection.execute(
                    "INSERT INTO provider_idempotency VALUES (?, ?, ?, ?, 'failed', ?)",
                    (
                        logical_execution_id,
                        scope,
                        request_fingerprint,
                        admission_digest,
                        rejection,
                    ),
                )
                self._connection.commit()
                return ("failed", rejection)
            provider_ticket_id = str(uuid4())
            self._connection.execute(
                "INSERT INTO provider_created_tickets VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    logical_execution_id,
                    scope,
                    target[0],
                    provider_ticket_id,
                    external_resource_reference,
                    title,
                    description,
                ),
            )
            self._connection.execute(
                "INSERT INTO provider_idempotency VALUES (?, ?, ?, ?, 'succeeded', ?)",
                (
                    logical_execution_id,
                    scope,
                    request_fingerprint,
                    admission_digest,
                    external_resource_reference,
                ),
            )
            self._connection.commit()
            return ("succeeded", external_resource_reference)
        except Exception:
            self._connection.rollback()
            raise

    def authorize_write_target(self, *, scope: str, provider_routing_handle: str) -> str:
        record = self._connection.execute(
            "SELECT provider_resource_id FROM tool_references WHERE provider_routing_handle = ?",
            (provider_routing_handle,),
        ).fetchone()
        if record is None:
            return "target_not_found"
        scoped = self._connection.execute(
            "SELECT 1 FROM tickets WHERE provider_resource_id = ? AND scope = ?",
            (record[0], scope),
        ).fetchone()
        return "authorized" if scoped is not None else "scope_denied"

    def get_execution_outcome(
        self, *, scope: str, logical_execution_id: str
    ) -> tuple[str, str] | None:
        row = self._connection.execute(
            "SELECT outcome_type, outcome_value FROM provider_idempotency "
            "WHERE logical_execution_id = ? AND scope = ?",
            (logical_execution_id, scope),
        ).fetchone()
        return None if row is None else (row[0], row[1])

    def provider_effect_count(self, logical_execution_id: str | None = None) -> int:
        if logical_execution_id is None:
            row = self._connection.execute(
                "SELECT count(*) FROM provider_created_tickets"
            ).fetchone()
        else:
            row = self._connection.execute(
                "SELECT count(*) FROM provider_created_tickets WHERE logical_execution_id = ?",
                (logical_execution_id,),
            ).fetchone()
        assert row is not None
        return int(row[0])
