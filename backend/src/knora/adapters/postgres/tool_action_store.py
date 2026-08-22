from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.tables import (
    ToolActionAuditEventTable,
    ToolProposalDecisionTable,
    ToolProposalTable,
)
from knora.domain.errors import KnoraError
from knora.tools.proposals import (
    ActorContext,
    AuditProjection,
    _DecisionResult,
    _StoredProposal,
)


class PostgresToolActionStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def create_proposal(self, proposal: _StoredProposal) -> _StoredProposal:
        try:
            with self._session_factory.begin() as session:
                session.add(self._proposal_row(proposal))
                session.flush()
                session.add(
                    ToolActionAuditEventTable(
                        id=str(uuid4()),
                        proposal_id=proposal.proposal_id,
                        workspace_id=proposal.workspace_id,
                        sequence=1,
                        event_type="proposed",
                        actor_id=proposal.proposal_actor_id,
                        actor_kind=proposal.proposal_actor_kind,
                        payload={"caller_principal_id": proposal.caller_principal_id},
                    )
                )
            stored = self.read_proposal(proposal.workspace_id, proposal.proposal_id)
            assert stored is not None
            return stored
        except IntegrityError as error:
            raise KnoraError("TOOL_REQUEST_INVALID") from error
        except SQLAlchemyError as error:
            raise KnoraError("PERSISTENCE_OPERATION_FAILED") from error

    def read_proposal(self, workspace_id: str, proposal_id: str) -> _StoredProposal | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ToolProposalTable).where(
                    ToolProposalTable.id == proposal_id,
                    ToolProposalTable.workspace_id == workspace_id,
                )
            )
            return None if row is None else self._to_stored(session, row)

    def decide_proposal(
        self,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        decision: str,
        actor: ActorContext,
        reason_code: str | None,
    ) -> _DecisionResult:
        with self._session_factory.begin() as session:
            changed = session.execute(
                update(ToolProposalTable)
                .where(
                    ToolProposalTable.id == proposal_id,
                    ToolProposalTable.workspace_id == workspace_id,
                    ToolProposalTable.state == "proposed",
                    ToolProposalTable.revision == expected_revision,
                )
                .values(
                    state=decision,
                    revision=expected_revision + 1,
                    decision_actor_id=actor.actor_id,
                    decision_actor_kind=actor.actor_kind,
                    decision_reason=reason_code,
                    updated_at=datetime.now(UTC),
                )
            )
            row = session.scalar(
                select(ToolProposalTable).where(
                    ToolProposalTable.id == proposal_id,
                    ToolProposalTable.workspace_id == workspace_id,
                )
            )
            if row is None:
                raise KnoraError("TOOL_PROPOSAL_NOT_FOUND")
            if changed.rowcount == 1:
                self._append_decision(
                    session,
                    workspace_id,
                    proposal_id,
                    expected_revision,
                    decision,
                    actor,
                    reason_code,
                )
            return _DecisionResult(changed.rowcount == 1, self._to_stored(session, row))

    @staticmethod
    def _proposal_row(proposal: _StoredProposal) -> ToolProposalTable:
        return ToolProposalTable(
            id=proposal.proposal_id,
            workspace_id=proposal.workspace_id,
            state=proposal.state,
            revision=proposal.revision,
            capability_id=proposal.capability_id,
            capability_version=proposal.capability_version,
            capability_digest=proposal.capability_digest,
            binding_id=proposal.binding_id,
            binding_version=proposal.binding_version,
            binding_digest=proposal.binding_digest,
            policy_id=proposal.policy_id,
            policy_version=proposal.policy_version,
            policy_digest=proposal.policy_digest,
            policy_snapshot=dict(proposal.policy_snapshot),
            target_reference=proposal.target_reference,
            target_reference_digest=proposal.target_reference_digest,
            resource_kind=proposal.resource_kind,
            parameters=dict(proposal.parameters),
            parameters_digest=proposal.parameters_digest,
            request_fingerprint=proposal.request_fingerprint,
            caller_principal_id=proposal.caller_principal_id,
            caller_key_id=proposal.caller_key_id,
            proposal_actor_id=proposal.proposal_actor_id,
            proposal_actor_kind=proposal.proposal_actor_kind,
            logical_execution_id=proposal.logical_execution_id,
            expires_at=proposal.expires_at,
        )

    @staticmethod
    def _append_decision(
        session: Session,
        workspace_id: str,
        proposal_id: str,
        expected_revision: int,
        decision: str,
        actor: ActorContext,
        reason_code: str | None,
    ) -> None:
        session.add(
            ToolProposalDecisionTable(
                id=str(uuid4()),
                proposal_id=proposal_id,
                workspace_id=workspace_id,
                decision=decision,
                expected_revision=expected_revision,
                resulting_revision=expected_revision + 1,
                actor_id=actor.actor_id,
                actor_kind=actor.actor_kind,
                reason_code=reason_code,
            )
        )
        sequence = session.scalar(
            select(ToolActionAuditEventTable.sequence)
            .where(ToolActionAuditEventTable.proposal_id == proposal_id)
            .order_by(ToolActionAuditEventTable.sequence.desc())
            .limit(1)
        ) or 0
        session.add(
            ToolActionAuditEventTable(
                id=str(uuid4()),
                proposal_id=proposal_id,
                workspace_id=workspace_id,
                sequence=sequence + 1,
                event_type=decision,
                actor_id=actor.actor_id,
                actor_kind=actor.actor_kind,
                payload={"reason_code": reason_code, "revision": expected_revision + 1},
            )
        )

    @staticmethod
    def _to_stored(session: Session, row: ToolProposalTable) -> _StoredProposal:
        audits = session.scalars(
            select(ToolActionAuditEventTable)
            .where(ToolActionAuditEventTable.proposal_id == row.id)
            .order_by(ToolActionAuditEventTable.sequence)
        ).all()
        return _StoredProposal(
            proposal_id=row.id,
            workspace_id=row.workspace_id,
            state=row.state,
            revision=row.revision,
            capability_id=row.capability_id,
            capability_version=row.capability_version,
            capability_digest=row.capability_digest,
            binding_id=row.binding_id,
            binding_version=row.binding_version,
            binding_digest=row.binding_digest,
            policy_id=row.policy_id,
            policy_version=row.policy_version,
            policy_digest=row.policy_digest,
            policy_snapshot=row.policy_snapshot,
            target_reference=row.target_reference,
            target_reference_digest=row.target_reference_digest,
            resource_kind=row.resource_kind,
            parameters=row.parameters,
            parameters_digest=row.parameters_digest,
            request_fingerprint=row.request_fingerprint,
            caller_principal_id=row.caller_principal_id,
            caller_key_id=row.caller_key_id,
            proposal_actor_id=row.proposal_actor_id,
            proposal_actor_kind=row.proposal_actor_kind,
            logical_execution_id=row.logical_execution_id,
            expires_at=row.expires_at,
            decision_actor_id=row.decision_actor_id,
            decision_actor_kind=row.decision_actor_kind,
            decision_reason=row.decision_reason,
            audit=tuple(
                AuditProjection(a.sequence, a.event_type, a.actor_id, a.actor_kind, a.payload)
                for a in audits
            ),
        )
