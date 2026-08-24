from __future__ import annotations

from datetime import timedelta
from threading import Event

from sqlalchemy import select
from test_execution_postgres import actor, prepared

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.tables import ToolActionAuditEventTable, ToolExecutionTable
from knora.tools import (
    ExecuteApprovedProposal,
    ProviderWriteIndeterminate,
    ReconciledSucceeded,
    ReconcileExecution,
)


def test_postgres_reconciliation_takes_over_a_strictly_expired_lease_before_finalizing() -> None:
    owners = iter(("worker-a", "recovery-b"))
    workflow, _, _, _, gateway, principal, approved = prepared(
        lease_duration=timedelta(milliseconds=200),
        outcome=ProviderWriteIndeterminate(),
        owner_factory=lambda: next(owners),
    )
    first = workflow.handle(
        ExecuteApprovedProposal(approved.projection.proposal_id, 1),
        principal,
        actor("executor-a", "system"),
    )
    assert first.outcome_type == "execution_indeterminate"
    Event().wait(0.3)

    result = workflow.handle(
        ReconcileExecution(approved.projection.proposal_id, 1),
        principal,
        actor("recovery-a", "system"),
    )

    assert isinstance(result, ReconciledSucceeded)
    assert gateway.observations == [("scope-a", approved.projection.logical_execution_id)]
    assert len(gateway.calls) == 1
    with SessionFactory() as session:
        execution = session.get(ToolExecutionTable, approved.projection.proposal_id)
        events = session.scalars(
            select(ToolActionAuditEventTable.event_type)
            .where(ToolActionAuditEventTable.proposal_id == approved.projection.proposal_id)
            .order_by(ToolActionAuditEventTable.sequence)
        ).all()
    assert execution is not None
    assert (execution.owner, execution.generation, execution.lifecycle) == (
        "recovery-b",
        2,
        "succeeded",
    )
    assert events[-3:] == ["execution_taken_over", "execution_observed", "succeeded"]
