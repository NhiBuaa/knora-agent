from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from knora.adapters.http.routes import authorize_workspace_principal
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.api.question_stream import format_sse_event
from knora.api.schemas import QuestionRequest, QuestionResponse

router = APIRouter()


def get_answer_question(request: Request) -> AnswerQuestion:
    return request.app.state.answer_question


@router.post("/v1/questions", response_model=QuestionResponse)
async def answer_question(
    payload: QuestionRequest,
    request: Request,
    service: Annotated[AnswerQuestion, Depends(get_answer_question)],
) -> QuestionResponse:
    principal = authorize_workspace_principal(request, payload.workspace_id, "questions:ask")
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
    service: Annotated[AnswerQuestion, Depends(get_answer_question)],
) -> StreamingResponse:
    principal = authorize_workspace_principal(request, payload.workspace_id, "questions:ask")

    async def event_body():
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
