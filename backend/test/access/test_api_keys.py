import pytest

from knora.access.api_keys import (
    ApiCredential,
    ApiKeyAuthenticator,
    credentials_from_json,
    hash_api_key,
)
from knora.domain.errors import KnoraError


def test_authenticator_rejects_disabled_keys_and_returns_safe_principal() -> None:
    enabled = ApiCredential("enabled", hash_api_key("secret-a"), "workspace-a", True)
    disabled = ApiCredential("disabled", hash_api_key("secret-b"), "workspace-a", False)
    authenticator = ApiKeyAuthenticator((enabled, disabled))

    principal = authenticator.authenticate("secret-a")

    assert principal.workspace_id == "workspace-a"
    assert principal.key_id == "enabled"
    with pytest.raises(KnoraError, match="UNAUTHENTICATED"):
        authenticator.authenticate("secret-b")


def test_one_key_hash_cannot_authorize_multiple_workspaces() -> None:
    shared_hash = hash_api_key("shared")

    with pytest.raises(ValueError, match="cannot authorize multiple Workspaces"):
        ApiKeyAuthenticator(
            (
                ApiCredential("a", shared_hash, "workspace-a", True),
                ApiCredential("b", shared_hash, "workspace-b", True),
            )
        )


@pytest.mark.parametrize(
    "payload",
    [
        '{}',
        '[{"key_id":"a","key_hash":"not-a-hash","workspace_id":"w","enabled":true}]',
        '[{"key_id":"a","key_hash":"sha256:00","workspace_id":"w","enabled":"yes"}]',
    ],
)
def test_runtime_credential_configuration_rejects_invalid_shapes(payload: str) -> None:
    with pytest.raises(ValueError):
        credentials_from_json(payload)
