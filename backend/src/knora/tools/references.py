from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from knora.domain.errors import KnoraError
from knora.tools.contracts import (
    canonical_json_v1,
    format_timestamp,
    parse_timestamp,
    require_digest,
)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    if not value or any(character not in alphabet for character in value):
        raise ValueError("invalid base64url")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _b64encode(decoded) != value:
        raise ValueError("non-canonical base64url")
    return decoded


def _validate_reference_id(value: str) -> None:
    try:
        decoded = _b64decode(value)
    except ValueError as exc:
        raise ValueError("reference_id must encode 256 bits") from exc
    if len(decoded) != 32:
        raise ValueError("reference_id must encode 256 bits")


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
class ReferenceKeyRing:
    keys: tuple[ReferenceKey, ...]

    def __post_init__(self) -> None:
        versions = [key.version for key in self.keys]
        if len(set(versions)) != len(versions):
            raise ValueError("reference key versions must be unique")
        if sum(key.status == "active" for key in self.keys) != 1:
            raise ValueError("reference key ring requires exactly one active key")

    @property
    def active_key(self) -> ReferenceKey:
        return next(key for key in self.keys if key.status == "active")

    def get(self, version: str) -> ReferenceKey | None:
        return next((key for key in self.keys if key.version == version), None)


@dataclass(frozen=True, slots=True)
class AuthorizedReferenceMintingResource:
    """Trusted current authorization consumed by the reference minter."""

    workspace_id: str
    capability_id: str
    capability_version: str
    binding_id: str
    binding_version: str
    binding_digest: str
    resource_kind: str
    resource_identity_digest: str
    resource_claims_digest: str
    provider_routing_handle: str

    def __post_init__(self) -> None:
        for field_name in (
            "workspace_id",
            "capability_id",
            "capability_version",
            "binding_id",
            "binding_version",
            "resource_kind",
            "provider_routing_handle",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        require_digest(self.binding_digest, "binding_digest")
        require_digest(self.resource_identity_digest, "resource_identity_digest")
        require_digest(self.resource_claims_digest, "resource_claims_digest")


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
    resource_identity_digest: str
    resource_claims_digest: str
    provider_routing_handle: str
    issued_at: datetime
    expires_at: datetime
    key_version: str

    def __post_init__(self) -> None:
        _validate_reference_id(self.reference_id)
        AuthorizedReferenceMintingResource(
            workspace_id=self.workspace_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            binding_id=self.binding_id,
            binding_version=self.binding_version,
            binding_digest=self.binding_digest,
            resource_kind=self.resource_kind,
            resource_identity_digest=self.resource_identity_digest,
            resource_claims_digest=self.resource_claims_digest,
            provider_routing_handle=self.provider_routing_handle,
        )
        if not self.key_version:
            raise ValueError("key_version is required")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("reference timestamps must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("reference expiry must follow issue time")

    def protected_claims(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "reference_id": self.reference_id,
            "key_version": self.key_version,
            "workspace_id": self.workspace_id,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "binding_id": self.binding_id,
            "binding_version": self.binding_version,
            "binding_digest": self.binding_digest,
            "resource_kind": self.resource_kind,
            "resource_identity_digest": self.resource_identity_digest,
            "resource_claims_digest": self.resource_claims_digest,
            "issued_at": format_timestamp(self.issued_at),
            "expires_at": format_timestamp(self.expires_at),
        }


@dataclass(frozen=True, slots=True)
class AuthorizedExternalResource:
    reference_id: str
    binding_id: str
    binding_version: str
    binding_digest: str
    resource_kind: str
    provider_routing_handle: str
    resource_identity_digest: str
    resource_claims_digest: str
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
    resource_identity_digest: str
    resource_claims_digest: str
    provider_routing_handle: str
    reference_id: str


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
    """Opaque integrity-protected m4r1 envelope."""

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
    def from_token(cls, value: str) -> ExternalResourceReference:
        return cls(value)

    def verify(self, verifier: ReferenceVerifier) -> VerifiedResourceReference:
        return verifier.verify(self)


@dataclass(frozen=True, slots=True)
class MintedExternalResourceReference:
    reference: ExternalResourceReference
    record: ReferenceRecord


class ExternalResourceReferenceMinter:
    def __init__(
        self,
        key_ring: ReferenceKeyRing,
        *,
        clock: Callable[[], datetime] | None = None,
        reference_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._key_ring = key_ring
        self._clock = clock or (lambda: datetime.now(UTC))
        self._reference_id_factory = reference_id_factory or (
            lambda: _b64encode(secrets.token_bytes(32))
        )

    def mint(
        self,
        authorized: AuthorizedReferenceMintingResource,
        *,
        expires_at: datetime,
    ) -> MintedExternalResourceReference:
        issued_at = self._clock()
        key = self._key_ring.active_key
        record = ReferenceRecord(
            reference_id=self._reference_id_factory(),
            workspace_id=authorized.workspace_id,
            capability_id=authorized.capability_id,
            capability_version=authorized.capability_version,
            binding_id=authorized.binding_id,
            binding_version=authorized.binding_version,
            binding_digest=authorized.binding_digest,
            resource_kind=authorized.resource_kind,
            resource_identity_digest=authorized.resource_identity_digest,
            resource_claims_digest=authorized.resource_claims_digest,
            provider_routing_handle=authorized.provider_routing_handle,
            issued_at=issued_at,
            expires_at=expires_at,
            key_version=key.version,
        )
        payload = canonical_json_v1(record.protected_claims())
        mac = hmac.new(key.secret, payload, hashlib.sha256).digest()
        token = ExternalResourceReference(f"m4r1.{_b64encode(payload)}.{_b64encode(mac)}")
        return MintedExternalResourceReference(token, record)


class ReferenceVerifier:
    _FIELDS = {
        "schema_version",
        "reference_id",
        "key_version",
        "workspace_id",
        "capability_id",
        "capability_version",
        "binding_id",
        "binding_version",
        "binding_digest",
        "resource_kind",
        "resource_identity_digest",
        "resource_claims_digest",
        "issued_at",
        "expires_at",
    }

    def __init__(
        self,
        store: ReferenceStore,
        key_ring: ReferenceKeyRing,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._key_ring = key_ring
        self._clock = clock or (lambda: datetime.now(UTC))

    def verify(self, reference: str | ExternalResourceReference) -> VerifiedResourceReference:
        token = reference.token if isinstance(reference, ExternalResourceReference) else reference
        if not isinstance(token, str):
            raise ValueError("reference must be text")
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != "m4r1":
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        try:
            payload_bytes = _b64decode(parts[1])
            mac = _b64decode(parts[2])
            payload = json.loads(payload_bytes.decode("utf-8"))
            if canonical_json_v1(payload) != payload_bytes:
                raise ValueError("payload is not canonical")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE") from exc
        if not isinstance(payload, dict) or set(payload) != self._FIELDS:
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        if payload.get("schema_version") != 1 or not isinstance(payload.get("key_version"), str):
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE")
        key = self._key_ring.get(payload["key_version"])
        if key is None or key.status == "revoked":
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        expected_mac = hmac.new(key.secret, payload_bytes, hashlib.sha256).digest()
        if len(mac) != hashlib.sha256().digest_size or not hmac.compare_digest(expected_mac, mac):
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        try:
            reference_id = payload["reference_id"]
            if not isinstance(reference_id, str):
                raise ValueError("reference_id must be text")
            _validate_reference_id(reference_id)
            issued_at = parse_timestamp(payload["issued_at"], "issued_at")
            expires_at = parse_timestamp(payload["expires_at"], "expires_at")
            for field_name in (
                "workspace_id",
                "capability_id",
                "capability_version",
                "binding_id",
                "binding_version",
                "resource_kind",
            ):
                if not isinstance(payload.get(field_name), str) or not payload[field_name]:
                    raise ValueError(f"{field_name} is required")
            for field_name in (
                "binding_digest",
                "resource_identity_digest",
                "resource_claims_digest",
            ):
                require_digest(payload.get(field_name), field_name)
        except ValueError as exc:
            raise KnoraError("INVALID_TOOL_RESOURCE_REFERENCE") from exc
        now = self._clock()
        if now.tzinfo is None:
            raise RuntimeError("reference verifier clock must be timezone-aware")
        if issued_at > now or expires_at <= now:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        record = self._store.get_reference(reference_id)
        if record is None or record.protected_claims() != payload:
            raise KnoraError("TOOL_RESOURCE_ACCESS_DENIED")
        return VerifiedResourceReference(
            workspace_id=record.workspace_id,
            capability_id=record.capability_id,
            capability_version=record.capability_version,
            binding_id=record.binding_id,
            binding_version=record.binding_version,
            binding_digest=record.binding_digest,
            resource_kind=record.resource_kind,
            resource_identity_digest=record.resource_identity_digest,
            resource_claims_digest=record.resource_claims_digest,
            provider_routing_handle=record.provider_routing_handle,
            reference_id=record.reference_id,
        )
