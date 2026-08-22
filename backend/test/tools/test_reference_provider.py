from pathlib import Path

from knora.domain.access import WorkspacePrincipal
from knora.tools import (
    ExternalResourceReference,
    ExternalScopeBinding,
    ReadTool,
    ReadToolCommand,
    ReferenceKey,
    ReferenceRecord,
    ReferenceVerifier,
    SQLiteReferenceProvider,
    SQLiteSupportToolGateway,
    WorkspaceResourceAuthorizer,
)


def test_sqlite_reference_provider_survives_adapter_restart(tmp_path: Path) -> None:
    database = tmp_path / "provider.sqlite"
    record = ReferenceRecord(
        reference_id="ticket-fixture-75",
        workspace_id="workspace-a",
        capability_id="ticket_lookup",
        capability_version="m4.1",
        binding_id="binding-a",
        binding_version="v1",
        binding_digest="sha256:binding-a",
        resource_kind="ticket",
        resource_claims={"scope": "support"},
        provider_resource_id="provider-ticket-75",
        expires_at=4_000_000_000,
        key_version="k1",
    )
    key = ReferenceKey("k1", b"test-only-secret")
    provider = SQLiteReferenceProvider(database)
    provider.register_reference(record)
    provider.register_ticket(
        scope="scope-a",
        provider_resource_id=record.provider_resource_id,
        title="Cannot sign in",
        status="open",
        summary="Customer cannot complete SSO sign-in.",
    )
    token = ExternalResourceReference.mint(record, key)
    verifier = ReferenceVerifier(provider, {"k1": key}, clock=lambda: 1_700_000_000)
    tool = ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={
                "workspace-a": ExternalScopeBinding(
                    "workspace-a", "binding-a", "v1", "sha256:binding-a", "scope-a"
                )
            },
            reference_verifier=verifier,
        ),
        gateway=SQLiteSupportToolGateway(provider),
    )

    first = tool.execute(
        ReadToolCommand(str(token)),
        WorkspacePrincipal("workspace-a", "key-a"),
    )
    provider.close()

    restarted = SQLiteReferenceProvider(database)
    restarted_tool = ReadTool(
        resource_authorizer=WorkspaceResourceAuthorizer(
            bindings={
                "workspace-a": ExternalScopeBinding(
                    "workspace-a", "binding-a", "v1", "sha256:binding-a", "scope-a"
                )
            },
            reference_verifier=ReferenceVerifier(
                restarted, {"k1": key}, clock=lambda: 1_700_000_000
            ),
        ),
        gateway=SQLiteSupportToolGateway(restarted),
    )
    second = restarted_tool.execute(
        ReadToolCommand(str(token)),
        WorkspacePrincipal("workspace-a", "key-a"),
    )

    assert first == second
    assert second.ticket_reference == "ticket-fixture-75"
    restarted.close()
