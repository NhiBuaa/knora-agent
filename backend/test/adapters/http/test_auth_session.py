import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from knora.access.supabase import SupabaseAuthenticator
from knora.main import create_app


class FakeAccessStore:
    def get_or_create_baseline(self, issuer: str, subject: str) -> tuple[str, ...]:
        return ("documents:read", "documents:write", "questions:ask")


class FakeSessionReader:
    def is_active(self, subject: str, session_id: str) -> bool:
        return True


@pytest.fixture
def ec_key_pair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture
def issuer():
    return "https://demo.supabase.co/auth/v1"


@pytest.fixture
def audience():
    return "authenticated"


@pytest.fixture
def supabase_auth(ec_key_pair, issuer, audience):
    _, public_key = ec_key_pair

    def validator(raw):
        return jwt.decode(
            raw,
            public_key,
            algorithms=["ES256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

    return SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(),
    )


@pytest.fixture
def client(supabase_auth):
    app = create_app(bearer_authenticator=supabase_auth)
    return TestClient(app)


def test_auth_session_returns_session_details_with_no_store(client, ec_key_pair, issuer, audience):
    private_key, _ = ec_key_pair
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": "user-test-uuid",
            "session_id": "sess-test-uuid",
            "role": "authenticated",
            "is_anonymous": False,
            "exp": now + 3600,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "k1", "alg": "ES256"},
    )

    response = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"

    body = response.json()
    assert body["issuer"] == issuer
    assert body["subject"] == "user-test-uuid"
    assert body["session_id"] == "sess-test-uuid"
    assert set(body["capabilities"]) == {"documents:read", "documents:write", "questions:ask"}
    assert "token" not in body
    assert "access_token" not in body
    assert "refresh_token" not in body


def test_auth_session_rejects_missing_or_invalid_bearer(client):
    response = client.get("/v1/auth/session")
    assert response.status_code == 401

    response = client.get("/v1/auth/session", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_auth_session_returns_503_when_auth_provider_unavailable(ec_key_pair, issuer, audience):
    def failing_validator(raw):
        raise jwt.PyJWKClientConnectionError("Connection timeout to JWKS endpoint")

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=failing_validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(),
    )
    app = create_app(bearer_authenticator=auth)
    c = TestClient(app)

    response = c.get("/v1/auth/session", headers={"Authorization": "Bearer some-token"})
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "AUTH_PROVIDER_UNAVAILABLE"}}


def test_auth_session_returns_401_when_jwks_kid_mismatch(ec_key_pair, issuer, audience):
    def kid_mismatch_validator(raw):
        raise jwt.PyJWKClientError('Unable to find a signing key that matches: "unknown-kid"')

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=kid_mismatch_validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(),
    )
    app = create_app(bearer_authenticator=auth)
    c = TestClient(app)

    response = c.get("/v1/auth/session", headers={"Authorization": "Bearer some-token"})
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "UNAUTHENTICATED"}}


def test_auth_session_returns_503_when_session_reader_fails(ec_key_pair, issuer, audience):
    private_key, public_key = ec_key_pair
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": "user-uuid",
            "session_id": "sess-uuid",
            "role": "authenticated",
            "is_anonymous": False,
            "exp": now + 3600,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "k1", "alg": "ES256"},
    )

    class FailingSessionReader:
        def is_active(self, subject: str, session_id: str) -> bool:
            from knora.domain.errors import KnoraError

            raise KnoraError("AUTH_PROVIDER_UNAVAILABLE")

    def validator(raw):
        return jwt.decode(
            raw,
            public_key,
            algorithms=["ES256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=validator,
        access_store=FakeAccessStore(),
        session_reader=FailingSessionReader(),
    )
    app = create_app(bearer_authenticator=auth)
    c = TestClient(app)

    response = c.get("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "AUTH_PROVIDER_UNAVAILABLE"}}
