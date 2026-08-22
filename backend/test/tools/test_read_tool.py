import base64
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    AuthorizedReferenceMintingResource,
    CapabilityRegistry,
    ExternalResourceReference,
    ExternalResourceReferenceMinter,
    ExternalScopeBinding,
    FakeSupportToolGateway,
    InMemoryReferenceStore,
    ProviderContractInvalid,
    ProviderResourceNotFound,
    ProviderScopeDenied,
    ProviderUnavailable,
    ReadTool,
    ReadToolCommand,
    ReferenceKey,
    ReferenceKeyRing,
    ReferenceRecord,
    ReferenceVerifier,
    TicketLookupResult,
    WorkspaceResourceAuthorizer,
)

NOW = datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
EXPIRES = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
RESOURCE_IDENTITY_DIGEST = "sha256:" + "1" * 64
RESOURCE_CLAIMS_DIGEST = "sha256:" + "2" * 64


def _reference_id(value: int) -> str:
    return base64.urlsafe_b64encode(bytes([value]) * 32).decode("ascii").rstrip("=")


def _binding(
    workspace_id: str = "workspace-a", *, external_scope: str = "scope-a"
) -> ExternalScopeBinding:
    return ExternalScopeBinding.for_workspace(
        workspace_id,
        binding_id="binding-a",
        external_scope=external_scope,
    )


def _tamper_payload(token: str, field: str, value: object) -> str:
    prefix, payload_text, mac_text = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_text + "="))
    payload[field] = value
    tampered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(tampered).decode("ascii").rstrip("=")
    return f"{prefix}.{encoded}.{mac_text}"


def _minted_reference(
    *,
    binding: ExternalScopeBinding,
    reference_id: str | None = None,
    routing_handle: str = "routing-ticket-75",
    key_ring: ReferenceKeyRing | None = None,
    workspace_id: str | None = None,
    capability_version: str = "m4.1",
    binding_digest: str | None = None,
    resource_claims_digest: str = RESOURCE_CLAIMS_DIGEST,
):
    ring = key_ring or ReferenceKeyRing((ReferenceKey("k1", b"test-only-secret"),))
    authorization = AuthorizedReferenceMintingResource(
        workspace_id=workspace_id or binding.workspace_id,
        capability_id="ticket_lookup",
        capability_version=capability_version,
        binding_id=binding.binding_id,
        binding_version=binding.version,
        binding_digest=binding_digest or binding.digest,
        resource_kind="ticket",
        resource_identity_digest=RESOURCE_IDENTITY_DIGEST,
        resource_claims_digest=resource_claims_digest,
        provider_routing_handle=routing_handle,
    )
    minted = ExternalResourceReferenceMinter(
        ring,
        clock=lambda: NOW,
        reference_id_factory=lambda: reference_id or _reference_id(1),
    ).mint(authorization, expires_at=EXPIRES)
    return minted, ring


def prepared_tool() -> tuple[
    ReadTool,
    FakeSupportToolGateway,
    ExternalResourceReference,
    ReferenceRecord,
    ReferenceKeyRing,
    InMemoryReferenceStore,
]:
    binding = _binding()
    minted, ring = _minted_reference(binding=binding)
    store = InMemoryReferenceStore((minted.record,))
    verifier = ReferenceVerifier(store, ring, clock=lambda: NOW)
    authorizer = WorkspaceResourceAuthorizer(
        bindings={"workspace-a": binding},
        reference_verifier=verifier,
    )
    gateway = FakeSupportToolGateway(
        outcomes={
            minted.record.provider_routing_handle: TicketLookupResult(
                ticket_reference=minted.record.reference_id,
                title="Cannot sign in",
                status="open",
                summary="Customer cannot complete SSO sign-in.",
            )
        }
    )
    return (
        ReadTool(gateway=gateway, resource_authorizer=authorizer),
        gateway,
        minted.reference,
        minted.record,
        ring,
        store,
    )


def test_static_registry_and_authorized_lookup_are_typed() -> None:
    tool, gateway, token, record, _, _ = prepared_tool()

    result = tool.execute(
        ReadToolCommand(str(token)), WorkspacePrincipal("workspace-a", "key-a")
    )

    descriptor = CapabilityRegistry.static().resolve("ticket_lookup")
    assert descriptor.version == "m4.1"
    canonical_descriptor = (
        b'{"capability_id":"ticket_lookup","operation":"read",'
        b'"resource_kind":"ticket","version":"m4.1"}'
    )
    assert descriptor.digest == "sha256:" + hashlib.sha256(canonical_descriptor).hexdigest()
    assert result == TicketLookupResult(
        ticket_reference=record.reference_id,
        title="Cannot sign in",
        status="open",
        summary="Customer cannot complete SSO sign-in.",
    )
    assert gateway.call_count == 1
    assert gateway.calls[0].resource.provider_routing_handle == "routing-ticket-75"
    assert not hasattr(gateway.calls[0].resource, "provider_resource_id")

    with pytest.raises(KnoraError) as error:
        CapabilityRegistry.static().resolve("unknown")
    assert error.value.code == "TOOL_CAPABILITY_NOT_FOUND"


def test_external_scope_binding_digest_covers_exact_scope_semantics() -> None:
    binding = _binding(external_scope="scope-a")
    assert binding != _binding(external_scope="scope-b")
    assert binding.digest != _binding(external_scope="scope-b").digest

    with pytest.raises(ValueError, match="binding digest does not match"):
        ExternalScopeBinding(
            workspace_id="workspace-a",
            binding_id="binding-a",
            version="v1",
            digest=binding.digest,
            external_scope="scope-b",
        )


@pytest.mark.parametrize(
    "principal,reference",
    [
        (WorkspacePrincipal("workspace-b", "key-b"), None),
        (WorkspacePrincipal("workspace-a", "key-a"), "m4r1.invalid.invalid"),
    ],
)
def test_denial_happens_before_gateway_invocation(principal, reference) -> None:
    tool, gateway, token, _, _, _ = prepared_tool()

    with pytest.raises(KnoraError):
        tool.execute(ReadToolCommand(reference or str(token)), principal)

    assert gateway.call_count == 0


def test_missing_workspace_binding_denies_before_gateway_invocation() -> None:
    synthesized = ExternalScopeBinding.for_workspace("workspace-a")
    minted, ring = _minted_reference(binding=synthesized, reference_id=_reference_id(2))
    gateway = FakeSupportToolGateway(
        outcomes={
            minted.record.provider_routing_handle: TicketLookupResult(
                minted.record.reference_id, "Title", "open", "Summary"
            )
        }
    )
    tool = ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={},
            reference_verifier=ReferenceVerifier(
                InMemoryReferenceStore((minted.record,)), ring, clock=lambda: NOW
            ),
        ),
        gateway=gateway,
    )

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand(str(minted.reference)), WorkspacePrincipal("workspace-a", "key-a")
        )

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
    assert gateway.call_count == 0


def test_malformed_reference_has_typed_invalid_reference_error() -> None:
    tool, gateway, _, _, _, _ = prepared_tool()

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand("m4r1.%%%.___"), WorkspacePrincipal("workspace-a", "key-a")
        )

    assert error.value.code == "INVALID_TOOL_RESOURCE_REFERENCE"
    assert gateway.call_count == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", "workspace-b"),
        ("capability_version", "m4.2"),
        ("binding_digest", "sha256:" + "4" * 64),
        ("resource_claims_digest", "sha256:" + "5" * 64),
    ],
    ids=["workspace", "capability-version", "binding-digest", "resource-claims"],
)
def test_tampered_reference_claims_fail_integrity_before_gateway(field, value) -> None:
    tool, gateway, token, _, _, _ = prepared_tool()

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand(_tamper_payload(str(token), field, value)),
            WorkspacePrincipal("workspace-a", "key-a"),
        )

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
    assert gateway.call_count == 0


def test_tampered_reference_mac_fails_before_gateway() -> None:
    tool, gateway, token, _, _, _ = prepared_tool()
    prefix, payload, mac = str(token).split(".")
    tampered_mac = ("A" if mac[0] != "A" else "B") + mac[1:]

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand(f"{prefix}.{payload}.{tampered_mac}"),
            WorkspacePrincipal("workspace-a", "key-a"),
        )

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
    assert gateway.call_count == 0


@pytest.mark.parametrize(
    "outcome,code",
    [
        (ProviderScopeDenied(), "TOOL_RESOURCE_ACCESS_DENIED"),
        (ProviderResourceNotFound(), "TOOL_TICKET_NOT_FOUND"),
        (ProviderUnavailable(), "TOOL_PROVIDER_UNAVAILABLE"),
        (ProviderContractInvalid(), "TOOL_PROVIDER_CONTRACT_INVALID"),
    ],
)
def test_provider_outcomes_have_closed_mappings_and_one_call(outcome, code) -> None:
    tool, gateway, token, record, _, _ = prepared_tool()
    gateway.outcomes[record.provider_routing_handle] = outcome

    with pytest.raises(KnoraError) as error:
        tool.execute(ReadToolCommand(str(token)), WorkspacePrincipal("workspace-a", "key-a"))

    assert error.value.code == code
    assert gateway.call_count == 1


def test_reference_store_claim_mismatch_fails_closed_before_gateway() -> None:
    tool, gateway, token, record, _, store = prepared_tool()
    store.register(replace(record, workspace_id="workspace-b"))

    with pytest.raises(KnoraError) as error:
        tool.execute(ReadToolCommand(str(token)), WorkspacePrincipal("workspace-a", "key-a"))

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
    assert gateway.call_count == 0


def test_missing_reference_store_record_fails_closed_before_gateway() -> None:
    tool, gateway, token, _, ring, _ = prepared_tool()
    tool.resource_authorizer = WorkspaceResourceAuthorizer(
        bindings={"workspace-a": _binding()},
        reference_verifier=ReferenceVerifier(InMemoryReferenceStore(), ring, clock=lambda: NOW),
    )

    with pytest.raises(KnoraError) as error:
        tool.execute(ReadToolCommand(str(token)), WorkspacePrincipal("workspace-a", "key-a"))

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
    assert gateway.call_count == 0


@pytest.mark.parametrize(
    "mint_overrides",
    [
        {"workspace_id": "workspace-b"},
        {"capability_version": "m4.2"},
        {"binding_digest": "sha256:" + "4" * 64},
    ],
    ids=["workspace", "capability-version", "binding-digest"],
)
def test_exact_reference_claim_mismatch_denies_before_gateway(mint_overrides) -> None:
    binding = _binding()
    minted, ring = _minted_reference(
        binding=binding,
        reference_id=_reference_id(4),
        **mint_overrides,
    )
    gateway = FakeSupportToolGateway()
    tool = ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={"workspace-a": binding},
            reference_verifier=ReferenceVerifier(
                InMemoryReferenceStore((minted.record,)), ring, clock=lambda: NOW
            ),
        ),
        gateway=gateway,
    )

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand(str(minted.reference)), WorkspacePrincipal("workspace-a", "key-a")
        )

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
    assert gateway.call_count == 0


def test_current_binding_scope_change_denies_old_reference_before_gateway() -> None:
    approved_binding = _binding(external_scope="scope-a")
    current_binding = _binding(external_scope="scope-b")
    minted, ring = _minted_reference(binding=approved_binding, reference_id=_reference_id(5))
    gateway = FakeSupportToolGateway()
    tool = ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={"workspace-a": current_binding},
            reference_verifier=ReferenceVerifier(
                InMemoryReferenceStore((minted.record,)), ring, clock=lambda: NOW
            ),
        ),
        gateway=gateway,
    )

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand(str(minted.reference)), WorkspacePrincipal("workspace-a", "key-a")
        )

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
    assert gateway.call_count == 0


def test_reference_key_lifecycle_accepts_retiring_and_rejects_unknown_revoked_or_expired() -> None:
    binding = _binding()
    old_active = ReferenceKey("k1", b"old-test-secret")
    minted, _ = _minted_reference(
        binding=binding,
        reference_id=_reference_id(3),
        key_ring=ReferenceKeyRing((old_active,)),
    )
    store = InMemoryReferenceStore((minted.record,))
    new_active = ReferenceKey("k2", b"new-test-secret")
    retiring_ring = ReferenceKeyRing(
        (new_active, ReferenceKey("k1", b"old-test-secret", "retiring"))
    )
    retiring_gateway = FakeSupportToolGateway(
        outcomes={
            minted.record.provider_routing_handle: TicketLookupResult(
                minted.record.reference_id, "Title", "open", "Summary"
            )
        }
    )
    retiring_tool = ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={"workspace-a": binding},
            reference_verifier=ReferenceVerifier(store, retiring_ring, clock=lambda: NOW),
        ),
        gateway=retiring_gateway,
    )
    assert retiring_tool.execute(
        ReadToolCommand(str(minted.reference)), WorkspacePrincipal("workspace-a", "key-a")
    ).title == "Title"

    cases = [
        (ReferenceKeyRing((new_active,)), NOW),
        (
            ReferenceKeyRing(
                (new_active, ReferenceKey("k1", b"old-test-secret", "revoked"))
            ),
            NOW,
        ),
        (ReferenceKeyRing((old_active,)), EXPIRES),
    ]
    for ring, now in cases:
        gateway = FakeSupportToolGateway()
        tool = ReadTool(
            resource_authorizer=WorkspaceResourceAuthorizer(
                bindings={"workspace-a": binding},
                reference_verifier=ReferenceVerifier(store, ring, clock=lambda now=now: now),
            ),
            gateway=gateway,
        )
        with pytest.raises(KnoraError) as error:
            tool.execute(
                ReadToolCommand(str(minted.reference)), WorkspacePrincipal("workspace-a", "key-a")
            )
        assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
        assert gateway.call_count == 0
