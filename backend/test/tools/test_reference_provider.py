import base64
import hashlib
import hmac
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    AuthorizedExternalResource,
    AuthorizedReferenceMintingResource,
    ExternalResourceReferenceMinter,
    ExternalScopeBinding,
    LookupTicketRequest,
    ProviderScopeDenied,
    ReadTool,
    ReadToolCommand,
    ReferenceKey,
    ReferenceKeyRing,
    ReferenceVerifier,
    SQLiteReferenceProvider,
    SQLiteSupportToolGateway,
    WorkspaceResourceAuthorizer,
)


def test_m4r1_minter_uses_exact_canonical_payload_and_active_key_only() -> None:
    active = ReferenceKey("k2", b"active-test-secret", status="active")
    retiring = ReferenceKey("k1", b"retiring-test-secret", status="retiring")
    ring = ReferenceKeyRing((active, retiring))
    authorized = AuthorizedReferenceMintingResource(
        workspace_id="workspace-a",
        capability_id="ticket_lookup",
        capability_version="m4.1",
        binding_id="binding-a",
        binding_version="v1",
        binding_digest="sha256:" + "3" * 64,
        resource_kind="ticket",
        resource_identity_digest="sha256:" + "1" * 64,
        resource_claims_digest="sha256:" + "2" * 64,
        provider_routing_handle="routing-ticket-a",
    )
    issued_at = datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
    expires_at = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
    minted = ExternalResourceReferenceMinter(
        ring,
        clock=lambda: issued_at,
        reference_id_factory=lambda: "A" * 43,
    ).mint(authorized, expires_at=expires_at)

    prefix, payload_text, mac_text = str(minted.reference).split(".")
    payload_bytes = base64.urlsafe_b64decode(payload_text + "=")
    payload = json.loads(payload_bytes)
    assert prefix == "m4r1"
    assert payload == {
        "binding_digest": "sha256:" + "3" * 64,
        "binding_id": "binding-a",
        "binding_version": "v1",
        "capability_id": "ticket_lookup",
        "capability_version": "m4.1",
        "expires_at": "2026-08-22T09:00:00.000000Z",
        "issued_at": "2026-08-22T08:00:00.000000Z",
        "key_version": "k2",
        "reference_id": "A" * 43,
        "resource_claims_digest": "sha256:" + "2" * 64,
        "resource_identity_digest": "sha256:" + "1" * 64,
        "resource_kind": "ticket",
        "schema_version": 1,
        "workspace_id": "workspace-a",
    }
    assert mac_text == base64.urlsafe_b64encode(
        hmac.new(active.secret, payload_bytes, hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    assert minted.record.key_version == "k2"

    with pytest.raises(ValueError, match="exactly one active"):
        ReferenceKeyRing((retiring,))
    with pytest.raises(ValueError, match="exactly one active"):
        ReferenceKeyRing((active, ReferenceKey("k3", b"another-active-secret")))


def _provider_fixture(database: Path):
    issued_at = datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
    expires_at = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
    binding = ExternalScopeBinding.for_workspace(
        "workspace-a", binding_id="binding-a", external_scope="scope-a"
    )
    key_ring = ReferenceKeyRing((ReferenceKey("k1", b"test-only-secret"),))
    minted = ExternalResourceReferenceMinter(
        key_ring,
        clock=lambda: issued_at,
        reference_id_factory=lambda: "A" * 42 + "Q",
    ).mint(
        AuthorizedReferenceMintingResource(
            workspace_id="workspace-a",
            capability_id="ticket_lookup",
            capability_version="m4.1",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest=binding.digest,
            resource_kind="ticket",
            resource_identity_digest="sha256:" + "1" * 64,
            resource_claims_digest="sha256:" + "2" * 64,
            provider_routing_handle="routing-ticket-75",
        ),
        expires_at=expires_at,
    )
    provider = SQLiteReferenceProvider(database)
    provider.register_reference(minted.record, provider_resource_id="provider-ticket-75")
    return provider, minted, key_ring, binding, issued_at


def _tool(provider, minted, key_ring, binding, now) -> ReadTool:
    return ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={"workspace-a": binding},
            reference_verifier=ReferenceVerifier(provider, key_ring, clock=lambda: now),
        ),
        gateway=SQLiteSupportToolGateway(provider),
    )


def test_sqlite_reference_provider_survives_adapter_restart(tmp_path: Path) -> None:
    database = tmp_path / "provider.sqlite"
    provider, minted, key_ring, binding, now = _provider_fixture(database)
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id="provider-ticket-75",
        title="Cannot sign in",
        status="open",
        summary="Customer cannot complete SSO sign-in.",
    )
    tool = _tool(provider, minted, key_ring, binding, now)

    first = tool.execute(
        ReadToolCommand(str(minted.reference)),
        WorkspacePrincipal("workspace-a", "key-a"),
    )
    provider.close()

    restarted = SQLiteReferenceProvider(database)
    restarted_tool = _tool(restarted, minted, key_ring, binding, now)
    second = restarted_tool.execute(
        ReadToolCommand(str(minted.reference)),
        WorkspacePrincipal("workspace-a", "key-a"),
    )

    assert first == second
    assert second.ticket_reference == minted.record.reference_id
    restarted.close()


def test_sqlite_gateway_rejects_cross_scope_before_provider_lookup(tmp_path: Path) -> None:
    provider, minted, _, _, _ = _provider_fixture(tmp_path / "provider.sqlite")
    gateway = SQLiteSupportToolGateway(provider)
    resource = AuthorizedExternalResource(
        reference_id=minted.record.reference_id,
        resource_kind="ticket",
        provider_routing_handle=minted.record.provider_routing_handle,
        resource_identity_digest=minted.record.resource_identity_digest,
        resource_claims_digest=minted.record.resource_claims_digest,
        external_scope="scope-a",
    )

    outcome = gateway.lookup_ticket(LookupTicketRequest(scope="scope-b", resource=resource))

    assert isinstance(outcome, ProviderScopeDenied)
    provider.close()


def test_sqlite_gateway_maps_malformed_provider_state_to_contract_invalid(
    tmp_path: Path,
) -> None:
    provider, minted, key_ring, binding, now = _provider_fixture(tmp_path / "provider.sqlite")
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id="provider-ticket-75",
        title=b"raw-bytes",  # type: ignore[arg-type]
        status="open",
        summary="Summary",
    )
    tool = _tool(provider, minted, key_ring, binding, now)

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand(str(minted.reference)), WorkspacePrincipal("workspace-a", "key-a")
        )

    assert error.value.code == "TOOL_PROVIDER_CONTRACT_INVALID"
    provider.close()


def test_sqlite_reference_registration_is_idempotent_but_cannot_retarget() -> None:
    provider, minted, _, _, _ = _provider_fixture(Path(":memory:"))

    provider.register_reference(minted.record, provider_resource_id="provider-ticket-75")
    with pytest.raises(ValueError, match="reference identity conflict"):
        provider.register_reference(minted.record, provider_resource_id="retargeted-ticket")
    with pytest.raises(ValueError, match="reference identity conflict"):
        provider.register_reference(
            replace(minted.record, provider_routing_handle="retargeted-routing"),
            provider_resource_id="provider-ticket-75",
        )

    assert provider.get_reference(minted.record.reference_id) == minted.record
    provider.close()
