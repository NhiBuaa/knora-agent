from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel

from knora.adapters.http.routes import authenticate_principal
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


@router.post(
    "/v1/workspaces/{workspace_id}/tools/ticket-lookup",
    response_model=TicketLookupResponse,
)
def ticket_lookup(
    workspace_id: str,
    payload: Annotated[dict[str, object], Body(...)],
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    read_tool: Annotated[ReadTool, Depends(get_read_tool)],
) -> TicketLookupResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    if set(payload) != {"ticket_reference"} or not isinstance(
        payload.get("ticket_reference"), str
    ):
        raise KnoraError("TOOL_REQUEST_INVALID")
    reference = payload["ticket_reference"]
    assert isinstance(reference, str)
    if not reference.strip():
        raise KnoraError("TOOL_REQUEST_INVALID")
    result = read_tool.execute(ReadToolCommand(reference), principal)
    return TicketLookupResponse.model_validate(result, from_attributes=True)
