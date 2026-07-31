from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


def hash_api_key(raw_key: str) -> str:
    return f"sha256:{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class ApiCredential:
    key_id: str
    key_hash: str
    workspace_id: str
    enabled: bool

    def __post_init__(self) -> None:
        if not self.key_id or not self.workspace_id:
            raise ValueError("API credential identifiers must not be blank")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.key_hash):
            raise ValueError("API credential key_hash must be a SHA-256 digest")
        if type(self.enabled) is not bool:
            raise ValueError("API credential enabled must be boolean")


class ApiKeyAuthenticator:
    def __init__(self, credentials: tuple[ApiCredential, ...]) -> None:
        owners: dict[str, str] = {}
        for credential in credentials:
            owner = owners.setdefault(credential.key_hash, credential.workspace_id)
            if owner != credential.workspace_id:
                raise ValueError("one API key hash cannot authorize multiple Workspaces")
        self._credentials = credentials

    def authenticate(self, raw_key: str | None) -> WorkspacePrincipal:
        if raw_key is None:
            raise KnoraError("UNAUTHENTICATED")

        candidate_hash = hash_api_key(raw_key)
        matched: ApiCredential | None = None
        for credential in self._credentials:
            matches = hmac.compare_digest(candidate_hash, credential.key_hash)
            if matches and credential.enabled:
                matched = credential
        if matched is None:
            raise KnoraError("UNAUTHENTICATED")
        return WorkspacePrincipal(workspace_id=matched.workspace_id, key_id=matched.key_id)


def credentials_from_json(value: str) -> tuple[ApiCredential, ...]:
    payload = json.loads(value)
    if not isinstance(payload, list):
        raise ValueError("API credentials configuration must be a JSON array")
    required = {"key_id", "key_hash", "workspace_id", "enabled"}
    credentials: list[ApiCredential] = []
    for item in payload:
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError(
                "API credential must contain only key_id, key_hash, workspace_id, enabled"
            )
        credentials.append(ApiCredential(**item))
    return tuple(credentials)
