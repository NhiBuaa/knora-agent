from dataclasses import replace

import pytest
from backend.test.adapters.postgres.test_s2_submission_fence import scenario as scenario
from backend.test.adapters.postgres.test_s2_submission_fence import (
    selected_generation as selected_generation,
)

from knora.adapters.postgres.tables import IngestionJobTable, LexicalGenerationTable


def retry(scenario, key):
    return scenario.store.commit_reprocess(
        replace(
            scenario.reprocess,
            requested_config_mode="current",
            resolved_config_mode="current",
            config_source_job_id=None,
            idempotency_key=key,
        )
    )


def child(scenario, selected, status):
    row = IngestionJobTable(
        id="index-A",
        workspace_id="workspace",
        operation="lexical_index",
        content_fingerprint="index-A",
        derivation_kind="lexical_index",
        parent_ingestion_job_id=selected.job.id,
        lexical_generation_id=selected.row.id,
        status=status,
    )
    scenario.session.add(row)
    return row


@pytest.mark.parametrize("status", ["queued", "processing", "retry_scheduled"])
def test_new_key_reuses_viable_extraction_instead_of_colliding(scenario, status):
    first = retry(scenario, "first")
    scenario.session.get(IngestionJobTable, first.ingestion_job_id).status = status
    second = retry(scenario, "second")
    assert second.ingestion_job_id == first.ingestion_job_id and second.outcome == "reused"


@pytest.mark.parametrize("status", ["failed", "superseded"])
def test_failed_index_creates_fresh_extraction_and_replay_is_stable(
    scenario, selected_generation, status
):
    old_child = child(scenario, selected_generation, status)
    first = retry(scenario, "retry-index")
    assert first.outcome == "created" and first.ingestion_job_id != selected_generation.job.id
    job = scenario.session.get(IngestionJobTable, first.ingestion_job_id)
    assert job.derivation_kind == "pdf_extraction" and job.parent_ingestion_job_id is None
    assert old_child.parent_ingestion_job_id == selected_generation.job.id
    assert old_child.status == status
    replay = retry(scenario, "retry-index")
    assert (
        replay.ingestion_job_id == first.ingestion_job_id and replay.outcome == "idempotency_replay"
    )
    assert retry(scenario, "concurrent-key").ingestion_job_id == first.ingestion_job_id


def test_repeated_failed_extractions_have_new_job_fingerprints(scenario):
    jobs = []
    for key in ("retry-1", "retry-2", "retry-3"):
        result = retry(scenario, key)
        job = scenario.session.get(IngestionJobTable, result.ingestion_job_id)
        assert job.status == "queued"
        jobs.append(job)
        job.status = "failed"
    assert len({job.id for job in jobs}) == len({job.content_fingerprint for job in jobs}) == 3


@pytest.mark.parametrize("status", ["queued", "processing", "retry_scheduled", "succeeded"])
def test_viable_child_of_current_desired_generation_reuses_parent(
    scenario, selected_generation, status
):
    child(scenario, selected_generation, status)
    result = retry(scenario, "same-current-chain")
    assert result.outcome == "reused" and result.ingestion_job_id == selected_generation.job.id


def test_old_success_a_does_not_swallow_retry_of_desired_failed_b(scenario, selected_generation):
    child(scenario, selected_generation, "succeeded")
    a = selected_generation.job
    b = IngestionJobTable(**{column.key: getattr(a, column.key) for column in a.__table__.columns})
    b.id = "parent-B"
    b.content_fingerprint = "B"
    scenario.session.add(b)
    scenario.session.add(
        IngestionJobTable(
            id="index-B",
            workspace_id="workspace",
            operation="lexical_index",
            content_fingerprint="index-B",
            derivation_kind="lexical_index",
            parent_ingestion_job_id=b.id,
            lexical_generation_id="generation-B",
            status="failed",
        )
    )
    generation_b = LexicalGenerationTable(
        **{
            column.key: getattr(selected_generation.row, column.key)
            for column in selected_generation.row.__table__.columns
        }
    )
    generation_b.id = "generation-B"
    generation_b.revision = 3
    generation_b.status = "requested"
    scenario.session.add(generation_b)
    selected_generation.head.desired_generation_id = "generation-B"
    selected_generation.head.revision = 3
    result = retry(scenario, "retry-B")
    assert result.outcome == "created" and result.ingestion_job_id not in {a.id, b.id}


def test_stale_reserved_rollback_extraction_is_not_reused(scenario, selected_generation):
    first = retry(scenario, "first")
    job = scenario.session.get(IngestionJobTable, first.ingestion_job_id)
    job.status = "queued"
    job.lexical_head_revision = selected_generation.head.revision - 1
    second = retry(scenario, "fresh")
    assert second.outcome == "created" and second.ingestion_job_id != job.id


def test_matching_reserved_rollback_extraction_is_reused(scenario, selected_generation):
    first = retry(scenario, "first")
    job = scenario.session.get(IngestionJobTable, first.ingestion_job_id)
    job.lexical_head_revision = selected_generation.head.revision
    assert retry(scenario, "fresh").ingestion_job_id == job.id


@pytest.mark.parametrize("field", ["profile_digest", "document_version_id", "workspace_id"])
def test_succeeded_parent_reuse_rejects_generation_provenance(scenario, selected_generation, field):
    child(scenario, selected_generation, "succeeded")
    setattr(selected_generation.row, field, "wrong")
    result = retry(scenario, "different-provenance")
    assert result.outcome == "created" and result.ingestion_job_id != selected_generation.job.id
