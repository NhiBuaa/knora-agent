from dataclasses import dataclass
from datetime import datetime

from knora.answering.interface import QuestionResult


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
class ConversationPage:
    items: tuple[ConversationView, ...]
    next_cursor: str | None = None
