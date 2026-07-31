from typing import Annotated

from fastapi import APIRouter, Depends, Request

from knora.adapters.http.routes import authenticate_principal
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.api.schemas import QuestionRequest, QuestionResponse
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError

router = APIRouter()


def get_answer_question(request: Request) -> AnswerQuestion:
    return request.app.state.answer_question


@router.post("/v1/questions", response_model=QuestionResponse)
async def answer_question(
    payload: QuestionRequest,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    service: Annotated[AnswerQuestion, Depends(get_answer_question)],
) -> QuestionResponse:
    if principal.workspace_id != payload.workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    result = await service.execute(
        QuestionCommand(workspace_id=payload.workspace_id, question=payload.question),
        principal,
    )
    return QuestionResponse.model_validate(result, from_attributes=True)
