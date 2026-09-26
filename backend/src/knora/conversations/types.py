from dataclasses import dataclass
from datetime import datetime

from knora.answering.interface import QuestionResult
from knora.workspaces.ports import WorkspaceAdmission


@dataclass(frozen=True, slots=True)
class ConversationView:
    id: str
    workspace_id: str
    title: str
    title_source: str
    archived: bool
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TurnView:
    id: str
    conversation_id: str
    sequence: int
    question: str
    status: str
    stage: str | None
    result: QuestionResult | None
    error_code: str | None


@dataclass(frozen=True, slots=True)
class TurnAdmission:
    turn: TurnView
    replayed: bool


@dataclass(frozen=True, slots=True)
class ClaimedTurn:
    turn: TurnView
    workspace_id: str
    worker_id: str
    claim_token: str
    lease_expires_at: datetime
    execution_deadline_at: datetime
    workspace_admission: WorkspaceAdmission


@dataclass(frozen=True, slots=True)
class ExpiredTurnObservation:
    turn_id: str
    workspace_id: str
    conversation_id: str
    claim_token: str
    observed_lease_expires_at: datetime
    observed_execution_deadline_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationPage:
    items: tuple[ConversationView, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class TurnPage:
    items: tuple[TurnView, ...]
    next_cursor: str | None = None
