import time

import pytest

from knora.access.identity import Identity
from knora.access.keycloak import KeycloakAuthenticator
from knora.access.workspace_authorization import WorkspaceAuthorizer
from knora.domain.errors import KnoraError


class FakeOwnershipStore:
    def __init__(self, owners):
        self.owners = owners
        self.content_reads = 0

    def owner_for(self, workspace_id):
        return self.owners.get(workspace_id)


def test_bearer_identity_does_not_require_workspace_claim():
    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _token: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "alice",
            "capabilities": [],
        },
    )
    identity = authenticator.authenticate_identity("Bearer token")
    assert identity.subject == "alice"
    assert identity.issuer == "https://issuer"


def test_authorizer_returns_principal_for_owned_workspace():
    store = FakeOwnershipStore({"workspace-a": Identity("https://issuer", "alice", ())})
    authorizer = WorkspaceAuthorizer(store)

    principal = authorizer.authorize(
        Identity("https://issuer", "alice", ("documents:read",)),
        "workspace-a",
        "documents:read",
    )

    assert principal.workspace_id == "workspace-a"
    assert principal.subject == "alice"


def test_authorizer_denies_foreign_owner_before_content_lookup():
    store = FakeOwnershipStore({"workspace-a": Identity("https://issuer", "alice", ())})
    authorizer = WorkspaceAuthorizer(store)

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        authorizer.authorize(
            Identity("https://issuer", "bob", ("documents:read",)),
            "workspace-a",
            "documents:read",
        )

    assert store.content_reads == 0


def test_authorizer_fails_closed_when_workspace_has_no_owner():
    authorizer = WorkspaceAuthorizer(FakeOwnershipStore({}))

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        authorizer.authorize(
            Identity("https://issuer", "alice", ("documents:read",)),
            "workspace-a",
            "documents:read",
        )


def test_supabase_identity_works_with_workspace_authorizer():
    from knora.access.supabase import SupabaseAuthenticator

    class FakeStore:
        def get_or_create_baseline(self, issuer: str, subject: str) -> tuple[str, ...]:
            return ("documents:read", "documents:write", "questions:ask")

    class FakeSession:
        def is_active(self, subject: str, session_id: str) -> bool:
            return True

    auth = SupabaseAuthenticator(
        issuer="https://demo.supabase.co/auth/v1",
        audience="authenticated",
        algorithm="ES256",
        token_validator=lambda _token: {
            "iss": "https://demo.supabase.co/auth/v1",
            "aud": "authenticated",
            "exp": time.time() + 60,
            "sub": "alice",
            "session_id": "sess-1",
            "role": "authenticated",
        },
        access_store=FakeStore(),
        session_reader=FakeSession(),
    )
    identity = auth.authenticate_identity("Bearer token")
    assert identity.subject == "alice"
    assert identity.issuer == "https://demo.supabase.co/auth/v1"

    store = FakeOwnershipStore(
        {"workspace-a": Identity("https://demo.supabase.co/auth/v1", "alice", ())}
    )
    authorizer = WorkspaceAuthorizer(store)
    principal = authorizer.authorize(identity, "workspace-a", "documents:read")
    assert principal.workspace_id == "workspace-a"
    assert principal.subject == "alice"
