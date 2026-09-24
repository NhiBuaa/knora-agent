"""Provision isolated M5 E2E fixture workspaces through the control plane."""

from __future__ import annotations

import json

from knora.adapters.postgres.database import SessionFactory
from knora.application.evaluation_environment import PostgresEvaluationWorkspaceGateway

FIXTURE_WORKSPACES = (
    ("m5-workspace", "M5 E2E Workspace"),
    ("m5-other-workspace", "M5 E2E Other Workspace"),
)


def main() -> None:
    gateway = PostgresEvaluationWorkspaceGateway(SessionFactory)
    for workspace_id, name in FIXTURE_WORKSPACES:
        gateway.provision_or_reuse(workspace_id=workspace_id, name=name)
    print(
        json.dumps(
            {
                "outcome": "provisioned",
                "workspaces": sorted(workspace_id for workspace_id, _ in FIXTURE_WORKSPACES),
            }
        )
    )


if __name__ == "__main__":
    main()
