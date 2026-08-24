"""Exact-candidate structural guardrails for Issue #78 recovery delivery."""

from __future__ import annotations

import inspect

from knora.tools import CapabilityRegistry, ReconcileExecution, SupportToolGateway
from knora.tools.proposal_types import TypedWriteCommand


def test_static_tool_registry_remains_allowlisted_without_runtime_registration() -> None:
    first = CapabilityRegistry.static()
    restarted = CapabilityRegistry.static()

    assert first.registry_identity == "knora-static-tool-capability-registry"
    assert first.capability_ids == ("ticket_lookup", "create_ticket")
    assert first.registry_digest == restarted.registry_digest
    assert not any(
        hasattr(first, forbidden)
        for forbidden in ("register", "discover", "load_plugin", "load_provider")
    )


def test_reconciliation_remains_the_only_new_typed_write_command_surface() -> None:
    assert ReconcileExecution in TypedWriteCommand.__args__
    assert set(SupportToolGateway.__dict__) >= {
        "lookup_ticket",
        "create_ticket",
        "get_execution_outcome",
    }
    source = inspect.getsource(CapabilityRegistry)
    assert "dynamic loading path" in source
    assert "plugin" not in source.lower()
