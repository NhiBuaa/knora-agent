from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from knora.adapters.http.routes import authenticate_principal
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.proposals import (
    ActorContext,
    AlreadyDecided,
    ApproveProposal,
    ProposeWriteAction,
    RejectProposal,
    WriteProposalWorkflow,
)

router = APIRouter()


class ActorContextProvider(Protocol):
    def resolve(self, principal: WorkspacePrincipal) -> ActorContext: ...


def get_workflow(request: Request) -> WriteProposalWorkflow:
    return request.app.state.write_proposal_workflow


def get_actor_context(
    workspace_id: str,
    request: Request,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
) -> ActorContext:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    provider: ActorContextProvider | None = request.app.state.tool_actor_context_provider
    if provider is None:
        raise KnoraError("TOOL_APPROVAL_FORBIDDEN")
    return provider.resolve(principal)


def _projection_response(projection) -> JSONResponse:
    return JSONResponse(content=jsonable_encoder(projection))


def _decision_response(result) -> JSONResponse:
    if isinstance(result, AlreadyDecided):
        return JSONResponse(
            status_code=409,
            content={
                "error": {"code": "TOOL_PROPOSAL_ALREADY_DECIDED"},
                "proposal": jsonable_encoder(result.projection),
            },
        )
    return _projection_response(result.projection)


def _validate_payload(payload: dict[str, object], fields: set[str]) -> None:
    if set(payload) != fields:
        raise KnoraError("TOOL_REQUEST_INVALID")


async def _read_payload(request: Request) -> dict[str, object]:
    try:
        payload = await request.json()
    except (UnicodeDecodeError, ValueError) as exc:
        raise KnoraError("TOOL_REQUEST_INVALID") from exc
    if not isinstance(payload, dict):
        raise KnoraError("TOOL_REQUEST_INVALID")
    return payload


@router.post("/v1/workspaces/{workspace_id}/tool-proposals")
async def create_proposal(
    workspace_id: str,
    request: Request,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    workflow: Annotated[WriteProposalWorkflow, Depends(get_workflow)],
    actor_context: Annotated[ActorContext, Depends(get_actor_context)],
) -> JSONResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    payload = await _read_payload(request)
    _validate_payload(payload, {"capability_id", "target_reference", "title", "description"})
    if not all(isinstance(payload.get(field), str) for field in payload):
        raise KnoraError("TOOL_REQUEST_INVALID")
    result = workflow.handle(
        ProposeWriteAction(
            capability_id=payload["capability_id"],  # type: ignore[arg-type]
            target_reference=payload["target_reference"],  # type: ignore[arg-type]
            title=payload["title"],  # type: ignore[arg-type]
            description=payload["description"],  # type: ignore[arg-type]
        ),
        principal,
        actor_context,
    )
    return _projection_response(result.projection)


@router.get("/v1/workspaces/{workspace_id}/tool-proposals/{proposal_id}")
def read_proposal(
    workspace_id: str,
    proposal_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    workflow: Annotated[WriteProposalWorkflow, Depends(get_workflow)],
) -> JSONResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    return _projection_response(workflow.read(proposal_id, principal))


@router.post("/v1/workspaces/{workspace_id}/tool-proposals/{proposal_id}/approve")
async def approve_proposal(
    workspace_id: str,
    proposal_id: str,
    request: Request,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    workflow: Annotated[WriteProposalWorkflow, Depends(get_workflow)],
    actor_context: Annotated[ActorContext, Depends(get_actor_context)],
) -> JSONResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    payload = await _read_payload(request)
    _validate_payload(payload, {"expected_revision"})
    if not isinstance(payload.get("expected_revision"), int) or isinstance(
        payload.get("expected_revision"), bool
    ):
        raise KnoraError("TOOL_REQUEST_INVALID")
    result = workflow.handle(
        ApproveProposal(proposal_id, payload["expected_revision"]),  # type: ignore[arg-type]
        principal,
        actor_context,
    )
    return _decision_response(result)


@router.post("/v1/workspaces/{workspace_id}/tool-proposals/{proposal_id}/reject")
async def reject_proposal(
    workspace_id: str,
    proposal_id: str,
    request: Request,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    workflow: Annotated[WriteProposalWorkflow, Depends(get_workflow)],
    actor_context: Annotated[ActorContext, Depends(get_actor_context)],
) -> JSONResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    payload = await _read_payload(request)
    _validate_payload(payload, {"expected_revision", "reason_code"})
    if (
        not isinstance(payload.get("expected_revision"), int)
        or isinstance(payload.get("expected_revision"), bool)
        or not isinstance(payload.get("reason_code"), str)
    ):
        raise KnoraError("TOOL_REQUEST_INVALID")
    result = workflow.handle(
        RejectProposal(
            proposal_id,
            payload["expected_revision"],  # type: ignore[arg-type]
            payload["reason_code"],  # type: ignore[arg-type]
        ),
        principal,
        actor_context,
    )
    return _decision_response(result)
