from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from knora.adapters.postgres.tables import WorkspaceAdmissionTable, WorkspaceTable
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.workspaces.ports import WorkspaceAdmission


class PostgresWorkspaceAdmissionStore:
    """Serializes public mutation admission with Workspace archive transitions."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _admission(row: WorkspaceAdmissionTable) -> WorkspaceAdmission:
        return WorkspaceAdmission(
            id=row.id,
            workspace_id=row.workspace_id,
            operation=row.operation,
            operation_id=row.operation_id,
            admitted_at=row.admitted_at,
        )

    def admit(
        self,
        *,
        principal: WorkspacePrincipal,
        operation: str,
        operation_id: str,
    ) -> WorkspaceAdmission:
        if not operation or not operation_id:
            raise ValueError("operation and operation_id are required")
        try:
            with self._session_factory.begin() as session:
                workspace = session.scalar(
                    select(WorkspaceTable)
                    .where(WorkspaceTable.id == principal.workspace_id)
                    .with_for_update()
                )
                if workspace is None:
                    raise KnoraError("WORKSPACE_ACCESS_DENIED")
                existing = session.scalar(
                    select(WorkspaceAdmissionTable)
                    .where(
                        WorkspaceAdmissionTable.workspace_id == principal.workspace_id,
                        WorkspaceAdmissionTable.operation == operation,
                        WorkspaceAdmissionTable.operation_id == operation_id,
                    )
                    .with_for_update()
                )
                if existing is not None:
                    return self._admission(existing)
                if workspace.archived:
                    raise KnoraError("WORKSPACE_ARCHIVED")
                row = WorkspaceAdmissionTable(
                    id=str(uuid4()),
                    workspace_id=principal.workspace_id,
                    operation=operation,
                    operation_id=operation_id,
                )
                session.add(row)
                session.flush()
                return self._admission(row)
        except KnoraError:
            raise
        except (IntegrityError, SQLAlchemyError) as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error
