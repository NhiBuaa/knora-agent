"""Owner-scoped Conversation and Turn HTTP contracts."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from knora.access.identity import Identity
from knora.adapters.http.workspaces import require_identity
from knora.conversations.service import ConversationService
from knora.conversations.types import ConversationView, TurnAdmission, TurnView
from knora.domain.errors import KnoraError

router = APIRouter(prefix="/v1/workspaces")


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    title: str
    title_source: str
    archived: bool
    revision: int
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    next_cursor: str | None


class ConversationNameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


class ConversationTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str
    document_id: str
    document_version_id: str
    source_key: str
    source_name: str
    heading_path: tuple[str, ...]
    start_line: int
    end_line: int
    excerpt: str
    content_checksum: str
    page_start: int | None = None
    page_end: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


class QuestionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision: str
    answer: str | None
    citations: tuple[CitationResponse, ...]
    refusal_reason: str | None
    trace_id: str
    workspace_id: str


class TurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sequence: int
    question: str
    status: str
    stage: str | None
    result: QuestionResultResponse | None
    error_code: str | None


class TurnListResponse(BaseModel):
    items: list[TurnResponse]
    next_cursor: str | None


def get_conversation_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


def private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def required_revision(value: str | None) -> int:
    if value is None:
        raise KnoraError("MISSING_CONVERSATION_REVISION")
    try:
        revision = int(value.strip('"'))
        if revision < 0:
            raise ValueError
        return revision
    except ValueError as exc:
        raise KnoraError("INVALID_CONVERSATION_REVISION") from exc


def _turn_response(turn: TurnView) -> TurnResponse:
    return TurnResponse.model_validate(turn)


@router.post(
    "/{workspace_id}/conversations",
    status_code=201,
    response_model=ConversationResponse,
)
def create_conversation(
    workspace_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConversationView:
    if idempotency_key is None:
        raise KnoraError("MISSING_IDEMPOTENCY_KEY")
    private(response)
    return service.create(identity, workspace_id, idempotency_key)


@router.get(
    "/{workspace_id}/conversations",
    response_model=ConversationListResponse,
)
def list_conversations(
    workspace_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    archived: bool = False,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationListResponse:
    private(response)
    page = service.list(identity, workspace_id, archived, cursor, limit)
    return ConversationListResponse(
        items=[ConversationResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def read_conversation(
    workspace_id: str,
    conversation_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationView:
    private(response)
    return service.read(identity, workspace_id, conversation_id)


@router.patch(
    "/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def rename_conversation(
    workspace_id: str,
    conversation_id: str,
    payload: ConversationNameRequest,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ConversationView:
    private(response)
    return service.rename(
        identity,
        workspace_id,
        conversation_id,
        payload.title,
        required_revision(if_match),
    )


@router.post(
    "/{workspace_id}/conversations/{conversation_id}/archive",
    response_model=ConversationResponse,
)
def archive_conversation(
    workspace_id: str,
    conversation_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ConversationView:
    private(response)
    return service.archive(
        identity,
        workspace_id,
        conversation_id,
        required_revision(if_match),
    )


@router.post(
    "/{workspace_id}/conversations/{conversation_id}/restore",
    response_model=ConversationResponse,
)
def restore_conversation(
    workspace_id: str,
    conversation_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ConversationView:
    private(response)
    return service.restore(
        identity,
        workspace_id,
        conversation_id,
        required_revision(if_match),
    )


@router.get(
    "/{workspace_id}/conversations/{conversation_id}/turns",
    response_model=TurnListResponse,
)
def list_turns(
    workspace_id: str,
    conversation_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TurnListResponse:
    private(response)
    page = service.list_turns(identity, workspace_id, conversation_id, cursor, limit)
    return TurnListResponse(
        items=[_turn_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/{workspace_id}/conversations/{conversation_id}/turns/{turn_id}",
    response_model=TurnResponse,
)
def get_turn(
    workspace_id: str,
    conversation_id: str,
    turn_id: str,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> TurnResponse:
    private(response)
    return _turn_response(service.get_turn(identity, workspace_id, conversation_id, turn_id))


@router.post(
    "/{workspace_id}/conversations/{conversation_id}/turns",
    status_code=202,
    response_model=TurnResponse,
    responses={
        200: {"model": TurnResponse, "description": "Terminal idempotent replay."},
        409: {
            "description": "CONVERSATION_BUSY; retry after the indicated delay.",
            "headers": {
                "Retry-After": {
                    "description": "Minimum seconds to wait before submitting another Turn.",
                    "schema": {"type": "integer", "example": 2},
                }
            },
        },
    },
)
def submit_turn(
    workspace_id: str,
    conversation_id: str,
    payload: ConversationTurnRequest,
    response: Response,
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TurnResponse:
    if idempotency_key is None:
        raise KnoraError("MISSING_IDEMPOTENCY_KEY")
    private(response)
    admission: TurnAdmission = service.submit_turn(
        identity,
        workspace_id,
        conversation_id,
        idempotency_key,
        payload.question,
    )
    if admission.replayed and admission.turn.status in {
        "answered",
        "refused",
        "failed",
        "interrupted",
    }:
        response.status_code = 200
    else:
        response.status_code = 202
    response.headers["Location"] = (
        f"/v1/workspaces/{workspace_id}/conversations/{conversation_id}/turns/"
        f"{admission.turn.id}"
    )
    return _turn_response(admission.turn)
