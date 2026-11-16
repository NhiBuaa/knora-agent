from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from knora.access.identity_access import SupabaseSessionReader
from knora.domain.errors import KnoraError


class PostgresSupabaseSessionReader(SupabaseSessionReader):
    def __init__(
        self,
        session_factory: sessionmaker,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._has_managed_schema: bool | None = None

    def is_active(self, subject: str, session_id: str) -> bool:
        if not subject or not session_id:
            return False

        if self._has_managed_schema is False:
            return True

        now = self._clock()
        cutoff = now - timedelta(hours=8)

        query = text(
            """
            SELECT 1
            FROM auth.sessions s
            JOIN auth.users u ON s.user_id = u.id
            WHERE s.id::text = :session_id
              AND s.user_id::text = :subject
              AND u.deleted_at IS NULL
              AND (u.banned_until IS NULL OR u.banned_until <= :now)
              AND s.created_at >= :cutoff
            LIMIT 1;
            """
        )

        try:
            with self._session_factory() as session:
                row = session.execute(
                    query,
                    {
                        "session_id": session_id,
                        "subject": subject,
                        "now": now,
                        "cutoff": cutoff,
                    },
                ).first()
                if self._has_managed_schema is None:
                    self._has_managed_schema = True
                return row is not None
        except SQLAlchemyError as exc:
            err_str = str(exc).lower()
            orig = getattr(exc, "orig", None)
            orig_name = type(orig).__name__ if orig else ""
            if (
                orig_name == "UndefinedTable"
                or "auth.sessions" in err_str
                or "auth.users" in err_str
                or "schema auth does not exist" in err_str
                or 'relation "auth.sessions" does not exist' in err_str
            ) and (
                "does not exist" in err_str or "no such table" in err_str or "undefined" in err_str
            ):
                self._has_managed_schema = False
                return True
            raise KnoraError("AUTH_PROVIDER_UNAVAILABLE") from exc
