"""Operator run routes; selection and runtime authority remain in the application service."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, Request, Response
from pydantic import BaseModel, ConfigDict

from knora.adapters.http.routes import authorize_workspace_principal
from knora.domain.errors import KnoraError

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/evaluation", tags=["evaluation-runs"])


class PreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    case_ids: list[str]
    profile_id: str


class PreflightResponse(BaseModel):
    preflight_id: str
    status: str
    reasons: list[str]
    workspace_id: str | None = None
    dataset_id: str | None = None
    dataset_digest: str | None = None
    case_ids: list[str] = []
    context_only_case_ids: list[str] = []
    profile_id: str | None = None
    expires_at: str | None = None


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preflight_id: str


class RunResponse(BaseModel):
    run_id: str
    workspace_id: str
    selection: dict[str, Any]
    selection_digest: str
    profile_id: str
    binding: dict[str, Any]
    execution_status: str
    quality_status: str
    observations: dict[str, dict[str, Any]]
    report: dict[str, Any] | None


def _service(request: Request):
    return request.app.state.evaluation_runs


def _principal(request: Request, workspace_id: str):
    return authorize_workspace_principal(request, workspace_id, "operator:read")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/profiles", response_model=list[dict[str, str]])
def list_profiles(workspace_id: str, request: Request, response: Response):
    _private(response)
    return _service(request).list_profiles(workspace_id, _principal(request, workspace_id))


@router.post("/preflight", response_model=PreflightResponse)
def preflight(workspace_id: str, payload: PreflightRequest, request: Request, response: Response):
    _private(response)
    return _service(request).preflight(
        workspace_id,
        _principal(request, workspace_id),
        payload.dataset_id,
        tuple(payload.case_ids),
        payload.profile_id,
    )


@router.post("/runs", status_code=202, response_model=RunResponse)
def start_run(
    workspace_id: str,
    payload: StartRunRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    _private(response)
    if idempotency_key is None:
        raise KnoraError("EVALUATION_IDEMPOTENCY_KEY_INVALID")
    service = _service(request)
    run = service.start_run(
        workspace_id, _principal(request, workspace_id), payload.preflight_id, idempotency_key
    )
    if run["execution_status"] == "QUEUED":
        background_tasks.add_task(service.process_run, workspace_id, run["run_id"])
    return run


@router.get("/runs", response_model=list[RunResponse])
def list_runs(workspace_id: str, request: Request, response: Response):
    _private(response)
    return _service(request).list_runs(workspace_id, _principal(request, workspace_id))


@router.get("/runs/{run_id}", response_model=RunResponse)
def read_run(workspace_id: str, run_id: str, request: Request, response: Response):
    _private(response)
    return _service(request).read_run(workspace_id, _principal(request, workspace_id), run_id)


@router.get("/runs/{run_id}/cases/{case_id}", response_model=dict[str, Any])
def read_case(workspace_id: str, run_id: str, case_id: str, request: Request, response: Response):
    _private(response)
    run = _service(request).read_run(workspace_id, _principal(request, workspace_id), run_id)
    case = run["observations"].get(case_id)
    if case is None:
        response.status_code = 404
        return {"detail": "EVALUATION_CASE_NOT_FOUND"}
    return {"case_id": case_id, **case}


@router.get("/runs/{run_id}/report", response_model=dict[str, Any])
def read_report(workspace_id: str, run_id: str, request: Request, response: Response):
    _private(response)
    report = _service(request).read_run(workspace_id, _principal(request, workspace_id), run_id)[
        "report"
    ]
    if report is None:
        response.status_code = 409
        return {"detail": "EVALUATION_REPORT_UNAVAILABLE"}
    return report
