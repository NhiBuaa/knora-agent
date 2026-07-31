from typing import Annotated

from fastapi import APIRouter, Depends, Request

from knora.api.schemas import HealthResponse, QuestionRequest, QuestionResponse
from knora.application.answer_question import AnswerQuestion

router = APIRouter()


def get_answer_question(request: Request) -> AnswerQuestion:
    return request.app.state.answer_question


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="knora-agent")


@router.post("/v1/questions", response_model=QuestionResponse)
async def answer_question(
    payload: QuestionRequest,
    service: Annotated[AnswerQuestion, Depends(get_answer_question)],
) -> QuestionResponse:
    result = await service.execute(
        question=payload.question,
        workspace_id=payload.workspace_id,
    )
    return QuestionResponse.model_validate(result, from_attributes=True)
