from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from knora.domain.errors import KnoraError
from knora.tools.contracts import canonical_json_v1
from knora.tools.execution_types import DispatchEnvelopeClaims


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True, slots=True)
class DispatchEnvelope:
    token: str

    def __post_init__(self) -> None:
        if not self.token.startswith("m4-dispatch-admission-v1."):
            raise ValueError("invalid dispatch envelope domain")

    def __str__(self) -> str:
        return self.token


class HmacDispatchEnvelopeSigner:
    """Versioned production-capable signer; test harness keys are supplied out of band."""

    def __init__(self, *, key_identity: str, key_version: str, secret: bytes) -> None:
        if not key_identity or not key_version or not secret:
            raise ValueError("dispatch signing material is required")
        self.key_identity = key_identity
        self.key_version = key_version
        self._secret = bytes(secret)
        self.sign_count = 0

    def sign(self, claims: DispatchEnvelopeClaims) -> DispatchEnvelope:
        payload = canonical_json_v1(
            {
                "schema_version": 1,
                "purpose": "m4-dispatch-admission-v1",
                "signing_key_identity": self.key_identity,
                "signing_key_version": self.key_version,
                "admission_identity": claims.admission_identity,
                "admission_claims_digest": claims.admission_claims_digest,
                "workspace_id": claims.workspace_id,
                "proposal_id": claims.proposal_id,
                "logical_execution_id": claims.logical_execution_id,
                "request_fingerprint": claims.request_fingerprint,
                "external_scope": claims.external_scope,
                "provider_routing_handle": claims.provider_routing_handle,
                "intent": claims.intent,
            }
        )
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        self.sign_count += 1
        return DispatchEnvelope(f"m4-dispatch-admission-v1.{_encode(payload)}.{_encode(signature)}")

    def verify(self, envelope: DispatchEnvelope) -> dict[str, object]:
        parts = envelope.token.split(".")
        if len(parts) != 3 or parts[0] != "m4-dispatch-admission-v1":
            raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID")
        try:
            payload = _decode(parts[1])
            signature = _decode(parts[2])
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID") from exc
        expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected) or canonical_json_v1(decoded) != payload:
            raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID")
        if (
            not isinstance(decoded, dict)
            or decoded.get("purpose") != "m4-dispatch-admission-v1"
            or decoded.get("signing_key_identity") != self.key_identity
            or decoded.get("signing_key_version") != self.key_version
        ):
            raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID")
        return decoded

    def mint_external_resource_reference(self, logical_execution_id: str) -> str:
        """Mint a provider-facing opaque reference without exposing its raw resource ID."""
        if not logical_execution_id:
            raise ValueError("logical execution identity is required")
        payload = canonical_json_v1(
            {
                "schema_version": 1,
                "purpose": "m4-provider-created-resource-reference-v1",
                "logical_execution_id": logical_execution_id,
                "signing_key_identity": self.key_identity,
                "signing_key_version": self.key_version,
            }
        )
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return f"m4r1.{_encode(payload)}.{_encode(signature)}"
