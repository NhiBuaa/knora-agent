from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import (
    ToolActionAuditEventTable,
    ToolProposalDecisionTable,
    ToolProposalTable,
    WorkspaceTable,
)
from knora.adapters.postgres.tool_action_store import PostgresToolActionStore
from knora.domain.access import WorkspacePrincipal
from knora.tools import (
    ActorContext,
    AlreadyDecided,
    ApproveProposal,
    ProposeWriteAction,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)
from knora.tools.proposals import PolicyProvenance, ResolvedCapabilityContext


class PostgresResolver:
    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        del workspace_id
        return ResolvedCapabilityContext(
            capability_id=capability_id,
            capability_version="m4.2",
            capability_digest="sha256:create-ticket-v1",
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:binding-a",
            policy=PolicyProvenance(),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )


class PostgresTargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        return VerifiedProposalTarget(
            reference=target_reference,
            reference_digest="sha256:verified-target",
            workspace_id=workspace_id,
            capability_id=capability.capability_id,
            capability_version=capability.capability_version,
            binding_id=capability.binding_id,
            binding_version=capability.binding_version,
            binding_digest=capability.binding_digest,
            resource_kind=capability.resource_kind,
        )


def test_postgres_store_persists_atomic_decision_and_append_only_audit() -> None:
    workspace_id = f"m4-proposal-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 proposal"))
    service = WriteProposalWorkflow(
        capability_resolver=PostgresResolver(),
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    principal = WorkspacePrincipal(workspace_id, "caller-key")
    created = service.handle(
        ProposeWriteAction(
            "create_ticket", "m4r1.target.opaque", "Cannot sign in", "Customer blocked"
        ),
        principal,
        ActorContext("agent-a", "model"),
    )
    approved = service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        ActorContext("human-a", "human"),
    )

    with SessionFactory() as session:
        proposal = session.get(ToolProposalTable, created.projection.proposal_id)
        decisions = session.scalars(
            select(ToolProposalDecisionTable).where(
                ToolProposalDecisionTable.proposal_id == created.projection.proposal_id
            )
        ).all()
        audits = session.scalars(
            select(ToolActionAuditEventTable)
            .where(ToolActionAuditEventTable.proposal_id == created.projection.proposal_id)
            .order_by(ToolActionAuditEventTable.sequence)
        ).all()
    assert proposal.state == "approved"
    assert proposal.revision == 1
    assert len(decisions) == 1
    assert [event.event_type for event in audits] == ["proposed", "approved"]
    assert approved.projection.audit[-1].event_type == "approved"

    with pytest.raises(Exception, match="immutable"), SessionFactory.begin() as session:
        session.execute(
            text("UPDATE tool_proposals SET capability_digest='tampered' WHERE id=:id"),
            {"id": proposal.id},
        )
    with pytest.raises(Exception, match="append-only"), SessionFactory.begin() as session:
        session.execute(
            text("DELETE FROM tool_action_audit_events WHERE proposal_id=:id"),
            {"id": proposal.id},
        )


def test_postgres_decision_cas_has_one_winner() -> None:
    workspace_id = f"m4-proposal-cas-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 proposal CAS"))
    service = WriteProposalWorkflow(
        capability_resolver=PostgresResolver(),
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
    )
    principal = WorkspacePrincipal(workspace_id, "caller-key")
    created = service.handle(
        ProposeWriteAction("create_ticket", "m4r1.target.opaque", "Title", "Description"),
        principal,
        ActorContext("agent-a", "model"),
    )
    command = ApproveProposal(created.projection.proposal_id, 0)
    service.handle(command, principal, ActorContext("human-a", "human"))

    loser = service.handle(command, principal, ActorContext("human-b", "human"))
    assert isinstance(loser, AlreadyDecided)
    assert loser.projection.state == "approved"
    assert loser.projection.revision == 1
