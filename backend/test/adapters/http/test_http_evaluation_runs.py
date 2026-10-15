from fastapi import FastAPI
from fastapi.testclient import TestClient

from knora.adapters.http.evaluation_runs import router
from knora.domain.access import WorkspacePrincipal


class Service:
    def __init__(self):
        self.calls = []

    def preflight(self, workspace_id, principal, dataset_id, case_ids, profile_id):
        self.calls.append((workspace_id, principal, dataset_id, case_ids, profile_id))
        return {"status": "BLOCKED", "reasons": ["PROVIDER_APPROVAL_REQUIRED"], "preflight_id": "p"}

    def read_run(self, workspace_id, principal, run_id):
        self.calls.append((workspace_id, principal, run_id))
        return {"run_id": run_id, "observations": {"case-1": {"status": "FAILED"}}, "report": None}


def test_http_preflight_and_case_are_workspace_scoped(monkeypatch):
    service = Service()
    app = FastAPI()
    app.state.evaluation_runs = service
    app.include_router(router)
    principal = WorkspacePrincipal(
        "workspace-1", "owner", ("operator:read", "evaluations:run", "questions:ask")
    )
    monkeypatch.setattr(
        "knora.adapters.http.evaluation_runs.authorize_workspace_principal",
        lambda request, workspace_id, capability: principal,
    )
    client = TestClient(app)
    response = client.post(
        "/v1/workspaces/workspace-1/evaluation/preflight",
        json={"dataset_id": "m3-dataset-v1", "case_ids": ["case-1"], "profile_id": "live"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
    assert service.calls[0][-2:] == (("case-1",), "live")
    case = client.get("/v1/workspaces/workspace-1/evaluation/runs/run-1/cases/case-1")
    assert case.json()["status"] == "FAILED"
    missing = client.get("/v1/workspaces/workspace-1/evaluation/runs/run-1/cases/other")
    assert missing.status_code == 404
