import base64
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    ActorContext,
    AuthorityProvenance,
    AuthorizedReferenceMintingResource,
    CapabilityRegistry,
    ExternalResourceReferenceMinter,
    ExternalScopeBinding,
    InMemoryReferenceStore,
    InMemoryToolActionStore,
    PolicyProvenance,
    ProposeWriteAction,
    ReferenceKey,
    ReferenceKeyRing,
    ReferenceRecord,
    ReferenceVerifier,
    WriteProposalWorkflow,
)
from knora.tools.proposal_integration import (
    ReferenceProposalTargetVerifier,
    RegistryCapabilityResolver,
)

NOW = datetime(2026, 8, 23, 8, 0, tzinfo=UTC)
EXPIRES = datetime(2026, 8, 23, 9, 0, tzinfo=UTC)


def _reference_id(value: int = 7) -> str:
    return base64.urlsafe_b64encode(bytes([value]) * 32).decode("ascii").rstrip("=")


def _binding(workspace_id: str = "workspace-a") -> ExternalScopeBinding:
    return ExternalScopeBinding.for_workspace(
        workspace_id,
        binding_id="support-binding",
        version="v1",
        external_scope="support-scope-a",
    )


def _mint(
    *,
    ring: ReferenceKeyRing,
    binding: ExternalScopeBinding,
    workspace_id: str = "workspace-a",
    capability_id: str = "create_ticket",
    capability_version: str = "m4.2",
    binding_id: str | None = None,
    binding_version: str | None = None,
    binding_digest: str | None = None,
    resource_kind: str = "ticket",
    expires_at: datetime = EXPIRES,
):
    return ExternalResourceReferenceMinter(
        ring,
        clock=lambda: NOW,
        reference_id_factory=_reference_id,
    ).mint(
        AuthorizedReferenceMintingResource(
            workspace_id=workspace_id,
            capability_id=capability_id,
            capability_version=capability_version,
            binding_id=binding_id or binding.binding_id,
            binding_version=binding_version or binding.version,
            binding_digest=binding_digest or binding.digest,
            resource_kind=resource_kind,
            resource_identity_digest="sha256:" + "1" * 64,
            resource_claims_digest="sha256:" + "2" * 64,
            provider_routing_handle="routing-create-target",
        ),
        expires_at=expires_at,
    )


def _workflow(
    *,
    minted,
    verify_ring: ReferenceKeyRing,
    binding: ExternalScopeBinding,
    store_record: ReferenceRecord | None = None,
    now: datetime = NOW,
) -> WriteProposalWorkflow:
    reference_store = InMemoryReferenceStore(
        () if store_record is False else (store_record or minted.record,)
    )
    return WriteProposalWorkflow(
        capability_resolver=RegistryCapabilityResolver(
            CapabilityRegistry.static(),
            bindings={"workspace-a": binding},
            policy=PolicyProvenance(),
        ),
        store=InMemoryToolActionStore(),
        target_verifier=ReferenceProposalTargetVerifier(
            ReferenceVerifier(reference_store, verify_ring, clock=lambda: now)
        ),
        clock=lambda: now,
    )


def _propose(workflow: WriteProposalWorkflow, reference: str):
    return workflow.handle(
        ProposeWriteAction("create_ticket", reference, "Cannot sign in", "Customer is blocked"),
        WorkspacePrincipal("workspace-a", "caller-key"),
        ActorContext(
            "agent-a",
            "model",
            authority=AuthorityProvenance.from_semantics(
                "model-proposal-authority", "v1", {"actor_kinds": ["model"]}
            ),
        ),
    )


def test_registry_resolver_and_real_reference_verifier_bind_exact_proposal() -> None:
    binding = _binding()
    ring = ReferenceKeyRing((ReferenceKey("k1", b"test-only-reference-secret"),))
    minted = _mint(ring=ring, binding=binding)

    result = _propose(
        _workflow(minted=minted, verify_ring=ring, binding=binding), str(minted.reference)
    )
    descriptor = CapabilityRegistry.static().resolve("create_ticket")

    assert result.projection.capability_id == descriptor.capability_id
    assert result.projection.capability_version == descriptor.version
    assert result.projection.capability_digest == descriptor.digest
    assert result.projection.binding_digest == binding.digest
    assert result.projection.target_reference_id == minted.record.reference_id
    assert (
        result.projection.target_resource_identity_digest == minted.record.resource_identity_digest
    )
    assert result.projection.target_resource_claims_digest == minted.record.resource_claims_digest


@pytest.mark.parametrize("reference", ["m4r1.target.opaque", "", "not-an-envelope"])
def test_proposal_reference_syntax_failure_is_a_safe_400_code(reference: str) -> None:
    binding = _binding()
    ring = ReferenceKeyRing((ReferenceKey("k1", b"test-only-reference-secret"),))
    minted = _mint(ring=ring, binding=binding)

    with pytest.raises(KnoraError) as error:
        _propose(_workflow(minted=minted, verify_ring=ring, binding=binding), reference)

    expected = "TOOL_REQUEST_INVALID" if reference == "" else "INVALID_TOOL_RESOURCE_REFERENCE"
    assert error.value.code == expected


@pytest.mark.parametrize(
    "mismatch",
    [
        "bad_mac",
        "unknown_key",
        "revoked_key",
        "expired",
        "workspace",
        "capability",
        "binding",
        "resource",
        "store_missing",
        "store_mismatch",
    ],
)
def test_real_reference_integrity_scope_and_store_fail_closed(mismatch: str) -> None:
    binding = _binding()
    mint_ring = ReferenceKeyRing((ReferenceKey("k1", b"test-only-reference-secret"),))
    mint_kwargs = {}
    now = NOW
    verify_ring = mint_ring
    if mismatch == "workspace":
        mint_kwargs["workspace_id"] = "workspace-b"
    elif mismatch == "capability":
        mint_kwargs["capability_id"] = "ticket_lookup"
        mint_kwargs["capability_version"] = "m4.1"
    elif mismatch == "binding":
        mint_kwargs["binding_id"] = "other-binding"
    elif mismatch == "resource":
        mint_kwargs["resource_kind"] = "document"
    elif mismatch == "expired":
        now = datetime(2026, 8, 23, 10, 0, tzinfo=UTC)
    minted = _mint(ring=mint_ring, binding=binding, **mint_kwargs)
    reference = str(minted.reference)
    store_record: ReferenceRecord | None | bool = None
    if mismatch == "bad_mac":
        prefix, payload, mac = reference.split(".")
        reference = f"{prefix}.{payload}.{'A' if mac[0] != 'A' else 'B'}{mac[1:]}"
    elif mismatch == "unknown_key":
        verify_ring = ReferenceKeyRing((ReferenceKey("other", b"other-secret"),))
    elif mismatch == "revoked_key":
        verify_ring = ReferenceKeyRing(
            (
                ReferenceKey("active", b"active-secret"),
                ReferenceKey("k1", b"test-only-reference-secret", "revoked"),
            )
        )
    elif mismatch == "store_missing":
        store_record = False
    elif mismatch == "store_mismatch":
        store_record = replace(
            minted.record,
            resource_claims_digest="sha256:" + "3" * 64,
        )

    with pytest.raises(KnoraError) as error:
        _propose(
            _workflow(
                minted=minted,
                verify_ring=verify_ring,
                binding=binding,
                store_record=store_record,
                now=now,
            ),
            reference,
        )

    assert error.value.code == "TOOL_RESOURCE_ACCESS_DENIED"
