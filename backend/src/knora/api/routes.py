from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from knora.adapters.http.routes import authenticate_principal
from knora.answering.interface import QuestionCommand, QuestionEvent
from knora.answering.module import AnswerQuestion
from knora.api.m5_e2e_faults import M5E2EFaultScenario
from knora.api.question_stream import format_sse_event
from knora.api.schemas import QuestionRequest, QuestionResponse
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError

router = APIRouter()
m5_e2e_router = APIRouter()


class M5E2EFaultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=100)
    scenario: M5E2EFaultScenario


def get_answer_question(request: Request) -> AnswerQuestion:
    return request.app.state.answer_question


@m5_e2e_router.post("/m5-e2e/faults", include_in_schema=False)
async def arm_m5_e2e_fault(
    payload: M5E2EFaultRequest,
    request: Request,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
) -> dict[str, str]:
    if principal.workspace_id != payload.workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    principal.require_capability("questions:ask")
    request.app.state.m5_e2e_fault_controller.arm(
        principal=principal,
        scenario=payload.scenario,
    )
    return {"status": "armed"}


@router.post("/v1/questions", response_model=QuestionResponse)
async def answer_question(
    payload: QuestionRequest,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    service: Annotated[AnswerQuestion, Depends(get_answer_question)],
) -> QuestionResponse:
    if principal.workspace_id != payload.workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    principal.require_capability("questions:ask")
    result = await service.execute(
        QuestionCommand(workspace_id=payload.workspace_id, question=payload.question),
        principal,
    )
    return QuestionResponse.model_validate(result, from_attributes=True)


@router.post(
    "/v1/questions/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
async def stream_question(
    payload: QuestionRequest,
    request: Request,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    service: Annotated[AnswerQuestion, Depends(get_answer_question)],
) -> StreamingResponse:
    if principal.workspace_id != payload.workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    principal.require_capability("questions:ask")
    controller = getattr(request.app.state, "m5_e2e_fault_controller", None)
    fault_scenario = controller.consume(principal=principal) if controller is not None else None

    async def event_body():
        if fault_scenario == "provider_failure":
            yield format_sse_event(
                QuestionEvent(
                    stage="failure",
                    payload={"error_code": "PROVIDER_REQUEST_FAILED"},
                    terminal=True,
                )
            )
            return
        if fault_scenario == "stream_interruption":
            yield format_sse_event(QuestionEvent(stage="started", payload={}))
            return
        async for event in service.execute_stream(
            QuestionCommand(workspace_id=payload.workspace_id, question=payload.question),
            principal,
        ):
            yield format_sse_event(event)

    return StreamingResponse(
        event_body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
