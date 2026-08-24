import base64
import hashlib
import hmac
import json
import sqlite3
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
    HmacDispatchEnvelopeSigner,
    LookupTicketRequest,
    ProviderContractInvalid,
    ProviderIdempotencyConflict,
    ProviderOutcomeFound,
    ProviderOutcomeNotFound,
    ProviderScopeDenied,
    ProviderUnavailable,
    ProviderWriteFailed,
    ProviderWriteSucceeded,
    ReadTool,
    ReadToolCommand,
    ReferenceKey,
    ReferenceKeyRing,
    ReferenceVerifier,
    SQLiteReferenceProvider,
    SQLiteSupportToolGateway,
    WorkspaceResourceAuthorizer,
)
from knora.tools.contracts import canonical_digest_v1
from knora.tools.execution_types import DispatchEnvelopeClaims, ProviderTerminalFailureCode


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


def _authorized_resource(minted) -> AuthorizedExternalResource:
    return AuthorizedExternalResource(
        reference_id=minted.record.reference_id,
        binding_id=minted.record.binding_id,
        binding_version=minted.record.binding_version,
        binding_digest=minted.record.binding_digest,
        resource_kind="ticket",
        provider_routing_handle=minted.record.provider_routing_handle,
        resource_identity_digest=minted.record.resource_identity_digest,
        resource_claims_digest=minted.record.resource_claims_digest,
        external_scope="scope-a",
    )


def _lookup_request(minted, **overrides) -> LookupTicketRequest:
    resource = _authorized_resource(minted)
    values = {
        "scope": resource.external_scope,
        "binding_id": resource.binding_id,
        "binding_version": resource.binding_version,
        "binding_digest": resource.binding_digest,
        "resource": resource,
    }
    values.update(overrides)
    return LookupTicketRequest(**values)


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
    gateway = tool.gateway
    assert isinstance(gateway, SQLiteSupportToolGateway)
    request = gateway.calls[0]
    assert (request.binding_id, request.binding_version, request.binding_digest) == (
        binding.binding_id,
        binding.version,
        binding.digest,
    )
    assert (
        request.resource.binding_id,
        request.resource.binding_version,
        request.resource.binding_digest,
    ) == (binding.binding_id, binding.version, binding.digest)
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
    resource = _authorized_resource(minted)

    outcome = gateway.lookup_ticket(
        LookupTicketRequest(
            scope="scope-b",
            binding_id=resource.binding_id,
            binding_version=resource.binding_version,
            binding_digest=resource.binding_digest,
            resource=resource,
        )
    )

    assert isinstance(outcome, ProviderScopeDenied)
    provider.close()


def test_sqlite_gateway_rejects_mismatched_binding_provenance_before_lookup(
    tmp_path: Path,
) -> None:
    provider, minted, _, _, _ = _provider_fixture(tmp_path / "provider.sqlite")
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id="provider-ticket-75",
        title="Cannot sign in",
        status="open",
        summary="Customer cannot complete SSO sign-in.",
    )
    gateway = SQLiteSupportToolGateway(provider)
    resource = _authorized_resource(minted)

    outcome = gateway.lookup_ticket(
        LookupTicketRequest(
            scope="scope-a",
            binding_id=resource.binding_id,
            binding_version=resource.binding_version,
            binding_digest="sha256:" + "9" * 64,
            resource=resource,
        )
    )

    assert isinstance(outcome, ProviderScopeDenied)
    provider.close()


@pytest.mark.parametrize(
    "provider_result",
    [object(), ("Title", "open"), ("Title", "open", "Summary", "extra")],
    ids=["non-iterable", "too-short", "too-long"],
)
def test_sqlite_gateway_maps_malformed_provider_result_shapes_to_contract_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider_result: object,
) -> None:
    provider, minted, _, _, _ = _provider_fixture(tmp_path / "provider.sqlite")
    monkeypatch.setattr(provider, "lookup_ticket", lambda **_: provider_result)
    gateway = SQLiteSupportToolGateway(provider)

    outcome = gateway.lookup_ticket(_lookup_request(minted))

    assert isinstance(outcome, ProviderContractInvalid)
    provider.close()


@pytest.mark.parametrize(
    ("provider_error", "outcome_type"),
    [
        (sqlite3.OperationalError("provider unavailable"), ProviderUnavailable),
        (RuntimeError("unexpected provider failure"), ProviderContractInvalid),
    ],
    ids=["availability", "unexpected"],
)
def test_sqlite_gateway_closes_provider_exceptions_by_failure_kind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider_error: Exception,
    outcome_type: type,
) -> None:
    provider, minted, _, _, _ = _provider_fixture(tmp_path / "provider.sqlite")

    def raise_provider_error(**_) -> None:
        raise provider_error

    monkeypatch.setattr(provider, "lookup_ticket", raise_provider_error)
    gateway = SQLiteSupportToolGateway(provider)

    outcome = gateway.lookup_ticket(_lookup_request(minted))

    assert isinstance(outcome, outcome_type)
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


def _dispatch_envelope(
    signer: HmacDispatchEnvelopeSigner,
    *,
    logical_execution_id: str,
    title: str = "Cannot sign in",
    description: str = "Customer is blocked",
):
    fingerprint_input = {
        "operation": "create_ticket",
        "capability": {
            "id": "create_ticket",
            "version": "m4.2",
            "digest": "sha256:" + "a" * 64,
        },
        "binding": {
            "id": "binding-a",
            "version": "v1",
            "digest": "sha256:" + "b" * 64,
        },
        "target": {
            "reference_id": "A" * 42 + "Q",
            "resource_kind": "ticket",
            "resource_identity_digest": "sha256:" + "1" * 64,
            "resource_claims_digest": "sha256:" + "2" * 64,
        },
        "parameters": {"title": title, "description": description},
    }
    fingerprint = canonical_digest_v1(fingerprint_input)
    return signer.sign(
        DispatchEnvelopeClaims(
            admission_identity="admission-a",
            admission_claims_digest="sha256:" + "8" * 64,
            workspace_id="workspace-a",
            proposal_id="proposal-a",
            logical_execution_id=logical_execution_id,
            request_fingerprint=fingerprint,
            external_scope="scope-a",
            provider_routing_handle="routing-ticket-75",
            intent={
                "operation": "create_ticket",
                "title": title,
                "description": description,
                "fingerprint_input": fingerprint_input,
            },
        )
    )


def test_sqlite_provider_write_is_atomic_replayable_and_restart_stable(tmp_path: Path) -> None:
    database = tmp_path / "provider.sqlite"
    provider, _, _, _, _ = _provider_fixture(database)
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id="provider-ticket-75",
        title="Target",
        status="open",
        summary="Target for create_ticket",
    )
    signer = HmacDispatchEnvelopeSigner(
        key_identity="provider-dispatch-key",
        key_version="v1",
        secret=b"provider-dispatch-secret",
    )
    gateway = SQLiteSupportToolGateway(provider, dispatch_verifier=signer)
    envelope = _dispatch_envelope(signer, logical_execution_id="logical-a")

    first = gateway.create_ticket(envelope)
    replay = gateway.create_ticket(envelope)

    assert isinstance(first, ProviderWriteSucceeded)
    assert replay == first
    assert provider.provider_effect_count("logical-a") == 1
    provider.close()

    restarted_provider = SQLiteReferenceProvider(database)
    restarted_gateway = SQLiteSupportToolGateway(restarted_provider, dispatch_verifier=signer)
    assert restarted_gateway.create_ticket(envelope) == first
    assert restarted_gateway.get_execution_outcome(
        scope="scope-a", logical_execution_id="logical-a"
    ) == ProviderOutcomeFound(first)
    assert restarted_provider.provider_effect_count("logical-a") == 1
    restarted_provider.close()


def test_sqlite_provider_conflicts_on_same_identity_with_valid_different_intent(
    tmp_path: Path,
) -> None:
    provider, _, _, _, _ = _provider_fixture(tmp_path / "provider.sqlite")
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id="provider-ticket-75",
        title="Target",
        status="open",
        summary="Target",
    )
    signer = HmacDispatchEnvelopeSigner(
        key_identity="provider-dispatch-key",
        key_version="v1",
        secret=b"provider-dispatch-secret",
    )
    gateway = SQLiteSupportToolGateway(provider, dispatch_verifier=signer)

    first = gateway.create_ticket(
        _dispatch_envelope(signer, logical_execution_id="logical-conflict")
    )
    conflict = gateway.create_ticket(
        _dispatch_envelope(
            signer,
            logical_execution_id="logical-conflict",
            title="Different title",
        )
    )

    assert isinstance(first, ProviderWriteSucceeded)
    assert isinstance(conflict, ProviderIdempotencyConflict)
    assert provider.provider_effect_count("logical-conflict") == 1
    provider.close()


@pytest.mark.parametrize("rejection", list(ProviderTerminalFailureCode))
def test_sqlite_provider_closed_rejection_has_no_effect_and_survives_restart(
    tmp_path: Path, rejection: ProviderTerminalFailureCode
) -> None:
    database = tmp_path / f"provider-{rejection.value}.sqlite"
    provider, _, _, _, _ = _provider_fixture(database)
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id="provider-ticket-75",
        title="Target",
        status="open",
        summary="Target",
    )
    signer = HmacDispatchEnvelopeSigner(
        key_identity="provider-dispatch-key",
        key_version="v1",
        secret=b"provider-dispatch-secret",
    )
    envelope = _dispatch_envelope(signer, logical_execution_id=f"logical-{rejection.value}")
    gateway = SQLiteSupportToolGateway(
        provider,
        dispatch_verifier=signer,
        forced_rejection=rejection,
    )

    result = gateway.create_ticket(envelope)

    assert result == ProviderWriteFailed(rejection.value)
    assert provider.provider_effect_count() == 0
    provider.close()
    restarted = SQLiteReferenceProvider(database)
    observation = SQLiteSupportToolGateway(
        restarted, dispatch_verifier=signer
    ).get_execution_outcome(scope="scope-a", logical_execution_id=f"logical-{rejection.value}")
    assert observation == ProviderOutcomeFound(ProviderWriteFailed(rejection.value))
    assert restarted.provider_effect_count() == 0
    restarted.close()


def test_provider_outcome_not_found_is_read_only_boundary_evidence(tmp_path: Path) -> None:
    provider, _, _, _, _ = _provider_fixture(tmp_path / "provider.sqlite")
    signer = HmacDispatchEnvelopeSigner(
        key_identity="provider-dispatch-key",
        key_version="v1",
        secret=b"provider-dispatch-secret",
    )
    gateway = SQLiteSupportToolGateway(provider, dispatch_verifier=signer)

    assert (
        gateway.get_execution_outcome(scope="scope-a", logical_execution_id="absent")
        == ProviderOutcomeNotFound()
    )
    assert provider.provider_effect_count() == 0
    provider.close()


def test_provider_write_cross_binding_denies_before_idempotency_or_effect(
    tmp_path: Path,
) -> None:
    provider, _, _, _, _ = _provider_fixture(tmp_path / "provider.sqlite")
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id="provider-ticket-75",
        title="Target",
        status="open",
        summary="Target",
    )
    signer = HmacDispatchEnvelopeSigner(
        key_identity="provider-dispatch-key",
        key_version="v1",
        secret=b"provider-dispatch-secret",
    )
    original = _dispatch_envelope(signer, logical_execution_id="logical-cross-scope")
    claims = signer.verify(original)
    intent = claims["intent"]
    assert isinstance(intent, dict)
    cross_scope = signer.sign(
        DispatchEnvelopeClaims(
            admission_identity="admission-cross-scope",
            admission_claims_digest="sha256:" + "8" * 64,
            workspace_id="workspace-b",
            proposal_id="proposal-cross-scope",
            logical_execution_id="logical-cross-scope",
            request_fingerprint=claims["request_fingerprint"],
            external_scope="scope-b",
            provider_routing_handle="routing-ticket-75",
            intent=intent,
        )
    )
    gateway = SQLiteSupportToolGateway(provider, dispatch_verifier=signer)

    outcome = gateway.create_ticket(cross_scope)

    assert isinstance(outcome, ProviderScopeDenied)
    assert (
        provider.get_execution_outcome(scope="scope-b", logical_execution_id="logical-cross-scope")
        is None
    )
    assert provider.provider_effect_count() == 0
    provider.close()
