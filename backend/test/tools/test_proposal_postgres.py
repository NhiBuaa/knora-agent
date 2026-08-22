from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
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
    AuthorityProvenance,
    PolicyProvenance,
    ProposalApproved,
    ProposalRejected,
    ProposeWriteAction,
    RejectProposal,
    ResolvedCapabilityContext,
    VerifiedProposalTarget,
    WriteProposalWorkflow,
)


class PostgresResolver:
    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        del workspace_id
        return ResolvedCapabilityContext(
            capability_id=capability_id,
            capability_version="m4.2",
            capability_digest="sha256:" + "a" * 64,
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:" + "b" * 64,
            policy=PolicyProvenance(),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )


class PostgresTargetVerifier:
    def verify_for_proposal(self, workspace_id, capability, target_reference):
        return VerifiedProposalTarget(
            reference=target_reference,
            reference_digest="sha256:" + "c" * 64,
            reference_id="reference-76-postgres",
            workspace_id=workspace_id,
            capability_id=capability.capability_id,
            capability_version=capability.capability_version,
            binding_id=capability.binding_id,
            binding_version=capability.binding_version,
            binding_digest=capability.binding_digest,
            resource_kind=capability.resource_kind,
            resource_identity_digest="sha256:" + "d" * 64,
            resource_claims_digest="sha256:" + "e" * 64,
        )


def actor_context(actor_id: str, actor_kind: str, *, can_approve: bool = False) -> ActorContext:
    return ActorContext(
        actor_id,
        actor_kind,
        authority=AuthorityProvenance.from_semantics(
            f"{actor_kind}-identity-authority", "v1", {"actor_kinds": [actor_kind]}
        ),
        approval_authority=(
            AuthorityProvenance.from_semantics(
                "workspace-approval-authority", "v1", {"role": "approver"}
            )
            if can_approve
            else None
        ),
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
        actor_context("agent-a", "model"),
    )
    approved = service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        actor_context("human-a", "human", can_approve=True),
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
    assert decisions[0].authority_id == "workspace-approval-authority"
    assert decisions[0].authority_digest == approved.projection.approval_authority_digest
    assert proposal.proposal_actor_authority_id == "model-identity-authority"
    assert proposal.decision_authority_id == "workspace-approval-authority"
    assert [event.event_type for event in audits] == ["proposed", "approved"]
    assert approved.projection.audit[-1].event_type == "approved"

    material_mutations = {
        "workspace_id": "other-workspace",
        "capability_id": "other-capability",
        "capability_version": "other-version",
        "capability_digest": "sha256:" + "f" * 64,
        "binding_id": "other-binding",
        "binding_version": "other-version",
        "binding_digest": "sha256:" + "f" * 64,
        "policy_id": "other-policy",
        "policy_version": "other-version",
        "policy_digest": "sha256:" + "f" * 64,
        "policy_snapshot": '{"changed":true}',
        "target_reference": "other-reference",
        "target_reference_digest": "sha256:" + "f" * 64,
        "target_reference_id": "other-reference-id",
        "target_resource_identity_digest": "sha256:" + "f" * 64,
        "target_resource_claims_digest": "sha256:" + "f" * 64,
        "resource_kind": "other-resource",
        "parameters": '{"title":"changed"}',
        "parameters_digest": "sha256:" + "f" * 64,
        "request_fingerprint": "sha256:" + "f" * 64,
        "caller_principal_id": "other-principal",
        "caller_key_id": "other-key",
        "proposal_actor_id": "other-actor",
        "proposal_actor_kind": "system",
        "proposal_actor_authority_id": "other-authority",
        "proposal_actor_authority_version": "other-version",
        "proposal_actor_authority_digest": "sha256:" + "f" * 64,
        "logical_execution_id": str(uuid4()),
        "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        "expires_at": datetime(2031, 1, 1, tzinfo=UTC),
    }
    for column, value in material_mutations.items():
        assignment = (
            f"{column}=CAST(:value AS jsonb)"
            if column in {"policy_snapshot", "parameters"}
            else f"{column}=:value"
        )
        with pytest.raises(
            Exception, match="material fields are immutable"
        ), SessionFactory.begin() as session:
            session.execute(
                text(f"UPDATE tool_proposals SET {assignment} WHERE id=:id"),
                {"id": proposal.id, "value": value},
            )
    decision_projection_mutations = {
        "state": "rejected",
        "revision": 0,
        "decision_actor_id": "changed-actor",
        "decision_actor_kind": "model",
        "decision_authority_id": "changed-authority",
        "decision_authority_version": "changed-version",
        "decision_authority_digest": "sha256:" + "f" * 64,
        "decision_reason": "other",
        "decision_at": datetime(2031, 1, 1, tzinfo=UTC),
    }
    for column, value in decision_projection_mutations.items():
        with pytest.raises(
            Exception, match="decision projection is immutable"
        ), SessionFactory.begin() as session:
            session.execute(
                text(f"UPDATE tool_proposals SET {column}=:value WHERE id=:id"),
                {"id": proposal.id, "value": value},
            )
    for statement, message in (
        (
            "UPDATE tool_proposal_decisions SET actor_id='changed' WHERE proposal_id=:id",
            "decision is immutable",
        ),
        (
            "DELETE FROM tool_proposal_decisions WHERE proposal_id=:id",
            "decision is immutable",
        ),
        (
            "UPDATE tool_action_audit_events SET actor_id='changed' WHERE proposal_id=:id",
            "audit is append-only",
        ),
        (
            "DELETE FROM tool_action_audit_events WHERE proposal_id=:id",
            "audit is append-only",
        ),
    ):
        with pytest.raises(Exception, match=message), SessionFactory.begin() as session:
            session.execute(text(statement), {"id": proposal.id})


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
        actor_context("agent-a", "model"),
    )
    command = ApproveProposal(created.projection.proposal_id, 0)
    service.handle(command, principal, actor_context("human-a", "human", can_approve=True))

    loser = service.handle(
        command, principal, actor_context("human-b", "human", can_approve=True)
    )
    assert isinstance(loser, AlreadyDecided)
    assert loser.projection.state == "approved"
    assert loser.projection.revision == 1


def test_postgres_concurrent_approve_reject_has_one_atomic_winner() -> None:
    for iteration in range(5):
        workspace_id = f"m4-proposal-race-{iteration}-{uuid4()}"
        with SessionFactory.begin() as session:
            session.add(WorkspaceTable(id=workspace_id, name="M4 proposal race"))
        service = WriteProposalWorkflow(
            capability_resolver=PostgresResolver(),
            store=PostgresToolActionStore(SessionFactory),
            target_verifier=PostgresTargetVerifier(),
        )
        principal = WorkspacePrincipal(workspace_id, "caller-key")
        created = service.handle(
            ProposeWriteAction(
                "create_ticket", "m4r1.target.opaque", "Title", "Description"
            ),
            principal,
            actor_context("agent-a", "model"),
        )
        barrier = Barrier(2)

        def decide(
            command,
            actor_id,
            *,
            gate=barrier,
            workflow=service,
            workspace_principal=principal,
        ):
            gate.wait()
            return workflow.handle(
                command,
                workspace_principal,
                actor_context(actor_id, "human", can_approve=True),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            approve = executor.submit(
                decide,
                ApproveProposal(created.projection.proposal_id, 0),
                "human-approve",
            )
            reject = executor.submit(
                decide,
                RejectProposal(created.projection.proposal_id, 0, "other"),
                "human-reject",
            )
            outcomes = (approve.result(), reject.result())

        assert sum(isinstance(item, (ProposalApproved, ProposalRejected)) for item in outcomes) == 1
        assert sum(isinstance(item, AlreadyDecided) for item in outcomes) == 1
        winner = next(
            item for item in outcomes if isinstance(item, (ProposalApproved, ProposalRejected))
        )
        loser = next(item for item in outcomes if isinstance(item, AlreadyDecided))
        assert loser.projection.state == winner.projection.state
        assert loser.projection.revision == 1
        with SessionFactory() as session:
            decisions = session.scalars(
                select(ToolProposalDecisionTable).where(
                    ToolProposalDecisionTable.proposal_id
                    == created.projection.proposal_id
                )
            ).all()
            audits = session.scalars(
                select(ToolActionAuditEventTable).where(
                    ToolActionAuditEventTable.proposal_id
                    == created.projection.proposal_id
                )
            ).all()
        assert len(decisions) == 1
        assert len(audits) == 2


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE tool_proposals SET state='invented' WHERE id=:id",
        "UPDATE tool_proposals SET revision=7 WHERE id=:id",
    ],
)
def test_postgres_proposal_projection_rejects_invalid_lifecycle(
    statement: str,
) -> None:
    workspace_id = f"m4-proposal-invalid-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 invalid lifecycle"))
    service = WriteProposalWorkflow(
        capability_resolver=PostgresResolver(),
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
    )
    created = service.handle(
        ProposeWriteAction("create_ticket", "m4r1.target.opaque", "Title", "Description"),
        WorkspacePrincipal(workspace_id, "caller-key"),
        actor_context("agent-a", "model"),
    )

    with pytest.raises(Exception, match="ck_tool_proposal_"), SessionFactory.begin() as session:
        session.execute(text(statement), {"id": created.projection.proposal_id})

    with SessionFactory() as session:
        constraints = set(
            session.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'tool_proposals'::regclass"
                )
            ).all()
        )
    assert {
        "ck_tool_proposal_state",
        "ck_tool_proposal_revision",
        "ck_tool_proposal_decision_projection",
        "ck_tool_proposal_actor_kind",
        "ck_tool_proposal_digests",
    } <= constraints


@pytest.mark.parametrize(
    "decision,actor_kind,reason_code,authority_digest,constraint",
    [
        (
            "invented",
            "human",
            None,
            "sha256:" + "f" * 64,
            "ck_tool_proposal_decision_value",
        ),
        (
            "approved",
            "human",
            "other",
            "sha256:" + "f" * 64,
            "ck_tool_proposal_decision_reason",
        ),
        (
            "rejected",
            "human",
            None,
            "sha256:" + "f" * 64,
            "ck_tool_proposal_decision_reason",
        ),
        (
            "approved",
            "model",
            None,
            "sha256:" + "f" * 64,
            "ck_tool_proposal_decision_actor",
        ),
        (
            "approved",
            "human",
            None,
            "sha256:placeholder",
            "ck_tool_proposal_decision_authority_digest",
        ),
    ],
)
def test_postgres_rejects_invalid_decision_taxonomy(
    decision: str,
    actor_kind: str,
    reason_code: str | None,
    authority_digest: str,
    constraint: str,
) -> None:
    workspace_id = f"m4-proposal-invalid-decision-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 invalid decision"))
    service = WriteProposalWorkflow(
        capability_resolver=PostgresResolver(),
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
    )
    created = service.handle(
        ProposeWriteAction("create_ticket", "m4r1.target.opaque", "Title", "Description"),
        WorkspacePrincipal(workspace_id, "caller-key"),
        actor_context("agent-a", "model"),
    )

    with pytest.raises(
        Exception, match="ck_tool_proposal_decision_"
    ), SessionFactory.begin() as session:
        session.execute(
            text(
                "INSERT INTO tool_proposal_decisions "
                "(id,proposal_id,workspace_id,decision,expected_revision,resulting_revision,"
                "actor_id,actor_kind,authority_id,authority_version,authority_digest,reason_code) "
                "VALUES (:id,:proposal_id,:workspace_id,:decision,0,1,'actor',:actor_kind,"
                "'authority','v1',:authority_digest,:reason_code)"
            ),
            {
                "id": str(uuid4()),
                "proposal_id": created.projection.proposal_id,
                "workspace_id": workspace_id,
                "decision": decision,
                "actor_kind": actor_kind,
                "authority_digest": authority_digest,
                "reason_code": reason_code,
            },
        )
    with SessionFactory() as session:
        constraints = set(
            session.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'tool_proposal_decisions'::regclass"
                )
            ).all()
        )
    assert constraint in constraints
