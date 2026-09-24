from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ValidationError

from knora.adapters.http.routes import authorize_workspace_principal
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.read import ReadTool, ReadToolCommand


class TicketLookupResponse(BaseModel):
    ticket_reference: str
    title: str
    status: str
    summary: str


router = APIRouter()


def get_read_tool(request: Request) -> ReadTool:
    return request.app.state.read_tool


def require_tools_owner_read(
    workspace_id: str,
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> WorkspacePrincipal:
    del x_api_key, authorization
    return authorize_workspace_principal(request, workspace_id, None)


@router.post(
    "/v1/workspaces/{workspace_id}/tools/ticket-lookup",
    response_model=TicketLookupResponse,
)
async def ticket_lookup(
    workspace_id: str,
    request: Request,
    principal: Annotated[WorkspacePrincipal, Depends(require_tools_owner_read)],
    read_tool: Annotated[ReadTool, Depends(get_read_tool)],
) -> TicketLookupResponse:
    try:
        payload = await request.json()
    except (UnicodeDecodeError, ValueError) as exc:
        raise KnoraError("TOOL_REQUEST_INVALID") from exc
    if not isinstance(payload, dict) or set(payload) != {"ticket_reference"} or not isinstance(
        payload.get("ticket_reference"), str
    ):
        raise KnoraError("TOOL_REQUEST_INVALID")
    reference = payload["ticket_reference"]
    assert isinstance(reference, str)
    if not reference.strip():
        raise KnoraError("TOOL_REQUEST_INVALID")
    result = read_tool.execute(ReadToolCommand(reference), principal)
    try:
        return TicketLookupResponse.model_validate(result, from_attributes=True)
    except (TypeError, ValueError, ValidationError) as error:
        raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID") from error
