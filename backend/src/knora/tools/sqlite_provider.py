from __future__ import annotations

import sqlite3
from pathlib import Path

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
