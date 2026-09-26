from __future__ import annotations

from typing import Protocol

from knora.answering.interface import QuestionResult
from knora.conversations.types import (
    ClaimedTurn,
    ConversationPage,
    ConversationView,
    ExpiredTurnObservation,
    TurnAdmission,
    TurnPage,
    TurnView,
)


class ConversationStore(Protocol):
    """Persist Workspace-scoped Conversation lifecycle state."""

    def create(self, workspace_id: str, idempotency_key: str) -> ConversationView: ...

    def get(self, workspace_id: str, conversation_id: str) -> ConversationView | None: ...

    def list(
        self,
        workspace_id: str,
        archived: bool,
        cursor: str | None,
        limit: int,
    ) -> ConversationPage: ...

    def mutate(
        self,
        workspace_id: str,
        conversation_id: str,
        expected_revision: int,
        *,
        title: str | None = None,
        archived: bool | None = None,
    ) -> ConversationView: ...

    def submit_turn(
        self,
        workspace_id: str,
        conversation_id: str,
        idempotency_key: str,
        question: str,
        auto_title: str,
        request_fingerprint: str,
    ) -> TurnAdmission: ...

    def claim_next_turn(
        self, worker_id: str, workspace_id: str | None = None
    ) -> ClaimedTurn | None: ...

    def heartbeat_turn(self, turn_id: str, claim_token: str) -> bool: ...

    def set_turn_stage(self, turn_id: str, claim_token: str, stage: str) -> bool: ...

    def finish_turn(
        self,
        turn_id: str,
        claim_token: str,
        result: QuestionResult | None,
        error_code: str | None,
    ) -> bool: ...

    def expired_turns(self, limit: int = 100) -> tuple[ExpiredTurnObservation, ...]: ...

    def apply_expired_turn_recovery(
        self, observation: ExpiredTurnObservation, result: QuestionResult | None
    ) -> bool: ...

    def get_turn(
        self, workspace_id: str, conversation_id: str, turn_id: str
    ) -> TurnView | None: ...

    def list_turns(
        self,
        workspace_id: str,
        conversation_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> TurnPage: ...


class ConversationResultReader(Protocol):
    """Recover a validated result already persisted for one Conversation Turn."""

    def read_conversation_result(
        self, workspace_id: str, turn_id: str
    ) -> QuestionResult | None: ...
