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


def test_case_checkpoint_takes_precedence_over_queued_report(monkeypatch):
    service = Service()
    service.read_run = lambda *_: {
        "observations": {
            "case-1": {
                "status": "OBSERVED",
                "trace_id": "checkpoint-trace",
                "public_answer": "Saved answer",
            }
        },
        "report": {
            "cases": [
                {
                    "case_id": "case-1",
                    "question": "Gold question",
                    "status": "NOT_RUN",
                    "trace_id": None,
                    "public_answer": None,
                    "evaluable": False,
                    "reasons": ["OBSERVATION_NOT_RUN"],
                }
            ]
        },
    }
    app = FastAPI()
    app.state.evaluation_runs = service
    app.include_router(router)
    monkeypatch.setattr(
        "knora.adapters.http.evaluation_runs.authorize_workspace_principal",
        lambda *_: WorkspacePrincipal("w", "owner", ("operator:read",)),
    )
    case = TestClient(app).get("/v1/workspaces/w/evaluation/runs/run-1/cases/case-1").json()
    assert case["status"] == "OBSERVED"
    assert case["trace_id"] == "checkpoint-trace"
    assert case["public_answer"] == "Saved answer"
    assert case["question"] == "Gold question"
    assert "reasons" not in case
