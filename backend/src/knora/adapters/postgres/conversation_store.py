from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select

from knora.adapters.postgres.tables import (
    ConversationCreateRequestTable,
    ConversationTable,
    ConversationTurnTable,
    WorkspaceAdmissionTable,
    WorkspaceTable,
)
from knora.answering.interface import CitationProjection, QuestionResult
from knora.conversations.types import (
    ClaimedTurn,
    ConversationPage,
    ConversationView,
    ExpiredTurnObservation,
    TurnAdmission,
    TurnPage,
    TurnView,
)
from knora.domain.errors import KnoraError
from knora.workspaces.ports import WorkspaceAdmission

_TURN_LEASE = timedelta(seconds=60)
_TURN_EXECUTION_DEADLINE = timedelta(seconds=120)
_TURN_PAGE_DEFAULT = 50
_TURN_PAGE_MAX = 100


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

    @staticmethod
    def _question_result(data: dict | None) -> QuestionResult | None:
        if data is None:
            return None
        citations = tuple(
            CitationProjection(
                **{
                    **citation,
                    "heading_path": tuple(citation.get("heading_path", ())),
                }
            )
            for citation in data["citations"]
        )
        return QuestionResult(
            decision=data["decision"],
            answer=data["answer"],
            citations=citations,
            refusal_reason=data["refusal_reason"],
            trace_id=data["trace_id"],
            workspace_id=data["workspace_id"],
        )

    @classmethod
    def _turn_view(cls, row: ConversationTurnTable) -> TurnView:
        return TurnView(
            id=row.id,
            conversation_id=row.conversation_id,
            sequence=row.sequence,
            question=row.question,
            status=row.status,
            stage=row.stage,
            result=cls._question_result(row.result),
            error_code=row.error_code,
        )

    @staticmethod
    def _admission(row: WorkspaceAdmissionTable) -> WorkspaceAdmission:
        return WorkspaceAdmission(
            id=row.id,
            workspace_id=row.workspace_id,
            operation=row.operation,
            operation_id=row.operation_id,
            admitted_at=row.admitted_at,
        )

    @staticmethod
    def _database_now(session) -> datetime:
        return session.scalar(select(func.clock_timestamp()))

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

    def submit_turn(
        self,
        workspace_id: str,
        conversation_id: str,
        idempotency_key: str,
        question: str,
        auto_title: str,
        request_fingerprint: str,
    ) -> TurnAdmission:
        if not idempotency_key or len(idempotency_key) > 255:
            raise KnoraError("INVALID_IDEMPOTENCY_KEY")
        if not question.strip():
            raise KnoraError("INVALID_QUESTION")
        if len(request_fingerprint) != 64:
            raise KnoraError("INVALID_REQUEST_FINGERPRINT")

        with self._session_factory.begin() as session:
            workspace = session.scalar(
                select(WorkspaceTable)
                .where(WorkspaceTable.id == workspace_id)
                .with_for_update()
            )
            if workspace is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")
            conversation = session.scalar(
                select(ConversationTable)
                .where(
                    ConversationTable.workspace_id == workspace_id,
                    ConversationTable.id == conversation_id,
                )
                .with_for_update()
            )
            if conversation is None:
                raise KnoraError("CONVERSATION_NOT_FOUND")

            existing = session.scalar(
                select(ConversationTurnTable)
                .where(
                    ConversationTurnTable.workspace_id == workspace_id,
                    ConversationTurnTable.conversation_id == conversation_id,
                    ConversationTurnTable.idempotency_key == idempotency_key,
                )
                .with_for_update()
            )
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise KnoraError("IDEMPOTENCY_CONFLICT")
                return TurnAdmission(self._turn_view(existing), replayed=True)
            if workspace.archived:
                raise KnoraError("WORKSPACE_ARCHIVED")
            if conversation.archived:
                raise KnoraError("CONVERSATION_ARCHIVED")

            active_turn_id = session.scalar(
                select(ConversationTurnTable.id)
                .where(
                    ConversationTurnTable.workspace_id == workspace_id,
                    ConversationTurnTable.conversation_id == conversation_id,
                    ConversationTurnTable.status.in_(("queued", "processing")),
                )
                .limit(1)
            )
            if active_turn_id is not None:
                raise KnoraError("CONVERSATION_BUSY")

            last_sequence = session.scalar(
                select(func.max(ConversationTurnTable.sequence)).where(
                    ConversationTurnTable.workspace_id == workspace_id,
                    ConversationTurnTable.conversation_id == conversation_id,
                )
            )
            sequence = (last_sequence or 0) + 1
            turn = ConversationTurnTable(
                id=str(uuid4()),
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                sequence=sequence,
                question=question,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                status="queued",
            )
            admission = WorkspaceAdmissionTable(
                id=str(uuid4()),
                workspace_id=workspace_id,
                operation="conversation_turn",
                operation_id=turn.id,
            )
            session.add_all((turn, admission))
            if sequence == 1 and conversation.title_source == "auto":
                conversation.title = auto_title
            conversation.updated_at = func.now()
            session.flush()
            return TurnAdmission(self._turn_view(turn), replayed=False)

    def claim_next_turn(
        self, worker_id: str, workspace_id: str | None = None
    ) -> ClaimedTurn | None:
        if not worker_id or len(worker_id) > 100:
            raise KnoraError("INVALID_CONVERSATION_WORKER_ID")
        with self._session_factory.begin() as session:
            query = select(ConversationTurnTable).where(
                ConversationTurnTable.status == "queued"
            )
            if workspace_id is not None:
                query = query.where(ConversationTurnTable.workspace_id == workspace_id)
            turn = session.scalar(
                query.order_by(ConversationTurnTable.created_at, ConversationTurnTable.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if turn is None:
                return None

            now = self._database_now(session)
            admission_row = session.scalar(
                select(WorkspaceAdmissionTable)
                .where(
                    WorkspaceAdmissionTable.workspace_id == turn.workspace_id,
                    WorkspaceAdmissionTable.operation == "conversation_turn",
                    WorkspaceAdmissionTable.operation_id == turn.id,
                    WorkspaceAdmissionTable.terminal_at.is_(None),
                )
                .with_for_update()
            )
            if admission_row is None:
                raise KnoraError("CONVERSATION_ADMISSION_MISSING")

            claim_token = str(uuid4())
            deadline = now + _TURN_EXECUTION_DEADLINE
            turn.status = "processing"
            turn.worker_id = worker_id
            turn.claim_token = claim_token
            turn.lease_expires_at = min(now + _TURN_LEASE, deadline)
            turn.execution_deadline_at = deadline
            session.flush()
            return ClaimedTurn(
                turn=self._turn_view(turn),
                workspace_id=turn.workspace_id,
                worker_id=worker_id,
                claim_token=claim_token,
                lease_expires_at=turn.lease_expires_at,
                execution_deadline_at=deadline,
                workspace_admission=self._admission(admission_row),
            )

    def heartbeat_turn(self, turn_id: str, claim_token: str) -> bool:
        with self._session_factory.begin() as session:
            turn = session.scalar(
                select(ConversationTurnTable)
                .where(
                    ConversationTurnTable.id == turn_id,
                    ConversationTurnTable.status == "processing",
                    ConversationTurnTable.claim_token == claim_token,
                )
                .with_for_update()
            )
            if turn is None:
                return False
            now = self._database_now(session)
            if turn.lease_expires_at <= now or turn.execution_deadline_at <= now:
                return False
            turn.lease_expires_at = min(now + _TURN_LEASE, turn.execution_deadline_at)
            session.flush()
            return True

    def set_turn_stage(self, turn_id: str, claim_token: str, stage: str) -> bool:
        if stage not in {"retrieving", "selecting_evidence", "generating"}:
            raise KnoraError("INVALID_TURN_STAGE")
        with self._session_factory.begin() as session:
            turn = session.scalar(
                select(ConversationTurnTable)
                .where(
                    ConversationTurnTable.id == turn_id,
                    ConversationTurnTable.status == "processing",
                    ConversationTurnTable.claim_token == claim_token,
                )
                .with_for_update()
            )
            if turn is None:
                return False
            now = self._database_now(session)
            if turn.lease_expires_at <= now or turn.execution_deadline_at <= now:
                return False
            turn.stage = stage
            session.flush()
            return True

    def finish_turn(
        self,
        turn_id: str,
        claim_token: str,
        result: QuestionResult | None,
        error_code: str | None,
    ) -> bool:
        if result is None and not error_code:
            raise ValueError("a terminal Turn requires a result or safe error code")
        if result is not None and error_code is not None:
            raise ValueError("a validated result cannot also carry an error code")
        if result is not None and result.decision not in {"ANSWER", "REFUSAL"}:
            raise KnoraError("INVALID_TURN_RESULT")

        with self._session_factory.begin() as session:
            turn = session.scalar(
                select(ConversationTurnTable)
                .where(
                    ConversationTurnTable.id == turn_id,
                    ConversationTurnTable.status == "processing",
                    ConversationTurnTable.claim_token == claim_token,
                )
                .with_for_update()
            )
            if turn is None:
                return False
            now = self._database_now(session)
            if turn.lease_expires_at <= now or turn.execution_deadline_at <= now:
                return False
            if result is not None and result.workspace_id != turn.workspace_id:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")

            if result is None:
                turn.status = (
                    "interrupted"
                    if error_code == "EXECUTION_OUTCOME_UNKNOWN"
                    else "failed"
                )
                turn.result = None
                turn.stage = "failure"
            else:
                turn.status = "answered" if result.decision == "ANSWER" else "refused"
                turn.result = asdict(result)
                turn.stage = "final_validated" if result.decision == "ANSWER" else "refusal"
            turn.error_code = error_code
            turn.worker_id = None
            turn.claim_token = None
            turn.lease_expires_at = None
            turn.execution_deadline_at = None

            admission = session.scalar(
                select(WorkspaceAdmissionTable)
                .where(
                    WorkspaceAdmissionTable.workspace_id == turn.workspace_id,
                    WorkspaceAdmissionTable.operation == "conversation_turn",
                    WorkspaceAdmissionTable.operation_id == turn.id,
                    WorkspaceAdmissionTable.terminal_at.is_(None),
                )
                .with_for_update()
            )
            if admission is None:
                raise KnoraError("CONVERSATION_ADMISSION_MISSING")
            admission.terminal_at = now
            session.flush()
            return True

    def expired_turns(self, limit: int = 100) -> tuple[ExpiredTurnObservation, ...]:
        if limit < 1 or limit > 1000:
            raise KnoraError("INVALID_EXPIRED_TURN_LIMIT")
        with self._session_factory.begin() as session:
            candidates = session.scalars(
                select(ConversationTurnTable)
                .where(
                    ConversationTurnTable.status == "processing",
                    or_(
                        ConversationTurnTable.lease_expires_at <= func.clock_timestamp(),
                        ConversationTurnTable.execution_deadline_at <= func.clock_timestamp(),
                    ),
                )
                .order_by(ConversationTurnTable.id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
            observations = []
            for turn in candidates:
                now = self._database_now(session)
                if (
                    turn.lease_expires_at > now
                    and turn.execution_deadline_at > now
                ):
                    continue
                observations.append(
                    ExpiredTurnObservation(
                        turn_id=turn.id,
                        workspace_id=turn.workspace_id,
                        conversation_id=turn.conversation_id,
                        claim_token=turn.claim_token,
                        observed_lease_expires_at=turn.lease_expires_at,
                        observed_execution_deadline_at=turn.execution_deadline_at,
                    )
                )
            return tuple(observations)

    def apply_expired_turn_recovery(
        self,
        observation: ExpiredTurnObservation,
        result: QuestionResult | None,
    ) -> bool:
        if result is not None:
            if result.workspace_id != observation.workspace_id:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")
            if result.decision not in {"ANSWER", "REFUSAL"}:
                raise KnoraError("INVALID_TURN_RESULT")
        with self._session_factory.begin() as session:
            turn = session.scalar(
                select(ConversationTurnTable)
                .where(
                    ConversationTurnTable.id == observation.turn_id,
                    ConversationTurnTable.workspace_id == observation.workspace_id,
                    ConversationTurnTable.conversation_id == observation.conversation_id,
                    ConversationTurnTable.status == "processing",
                    ConversationTurnTable.claim_token == observation.claim_token,
                    ConversationTurnTable.lease_expires_at
                    == observation.observed_lease_expires_at,
                    ConversationTurnTable.execution_deadline_at
                    == observation.observed_execution_deadline_at,
                )
                .with_for_update()
            )
            if turn is None:
                return False
            now = self._database_now(session)
            if turn.lease_expires_at > now and turn.execution_deadline_at > now:
                return False
            if result is None:
                turn.status = "interrupted"
                turn.stage = "failure"
                turn.result = None
                turn.error_code = "EXECUTION_OUTCOME_UNKNOWN"
            else:
                turn.status = "answered" if result.decision == "ANSWER" else "refused"
                turn.stage = "final_validated" if result.decision == "ANSWER" else "refusal"
                turn.result = asdict(result)
                turn.error_code = None
            turn.worker_id = None
            turn.claim_token = None
            turn.lease_expires_at = None
            turn.execution_deadline_at = None
            admission = session.scalar(
                select(WorkspaceAdmissionTable)
                .where(
                    WorkspaceAdmissionTable.workspace_id == observation.workspace_id,
                    WorkspaceAdmissionTable.operation == "conversation_turn",
                    WorkspaceAdmissionTable.operation_id == observation.turn_id,
                    WorkspaceAdmissionTable.terminal_at.is_(None),
                )
                .with_for_update()
            )
            if admission is None:
                raise KnoraError("CONVERSATION_ADMISSION_MISSING")
            admission.terminal_at = now
            session.flush()
            return True

    def get_turn(
        self, workspace_id: str, conversation_id: str, turn_id: str
    ) -> TurnView | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ConversationTurnTable).where(
                    ConversationTurnTable.workspace_id == workspace_id,
                    ConversationTurnTable.conversation_id == conversation_id,
                    ConversationTurnTable.id == turn_id,
                )
            )
            return self._turn_view(row) if row is not None else None

    def list_turns(
        self,
        workspace_id: str,
        conversation_id: str,
        cursor: str | None = None,
        limit: int = _TURN_PAGE_DEFAULT,
    ) -> TurnPage:
        if limit < 1 or limit > _TURN_PAGE_MAX:
            raise KnoraError("INVALID_TURN_LIMIT")
        before_sequence: int | None = None
        if cursor is not None:
            try:
                decoded = json.loads(
                    base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
                )
                cursor_conversation_id, before_sequence = decoded
                if (
                    cursor_conversation_id != conversation_id
                    or not isinstance(before_sequence, int)
                    or before_sequence < 1
                ):
                    raise ValueError
            except (ValueError, TypeError, IndexError, KeyError) as exc:
                raise KnoraError("INVALID_TURN_CURSOR") from exc

        query = select(ConversationTurnTable).where(
            ConversationTurnTable.workspace_id == workspace_id,
            ConversationTurnTable.conversation_id == conversation_id,
        )
        if before_sequence is not None:
            query = query.where(ConversationTurnTable.sequence < before_sequence)
        query = query.order_by(ConversationTurnTable.sequence.desc())
        with self._session_factory() as session:
            rows = session.scalars(query.limit(limit + 1)).all()
            selected = rows[:limit]
            items = tuple(self._turn_view(row) for row in reversed(selected))
            next_cursor = None
            if len(rows) > limit:
                first = items[0]
                payload = json.dumps([conversation_id, first.sequence]).encode("utf-8")
                next_cursor = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
            return TurnPage(items, next_cursor)
