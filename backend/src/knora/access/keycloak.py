from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable, Mapping

import jwt

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


def _payload(token: str) -> Mapping[str, object]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError
        raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except Exception as exc:
        raise KnoraError("UNAUTHENTICATED") from exc


class KeycloakAuthenticator:
    """Validate bounded Keycloak claims and map them to a workspace principal.

    Cryptographic JWT/JWKS verification is supplied by the required ``token_validator``
    seam; construction without one rejects all bearer tokens.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        token_validator: Callable[[str], Mapping[str, object]] | None = None,
        jwks_url: str | None = None,
        jwks_cache_ttl_seconds: int = 300,
        api_key_authenticator=None,
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        if jwks_cache_ttl_seconds <= 0:
            raise ValueError("jwks_cache_ttl_seconds must be positive")
        if token_validator is None and jwks_url:
            client = jwt.PyJWKClient(
                jwks_url,
                cache_jwk_set=True,
                lifespan=jwks_cache_ttl_seconds,
            )

            def validate_with_jwks(raw_token: str) -> Mapping[str, object]:
                signing_key = client.get_signing_key_from_jwt(raw_token)
                return jwt.decode(
                    raw_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    issuer=self.issuer,
                    audience=self.audience,
                    options={"require": ["exp", "iss", "aud", "sub"]},
                )

            token_validator = validate_with_jwks
        self._token_validator = token_validator
        self.api_key_authenticator = api_key_authenticator

    def authenticate(self, authorization_header: str | None) -> WorkspacePrincipal:
        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise KnoraError("UNAUTHENTICATED")
        token = authorization_header[7:].strip()
        if not token:
            raise KnoraError("UNAUTHENTICATED")
        if self._token_validator is None:
            raise KnoraError("UNAUTHENTICATED")
        try:
            claims = self._token_validator(token)
        except Exception as exc:
            raise KnoraError("UNAUTHENTICATED") from exc
        try:
            if not isinstance(claims, Mapping):
                raise ValueError
            if claims.get("iss", "").rstrip("/") != self.issuer:
                raise ValueError
            aud = claims.get("aud")
            if not (aud == self.audience or isinstance(aud, list) and self.audience in aud):
                raise ValueError
            if float(claims["exp"]) <= time.time():
                raise ValueError
            subject = str(claims["sub"])
            workspace = str(claims.get("workspace_id") or claims.get("workspace"))
            if not subject or workspace in {"", "None"}:
                raise ValueError
            raw_caps = claims.get("capabilities", ())
            if isinstance(raw_caps, str):
                capabilities = (raw_caps,)
            elif isinstance(raw_caps, list):
                capabilities = tuple(str(item) for item in raw_caps if isinstance(item, str))
            else:
                capabilities = ()
            return WorkspacePrincipal(workspace, subject, capabilities)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise KnoraError("UNAUTHENTICATED") from exc
