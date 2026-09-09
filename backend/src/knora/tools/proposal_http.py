from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from knora.adapters.http.routes import authenticate_principal
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.tools.execution_types import (
    ExecutionFailed,
    ExecutionFenced,
    ExecutionIndeterminate,
    ExecutionInProgress,
    ExecutionSucceeded,
    ProposalNotExecutable,
    ReconciledFailed,
    ReconciledSucceeded,
    ReconciliationIndeterminate,
    ReconciliationOutcomeNotFound,
)
from knora.tools.proposal_types import ExecuteApprovedProposal, ReconcileExecution
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
    return JSONResponse(content=jsonable_encoder(_transport_value(projection)))


def _transport_value(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {
            projection_field.name: _transport_value(getattr(value, projection_field.name))
            for projection_field in fields(value)
            if not _is_private_transport_field(projection_field.name)
        }
    if isinstance(value, Mapping):
        return {
            key: _transport_value(nested)
            for key, nested in value.items()
            if not _is_private_transport_field(key)
        }
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return [_transport_value(item) for item in value]
    return value


def _is_private_transport_field(value) -> bool:
    if not isinstance(value, str):
        return False
    return value.casefold() in {
        "rejection_code",
        "provider_id",
        "provider_resource_id",
        "provider_ticket_id",
        "provider_routing_handle",
        "external_scope",
        "envelope_token",
        "secret",
        "credential",
        "credentials",
        "mac",
        "exception",
        "internal_exception",
        "raw_provider_response",
    }


def _decision_response(result) -> JSONResponse:
    if isinstance(result, AlreadyDecided):
        return JSONResponse(
            status_code=409,
            content={
                "error": {"code": "TOOL_PROPOSAL_ALREADY_DECIDED"},
                "proposal": jsonable_encoder(_transport_value(result.projection)),
            },
        )
    return _projection_response(result.projection)


def _execution_response(result) -> JSONResponse:
    if result.projection is None:
        raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID")
    proposal = jsonable_encoder(_transport_value(result.projection))
    if isinstance(result, ProposalNotExecutable):
        public_code = {
            "workspace_access_denied": "WORKSPACE_ACCESS_DENIED",
            "resource_access_denied": "TOOL_RESOURCE_ACCESS_DENIED",
            "execution_not_authorized": "TOOL_EXECUTION_NOT_AUTHORIZED",
            "invalid_tool_resource_reference": "INVALID_TOOL_RESOURCE_REFERENCE",
        }.get(result.reason_code, "TOOL_PROPOSAL_STALE")
        status = {
            "INVALID_TOOL_RESOURCE_REFERENCE": 400,
            "WORKSPACE_ACCESS_DENIED": 403,
            "TOOL_RESOURCE_ACCESS_DENIED": 403,
            "TOOL_EXECUTION_NOT_AUTHORIZED": 403,
            "TOOL_PROPOSAL_STALE": 409,
        }[public_code]
        return JSONResponse(
            status_code=status,
            content={"error": {"code": public_code}, "proposal": proposal},
        )
    status = 200
    if isinstance(result, (ExecutionFailed, ReconciledFailed)):
        if result.rejection_code == "provider_scope_denied":
            return JSONResponse(
                status_code=403,
                content={
                    "error": {"code": "TOOL_RESOURCE_ACCESS_DENIED"},
                    "proposal": proposal,
                },
            )
        if result.rejection_code == "provider_request_rejected":
            return JSONResponse(
                status_code=502,
                content={
                    "error": {"code": "TOOL_PROVIDER_REQUEST_FAILED"},
                    "proposal": proposal,
                },
            )
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "TOOL_PROVIDER_FAILURE",
                    "failure_code": result.rejection_code,
                },
                "proposal": proposal,
            },
        )
    elif isinstance(
        result,
        (
            ExecutionIndeterminate,
            ReconciliationIndeterminate,
            ReconciliationOutcomeNotFound,
        ),
    ):
        status = 202
    elif isinstance(result, (ExecutionInProgress, ExecutionFenced)):
        public_code = (
            "TOOL_PROVIDER_IDEMPOTENCY_CONFLICT"
            if isinstance(result, ExecutionInProgress)
            and result.reason_code == "provider_idempotency_conflict"
            else (
                "TOOL_EXECUTION_FENCED"
                if isinstance(result, ExecutionFenced)
                else "TOOL_EXECUTION_IN_PROGRESS"
            )
        )
        return JSONResponse(
            status_code=409,
            content={"error": {"code": public_code}, "proposal": proposal},
        )
    elif not isinstance(result, (ExecutionSucceeded, ReconciledSucceeded)):
        raise KnoraError("TOOL_PROVIDER_CONTRACT_INVALID")
    payload = _transport_value(result)
    del payload["projection"]
    payload["proposal"] = proposal
    return JSONResponse(status_code=status, content=jsonable_encoder(payload))


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


@router.post("/v1/workspaces/{workspace_id}/tool-proposals/{proposal_id}/execute")
async def execute_proposal(
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
        ExecuteApprovedProposal(
            proposal_id,
            payload["expected_revision"],  # type: ignore[arg-type]
        ),
        principal,
        actor_context,
    )
    return _execution_response(result)


@router.post("/v1/workspaces/{workspace_id}/tool-proposals/{proposal_id}/reconcile")
async def reconcile_execution(
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
    _validate_payload(payload, {"expected_lease_generation"})
    if not isinstance(payload.get("expected_lease_generation"), int) or isinstance(
        payload.get("expected_lease_generation"), bool
    ):
        raise KnoraError("TOOL_REQUEST_INVALID")
    result = workflow.handle(
        ReconcileExecution(
            proposal_id,
            payload["expected_lease_generation"],  # type: ignore[arg-type]
        ),
        principal,
        actor_context,
    )
    return _execution_response(result)
