from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
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
    def __init__(self, policy: PolicyProvenance | None = None) -> None:
        self.context = ResolvedCapabilityContext(
            capability_id="create_ticket",
            capability_version="m4.2",
            capability_digest="sha256:" + "a" * 64,
            resource_kind="ticket",
            binding_id="binding-a",
            binding_version="v1",
            binding_digest="sha256:" + "b" * 64,
            policy=policy or PolicyProvenance(),
        )

    def resolve_for_proposal(self, workspace_id: str, capability_id: str):
        del workspace_id, capability_id
        return self.context


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


class PostgresExecutionAuthorizer:
    def __init__(self, authorized: bool) -> None:
        self.authorized = authorized

    def is_authorized(self, principal, proposal) -> bool:
        del principal, proposal
        return self.authorized


class PostgresProviderWriteSentinel:
    identity = "m4-76-postgres-provider-write-sentinel-v1"

    def __init__(self) -> None:
        self.create_ticket_write_count = 0

    def create_ticket(self, request) -> None:
        del request
        self.create_ticket_write_count += 1
        raise AssertionError("Issue #76 must not invoke a provider write")


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


def test_postgres_restart_reconstructs_every_projection_field_and_new_material_ids() -> None:
    workspace_id = f"m4-proposal-reconstruct-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 proposal reconstruction"))
    now = datetime(2026, 2, 1, 3, 4, 5, 678901, tzinfo=UTC)
    principal = WorkspacePrincipal(workspace_id, "caller-key")
    resolver = PostgresResolver()
    sentinel = PostgresProviderWriteSentinel()
    service = WriteProposalWorkflow(
        capability_resolver=resolver,
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
        execution_authorizer=PostgresExecutionAuthorizer(False),
        clock=lambda: now,
    )
    created = service.handle(
        ProposeWriteAction(
            "create_ticket",
            "m4r1.target.opaque",
            "Cannot sign in",
            "Customer blocked",
        ),
        principal,
        actor_context("agent-a", "model"),
    )
    approved = service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        actor_context("human-a", "human", can_approve=True),
    )

    restarted = WriteProposalWorkflow(
        capability_resolver=PostgresResolver(),
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
        execution_authorizer=PostgresExecutionAuthorizer(False),
        clock=lambda: now,
    ).read(approved.projection.proposal_id, principal)

    for projection_field in fields(approved.projection):
        assert getattr(restarted, projection_field.name) == getattr(
            approved.projection, projection_field.name
        ), projection_field.name
    assert restarted.audit[0].payload["caller_principal_id"] == "caller-key"
    assert restarted.audit[1].payload["revision"] == 1

    title_replacement = service.handle(
        ProposeWriteAction(
            "create_ticket",
            "m4r1.target.opaque",
            "Cannot reset password",
            "Customer blocked",
        ),
        principal,
        actor_context("agent-a", "model"),
    ).projection
    target_replacement = service.handle(
        ProposeWriteAction(
            "create_ticket",
            "m4r1.target.replacement",
            "Cannot sign in",
            "Customer blocked",
        ),
        principal,
        actor_context("agent-a", "model"),
    ).projection
    policy_resolver = PostgresResolver(
        PolicyProvenance.from_semantics(
            "m4-human-approval-policy",
            "v2",
            {
                "approval_actor_kinds": ["human"],
                "execution_authority_required": True,
                "proposal_lifetime_seconds": 7200,
                "separation_of_duties": False,
            },
        )
    )
    policy_replacement = WriteProposalWorkflow(
        capability_resolver=policy_resolver,
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
        clock=lambda: now,
    ).handle(
        ProposeWriteAction(
            "create_ticket",
            "m4r1.target.opaque",
            "Cannot sign in",
            "Customer blocked",
        ),
        principal,
        actor_context("agent-a", "model"),
    ).projection

    replacements = (title_replacement, target_replacement, policy_replacement)
    assert len({approved.projection.proposal_id, *(item.proposal_id for item in replacements)}) == 4
    assert len(
        {
            approved.projection.logical_execution_id,
            *(item.logical_execution_id for item in replacements),
        }
    ) == 4
    assert all(item.state == "proposed" and item.revision == 0 for item in replacements)
    assert all(item.approval_actor_id is None for item in replacements)
    assert sentinel.identity == "m4-76-postgres-provider-write-sentinel-v1"
    assert sentinel.create_ticket_write_count == 0


@pytest.mark.parametrize(
    ("condition", "expected_stale", "expected_reason"),
    [
        ("execution_denied", False, "execution_not_authorized"),
        ("capability_id", True, "capability_identity_mismatch"),
        ("capability_version", True, "capability_version_mismatch"),
        ("capability_digest", True, "capability_digest_mismatch"),
        ("binding_id", True, "binding_identity_mismatch"),
        ("binding_version", True, "binding_version_mismatch"),
        ("binding_digest", True, "binding_digest_mismatch"),
        ("policy_id", True, "policy_identity_mismatch"),
        ("policy_version", True, "policy_version_mismatch"),
        ("policy_digest", True, "policy_digest_mismatch"),
        ("expired", False, "expired"),
    ],
)
def test_postgres_non_executable_projection_survives_restarted_composition(
    condition: str, expected_stale: bool, expected_reason: str
) -> None:
    workspace_id = f"m4-proposal-restart-{condition}-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="M4 proposal restart"))
    current = [datetime(2026, 3, 1, tzinfo=UTC)]
    principal = WorkspacePrincipal(workspace_id, "caller-key")
    initial_resolver = PostgresResolver()
    service = WriteProposalWorkflow(
        capability_resolver=initial_resolver,
        store=PostgresToolActionStore(SessionFactory),
        target_verifier=PostgresTargetVerifier(),
        execution_authorizer=PostgresExecutionAuthorizer(True),
        clock=lambda: current[0],
    )
    created = service.handle(
        ProposeWriteAction("create_ticket", "m4r1.target.opaque", "Title", "Description"),
        principal,
        actor_context("agent-a", "model"),
    )
    service.handle(
        ApproveProposal(created.projection.proposal_id, 0),
        principal,
        actor_context("human-a", "human", can_approve=True),
    )

    current_resolver = PostgresResolver()
    execution_authorized = condition != "execution_denied"
    if condition == "expired":
        current[0] = datetime(2026, 3, 2, tzinfo=UTC)
    elif condition.startswith("capability_") or condition.startswith("binding_"):
        replacement = {
            "capability_id": "create_ticket_v2",
            "capability_version": "m4.3",
            "capability_digest": "sha256:" + "f" * 64,
            "binding_id": "binding-b",
            "binding_version": "v2",
            "binding_digest": "sha256:" + "f" * 64,
        }[condition]
        current_resolver.context = replace(current_resolver.context, **{condition: replacement})
    elif condition.startswith("policy_"):
        current_policy = current_resolver.context.policy
        policy_id = "policy-v2" if condition == "policy_id" else current_policy.policy_id
        policy_version = (
            "v2" if condition == "policy_version" else current_policy.policy_version
        )
        snapshot = dict(current_policy.snapshot)
        if condition == "policy_digest":
            snapshot["execution_authority_required"] = False
        current_resolver.context = replace(
            current_resolver.context,
            policy=PolicyProvenance.from_semantics(policy_id, policy_version, snapshot),
        )

    def composition() -> WriteProposalWorkflow:
        resolver = PostgresResolver()
        resolver.context = current_resolver.context
        return WriteProposalWorkflow(
            capability_resolver=resolver,
            store=PostgresToolActionStore(SessionFactory),
            target_verifier=PostgresTargetVerifier(),
            execution_authorizer=PostgresExecutionAuthorizer(execution_authorized),
            clock=lambda: current[0],
        )

    before = composition().read(created.projection.proposal_id, principal)
    after = composition().read(created.projection.proposal_id, principal)

    assert after == before
    assert after.state == "approved"
    assert after.stale is expected_stale
    assert after.executable is False
    assert after.non_executable_reason == expected_reason
    assert [event.event_type for event in after.audit] == ["proposed", "approved"]


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
