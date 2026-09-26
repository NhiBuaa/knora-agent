from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, or_, select

from knora.adapters.postgres.tables import (
    ConversationCreateRequestTable,
    ConversationTable,
    WorkspaceTable,
)
from knora.conversations.types import ConversationPage, ConversationView
from knora.domain.errors import KnoraError


class PostgresConversationStore:
    """Persist owner-authorized Conversation lifecycle using short transactions."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _view(row: ConversationTable) -> ConversationView:
        return ConversationView(
            id=row.id,
            workspace_id=row.workspace_id,
            title=row.title,
            title_source=row.title_source,
            archived=row.archived,
            revision=row.revision,
            updated_at=row.updated_at,
        )

    def create(self, workspace_id: str, idempotency_key: str) -> ConversationView:
        fingerprint = hashlib.sha256(b"conversation-create-v1").hexdigest()
        with self._session_factory.begin() as session:
            workspace = session.scalar(
                select(WorkspaceTable)
                .where(WorkspaceTable.id == workspace_id)
                .with_for_update()
            )
            if workspace is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")

            request = session.scalar(
                select(ConversationCreateRequestTable).where(
                    ConversationCreateRequestTable.workspace_id == workspace_id,
                    ConversationCreateRequestTable.key == idempotency_key,
                )
            )
            if request is not None:
                if request.request_fingerprint != fingerprint:
                    raise KnoraError("IDEMPOTENCY_CONFLICT")
                existing = session.get(ConversationTable, request.conversation_id)
                assert existing is not None
                return self._view(existing)
            if workspace.archived:
                raise KnoraError("WORKSPACE_ARCHIVED")

            row = ConversationTable(
                id=str(uuid4()),
                workspace_id=workspace_id,
                title="New conversation",
                title_source="auto",
                archived=False,
                revision=0,
            )
            session.add(row)
            session.flush()
            session.add(
                ConversationCreateRequestTable(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    key=idempotency_key,
                    request_fingerprint=fingerprint,
                    conversation_id=row.id,
                )
            )
            session.flush()
            return self._view(row)

    def get(self, workspace_id: str, conversation_id: str) -> ConversationView | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ConversationTable).where(
                    ConversationTable.workspace_id == workspace_id,
                    ConversationTable.id == conversation_id,
                )
            )
            return self._view(row) if row is not None else None

    def list(
        self,
        workspace_id: str,
        archived: bool,
        cursor: str | None,
        limit: int,
    ) -> ConversationPage:
        query = select(ConversationTable).where(
            ConversationTable.workspace_id == workspace_id,
            ConversationTable.archived == archived,
        )
        if cursor is not None:
            try:
                decoded = json.loads(
                    base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
                )
                updated_at = datetime.fromisoformat(decoded[0])
                cursor_id = decoded[1]
                if not isinstance(cursor_id, str) or updated_at.tzinfo is None:
                    raise ValueError
            except (ValueError, TypeError, IndexError, KeyError) as exc:
                raise KnoraError("INVALID_CONVERSATION_CURSOR") from exc
            query = query.where(
                or_(
                    ConversationTable.updated_at < updated_at,
                    and_(
                        ConversationTable.updated_at == updated_at,
                        ConversationTable.id < cursor_id,
                    ),
                )
            )
        query = query.order_by(ConversationTable.updated_at.desc(), ConversationTable.id.desc())
        with self._session_factory() as session:
            rows = session.scalars(query.limit(limit + 1)).all()
            items = tuple(self._view(row) for row in rows[:limit])
            next_cursor = None
            if len(rows) > limit:
                last = items[-1]
                payload = json.dumps([last.updated_at.isoformat(), last.id]).encode("utf-8")
                next_cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
            return ConversationPage(items, next_cursor)

    def mutate(
        self,
        workspace_id: str,
        conversation_id: str,
        expected_revision: int,
        *,
        title: str | None = None,
        archived: bool | None = None,
    ) -> ConversationView:
        with self._session_factory.begin() as session:
            workspace = session.scalar(
                select(WorkspaceTable)
                .where(WorkspaceTable.id == workspace_id)
                .with_for_update()
            )
            if workspace is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")
            if workspace.archived:
                raise KnoraError("WORKSPACE_ARCHIVED")
            row = session.scalar(
                select(ConversationTable)
                .where(
                    ConversationTable.workspace_id == workspace_id,
                    ConversationTable.id == conversation_id,
                )
                .with_for_update()
            )
            if row is None:
                raise KnoraError("CONVERSATION_NOT_FOUND")
            if row.revision != expected_revision:
                raise KnoraError("REVISION_CONFLICT")
            if title is not None:
                row.title = title
                row.title_source = "manual"
            if archived is not None:
                row.archived = archived
            row.revision += 1
            session.flush()
            return self._view(row)
