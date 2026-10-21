from dataclasses import replace
from types import SimpleNamespace

import pytest
from backend.test.adapters.postgres.test_s2_submission_fence import (
    scenario as scenario,
)
from backend.test.adapters.postgres.test_s2_submission_fence import (
    selected_generation as selected_generation,
)

from knora.adapters.http.schemas import ReprocessRequest
from knora.adapters.postgres.tables import IngestionJobTable, OriginalSourceObjectTable
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import IngestionJobs, ReprocessDocumentVersionCommand


@pytest.fixture
def rollback(scenario, selected_generation):
    scenario.store._lexical_population = SimpleNamespace(
        profile=scenario.reprocess.configuration.lexical_profile
    )
    source = selected_generation.job
    source.source_object_id = "object"
    selected_generation.row.acknowledged_count = 1
    scenario.session.add(
        IngestionJobTable(
            id="index-A",
            derivation_kind="lexical_index",
            status="succeeded",
            parent_ingestion_job_id=source.id,
            lexical_generation_id=selected_generation.row.id,
        )
    )
    selected_generation.head.revision = 3
    selected_generation.head.desired_generation_id = "B"
    return replace(
        scenario.reprocess,
        config_source_job_id=source.id,
        prior_job_id=source.id,
        expected_lexical_revision=3,
        request_fingerprint="rollback-3",
    )


def test_rollback_enqueues_fresh_extraction_and_fences_desired_b(
    scenario, selected_generation, rollback
):
    result = scenario.store.commit_reprocess(rollback)
    job = scenario.session.get(IngestionJobTable, result.ingestion_job_id)
    assert result.outcome == "created"
    assert job.id != selected_generation.job.id and job.derivation_kind == "pdf_extraction"
    assert job.status == "queued" and job.parent_ingestion_job_id is None
    assert job.reprocess_of_job_id == selected_generation.job.id
    assert job.lexical_head_revision == selected_generation.head.revision == 4
    assert selected_generation.head.desired_generation_id is None
    assert selected_generation.head.active_generation_id == selected_generation.row.id
    assert selected_generation.row.revision == 2
    assert selected_generation.row.status == "active"


def test_stale_rollback_cas_changes_nothing(scenario, selected_generation, rollback):
    with pytest.raises(KnoraError, match="REVISION_CONFLICT"):
        scenario.store.commit_reprocess(replace(rollback, expected_lexical_revision=2))
    assert selected_generation.head.revision == 3
    assert selected_generation.head.desired_generation_id == "B"
    assert len([r for r in scenario.session.rows if isinstance(r, IngestionJobTable)]) == 2


@pytest.mark.parametrize(
    "damage",
    [
        "revoked",
        "ack",
        "profile",
        "document_revision",
        "workspace_revision",
        "source",
        "source_deleted",
        "child",
        "archive",
    ],
)
def test_rollback_requires_current_source_and_verified_prior_generation(
    scenario, selected_generation, rollback, damage
):
    if damage == "revoked":
        selected_generation.row.status = "revoked"
    elif damage == "ack":
        selected_generation.row.acknowledged_count = 0
    elif damage == "profile":
        selected_generation.row.profile_digest = "bad"
    elif damage == "document_revision":
        scenario.document.revision += 2
    elif damage == "workspace_revision":
        scenario.workspace.revision += 2
    elif damage == "source":
        selected_generation.job.source_object_id = "other-source"
    elif damage == "source_deleted":
        scenario.session.get(OriginalSourceObjectTable, "object").deleted_at = object()
    elif damage == "child":
        scenario.session.get(IngestionJobTable, "index-A").status = "failed"
    elif damage == "archive":
        scenario.document.archived = True
    with pytest.raises(KnoraError, match="CONFIGURATION_NOT_AVAILABLE"):
        scenario.store.commit_reprocess(rollback)
    assert selected_generation.head.revision == 3
    assert selected_generation.head.desired_generation_id == "B"


def test_rollback_replay_precedes_current_cas_check(scenario, selected_generation, rollback):
    first = scenario.store.commit_reprocess(rollback)
    selected_generation.head.revision = 6
    replay = scenario.store.commit_reprocess(rollback)
    assert replay.ingestion_job_id == first.ingestion_job_id
    assert replay.outcome == "idempotency_replay"
    assert selected_generation.head.revision == 6


def test_cas_is_part_of_reprocess_identity_without_changing_legacy_identity():
    command = ReprocessDocumentVersionCommand("w", "v", "same_as_job", "A", "key")
    legacy = IngestionJobs._reprocess_fingerprint(command=command)
    assert legacy == "w\nv\nsame_as_job\nA"
    first = replace(command, expected_lexical_revision=3)
    second = replace(first, expected_lexical_revision=4)
    assert IngestionJobs._reprocess_fingerprint(command=first) != legacy
    assert IngestionJobs._reprocess_fingerprint(
        command=first
    ) != IngestionJobs._reprocess_fingerprint(command=second)


@pytest.mark.parametrize("bad", [True, -1, 1.5, "3"])
def test_http_revision_is_a_strict_nonnegative_integer(bad):
    with pytest.raises(ValueError):
        ReprocessRequest(
            config_mode="same_as_job", config_source_job_id="A", expected_lexical_revision=bad
        )


def test_eligible_history_a_is_rederived_even_when_active_pointer_moved(
    scenario, selected_generation, rollback
):
    selected_generation.head.active_generation_id = "D"
    result = scenario.store.commit_reprocess(rollback)
    assert result.outcome == "created" and result.ingestion_job_id != selected_generation.job.id
    assert selected_generation.head.active_generation_id == "D"
    assert selected_generation.row.status == "active"


def test_http_and_service_preserve_the_cas_token(scenario):
    import asyncio
    from unittest.mock import Mock

    from fastapi import Response

    from knora.adapters.http.routes import reprocess_document_version
    from knora.domain.access import WorkspacePrincipal
    from knora.ingestion.jobs import ReprocessContext, ReprocessResult

    principal = WorkspacePrincipal("workspace", "actor")
    result = ReprocessResult("new-extraction", "version", "created", "queued")
    store = Mock()
    store.read_reprocess_replay.return_value = None
    store.read_reprocess_context.return_value = ReprocessContext(
        "workspace",
        "document",
        "version",
        scenario.reprocess.source_object,
        scenario.reprocess.configuration,
        "A",
        "A",
    )
    store.commit_reprocess.return_value = result
    objects = Mock()
    objects.head.return_value = scenario.reprocess.source_object
    service = IngestionJobs(object_store=objects, store=store)
    response = Response()
    observed = asyncio.run(
        reprocess_document_version(
            "workspace",
            "version",
            ReprocessRequest(
                config_mode="same_as_job", config_source_job_id="A", expected_lexical_revision=3
            ),
            response,
            principal,
            service,
            idempotency_key="rollback",
        )
    )
    assert observed.ingestion_job_id == "new-extraction" and response.status_code == 202
    prepared = store.commit_reprocess.call_args.args[0]
    assert prepared.expected_lexical_revision == 3
    assert prepared.requested_config_mode == "same_as_job" and prepared.config_source_job_id == "A"


@pytest.mark.parametrize(
    "mode, revision", [("current", 3), ("deployed", 3), ("same_as_job", True), ("same_as_job", -1)]
)
def test_service_rejects_invalid_cas_before_admission_or_storage(mode, revision):
    from unittest.mock import Mock

    from knora.domain.access import WorkspacePrincipal

    store, objects, admission = Mock(), Mock(), Mock()
    service = IngestionJobs(object_store=objects, store=store, admission_store=admission)
    command = ReprocessDocumentVersionCommand(
        "w", "v", mode, "A" if mode == "same_as_job" else None, "key", revision
    )
    with pytest.raises(KnoraError, match="CONFIG_SOURCE_JOB_INVALID"):
        service.reprocess_document_version(command, WorkspacePrincipal("w", "actor"))
    assert not admission.mock_calls and not store.mock_calls and not objects.mock_calls
