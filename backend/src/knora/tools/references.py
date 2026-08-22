from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from knora.domain.errors import KnoraError


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    if not value or any(character not in alphabet for character in value):
        raise ValueError("invalid base64url")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


@dataclass(frozen=True, slots=True)
class ReferenceKey:
    version: str
    secret: bytes
    status: str = "active"

    def __post_init__(self) -> None:
        if not self.version or not self.secret:
            raise ValueError("reference key must have a version and secret")
        if self.status not in {"active", "retiring", "revoked"}:
            raise ValueError("unsupported reference key status")


@dataclass(frozen=True, slots=True)
class ReferenceRecord:
    reference_id: str
    workspace_id: str
    capability_id: str
    capability_version: str
    binding_id: str
    binding_version: str
    binding_digest: str
    resource_kind: str
    resource_claims: Mapping[str, str]
    provider_resource_id: str
    expires_at: float
    key_version: str


@dataclass(frozen=True, slots=True)
class AuthorizedExternalResource:
    """Internal provider-bound resource; never returned by a public tool result."""

    reference_id: str
    resource_kind: str
    provider_resource_id: str
    resource_claims: Mapping[str, str]
    external_scope: str


@dataclass(frozen=True, slots=True)
class VerifiedResourceReference:
    workspace_id: str
    capability_id: str
    capability_version: str
    binding_id: str
    binding_version: str
    binding_digest: str
    resource_kind: str
    reference_id: str
    authorized_resource: AuthorizedExternalResource


class ReferenceStore(Protocol):
    def get_reference(self, reference_id: str) -> ReferenceRecord | None: ...


class InMemoryReferenceStore:
    def __init__(self, records: tuple[ReferenceRecord, ...] = ()) -> None:
        self._records = {record.reference_id: record for record in records}

    def register(self, record: ReferenceRecord) -> None:
        self._records[record.reference_id] = record

    def get_reference(self, reference_id: str) -> ReferenceRecord | None:
        return self._records.get(reference_id)


class ExternalResourceReference:
    """Opaque m4r1 envelope.  Callers can carry the token but cannot inspect protected claims."""

    __slots__ = ("_token",)

    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or not token:
            raise ValueError("resource reference must be a non-empty string")
        self._token = token

    @property
    def token(self) -> str:
        return self._token

    def __str__(self) -> str:
        return self._token

    def __repr__(self) -> str:
        return "ExternalResourceReference(<opaque>)"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ExternalResourceReference) and hmac.compare_digest(
            self._token, other._token
        )

    def __hash__(self) -> int:
        return hash(self._token)

    @classmethod
    def mint(cls, record: ReferenceRecord, key: ReferenceKey) -> ExternalResourceReference:
        if record.key_version != key.version:
            raise ValueError("record and key versions differ")
        protected = {
            "binding_digest": record.binding_digest,
            "binding_id": record.binding_id,
            "binding_version": record.binding_version,
            "capability_id": record.capability_id,
            "capability_version": record.capability_version,
            "expires_at": record.expires_at,
            "key_version": record.key_version,
            "reference_id": record.reference_id,
            "resource_claims": dict(record.resource_claims),
            "resource_kind": record.resource_kind,
            "workspace_id": record.workspace_id,
        }
        payload = _b64encode(_canonical_json(protected))
        mac = _b64encode(
            hmac.new(
                key.secret, f"m4r1.{payload}".encode("ascii"), hashlib.sha256
            ).digest()
        )
        return cls(f"m4r1.{payload}.{mac}")

    @classmethod
    def from_token(cls, value: str) -> ExternalResourceReference:
        return cls(value)

    create = mint

    def verify(self, verifier: ReferenceVerifier) -> VerifiedResourceReference:
        return verifier.verify(self)


class ReferenceVerifier:
    def __init__(
        self,
        store: ReferenceStore,
        keys: Mapping[str, ReferenceKey],
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._store = store
        self._keys = dict(keys)
        self._clock = clock or time.time

    def verify(self, reference: str | ExternalResourceReference) -> VerifiedResourceReference:
        token = reference.token if isinstance(reference, ExternalResourceReference) else reference
        if not isinstance(token, str):
            raise ValueError("reference must be text")
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != "m4r1":
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        payload_encoded, mac_encoded = parts[1], parts[2]
        try:
            payload_bytes = _b64decode(payload_encoded)
            mac = _b64decode(mac_encoded)
        except ValueError as exc:
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE") from exc
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE") from exc
        if not isinstance(payload, dict):
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        required = {
            "binding_digest", "binding_id", "binding_version", "capability_id",
            "capability_version", "expires_at", "key_version", "reference_id",
            "resource_claims", "resource_kind", "workspace_id",
        }
        if set(payload) != required or not isinstance(payload["resource_claims"], dict):
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        key_version = payload["key_version"]
        if not all(
            isinstance(payload.get(name), str)
            for name in (
                "binding_digest",
                "binding_id",
                "binding_version",
                "capability_id",
                "capability_version",
                "key_version",
                "reference_id",
                "resource_kind",
                "workspace_id",
            )
        ) or not isinstance(payload["expires_at"], (int, float)):
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        if not isinstance(key_version, str):
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        key = self._keys.get(key_version)
        if key is None or key.status == "revoked":
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        expected = hmac.new(
            key.secret, f"m4r1.{payload_encoded}".encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, mac):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        try:
            expires_at = float(payload["expires_at"])
        except (TypeError, ValueError) as exc:
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE") from exc
        if expires_at <= self._clock():
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        record = self._store.get_reference(str(payload["reference_id"]))
        if record is None:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        expected_claims = {
            "binding_digest": record.binding_digest,
            "binding_id": record.binding_id,
            "binding_version": record.binding_version,
            "capability_id": record.capability_id,
            "capability_version": record.capability_version,
            "expires_at": record.expires_at,
            "key_version": record.key_version,
            "reference_id": record.reference_id,
            "resource_claims": dict(record.resource_claims),
            "resource_kind": record.resource_kind,
            "workspace_id": record.workspace_id,
        }
        if payload != expected_claims:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        return VerifiedResourceReference(
            workspace_id=record.workspace_id,
            capability_id=record.capability_id,
            capability_version=record.capability_version,
            binding_id=record.binding_id,
            binding_version=record.binding_version,
            binding_digest=record.binding_digest,
            resource_kind=record.resource_kind,
            reference_id=record.reference_id,
            authorized_resource=AuthorizedExternalResource(
                reference_id=record.reference_id,
                resource_kind=record.resource_kind,
                provider_resource_id=record.provider_resource_id,
                resource_claims=dict(record.resource_claims),
                external_scope=f"external-scope:{record.workspace_id}",
            ),
        )


class SQLiteReferenceProvider:
    """Independent deterministic reference/ticket ledger used by provider-boundary tests."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS tool_references ("
            "reference_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, "
            "capability_id TEXT NOT NULL, capability_version TEXT NOT NULL, "
            "binding_id TEXT NOT NULL, binding_version TEXT NOT NULL, "
            "binding_digest TEXT NOT NULL, resource_kind TEXT NOT NULL, "
            "resource_claims TEXT NOT NULL, provider_resource_id TEXT NOT NULL, "
            "expires_at REAL NOT NULL, key_version TEXT NOT NULL)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS tickets ("
            "scope TEXT NOT NULL, provider_resource_id TEXT NOT NULL, title TEXT NOT NULL,"
            "status TEXT NOT NULL, summary TEXT NOT NULL, PRIMARY KEY(scope, provider_resource_id))"
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def register(self, record: ReferenceRecord) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO tool_references VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.reference_id,
                record.workspace_id,
                record.capability_id,
                record.capability_version,
                record.binding_id,
                record.binding_version,
                record.binding_digest,
                record.resource_kind,
                json.dumps(dict(record.resource_claims), sort_keys=True),
                record.provider_resource_id,
                record.expires_at,
                record.key_version,
            ),
        )
        self._connection.commit()

    register_reference = register

    def get_reference(self, reference_id: str) -> ReferenceRecord | None:
        row = self._connection.execute(
            "SELECT reference_id, workspace_id, capability_id, capability_version, binding_id,"
            "binding_version, binding_digest, resource_kind, resource_claims, provider_resource_id,"
            "expires_at, key_version FROM tool_references WHERE reference_id = ?",
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
            resource_claims=json.loads(row[8]),
            provider_resource_id=row[9],
            expires_at=row[10],
            key_version=row[11],
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
        self, *, scope: str, provider_resource_id: str
    ) -> tuple[str, str, str] | None:
        row = self._connection.execute(
            "SELECT title, status, summary FROM tickets "
            "WHERE scope = ? AND provider_resource_id = ?",
            (scope, provider_resource_id),
        ).fetchone()
        return None if row is None else (row[0], row[1], row[2])
