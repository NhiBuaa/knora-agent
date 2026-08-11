"""PostgreSQL read seams used by object lifecycle reconciliation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.tables import ObjectLifecycleWorkTable, OriginalSourceObjectTable


class PostgresClock:
    """Lifecycle clock backed by a fresh PostgreSQL wall-clock observation."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def now(self) -> datetime:
        with self._session_factory() as session:
            value = session.scalar(select(func.clock_timestamp()))
            if not isinstance(value, datetime):
                raise RuntimeError("PostgreSQL did not return an authoritative lifecycle timestamp")
            return value


class PostgresObjectReferenceResolver:
    """Authoritative Workspace-scoped retention and inconsistency lookup."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def is_authoritatively_retained(self, *, workspace_id: str, object_key: str) -> bool:
        try:
            with self._session_factory() as session:
                return (
                    session.scalar(
                        select(1).where(
                            or_(
                                exists(
                                    select(1).where(
                                        OriginalSourceObjectTable.workspace_id == workspace_id,
                                        OriginalSourceObjectTable.object_key == object_key,
                                        OriginalSourceObjectTable.deleted_at.is_(None),
                                    )
                                ),
                                exists(
                                    select(1).where(
                                        ObjectLifecycleWorkTable.workspace_id == workspace_id,
                                        ObjectLifecycleWorkTable.object_key == object_key,
                                        or_(
                                            ObjectLifecycleWorkTable.state.in_(
                                                ("queued", "processing", "retry_scheduled")
                                            ),
                                            and_(
                                                ObjectLifecycleWorkTable.artifact_class
                                                == "failed_upload_diagnostic",
                                                or_(
                                                    ObjectLifecycleWorkTable.eligible_at.is_(None),
                                                    ObjectLifecycleWorkTable.eligible_at
                                                    > func.clock_timestamp(),
                                                ),
                                            ),
                                        ),
                                    )
                                ),
                            )
                        )
                    )
                    is not None
                )
        except Exception:
            # An authoritative ownership read that cannot be completed must fail closed. The
            # reconciler will leave the object untouched and retry on a later pass.
            return True

    def inconsistent_object_keys(
        self, *, workspace_id: str, observed_object_keys: set[str]
    ) -> tuple[str, ...]:
        """Return retained database records absent from one Workspace inventory snapshot.

        A missing object-store observation is reported as an inconsistency; it is never treated as
        permission to delete the database record or to delete another object with the same key.
        A failed authoritative read returns no report so a transient database failure cannot
        manufacture reconciliation work.
        """

        try:
            with self._session_factory() as session:
                keys = session.scalars(
                    select(OriginalSourceObjectTable.object_key).where(
                        OriginalSourceObjectTable.workspace_id == workspace_id,
                        OriginalSourceObjectTable.deleted_at.is_(None),
                    )
                ).all()
        except Exception:
            return ()
        return tuple(sorted(set(keys) - observed_object_keys))
