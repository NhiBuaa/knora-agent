from __future__ import annotations

import json

from knora.adapters.cli import m5_e2e_bootstrap as module


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def provision_or_reuse(self, *, workspace_id: str, name: str) -> str:
        self.calls.append((workspace_id, name))
        return workspace_id


def test_main_provisions_exact_fixture_workspaces_idempotently(
    monkeypatch, capsys
) -> None:
    gateway = FakeGateway()
    monkeypatch.setattr(module, "PostgresEvaluationWorkspaceGateway", lambda _: gateway)

    module.main()

    assert gateway.calls == [
        ("m5-workspace", "M5 E2E Workspace"),
        ("m5-other-workspace", "M5 E2E Other Workspace"),
    ]
    assert json.loads(capsys.readouterr().out) == {
        "outcome": "provisioned",
        "workspaces": ["m5-other-workspace", "m5-workspace"],
    }
