"""Fixed, authenticated saved-run scoring routes; no browser execution configuration."""

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from knora.adapters.http.routes import authorize_workspace_principal

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/evaluation", tags=["evaluation-scoring"])


class ScoringPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_ids: list[str] = Field(min_length=1)
    profile_id: str


class ScoreSavedRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preflight_id: str
    request_id: str = Field(min_length=1, max_length=255)


@router.get("/runs/{run_id}/scoring", response_model=dict)
def read_scoring(workspace_id: str, run_id: str, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    principal = authorize_workspace_principal(request, workspace_id, "operator:read")
    return request.app.state.evaluation_scoring.read(workspace_id, principal, run_id)


@router.post("/runs/{run_id}/scoring/preflight", response_model=dict)
def preflight_scoring(
    workspace_id: str,
    run_id: str,
    payload: ScoringPreflightRequest,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    principal = authorize_workspace_principal(request, workspace_id, "operator:read")
    return request.app.state.evaluation_scoring.preflight(
        workspace_id, principal, run_id, tuple(payload.case_ids), payload.profile_id
    )


@router.post("/runs/{run_id}/scoring", response_model=dict)
async def score_saved_run(
    workspace_id: str,
    run_id: str,
    payload: ScoreSavedRunRequest,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    principal = authorize_workspace_principal(request, workspace_id, "operator:read")
    return await request.app.state.evaluation_scoring.score(
        workspace_id, principal, run_id, payload.preflight_id, payload.request_id
    )
