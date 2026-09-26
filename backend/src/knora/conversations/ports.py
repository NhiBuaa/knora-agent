from __future__ import annotations

from typing import Protocol

from knora.conversations.types import ConversationPage, ConversationView


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
