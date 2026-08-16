from __future__ import annotations

import multiprocessing
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from queue import Empty
from types import SimpleNamespace

import pytest
from evals.runners.evaluation_ownership import (
    EvaluationOwnershipError,
    SqliteEvaluationOwnershipStore,
)
from evals.runners.milestone_3 import (
    EvaluationEnvironmentBinding,
    EvaluationEnvironmentSeal,
    ObservationFailure,
    SourceBinding,
)


@dataclass
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value

    def advance(self, duration: timedelta) -> None:
        self.value += duration


def _clock() -> MutableClock:
    return MutableClock(datetime(2026, 8, 16, 4, 0, tzinfo=UTC))


def _binding() -> EvaluationEnvironmentBinding:
    return EvaluationEnvironmentBinding(
        dataset_manifest_identity="m3-dataset-v1",
        corpus_manifest_identity="m3-corpus-v1",
        chunk_set_provenance_id="set-1",
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        source_bindings=(SourceBinding("support/a", "version-1", "set-1"),),
    )


def _manifest() -> SimpleNamespace:
    return SimpleNamespace(
        version="m3-corpus-v1",
        workspace_id="workspace",
        chunk_set_id="set-1",
        chunks=frozenset({"support/a#0"}),
    )


def _corpus() -> SimpleNamespace:
    return SimpleNamespace(
        workspace_id="workspace",
        documents=(
            SimpleNamespace(
                source_key="support/a",
                document_version_id="version-1",
                chunk_set_id="set-1",
                chunk_references=("support/a#0",),
            ),
        ),
    )


def _store(path, clock: MutableClock) -> SqliteEvaluationOwnershipStore:
    return SqliteEvaluationOwnershipStore(path=path, clock=clock)


def _hold_process_ownership(path: str, ready, release) -> None:
    store = SqliteEvaluationOwnershipStore(path=path)
    capability = store.acquire(
        run_id="run-process", owner_id="process-a", lease_duration=timedelta(seconds=30)
    )
    ready.put(capability.fencing_version)
    release.wait(timeout=10)
    store.release(capability)


def test_durable_store_rejects_second_live_owner_and_preserves_owner(tmp_path) -> None:
    clock = _clock()
    path = tmp_path / "ownership.sqlite3"
    first = _store(path, clock)
    second = _store(path, clock)

    first_capability = first.acquire(
        run_id="run-1", owner_id="A", lease_duration=timedelta(seconds=10)
    )

    with pytest.raises(EvaluationOwnershipError, match="EVALUATION_SEAL_ACQUIRE_FAILED"):
        second.acquire(run_id="run-1", owner_id="B", lease_duration=timedelta(seconds=10))

    snapshot = first.snapshot(run_id="run-1")
    assert snapshot.owner_id == "A"
    assert snapshot.fencing_version == first_capability.fencing_version


def test_independent_processes_share_the_exclusive_lease(tmp_path) -> None:
    context = multiprocessing.get_context("spawn")
    path = tmp_path / "ownership.sqlite3"
    ready = context.Queue()
    release = context.Event()
    process = context.Process(
        target=_hold_process_ownership,
        args=(str(path), ready, release),
    )
    process.start()
    try:
        assert ready.get(timeout=10) == 1
        second = SqliteEvaluationOwnershipStore(path=path)
        with pytest.raises(EvaluationOwnershipError, match="EVALUATION_SEAL_ACQUIRE_FAILED"):
            second.acquire(
                run_id="run-process", owner_id="process-b", lease_duration=timedelta(seconds=30)
            )
    except Empty as error:
        raise AssertionError("independent owner process did not acquire the lease") from error
    finally:
        release.set()
        process.join(timeout=10)
    assert process.exitcode == 0


def test_expiry_transfer_fences_stale_mutation_and_release_then_reacquires(tmp_path) -> None:
    clock = _clock()
    path = tmp_path / "ownership.sqlite3"
    seal_a = EvaluationEnvironmentSeal(
        ownership_store=_store(path, clock), owner_id="A", lease_duration=timedelta(seconds=10)
    )
    seal_b = EvaluationEnvironmentSeal(
        ownership_store=_store(path, clock), owner_id="B", lease_duration=timedelta(seconds=10)
    )

    first_capability = seal_a.acquire(run_id="run-1")
    seal_a.capture_preflight(binding=_binding(), corpus=_corpus(), manifest=_manifest())
    clock.advance(timedelta(seconds=11))

    second_capability = seal_b.acquire(run_id="run-1")
    assert second_capability.fencing_version > first_capability.fencing_version
    seal_b.capture_preflight(binding=_binding(), corpus=_corpus(), manifest=_manifest())

    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_FENCED"):
        seal_a.capture_preflight(binding=_binding(), corpus=_corpus(), manifest=_manifest())
    stale_mutation_operation = seal_a.last_operation_id
    seal_b.verify_unchanged(binding=_binding(), corpus=_corpus(), manifest=_manifest())
    after_mutation = seal_b.ownership_snapshot()

    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_FENCED"):
        seal_a.release()
    stale_release_operation = seal_a.last_operation_id
    seal_b.verify_unchanged(binding=_binding(), corpus=_corpus(), manifest=_manifest())
    after_release = seal_b.ownership_snapshot()

    assert stale_mutation_operation
    assert stale_release_operation
    assert stale_mutation_operation != stale_release_operation
    assert after_mutation.owner_id == "B"
    assert after_mutation.fencing_version == second_capability.fencing_version
    assert after_release == after_mutation

    seal_b.release()
    reacquired = seal_a.acquire(run_id="run-1")

    assert reacquired.fencing_version > second_capability.fencing_version
    assert seal_a.ownership_snapshot().owner_id == "A"


def test_renewal_extends_lease_without_changing_fencing_version(tmp_path) -> None:
    clock = _clock()
    path = tmp_path / "ownership.sqlite3"
    store = _store(path, clock)

    capability = store.acquire(
        run_id="run-renew", owner_id="A", lease_duration=timedelta(seconds=10)
    )
    clock.advance(timedelta(seconds=9))

    renewed = store.renew(capability, lease_duration=timedelta(seconds=10))

    assert renewed.owner_id == capability.owner_id
    assert renewed.fencing_version == capability.fencing_version
    assert renewed.lease_expires_at == clock.value + timedelta(seconds=10)
    clock.advance(timedelta(seconds=9))
    store.assert_current(renewed)

    clock.advance(timedelta(seconds=2))
    with pytest.raises(EvaluationOwnershipError, match="EVALUATION_SEAL_FENCED"):
        store.renew(renewed, lease_duration=timedelta(seconds=10))


def test_lease_heartbeat_renews_until_stopped(tmp_path) -> None:
    clock = _clock()
    path = tmp_path / "ownership.sqlite3"
    store = _store(path, clock)
    seal = EvaluationEnvironmentSeal(
        ownership_store=store, owner_id="A", lease_duration=timedelta(seconds=10)
    )
    capability = seal.acquire(run_id="run-heartbeat")
    heartbeat = seal.start_heartbeat(interval=timedelta(milliseconds=10))
    try:
        for _ in range(12):
            clock.advance(timedelta(seconds=1))
            time.sleep(0.02)
        store.assert_current(capability)
        heartbeat.raise_if_failed()
    finally:
        heartbeat.stop()
        seal.release()


def test_readiness_owner_and_binding_combinations_fail_closed(tmp_path) -> None:
    clock = _clock()
    path = tmp_path / "ownership.sqlite3"
    seal = EvaluationEnvironmentSeal(
        ownership_store=_store(path, clock), owner_id="A", lease_duration=timedelta(seconds=10)
    )

    seal.acquire(run_id="run-1")
    mismatched_binding = EvaluationEnvironmentBinding(
        dataset_manifest_identity="m3-dataset-v1",
        corpus_manifest_identity="wrong-corpus",
        chunk_set_provenance_id="set-1",
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        source_bindings=_binding().source_bindings,
    )
    with pytest.raises(ObservationFailure, match="CORPUS_CLOSURE_MISMATCH"):
        seal.capture_preflight(
            binding=mismatched_binding, corpus=_corpus(), manifest=_manifest()
        )

    invalid_owner = EvaluationEnvironmentSeal(
        ownership_store=_store(path, clock),
        owner_id="invalid",
        lease_duration=timedelta(seconds=10),
    )
    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_REQUIRED"):
        invalid_owner.capture_preflight(binding=_binding(), corpus=_corpus(), manifest=_manifest())

    valid_owner = EvaluationEnvironmentSeal(
        ownership_store=_store(path, clock), owner_id="valid", lease_duration=timedelta(seconds=10)
    )
    clock.advance(timedelta(seconds=11))
    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_FENCED"):
        seal.capture_preflight(binding=_binding(), corpus=_corpus(), manifest=_manifest())

    valid_owner.acquire(run_id="run-1")
    environment = valid_owner.capture_preflight(
        binding=_binding(), corpus=_corpus(), manifest=_manifest()
    )
    assert environment.binding == _binding()
    valid_owner.release()
