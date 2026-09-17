import base64
import json
import time

import pytest

import knora.access.keycloak as keycloak_module
from knora.access.keycloak import KeycloakAuthenticator
from knora.domain.errors import KnoraError


def token(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"a.{body}.sig"


def test_valid_token_maps_principal():
    auth = KeycloakAuthenticator(issuer="https://issuer", audience="api", token_validator=lambda t: {"iss":"https://issuer","aud":"api","exp":time.time()+60,"sub":"u","workspace_id":"w","capabilities":["documents:write"]})
    p = auth.authenticate("Bearer " + token({}))
    assert (p.subject, p.workspace_id, p.capabilities) == ("u", "w", ("documents:write",))


@pytest.mark.parametrize("claims", [
    {"iss":"https://issuer","aud":"api","exp":time.time()-1,"sub":"u","workspace_id":"w"},
    {"iss":"https://wrong","aud":"api","exp":time.time()+1,"sub":"u","workspace_id":"w"},
    {"iss":"https://issuer","aud":"wrong","exp":time.time()+1,"sub":"u","workspace_id":"w"},
])
def test_invalid_claims_rejected(claims):
    with pytest.raises(KnoraError):
        KeycloakAuthenticator(
            issuer="https://issuer",
            audience="api",
            token_validator=lambda t, c=claims: c,
        ).authenticate("Bearer x.y.z")

def test_malformed_token_rejected_without_validator():
    with pytest.raises(KnoraError):
        KeycloakAuthenticator(issuer="i", audience="a").authenticate("Bearer x.y.z")


def test_default_validator_uses_cached_jwks_and_jwt_claim_validation(monkeypatch):
    observed = {}

    class FakeSigningKey:
        key = "public-key"

    class FakeJwkClient:
        def __init__(self, url, *, cache_jwk_set, lifespan):
            observed["client"] = (url, cache_jwk_set, lifespan)

        def get_signing_key_from_jwt(self, raw_token):
            observed["token"] = raw_token
            return FakeSigningKey()

    def fake_decode(raw_token, key, *, algorithms, issuer, audience, options):
        observed["decode"] = (raw_token, key, algorithms, issuer, audience, options)
        return {
            "iss": issuer,
            "aud": audience,
            "exp": time.time() + 60,
            "sub": "user-1",
            "workspace_id": "workspace-1",
            "capabilities": ["documents:write"],
        }

    monkeypatch.setattr(keycloak_module.jwt, "PyJWKClient", FakeJwkClient)
    monkeypatch.setattr(keycloak_module.jwt, "decode", fake_decode)

    principal = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        jwks_url="https://issuer/certs",
        jwks_cache_ttl_seconds=120,
    ).authenticate("Bearer signed-token")

    assert principal.subject == "user-1"
    assert observed["client"] == ("https://issuer/certs", True, 120)
    assert observed["decode"][1] == "public-key"
    assert "RS256" in observed["decode"][2]


def test_validator_failure_is_normalized_to_unauthenticated():
    def broken_validator(_token):
        raise RuntimeError("network or JWT failure")

    with pytest.raises(KnoraError, match="UNAUTHENTICATED"):
        KeycloakAuthenticator(
            issuer="https://issuer",
            audience="api",
            token_validator=broken_validator,
        ).authenticate("Bearer signed-token")


def test_malformed_claim_types_are_normalized_to_unauthenticated():
    with pytest.raises(KnoraError, match="UNAUTHENTICATED"):
        KeycloakAuthenticator(
            issuer="https://issuer",
            audience="api",
            token_validator=lambda _token: {
                "iss": None,
                "aud": "api",
                "exp": time.time() + 60,
                "sub": "u",
                "workspace_id": "w",
            },
        ).authenticate("Bearer signed-token")


def test_null_subject_is_rejected_as_unauthenticated():
    with pytest.raises(KnoraError, match="UNAUTHENTICATED"):
        KeycloakAuthenticator(
            issuer="https://issuer",
            audience="api",
            token_validator=lambda _token: {
                "iss": "https://issuer",
                "aud": "api",
                "exp": time.time() + 60,
                "sub": None,
                "workspace_id": "w",
            },
        ).authenticate("Bearer signed-token")


def test_missing_bearer_capability_is_not_unrestricted():
    principal = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "api",
            "exp": time.time() + 60,
            "sub": "u",
            "workspace_id": "w",
        },
    ).authenticate("Bearer signed-token")

    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        principal.require_capability("documents:write")
