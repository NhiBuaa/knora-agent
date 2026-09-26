from __future__ import annotations

from hashlib import sha256

from knora.access.identity import Identity
from knora.access.workspace_authorization import WorkspaceAuthorizer
from knora.conversations.ports import ConversationStore
from knora.conversations.types import (
    ConversationPage,
    ConversationView,
    TurnAdmission,
    TurnPage,
    TurnView,
)
from knora.domain.errors import KnoraError


def title_from_question(question: str) -> str:
    return " ".join(question.split())[:80] or "New conversation"


class ConversationService:
    """Own Conversation lifecycle policy; stores own persistence transactions."""

    def __init__(
        self,
        *,
        store: ConversationStore,
        workspace_authorizer: WorkspaceAuthorizer,
    ) -> None:
        self._store = store
        self._workspace_authorizer = workspace_authorizer

    def create(
        self, identity: Identity, workspace_id: str, idempotency_key: str
    ) -> ConversationView:
        if not idempotency_key or len(idempotency_key) > 255:
            raise KnoraError("INVALID_IDEMPOTENCY_KEY")
        self._authorize(identity, workspace_id)
        return self._store.create(workspace_id, idempotency_key)

    def read(
        self, identity: Identity, workspace_id: str, conversation_id: str
    ) -> ConversationView:
        self._authorize_owner(identity, workspace_id)
        conversation = self._store.get(workspace_id, conversation_id)
        if conversation is None:
            raise KnoraError("CONVERSATION_NOT_FOUND")
        return conversation

    def list(
        self,
        identity: Identity,
        workspace_id: str,
        archived: bool = False,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ConversationPage:
        if limit < 1 or limit > 100:
            raise KnoraError("INVALID_CONVERSATION_LIMIT")
        self._authorize_owner(identity, workspace_id)
        return self._store.list(workspace_id, archived, cursor, limit)

    def get_turn(
        self,
        identity: Identity,
        workspace_id: str,
        conversation_id: str,
        turn_id: str,
    ) -> TurnView:
        self._authorize_owner(identity, workspace_id)
        turn = self._store.get_turn(workspace_id, conversation_id, turn_id)
        if turn is None:
            raise KnoraError("CONVERSATION_TURN_NOT_FOUND")
        return turn

    def list_turns(
        self,
        identity: Identity,
        workspace_id: str,
        conversation_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> TurnPage:
        if limit < 1 or limit > 100:
            raise KnoraError("INVALID_TURN_LIMIT")
        self._authorize_owner(identity, workspace_id)
        conversation = self._store.get(workspace_id, conversation_id)
        if conversation is None:
            raise KnoraError("CONVERSATION_NOT_FOUND")
        return self._store.list_turns(workspace_id, conversation_id, cursor, limit)

    def rename(
        self,
        identity: Identity,
        workspace_id: str,
        conversation_id: str,
        title: str,
        expected_revision: int,
    ) -> ConversationView:
        normalized = title.strip()
        if not normalized or len(normalized) > 120:
            raise KnoraError("INVALID_CONVERSATION_TITLE")
        self._authorize(identity, workspace_id)
        return self._store.mutate(
            workspace_id, conversation_id, expected_revision, title=normalized
        )

    def archive(
        self, identity: Identity, workspace_id: str, conversation_id: str, expected_revision: int
    ) -> ConversationView:
        self._authorize(identity, workspace_id)
        return self._store.mutate(
            workspace_id, conversation_id, expected_revision, archived=True
        )

    def restore(
        self, identity: Identity, workspace_id: str, conversation_id: str, expected_revision: int
    ) -> ConversationView:
        self._authorize(identity, workspace_id)
        return self._store.mutate(
            workspace_id, conversation_id, expected_revision, archived=False
        )

    def submit_turn(
        self,
        identity: Identity,
        workspace_id: str,
        conversation_id: str,
        idempotency_key: str,
        question: str,
    ) -> TurnAdmission:
        if not idempotency_key or len(idempotency_key) > 255:
            raise KnoraError("INVALID_IDEMPOTENCY_KEY")
        normalized_question = " ".join(question.split())
        if not normalized_question:
            raise KnoraError("INVALID_QUESTION")
        self._authorize(identity, workspace_id)
        auto_title = title_from_question(question)
        request_fingerprint = sha256(normalized_question.encode("utf-8")).hexdigest()
        return self._store.submit_turn(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            question=question,
            auto_title=auto_title,
            request_fingerprint=request_fingerprint,
        )

    def _authorize(self, identity: Identity, workspace_id: str) -> None:
        self._workspace_authorizer.authorize(identity, workspace_id, "questions:ask")

    def _authorize_owner(self, identity: Identity, workspace_id: str) -> None:
        self._workspace_authorizer.authorize(identity, workspace_id, None)
