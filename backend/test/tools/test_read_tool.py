
import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools import (
    CapabilityRegistry,
    ExternalResourceReference,
    ExternalScopeBinding,
    FakeSupportToolGateway,
    InMemoryReferenceStore,
    ReadTool,
    ReadToolCommand,
    ReferenceKey,
    ReferenceRecord,
    ReferenceVerifier,
    TicketLookupResult,
    WorkspaceResourceAuthorizer,
)


def prepared_tool() -> tuple[ReadTool, FakeSupportToolGateway, ExternalResourceReference]:
    binding = "sha256:binding-a"
    record = ReferenceRecord(
        reference_id="ticket-fixture-75",
        workspace_id="workspace-a",
        capability_id="ticket_lookup",
        capability_version="m4.1",
        binding_id="workspace-binding:workspace-a",
        binding_version="v1",
        binding_digest=binding,
        resource_kind="ticket",
        resource_claims={"scope": "support"},
        provider_resource_id="provider-ticket-75",
        expires_at=4_000_000_000,
        key_version="k1",
    )
    key = ReferenceKey("k1", b"test-only-secret")
    token = ExternalResourceReference.mint(record, key)
    store = InMemoryReferenceStore((record,))
    verifier = ReferenceVerifier(store, {"k1": key}, clock=lambda: 1_700_000_000)
    authorizer = WorkspaceResourceAuthorizer(
        bindings={
            "workspace-a": ExternalScopeBinding(
                "workspace-a", record.binding_id, "v1", binding, "scope-a"
            )
        },
        reference_verifier=verifier,
    )
    gateway = FakeSupportToolGateway(
        outcomes={
            record.provider_resource_id: TicketLookupResult(
                ticket_reference=record.reference_id,
                title="Cannot sign in",
                status="open",
                summary="Customer cannot complete SSO sign-in.",
            )
        }
    )
    return ReadTool(gateway=gateway, resource_authorizer=authorizer), gateway, token


def test_static_registry_and_authorized_lookup_are_typed() -> None:
    tool, gateway, token = prepared_tool()

    result = tool.execute(
        ReadToolCommand(str(token)), WorkspacePrincipal("workspace-a", "key-a")
    )

    assert CapabilityRegistry.static().resolve("ticket_lookup").version == "m4.1"
    assert result == TicketLookupResult(
        ticket_reference="ticket-fixture-75",
        title="Cannot sign in",
        status="open",
        summary="Customer cannot complete SSO sign-in.",
    )
    assert gateway.call_count == 1
    assert gateway.calls[0].resource.provider_resource_id == "provider-ticket-75"


@pytest.mark.parametrize(
    "principal,reference",
    [
        (WorkspacePrincipal("workspace-b", "key-b"), None),
        (WorkspacePrincipal("workspace-a", "key-a"), "m4r1.invalid.invalid"),
    ],
)
def test_denial_happens_before_gateway_invocation(principal, reference) -> None:
    tool, gateway, token = prepared_tool()

    with pytest.raises(KnoraError):
        tool.execute(
            ReadToolCommand(reference or str(token)),
            principal,
        )

    assert gateway.call_count == 0


def test_malformed_reference_has_typed_invalid_reference_error() -> None:
    tool, gateway, _ = prepared_tool()

    with pytest.raises(KnoraError) as error:
        tool.execute(
            ReadToolCommand("m4r1.%%%.___"),
            WorkspacePrincipal("workspace-a", "key-a"),
        )

    assert error.value.code == "INVALID_TOOL_RESOURCE_REFERENCE"
    assert gateway.call_count == 0
