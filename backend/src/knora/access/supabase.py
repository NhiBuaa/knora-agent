from __future__ import annotations

import json
import urllib.error
from collections.abc import Callable, Mapping

import jwt

from knora.access.identity import BearerIdentityAuthenticator, Identity
from knora.access.identity_access import IdentityAccessStore, SupabaseSessionReader
from knora.domain.errors import KnoraError


class SupabaseAuthenticator(BearerIdentityAuthenticator):
    """Authenticate Supabase JWTs, enforce session validity, and attach Knora grants."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithm: str,
        access_store: IdentityAccessStore,
        session_reader: SupabaseSessionReader,
        jwks_url: str | None = None,
        jwks_client: jwt.PyJWKClient | None = None,
        token_validator: Callable[[str], Mapping[str, object]] | None = None,
        api_key_authenticator=None,
        jwks_cache_ttl_seconds: int = 300,
    ) -> None:
        if algorithm not in {"ES256", "RS256"}:
            raise ValueError(
                f"Unsupported Supabase JWT algorithm: {algorithm}. Must be ES256 or RS256."
            )
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.algorithm = algorithm
        self.access_store = access_store
        self.session_reader = session_reader
        self.api_key_authenticator = api_key_authenticator

        if token_validator is None:
            if jwks_client is None and jwks_url:
                jwks_client = jwt.PyJWKClient(
                    jwks_url,
                    cache_jwk_set=True,
                    lifespan=jwks_cache_ttl_seconds,
                )
            if jwks_client is not None:

                def validate_with_jwks(raw_token: str) -> Mapping[str, object]:
                    header = jwt.get_unverified_header(raw_token)
                    if header.get("alg") != self.algorithm:
                        raise ValueError(
                            f"Algorithm mismatch: expected {self.algorithm}, "
                            f"got {header.get('alg')}"
                        )
                    signing_key = jwks_client.get_signing_key_from_jwt(raw_token)
                    return jwt.decode(
                        raw_token,
                        signing_key.key,
                        algorithms=[self.algorithm],
                        issuer=self.issuer,
                        audience=self.audience,
                        options={"require": ["exp", "iss", "aud", "sub"]},
                    )

                token_validator = validate_with_jwks

        self._token_validator = token_validator

    def authenticate_identity(self, authorization_header: str | None) -> Identity:
        claims = self._claims_from_header(authorization_header)
        sub = str(claims["sub"])
        session_id = str(claims["session_id"])

        # Check managed session status
        if not self.session_reader.is_active(sub, session_id):
            raise KnoraError("UNAUTHENTICATED")

        # Read Knora capability grants
        capabilities = self.access_store.get_or_create_baseline(self.issuer, sub)

        return Identity(
            issuer=self.issuer,
            subject=sub,
            capabilities=capabilities,
        )

    def authenticate(self, authorization_header: str | None):
        # Supabase tokens carry no Workspace claims and cannot produce a
        # WorkspacePrincipal directly.
        raise KnoraError("UNAUTHENTICATED")

    def _claims_from_header(self, authorization_header: str | None) -> Mapping[str, object]:
        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise KnoraError("UNAUTHENTICATED")
        token = authorization_header[7:].strip()
        if not token:
            raise KnoraError("UNAUTHENTICATED")
        if self._token_validator is None:
            raise KnoraError("UNAUTHENTICATED")

        try:
            claims = self._token_validator(token)
        except KnoraError:
            raise
        except (
            jwt.PyJWKClientConnectionError,
            jwt.PyJWKSetError,
            json.JSONDecodeError,
            urllib.error.URLError,
            OSError,
            TimeoutError,
            ConnectionError,
        ) as exc:
            raise KnoraError("AUTH_PROVIDER_UNAVAILABLE") from exc
        except jwt.PyJWKClientError as exc:
            msg = str(exc)
            if "Unable to find a signing key that matches" in msg:
                raise KnoraError("UNAUTHENTICATED") from exc
            raise KnoraError("AUTH_PROVIDER_UNAVAILABLE") from exc
        except Exception as exc:
            raise KnoraError("UNAUTHENTICATED") from exc

        try:
            if not isinstance(claims, Mapping):
                raise ValueError
            if claims.get("iss", "").rstrip("/") != self.issuer:
                raise ValueError
            aud = claims.get("aud")
            if not (aud == self.audience or (isinstance(aud, list) and self.audience in aud)):
                raise ValueError
            sub = claims.get("sub")
            if not isinstance(sub, str) or not sub:
                raise ValueError
            session_id = claims.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise ValueError
            role = claims.get("role")
            if role != "authenticated":
                raise ValueError
            if claims.get("is_anonymous") is True:
                raise ValueError
            return claims
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise KnoraError("UNAUTHENTICATED") from exc
