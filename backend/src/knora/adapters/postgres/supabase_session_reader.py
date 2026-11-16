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

    def is_active(self, subject: str, session_id: str) -> bool:
        if not subject or not session_id:
            return False

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
                return row is not None
        except SQLAlchemyError as exc:
            raise KnoraError("AUTH_PROVIDER_UNAVAILABLE") from exc
