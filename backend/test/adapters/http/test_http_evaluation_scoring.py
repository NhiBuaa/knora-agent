from fastapi import FastAPI
from fastapi.testclient import TestClient

from knora.domain.access import WorkspacePrincipal


def test_scoring_routes_keep_fixed_workspace_and_reject_browser_execution_configuration(
    monkeypatch,
):
    from knora.adapters.http.evaluation_scoring import router

    calls = []

    class Service:
        def read(self, workspace, principal, run_id):
            calls.append((workspace, principal, run_id))
            return {"profiles": [], "batches": []}

        def preflight(self, workspace, principal, run_id, case_ids, profile_id):
            calls.append((workspace, run_id, case_ids, profile_id))
            return {"status": "BLOCKED", "reasons": ["JUDGE_APPROVAL_REQUIRED"]}

        async def score(self, workspace, principal, run_id, preflight_id, request_id):
            calls.append((workspace, run_id, preflight_id, request_id))
            return {"status": "INDETERMINATE"}

    principal = WorkspacePrincipal("w1", "owner", ("operator:read", "evaluations:run"))
    monkeypatch.setattr(
        "knora.adapters.http.evaluation_scoring.authorize_workspace_principal", lambda *_: principal
    )
    app = FastAPI()
    app.state.evaluation_scoring = Service()
    app.include_router(router)
    client = TestClient(app)
    path = "/v1/workspaces/w1/evaluation/runs/r1/scoring"
    response = client.get(path)
    assert response.json() == {"profiles": [], "batches": []}
    assert response.headers["cache-control"] == "no-store"
    payload = {"case_ids": ["a", "r"], "profile_id": "live"}
    assert client.post(path + "/preflight", json=payload).json()["status"] == "BLOCKED"
    assert calls[-1] == ("w1", "r1", ("a", "r"), "live")
    for extra in (
        {"endpoint": "https://unapproved"},
        {"command": "run"},
        {"path": "C:/private"},
        {"token": "secret"},
        {"approval": True},
    ):
        assert client.post(path + "/preflight", json={**payload, **extra}).status_code == 422
    assert (
        client.post(path, json={"preflight_id": "p1", "request_id": "request-1"}).json()["status"]
        == "INDETERMINATE"
    )
    assert calls[-1] == ("w1", "r1", "p1", "request-1")
