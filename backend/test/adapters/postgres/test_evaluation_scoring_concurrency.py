"""Scoring reservations and checkpoints must survive real PostgreSQL row contention."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.evaluation_runs import PostgresEvaluationRunStore
from knora.adapters.postgres.evaluation_runs_tables import EvaluationRunTable
from knora.adapters.postgres.tables import WorkspaceTable


@pytest.fixture
def scoring_store():
    from knora.infrastructure.settings import settings

    if not settings.database_url.endswith("/knora_issue110_task2"):
        pytest.skip("requires isolated knora_issue110_task2 database")
    application = f"scoring-test-{uuid4().hex}"
    engine = create_engine(
        settings.database_url,
        connect_args={"application_name": application, "options": "-c statement_timeout=10000"},
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    store = PostgresEvaluationRunStore(factory)
    run = {
        "run_id": str(uuid4()),
        "workspace_id": str(uuid4()),
        "request_digest": "a" * 64,
        "selection_digest": "b" * 64,
        "selection": {"selected_case_ids": ["answer"]},
        "profile_id": "offline",
        "binding": {},
        "execution_status": "COMPLETED",
        "quality_status": "SEMANTIC_PENDING",
        "observations": {"answer": {"status": "OBSERVED", "trace_id": "saved-trace"}},
        "report": {"quality_status": "SEMANTIC_PENDING"},
    }
    try:
        with factory.begin() as session:
            session.add(WorkspaceTable(id=run["workspace_id"], name="Scoring contention"))
        store.create(run, "source")
        yield store, factory, engine, application, run
    finally:
        with factory.begin() as session:
            session.execute(
                delete(EvaluationRunTable).where(EvaluationRunTable.run_id == run["run_id"])
            )
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == run["workspace_id"]))
        engine.dispose()


def contend(scoring_store, operation):
    _, factory, engine, application, run = scoring_store
    with ThreadPoolExecutor(max_workers=2) as workers:
        with factory.begin() as session:
            session.scalar(
                select(EvaluationRunTable)
                .where(EvaluationRunTable.run_id == run["run_id"])
                .with_for_update()
            )
            futures = [workers.submit(operation, index) for index in range(2)]
            deadline = monotonic() + 5
            while True:
                with engine.connect() as connection:
                    waiting = connection.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE application_name = :application AND wait_event_type = 'Lock'"
                        ),
                        {"application": application},
                    )
                if waiting == 2:
                    break
                assert monotonic() < deadline, "both scoring writes must contend on the saved run"
                sleep(0.01)
        return [future.result(timeout=10) for future in futures]


def batch(index, *, same_request=False):
    return {
        "id": f"batch-{index}",
        "request_id": "same" if same_request else f"request-{index}",
        "request_digest": "c" * 64,
        "status": "INDETERMINATE",
        "results": {},
    }


@pytest.mark.parametrize("same_request", [True, False])
def test_parallel_scoring_reservations_preserve_idempotency_and_other_batches(
    scoring_store, same_request
):
    store, _, _, _, run = scoring_store

    def reserve(index):
        return store.reserve_scoring_batch(
            run["workspace_id"], run["run_id"], batch(index, same_request=same_request)
        )

    results = contend(scoring_store, reserve)
    saved = store.get(run["workspace_id"], run["run_id"])
    if same_request:
        assert sorted(owned for _, owned in results) == [False, True]
        assert results[0][0] == results[1][0]
        assert saved["scoring_batches"] == [results[0][0]]
    else:
        assert all(owned for _, owned in results)
        assert {item["id"] for item in saved["scoring_batches"]} == {"batch-0", "batch-1"}
    assert saved["observations"] == run["observations"]
    assert saved["report"] == run["report"]
    assert saved["quality_status"] == "SEMANTIC_PENDING"


def test_parallel_scoring_checkpoints_keep_both_results_and_saved_qa(scoring_store):
    store, _, _, _, run = scoring_store
    for index in range(2):
        store.reserve_scoring_batch(run["workspace_id"], run["run_id"], batch(index))

    def checkpoint(index):
        completed = deepcopy(batch(index))
        completed.update(status="COMPLETED", results={"answer": {"score": index / 2}})
        return store.checkpoint_scoring_batch(run["workspace_id"], run["run_id"], completed)

    contend(scoring_store, checkpoint)
    saved = store.get(run["workspace_id"], run["run_id"])
    assert {item["id"]: item["results"] for item in saved["scoring_batches"]} == {
        "batch-0": {"answer": {"score": 0}},
        "batch-1": {"answer": {"score": 0.5}},
    }
    assert all(item["status"] == "COMPLETED" for item in saved["scoring_batches"])
    assert saved["observations"] == run["observations"]
    assert saved["report"] == run["report"]
