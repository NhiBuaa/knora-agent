from __future__ import annotations

from knora.access.identity import Identity
from knora.adapters.postgres.tables import WorkspaceIdentityTable, WorkspaceTable


class PostgresWorkspaceStore:
    """Read ownership from PostgreSQL for Workspace authorization."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def owner_for(self, workspace_id: str) -> Identity | None:
        with self._session_factory() as session:
            row = session.query(WorkspaceIdentityTable).join(
                WorkspaceTable,
                WorkspaceTable.owner_identity_id == WorkspaceIdentityTable.id,
            ).filter(WorkspaceTable.id == workspace_id).one_or_none()
            if row is None:
                return None
            return Identity(issuer=row.issuer, subject=row.subject)
