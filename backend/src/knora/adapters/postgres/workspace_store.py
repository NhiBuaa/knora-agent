from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert

from knora.access.identity import Identity
from knora.adapters.postgres.tables import (
    WorkspaceCreateRequestTable,
    WorkspaceIdentityTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.workspaces.types import (
    ResolutionState,
    WorkspacePage,
    WorkspaceResolution,
    WorkspaceView,
)


class PostgresWorkspaceStore:
    """Persist owner-scoped Workspace lifecycle with serialized identity creation."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def owner_for(self, workspace_id: str) -> Identity | None:
        with self._session_factory() as session:
            row = (
                session.query(WorkspaceIdentityTable)
                .join(
                    WorkspaceTable,
                    WorkspaceTable.owner_identity_id == WorkspaceIdentityTable.id,
                )
                .filter(WorkspaceTable.id == workspace_id)
                .one_or_none()
            )
            if row is None:
                return None
            return Identity(issuer=row.issuer, subject=row.subject)

    @staticmethod
    def _view(row: WorkspaceTable) -> WorkspaceView:
        return WorkspaceView(row.id, row.name, row.archived, row.revision, row.created_at)

    @staticmethod
    def _identity_id(session, identity: Identity) -> str | None:
        return session.scalar(
            select(WorkspaceIdentityTable.id).where(
                WorkspaceIdentityTable.issuer == identity.issuer,
                WorkspaceIdentityTable.subject == identity.subject,
            )
        )

    @classmethod
    def _lock_identity(cls, session, identity: Identity) -> str:
        session.execute(
            insert(WorkspaceIdentityTable)
            .values(id=str(uuid4()), issuer=identity.issuer, subject=identity.subject)
            .on_conflict_do_nothing(index_elements=["issuer", "subject"])
        )
        row = session.scalar(
            select(WorkspaceIdentityTable)
            .where(
                WorkspaceIdentityTable.issuer == identity.issuer,
                WorkspaceIdentityTable.subject == identity.subject,
            )
            .with_for_update()
        )
        assert row is not None
        return row.id

    @staticmethod
    def _ordered(owner_id: str):
        return (
            select(WorkspaceTable)
            .where(WorkspaceTable.owner_identity_id == owner_id)
            .order_by(WorkspaceTable.created_at, WorkspaceTable.id)
        )

    def get(self, identity: Identity, workspace_id: str) -> WorkspaceView | None:
        with self._session_factory() as session:
            owner_id = self._identity_id(session, identity)
            if owner_id is None:
                return None
            row = session.scalar(
                select(WorkspaceTable).where(
                    WorkspaceTable.owner_identity_id == owner_id,
                    WorkspaceTable.id == workspace_id,
                )
            )
            return self._view(row) if row is not None else None

    def resolve(self, identity: Identity, hint_id: str | None = None) -> WorkspaceResolution:
        with self._session_factory.begin() as session:
            owner_id = self._lock_identity(session, identity)
            workspaces = session.scalars(self._ordered(owner_id)).all()
            if not workspaces:
                row = WorkspaceTable(
                    id=str(uuid4()),
                    name="My Workspace",
                    owner_identity_id=owner_id,
                    archived=False,
                    revision=0,
                )
                session.add(row)
                session.flush()
                return WorkspaceResolution(ResolutionState.ACTIVE, self._view(row))
            active = [row for row in workspaces if not row.archived]
            if not active:
                return WorkspaceResolution(ResolutionState.NO_ACTIVE_WORKSPACE, None)
            selected = next((row for row in active if row.id == hint_id), active[0])
            return WorkspaceResolution(ResolutionState.ACTIVE, self._view(selected))

    def create(self, identity: Identity, name: str, idempotency_key: str) -> WorkspaceView:
        fingerprint = hashlib.sha256(name.encode("utf-8")).hexdigest()
        with self._session_factory.begin() as session:
            owner_id = self._lock_identity(session, identity)
            record = session.scalar(
                select(WorkspaceCreateRequestTable).where(
                    WorkspaceCreateRequestTable.identity_id == owner_id,
                    WorkspaceCreateRequestTable.operation == "create_workspace",
                    WorkspaceCreateRequestTable.key == idempotency_key,
                )
            )
            if record is not None:
                if record.request_fingerprint != fingerprint:
                    raise KnoraError("IDEMPOTENCY_CONFLICT")
                existing = session.get(WorkspaceTable, record.workspace_id)
                assert existing is not None
                return self._view(existing)
            row = WorkspaceTable(
                id=str(uuid4()),
                name=name,
                owner_identity_id=owner_id,
                archived=False,
                revision=0,
            )
            session.add(row)
            session.flush()
            session.add(
                WorkspaceCreateRequestTable(
                    id=str(uuid4()),
                    identity_id=owner_id,
                    operation="create_workspace",
                    key=idempotency_key,
                    request_fingerprint=fingerprint,
                    workspace_id=row.id,
                )
            )
            return self._view(row)

    def list(
        self,
        identity: Identity,
        archived: bool | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> WorkspacePage:
        with self._session_factory() as session:
            owner_id = self._identity_id(session, identity)
            if owner_id is None:
                return WorkspacePage(())
            query = self._ordered(owner_id)
            if archived is not None:
                query = query.where(WorkspaceTable.archived == archived)
            if cursor is not None:
                try:
                    decoded = json.loads(
                        base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
                    )
                    created_at = datetime.fromisoformat(decoded[0])
                    cursor_id = decoded[1]
                    if not isinstance(cursor_id, str) or created_at.tzinfo is None:
                        raise ValueError
                except (ValueError, TypeError, IndexError, KeyError) as exc:
                    raise KnoraError("INVALID_WORKSPACE_CURSOR") from exc
                query = query.where(
                    or_(
                        WorkspaceTable.created_at > created_at,
                        and_(
                            WorkspaceTable.created_at == created_at, WorkspaceTable.id > cursor_id
                        ),
                    )
                )
            rows = session.scalars(query.limit(limit + 1)).all()
            items = tuple(self._view(row) for row in rows[:limit])
            next_cursor = None
            if len(rows) > limit:
                last = items[-1]
                payload = json.dumps([last.created_at.isoformat(), last.id]).encode("utf-8")
                next_cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
            return WorkspacePage(items, next_cursor)

    def mutate(
        self,
        identity: Identity,
        workspace_id: str,
        expected_revision: int,
        *,
        archived: bool | None = None,
        name: str | None = None,
    ) -> WorkspaceView:
        with self._session_factory.begin() as session:
            owner_id = self._identity_id(session, identity)
            if owner_id is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")
            row = session.scalar(
                select(WorkspaceTable)
                .where(
                    WorkspaceTable.owner_identity_id == owner_id,
                    WorkspaceTable.id == workspace_id,
                )
                .with_for_update()
            )
            if row is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")
            if row.revision != expected_revision:
                raise KnoraError("REVISION_CONFLICT")
            if row.archived and name is not None:
                raise KnoraError("WORKSPACE_ARCHIVED")
            if archived is not None and archived == row.archived and name is None:
                return self._view(row)
            if archived is not None:
                row.archived = archived
            if name is not None:
                row.name = name
            row.revision += 1
            session.flush()
            return self._view(row)
