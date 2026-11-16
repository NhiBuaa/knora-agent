import json

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from knora.access.identity_access import BASELINE_CAPABILITIES, IdentityAccessStore
from knora.domain.errors import KnoraError


class PostgresIdentityAccessStore(IdentityAccessStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get_or_create_baseline(self, issuer: str, subject: str) -> tuple[str, ...]:
        baseline_json = json.dumps(list(BASELINE_CAPABILITIES))
        insert_stmt = text(
            """
            INSERT INTO identity_access (issuer, subject, capabilities, created_at)
            VALUES (:issuer, :subject, CAST(:capabilities AS jsonb), NOW())
            ON CONFLICT (issuer, subject) DO NOTHING;
            """
        )
        select_stmt = text(
            """
            SELECT capabilities
            FROM identity_access
            WHERE issuer = :issuer AND subject = :subject;
            """
        )
        try:
            with self._session_factory() as session:
                session.execute(
                    insert_stmt,
                    {
                        "issuer": issuer,
                        "subject": subject,
                        "capabilities": baseline_json,
                    },
                )
                session.commit()
                row = session.execute(
                    select_stmt,
                    {"issuer": issuer, "subject": subject},
                ).first()
                if row is None or row[0] is None:
                    return ()
                capabilities = row[0]
                if isinstance(capabilities, list):
                    return tuple(capabilities)
                return ()
        except SQLAlchemyError as exc:
            raise KnoraError("AUTH_PROVIDER_UNAVAILABLE") from exc
