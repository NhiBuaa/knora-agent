"""Owner-scoped Workspace HTTP contracts."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from knora.access.identity import Identity
from knora.access.keycloak import KeycloakAuthenticator
from knora.adapters.http.routes import get_authenticator
from knora.domain.errors import KnoraError
from knora.workspaces.service import WorkspaceService
from knora.workspaces.types import WorkspaceView

router = APIRouter(prefix="/v1/workspaces")


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    archived: bool
    revision: int
    created_at: datetime


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    next_cursor: str | None


class ResolutionResponse(BaseModel):
    state: Literal["ACTIVE", "NO_ACTIVE_WORKSPACE"]
    workspace: WorkspaceResponse | None


class WorkspaceNameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


def require_identity(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    authenticator=Depends(get_authenticator),  # noqa: B008
) -> Identity:
    if not isinstance(authenticator, KeycloakAuthenticator):
        raise KnoraError("UNAUTHENTICATED")
    return authenticator.authenticate_identity(authorization)


def get_workspace_service(request: Request) -> WorkspaceService:
    return request.app.state.workspace_service


def private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def required_revision(value: str | None) -> int:
    if value is None:
        raise KnoraError("MISSING_WORKSPACE_REVISION")
    try:
        revision = int(value.strip('"'))
        if revision < 0:
            raise ValueError
        return revision
    except ValueError as exc:
        raise KnoraError("INVALID_WORKSPACE_REVISION") from exc


@router.post("/resolve", response_model=ResolutionResponse)
def resolve_workspace(
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    hint_id: str | None = Body(default=None, embed=True),
) -> ResolutionResponse:
    private(response)
    result = service.resolve(identity, hint_id)
    return ResolutionResponse(
        state=result.state.value,
        workspace=WorkspaceResponse.model_validate(result.workspace) if result.workspace else None,
    )


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    archived: bool | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WorkspaceListResponse:
    private(response)
    page = service.list(identity, archived, cursor, limit)
    return WorkspaceListResponse(
        items=[WorkspaceResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.post("", status_code=201, response_model=WorkspaceResponse)
def create_workspace(
    payload: WorkspaceNameRequest,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkspaceView:
    if idempotency_key is None:
        raise KnoraError("MISSING_IDEMPOTENCY_KEY")
    private(response)
    return service.create(identity, payload.name, idempotency_key)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def read_workspace(
    workspace_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceView:
    private(response)
    return service.read(identity, workspace_id)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def rename_workspace(
    workspace_id: str,
    payload: WorkspaceNameRequest,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> WorkspaceView:
    private(response)
    return service.rename(identity, workspace_id, payload.name, required_revision(if_match))


@router.post("/{workspace_id}/archive", response_model=WorkspaceResponse)
def archive_workspace(
    workspace_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> WorkspaceView:
    private(response)
    return service.archive(identity, workspace_id, required_revision(if_match))


@router.post("/{workspace_id}/restore", response_model=WorkspaceResponse)
def restore_workspace(
    workspace_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> WorkspaceView:
    private(response)
    return service.restore(identity, workspace_id, required_revision(if_match))
