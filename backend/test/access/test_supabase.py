import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from knora.access.identity import BearerIdentityAuthenticator
from knora.access.supabase import SupabaseAuthenticator
from knora.domain.errors import KnoraError


class FakeAccessStore:
    def __init__(self, grants: tuple[str, ...] | None = None) -> None:
        self.grants = (
            grants if grants is not None else ("documents:read", "documents:write", "questions:ask")
        )

    def get_or_create_baseline(self, issuer: str, subject: str) -> tuple[str, ...]:
        return self.grants


class FakeSessionReader:
    def __init__(self, active: bool = True, raise_error: Exception | None = None) -> None:
        self.active = active
        self.raise_error = raise_error

    def is_active(self, subject: str, session_id: str) -> bool:
        if self.raise_error:
            raise self.raise_error
        return self.active


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
def signed_token(ec_key_pair, issuer, audience):
    private_key, _ = ec_key_pair

    def _sign(extra_claims: dict | None = None, alg="ES256", key=private_key) -> str:
        now = int(time.time())
        claims = {
            "iss": issuer,
            "aud": audience,
            "sub": "user-uuid-1234",
            "session_id": "session-uuid-5678",
            "role": "authenticated",
            "is_anonymous": False,
            "iat": now,
            "exp": now + 3600,
        }
        if extra_claims:
            claims.update(extra_claims)
        headers = {"kid": "key-1", "alg": alg}
        return jwt.encode(claims, key, algorithm=alg, headers=headers)

    return _sign


@pytest.fixture
def auth_with_empty_grants(ec_key_pair, issuer, audience):
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
        access_store=FakeAccessStore(grants=()),
        session_reader=FakeSessionReader(active=True),
    )


def test_satisfies_bearer_identity_protocol(auth_with_empty_grants):
    assert isinstance(auth_with_empty_grants, BearerIdentityAuthenticator)


def test_valid_token_authenticates(ec_key_pair, issuer, audience, signed_token):
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

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(active=True),
    )

    token = signed_token()
    identity = auth.authenticate_identity("Bearer " + token)
    assert identity.issuer == issuer
    assert identity.subject == "user-uuid-1234"
    assert set(identity.capabilities) == {"documents:read", "documents:write", "questions:ask"}


def test_user_metadata_cannot_grant_operator(auth_with_empty_grants, signed_token):
    raw = signed_token(
        {
            "user_metadata": {"capabilities": ["operator:read"]},
            "capabilities": ["operator:read"],
        }
    )
    identity = auth_with_empty_grants.authenticate_identity("Bearer " + raw)
    assert identity.capabilities == ()


def test_wrong_signature_fails(auth_with_empty_grants, issuer, audience):
    other_key = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": "user-1",
            "session_id": "sess-1",
            "role": "authenticated",
            "exp": now + 3600,
        },
        other_key,
        algorithm="ES256",
    )
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_wrong_algorithm_rejected(auth_with_empty_grants, signed_token):
    token = signed_token(alg="HS256", key="secret-key")
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_wrong_issuer_fails(auth_with_empty_grants, signed_token):
    token = signed_token({"iss": "https://other.supabase.co/auth/v1"})
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_wrong_audience_fails(auth_with_empty_grants, signed_token):
    token = signed_token({"aud": "wrong-audience"})
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_expired_token_fails(auth_with_empty_grants, signed_token):
    token = signed_token({"exp": int(time.time()) - 10})
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_missing_sub_fails(auth_with_empty_grants, signed_token):
    token = signed_token({"sub": ""})
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_missing_session_id_fails(auth_with_empty_grants, signed_token):
    token = signed_token({"session_id": None})
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_service_role_fails(auth_with_empty_grants, signed_token):
    token = signed_token({"role": "service_role"})
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_anonymous_user_fails(auth_with_empty_grants, signed_token):
    token = signed_token({"is_anonymous": True})
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_managed_session_inactive_fails(ec_key_pair, issuer, audience, signed_token):
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

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(active=False),
    )
    token = signed_token()
    with pytest.raises(KnoraError) as exc:
        auth.authenticate_identity("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_managed_session_db_error_propagates(ec_key_pair, issuer, audience, signed_token):
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

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(raise_error=KnoraError("AUTH_PROVIDER_UNAVAILABLE")),
    )
    token = signed_token()
    with pytest.raises(KnoraError) as exc:
        auth.authenticate_identity("Bearer " + token)
    assert exc.value.code == "AUTH_PROVIDER_UNAVAILABLE"


def test_authenticate_principal_fails_for_supabase(auth_with_empty_grants, signed_token):
    token = signed_token()
    with pytest.raises(KnoraError) as exc:
        auth_with_empty_grants.authenticate("Bearer " + token)
    assert exc.value.code == "UNAUTHENTICATED"


def test_jwks_transport_error_raises_auth_provider_unavailable(issuer, audience):
    def broken_validator(raw):
        raise jwt.PyJWKClientConnectionError("Network timeout connecting to JWKS")

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=broken_validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(),
    )
    with pytest.raises(KnoraError) as exc:
        auth.authenticate_identity("Bearer dummy-token")
    assert exc.value.code == "AUTH_PROVIDER_UNAVAILABLE"


def test_jwks_kid_mismatch_raises_unauthenticated(issuer, audience):
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
    with pytest.raises(KnoraError) as exc:
        auth.authenticate_identity("Bearer dummy-token")
    assert exc.value.code == "UNAUTHENTICATED"


def test_jwks_connection_error_raises_auth_provider_unavailable(issuer, audience):
    import urllib.error

    def broken_validator(raw):
        raise urllib.error.URLError("Connection refused")

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=broken_validator,
        access_store=FakeAccessStore(),
        session_reader=FakeSessionReader(),
    )
    with pytest.raises(KnoraError) as exc:
        auth.authenticate_identity("Bearer dummy-token")
    assert exc.value.code == "AUTH_PROVIDER_UNAVAILABLE"


def test_access_store_error_raises_auth_provider_unavailable(
    ec_key_pair, issuer, audience, signed_token
):
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

    class BrokenAccessStore:
        def get_or_create_baseline(self, issuer: str, subject: str):
            raise KnoraError("AUTH_PROVIDER_UNAVAILABLE")

    auth = SupabaseAuthenticator(
        issuer=issuer,
        audience=audience,
        algorithm="ES256",
        token_validator=validator,
        access_store=BrokenAccessStore(),
        session_reader=FakeSessionReader(),
    )
    token = signed_token()
    with pytest.raises(KnoraError) as exc:
        auth.authenticate_identity("Bearer " + token)
    assert exc.value.code == "AUTH_PROVIDER_UNAVAILABLE"
