import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.evaluation_runs import PostgresEvaluationRunStore
from knora.adapters.postgres.evaluation_runs_tables import (
    EvaluationPreflightTable,
    EvaluationRunTable,
)
from knora.domain.errors import KnoraError


def test_store_persists_idempotent_run_and_fenced_checkpoints():
    engine = create_engine("sqlite://")
    EvaluationRunTable.__table__.create(engine)
    EvaluationPreflightTable.__table__.create(engine)
    store = PostgresEvaluationRunStore(sessionmaker(bind=engine, expire_on_commit=False))
    run = {
        "run_id": "run-1",
        "workspace_id": "workspace-1",
        "request_digest": "a" * 64,
        "selection": {"selected_case_ids": ["case-1"]},
        "selection_digest": "b" * 64,
        "profile_id": "offline",
        "binding": {},
        "execution_status": "QUEUED",
        "quality_status": "UNAVAILABLE",
        "observations": {"case-1": {"status": "NOT_RUN"}},
        "report": None,
    }
    assert store.create(run, "key-1")["run_id"] == "run-1"
    assert store.create({**run, "run_id": "run-2"}, "key-1")["run_id"] == "run-1"
    with pytest.raises(KnoraError, match="EVALUATION_IDEMPOTENCY_CONFLICT"):
        store.create({**run, "run_id": "run-3", "request_digest": "c" * 64}, "key-1")
    attempt = store.claim("workspace-1", "run-1")
    assert attempt
    assert store.claim("workspace-1", "run-1") is None
    with pytest.raises(KnoraError, match="EVALUATION_ATTEMPT_STALE"):
        store.checkpoint("workspace-1", "run-1", "wrong", "case-1", {"status": "OBSERVED"})
    store.checkpoint("workspace-1", "run-1", attempt, "case-1", {"status": "OBSERVED"})
    store.finish(
        "workspace-1", "run-1", attempt, "COMPLETED", {"quality_status": "SEMANTIC_PENDING"}
    )
    saved = store.get("workspace-1", "run-1")
    assert saved["observations"]["case-1"]["status"] == "OBSERVED"
    assert saved["quality_status"] == "SEMANTIC_PENDING"
    assert store.get("other", "run-1") is None
    assert store.list("other") == []
