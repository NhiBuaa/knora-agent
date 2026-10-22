from contextlib import nullcontext
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from backend.test.fixtures.issue_18_acceptance import pdf_extraction, pdf_metadata, work_for

from knora.adapters.postgres.ingestion_jobs.coordination import (
    PostgresIngestionJobCoordinationStore,
)
from knora.adapters.postgres.tables import (
    DocumentTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    WorkspaceTable,
)
from knora.ingestion.job_processing import (
    CoordinationInvariantError,
    Fenced,
    FencingToken,
    FinalizationApplied,
    InvalidTransition,
    PdfExtractionSuccess,
    TransitionOperationId,
    WorkSuperseded,
)
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalIndexInput,
    LexicalIndexSuccess,
    LexicalProfile,
    StageReceipt,
    StaleGenerationError,
)


def _scenario(monkeypatch, *, kind="pdf_extraction"):
    now = datetime(2026, 10, 16, tzinfo=UTC)
    work = work_for(pdf_metadata())
    if kind != "dense":
        work = replace(
            work,
            derivation_kind=kind,
            embedding_configuration_id=None,
            lexical_profile_digest="profile",
            source_revision=2,
            workspace_revision=3,
            lexical_generation_id="generation" if kind == "lexical_index" else None,
            ingestion_job_id="job",
        )
    claim = SimpleNamespace(token=FencingToken("job", 1, "worker", 1), work=work)
    job = SimpleNamespace(
        id="job",
        workspace_id=work.workspace_id,
        document_id=work.document_id,
        target_document_version_id=work.document_version_id,
        derivation_kind=kind,
        source_revision=work.source_revision,
        workspace_revision=work.workspace_revision,
        lexical_generation_id=work.lexical_generation_id,
        lexical_head_revision=None,
        status="processing",
        operation="ingest_document",
        worker_id="worker",
        lease_version=1,
        current_attempt_number=1,
        lease_expires_at=now + timedelta(seconds=60),
    )
    attempt = SimpleNamespace(
        ingestion_job_id="job",
        closed_at=None,
        worker_id="worker",
        lease_version=1,
        attempt_number=1,
    )
    document = SimpleNamespace(
        current_document_version_id=work.document_version_id,
        revision=2,
        archived=False,
    )
    workspace = SimpleNamespace(revision=3, archived=False)
    head = SimpleNamespace(desired_generation_id="generation")
    generation = SimpleNamespace(status="requested")
    rows = {
        WorkspaceTable: workspace,
        DocumentTable: document,
        IngestionJobTable: job,
        IngestionJobAttemptTable: attempt,
        LexicalHeadTable: head,
        LexicalGenerationTable: generation,
    }
    session = SimpleNamespace(
        scalar=lambda query: rows[query.column_descriptions[0]["entity"]],
        get=lambda table, key: rows.get(table),
        flush=lambda: None,
        execute=lambda query: None,
    )
    factory = SimpleNamespace(begin=lambda: nullcontext(session))
    store = PostgresIngestionJobCoordinationStore(
        factory,
        lambda session: now,
        None,
        enqueue_terminal_cleanup=lambda **kwargs: None,
    )
    monkeypatch.setattr(store, "_assert_new_transition_operation", lambda **kwargs: None)
    monkeypatch.setattr(store, "_finalize_pdf_job_if_current_and_live", lambda **kwargs: True)
    return store, claim, job, attempt, document, workspace, head, generation


@pytest.mark.parametrize("kind", ["pdf_extraction", "lexical_index"])
@pytest.mark.parametrize(
    "change",
    ["document_revision", "workspace_revision", "document_archive", "workspace_archive", "version"],
)
def test_lexical_supersession_requires_and_records_actual_snapshot_change(
    monkeypatch, kind, change
):
    store, claim, job, attempt, document, workspace, _, _ = _scenario(monkeypatch, kind=kind)
    if change == "document_revision":
        document.revision += 2  # Archive followed by unarchive retains the same version.
    elif change == "workspace_revision":
        workspace.revision += 2
    elif change == "document_archive":
        document.archived = True
    elif change == "workspace_archive":
        workspace.archived = True
    else:
        document.current_document_version_id = "new-version"
    result = store._finalize_superseded_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
    )
    assert isinstance(result, FinalizationApplied)
    assert result.outcome == job.status == attempt.disposition == "superseded"
    assert job.terminal_outcome_code == attempt.closure_cause == "stale_derivation_snapshot"


@pytest.mark.parametrize("kind", ["pdf_extraction", "lexical_index", "dense"])
def test_supersession_cannot_invent_snapshot_change(monkeypatch, kind):
    store, claim, job, attempt, *_ = _scenario(monkeypatch, kind=kind)
    result = store._finalize_superseded_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
    )
    assert isinstance(result, InvalidTransition)
    assert job.status == "processing" and attempt.closed_at is None


def test_superseded_fingerprint_binds_the_reason(monkeypatch):
    store, claim, *_ = _scenario(monkeypatch)
    legacy = store._superseded_fingerprint(claim=claim, outcome=WorkSuperseded())
    snapshot = store._superseded_fingerprint(
        claim=claim,
        outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
    )
    assert legacy == "job\n1\nworker\n1\nsuperseded\nstale_document_version\n\n"
    assert snapshot != legacy


@pytest.mark.parametrize("change", ["desired", "revoked"])
def test_index_supersession_validates_current_generation_head(monkeypatch, change):
    store, claim, job, _, _, _, head, generation = _scenario(monkeypatch, kind="lexical_index")
    if change == "desired":
        head.desired_generation_id = "new-generation"
    else:
        generation.status = "revoked"
    result = store._finalize_superseded_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
    )
    assert isinstance(result, FinalizationApplied)
    assert job.status == "superseded"


@pytest.mark.parametrize("missing", [LexicalHeadTable, LexicalGenerationTable])
def test_missing_index_authority_does_not_prove_snapshot_supersession(monkeypatch, missing):
    store, claim, job, attempt, *_ = _scenario(monkeypatch, kind="lexical_index")
    with store._session_factory.begin() as session:
        original_get = session.get
        session.get = lambda table, key: None if table is missing else original_get(table, key)
    result = store._finalize_superseded_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
    )
    assert isinstance(result, InvalidTransition)
    assert job.status == "processing" and attempt.closed_at is None


def test_dense_cannot_use_lexical_snapshot_reason_even_with_a_new_version(monkeypatch):
    store, claim, job, attempt, document, *_ = _scenario(monkeypatch, kind="dense")
    document.current_document_version_id = "new-version"
    result = store._finalize_superseded_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
    )
    assert isinstance(result, InvalidTransition)
    assert job.status == "processing" and attempt.closed_at is None


def test_snapshot_supersession_keeps_the_final_live_lease_guard(monkeypatch):
    store, claim, _, _, document, *_ = _scenario(monkeypatch)
    document.revision += 2
    monkeypatch.setattr(store, "_finalize_pdf_job_if_current_and_live", lambda **kwargs: False)
    assert isinstance(
        store._finalize_superseded_once(
            operation_id=TransitionOperationId("transition"),
            claim=claim,
            outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
        ),
        Fenced,
    )


@pytest.mark.parametrize("kind", ["pdf_success", "pdf_extraction_success", "lexical_index_success"])
@pytest.mark.parametrize("disposition", ["succeeded", "superseded"])
def test_success_replay_scopes_operation_id_by_kind(kind, disposition):
    foreign = SimpleNamespace(
        transition_request_fingerprint="foreign-fingerprint",
        transition_operation_kind="terminal_failure",
        transition_operation_id="transition",
    )
    attempt = SimpleNamespace(
        transition_request_fingerprint="same-fingerprint",
        transition_operation_kind=kind,
        transition_operation_id="transition",
        disposition=disposition,
        ingestion_job_id="job",
        attempt_number=1,
        replacement_document_version_id=None,
        replacement_ingestion_job_id=None,
    )

    def scalar(query):
        params = query.compile().params
        return next(
            (
                row
                for row in (foreign, attempt)
                if all(
                    getattr(row, key.rsplit("_", 1)[0]) == value for key, value in params.items()
                )
            ),
            None,
        )

    store = object.__new__(PostgresIngestionJobCoordinationStore)
    store._session_factory = lambda: nullcontext(SimpleNamespace(scalar=scalar))
    replay = store._read_finalization_replay(
        operation_id="transition",
        request_fingerprint="same-fingerprint",
        operation_kind=kind,
    )
    assert isinstance(replay, FinalizationApplied) and replay.outcome == disposition


def test_explicit_superseded_replay_retains_its_own_operation_kind():
    attempt = SimpleNamespace(
        transition_request_fingerprint="fingerprint",
        disposition="superseded",
        terminal_outcome_code="stale_derivation_snapshot",
        ingestion_job_id="job",
        attempt_number=1,
        replacement_document_version_id=None,
        replacement_ingestion_job_id=None,
    )

    def scalar(query):
        assert query.compile().params["transition_operation_kind_1"] == "superseded"
        return attempt

    store = object.__new__(PostgresIngestionJobCoordinationStore)
    store._session_factory = lambda: nullcontext(SimpleNamespace(scalar=scalar))
    assert (
        store._read_superseded_replay(
            operation_id="transition", request_fingerprint="fingerprint"
        ).outcome
        == "superseded"
    )


def _extraction_inputs(monkeypatch):
    _, claim, job, *_ = _scenario(monkeypatch)
    extraction = pdf_extraction()
    profile = LexicalProfile("profile", "word", "1.19.2", 1.2, 0.75, 20, "stats")
    claim.work = replace(claim.work, lexical_profile_digest=profile.digest())
    for name in (
        "source_object_id",
        "parser_configuration_id",
        "normalizer_configuration_id",
        "chunking_configuration_id",
    ):
        setattr(job, name, getattr(claim.work, name))
    job.embedding_configuration_id = None
    job.lexical_profile = {**asdict(profile), "digest": profile.digest()}
    source = SimpleNamespace(
        document_version_id=claim.work.document_version_id,
        workspace_id=claim.work.workspace_id,
        object_key=claim.work.source_object_key,
        raw_sha256=claim.work.source_sha256,
        media_type=claim.work.source_media_type,
        byte_size=claim.work.source_byte_size,
    )
    version = SimpleNamespace(
        id=claim.work.document_version_id,
        raw_sha256=source.raw_sha256,
        media_type=source.media_type,
    )
    chunking = SimpleNamespace(
        parser_version=extraction.parser_version,
        chunker_version=extraction.chunking_policy_version,
        tokenizer_name=extraction.tokenizer_name,
        tokenizer_version=extraction.tokenizer_version,
        target_tokens=500,
        overlap_tokens=75,
        max_tokens=650,
    )
    return dict(
        job=job,
        claim=claim,
        success=PdfExtractionSuccess(extraction, profile),
        source_object=source,
        version=version,
        chunking=chunking,
    )


@pytest.mark.parametrize(
    "change",
    [
        "profile",
        "profile_digest",
        "job_revision",
        "job_workspace_revision",
        "kind",
        "claim_kind",
        "source_key",
        "job_id",
        "claim_sha",
        "claim_size",
    ],
)
def test_extraction_validates_durable_profile_and_enqueue_snapshot(monkeypatch, change):
    values = _extraction_inputs(monkeypatch)
    PostgresIngestionJobCoordinationStore._validate_pdf_extraction_inputs(**values)
    job, claim = values["job"], values["claim"]
    if change == "profile":
        job.lexical_profile["avg_len"] += 1
    elif change == "profile_digest":
        job.lexical_profile["digest"] = "forged"
    elif change == "job_revision":
        job.source_revision += 1
    elif change == "job_workspace_revision":
        job.workspace_revision += 1
    elif change == "kind":
        job.derivation_kind = "dense"
    elif change == "claim_kind":
        claim.work = work_for(pdf_metadata())
    elif change == "source_key":
        values["source_object"].object_key = "other-object"
    elif change == "job_id":
        claim.work = replace(claim.work, ingestion_job_id="other-job")
    elif change == "claim_sha":
        claim.work = replace(claim.work, source_sha256="")
    else:
        claim.work = replace(claim.work, source_byte_size=0)
    with pytest.raises(CoordinationInvariantError):
        PostgresIngestionJobCoordinationStore._validate_pdf_extraction_inputs(**values)


@pytest.mark.parametrize("change", ["page", "page_bounds", "chunk_content", "parser"])
def test_extraction_transition_fingerprint_includes_all_provenance(monkeypatch, change):
    values = _extraction_inputs(monkeypatch)
    claim, success = values["claim"], values["success"]
    extraction = success.extraction
    if change == "page":
        extraction = replace(
            extraction, pages=(replace(extraction.pages[0], text="changed"), *extraction.pages[1:])
        )
    elif change == "page_bounds":
        extraction = replace(
            extraction, chunks=(replace(extraction.chunks[0], page_end=7), *extraction.chunks[1:])
        )
    elif change == "chunk_content":
        extraction = replace(
            extraction,
            chunks=(replace(extraction.chunks[0], content="changed"), *extraction.chunks[1:]),
        )
    else:
        extraction = replace(extraction, parser_version="changed")
    fingerprint = PostgresIngestionJobCoordinationStore._pdf_extraction_success_fingerprint
    assert fingerprint(claim=claim, success=success) != fingerprint(
        claim=claim, success=replace(success, extraction=extraction)
    )


def _extraction_transaction(monkeypatch, *, live_at_commit=True):
    store, claim, job, attempt, document, workspace, _, _ = _scenario(monkeypatch)
    values = _extraction_inputs(monkeypatch)
    # Retain the claimed job/attempt while using a valid pinned extraction payload.
    claim.work = values["claim"].work
    job.__dict__.update(values["job"].__dict__)
    job.operation = "submit_pdf"
    document.id = job.document_id
    values["chunking"].id = job.chunking_configuration_id
    rows = {
        WorkspaceTable: workspace,
        DocumentTable: document,
        IngestionJobTable: job,
        IngestionJobAttemptTable: attempt,
    }
    from knora.adapters.postgres.tables import (
        ChunkingConfigurationTable,
        ChunkSetTable,
        ChunkTable,
        DocumentVersionTable,
        OriginalSourceObjectTable,
    )

    rows.update(
        {
            OriginalSourceObjectTable: values["source_object"],
            DocumentVersionTable: values["version"],
            ChunkingConfigurationTable: values["chunking"],
            ChunkSetTable: None,
        }
    )
    added, generations = [], []
    session = SimpleNamespace(
        rows=rows,
        scalar=lambda query: rows.get(query.column_descriptions[0]["entity"]),
        scalars=lambda query: SimpleNamespace(
            all=lambda: [row for row in added if isinstance(row, ChunkTable)]
        ),
        get=lambda table, key: rows.get(table),
        flush=lambda: None,
        execute=lambda query: None,
        add=added.append,
    )
    store._session_factory = SimpleNamespace(begin=lambda: nullcontext(session))
    store._search_index_store = SimpleNamespace(
        request_generation_in_transaction=lambda session, generation, **kwargs: generations.append(
            generation
        ),
    )
    monkeypatch.setattr(
        store, "_finalize_pdf_job_if_current_and_live", lambda **kwargs: live_at_commit
    )
    return store, claim, job, attempt, values["success"], added, generations


def test_extraction_queues_one_index_job_with_same_operation_and_pinned_snapshot(monkeypatch):
    store, claim, job, attempt, success, added, generations = _extraction_transaction(monkeypatch)
    result = store._finalize_pdf_extraction_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        success=success,
    )
    assert isinstance(result, FinalizationApplied)
    children = [row for row in added if isinstance(row, IngestionJobTable)]
    assert len(children) == len(generations) == 1
    child, generation = children[0], generations[0]
    assert child.operation == job.operation == "submit_pdf"
    assert child.derivation_kind == "lexical_index" and child.status == "queued"
    assert child.embedding_configuration_id is child.lexical_profile is None
    assert child.lexical_generation_id == generation.generation_id
    assert child.parent_ingestion_job_id == job.id
    assert (child.source_revision, child.workspace_revision) == (
        job.source_revision,
        job.workspace_revision,
    )
    assert attempt.transition_operation_kind == "pdf_extraction_success"


@pytest.mark.parametrize("field", ["worker_id", "lease_version", "attempt_number"])
def test_extraction_cannot_close_a_different_attempt_owner(monkeypatch, field):
    store, claim, _, attempt, success, added, generations = _extraction_transaction(monkeypatch)
    setattr(attempt, field, "other" if field == "worker_id" else 2)
    result = store._finalize_pdf_extraction_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        success=success,
    )
    assert isinstance(result, InvalidTransition)
    assert not added and not generations and attempt.closed_at is None


def test_extraction_lost_final_lease_guard_returns_fenced(monkeypatch):
    store, claim, _, _, success, _, _ = _extraction_transaction(monkeypatch, live_at_commit=False)
    assert isinstance(
        store._finalize_pdf_extraction_once(
            operation_id=TransitionOperationId("transition"),
            claim=claim,
            success=success,
        ),
        Fenced,
    )


def test_extraction_does_not_supersede_from_a_forged_claim_revision(monkeypatch):
    store, claim, _, attempt, success, added, generations = _extraction_transaction(monkeypatch)
    claim.work = replace(claim.work, source_revision=claim.work.source_revision + 1)
    with pytest.raises(CoordinationInvariantError):
        store._finalize_pdf_extraction_once(
            operation_id=TransitionOperationId("transition"),
            claim=claim,
            success=success,
        )
    assert not added and not generations and attempt.closed_at is None


def test_stale_extraction_enqueues_terminal_source_cleanup(monkeypatch):
    store, claim, _, attempt, success, added, generations = _extraction_transaction(monkeypatch)
    # The pinned job stays unchanged while authoritative workspace lifecycle advances.
    session = store._session_factory.begin().enter_result
    session.rows[WorkspaceTable].revision += 2
    cleanup = []
    store._enqueue_terminal_cleanup = lambda **kwargs: cleanup.append(kwargs)
    result = store._finalize_pdf_extraction_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        success=success,
    )
    assert isinstance(result, FinalizationApplied) and result.outcome == "superseded"
    assert attempt.transition_operation_kind == "pdf_extraction_success"
    assert len(cleanup) == 1 and not added and not generations


def _index_transaction(monkeypatch, *, stale=False, changed_profile=False):
    store, claim, job, attempt, document, workspace, head, row = _scenario(
        monkeypatch, kind="lexical_index"
    )
    claim.work = replace(claim.work, ingestion_job_id=job.id)
    profile = LexicalProfile("profile", "word", "1.19.2", 1.2, 0.75, 20, "stats")
    generation = LexicalGeneration(
        "generation",
        job.workspace_id,
        job.document_id,
        job.target_document_version_id,
        "set",
        profile,
        1,
        (LexicalChunk("chunk", 0, "a" * 64),),
    )
    row.id = generation.generation_id
    row.source_revision = job.source_revision
    row.workspace_revision = job.workspace_revision
    row.document_version_id = job.target_document_version_id
    rows = {
        WorkspaceTable: workspace,
        IngestionJobTable: job,
        IngestionJobAttemptTable: attempt,
        DocumentTable: document,
        LexicalHeadTable: head,
        LexicalGenerationTable: row,
    }
    session = SimpleNamespace(
        scalar=lambda query: rows[query.column_descriptions[0]["entity"]],
        get=lambda table, key: rows.get(table),
        execute=lambda query: None,
    )
    store._session_factory = SimpleNamespace(begin=lambda: nullcontext(session))
    validated, activated = [], []

    def load(active_session, work):
        assert active_session is session and work is claim.work
        validated.append(generation)
        if stale:
            raise StaleGenerationError("snapshot changed")
        expected = (
            replace(generation, lexical_profile=replace(profile, avg_len=21))
            if changed_profile
            else generation
        )
        return LexicalIndexInput(expected, (("chunk", "content"),))

    store._search_index_store = SimpleNamespace(
        load_generation_in_transaction=load,
        activate_ready_in_transaction=lambda active_session, value, receipt: activated.append(
            value
        ),
    )
    monkeypatch.setattr(store, "_finalize_pdf_job_if_current_and_live", lambda **kwargs: True)
    success = LexicalIndexSuccess(
        generation, StageReceipt("generation", 1, generation.content_digest())
    )
    return store, claim, attempt, success, validated, activated


def test_index_revalidates_durable_input_inside_activation_transaction(monkeypatch):
    store, claim, attempt, success, validated, activated = _index_transaction(monkeypatch)
    result = store._finalize_lexical_index_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        success=success,
    )
    assert isinstance(result, FinalizationApplied)
    assert validated == activated == [success.generation]
    assert attempt.transition_operation_kind == "lexical_index_success"


def test_index_does_not_activate_a_changed_persisted_profile(monkeypatch):
    store, claim, attempt, success, _, activated = _index_transaction(
        monkeypatch, changed_profile=True
    )
    with pytest.raises(CoordinationInvariantError):
        store._finalize_lexical_index_once(
            operation_id=TransitionOperationId("transition"),
            claim=claim,
            success=success,
        )
    assert not activated and attempt.closed_at is None


def test_index_snapshot_change_after_receipt_supersedes_without_activation(monkeypatch):
    store, claim, attempt, success, validated, activated = _index_transaction(
        monkeypatch, stale=True
    )
    result = store._finalize_lexical_index_once(
        operation_id=TransitionOperationId("transition"),
        claim=claim,
        success=success,
    )
    assert isinstance(result, FinalizationApplied) and result.outcome == "superseded"
    assert validated == [success.generation] and not activated
    assert attempt.terminal_outcome_code == "stale_derivation_snapshot"
    assert attempt.transition_operation_kind == "lexical_index_success"


def test_index_cannot_supersede_from_a_different_jobs_work(monkeypatch):
    store, claim, attempt, success, validated, activated = _index_transaction(
        monkeypatch, stale=True
    )
    claim.work = replace(claim.work, ingestion_job_id="other-job")
    with pytest.raises(CoordinationInvariantError):
        store._finalize_lexical_index_once(
            operation_id=TransitionOperationId("transition"),
            claim=claim,
            success=success,
        )
    assert not validated and not activated and attempt.closed_at is None


@pytest.mark.parametrize("head_revision", [4, 5, None])
def test_rollback_extraction_never_creates_child_after_reserved_revision_changes(
    monkeypatch, head_revision
):
    store, claim, job, attempt, success, added, generations = _extraction_transaction(monkeypatch)
    job.lexical_head_revision = 4
    session = store._session_factory.begin().enter_result
    session.rows[LexicalHeadTable] = (
        SimpleNamespace(revision=head_revision) if head_revision is not None else None
    )
    result = store._finalize_pdf_extraction_once(
        operation_id=TransitionOperationId("rollback-finalize"), claim=claim, success=success
    )
    assert isinstance(result, FinalizationApplied)
    if head_revision == 4:
        assert len(generations) == 1 and generations[0].revision == 5
        children = [row for row in added if isinstance(row, IngestionJobTable)]
        assert len(children) == 1 and children[0].parent_ingestion_job_id == job.id
    else:
        assert result.outcome == "superseded"
        assert attempt.terminal_outcome_code == "stale_derivation_snapshot"
        assert not added and not generations


@pytest.mark.parametrize("head_revision", [4, 5, None])
def test_rollback_supersession_revalidates_reserved_revision(monkeypatch, head_revision):
    store, claim, job, attempt, document, workspace, head, _ = _scenario(monkeypatch)
    job.lexical_head_revision = 4
    head.revision = head_revision
    result = store._finalize_superseded_once(
        operation_id=TransitionOperationId("rollback-supersede"),
        claim=claim,
        outcome=WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot"),
    )
    if head_revision == 4:
        assert isinstance(result, InvalidTransition)
        assert attempt.closed_at is None
    else:
        assert isinstance(result, FinalizationApplied) and result.outcome == "superseded"
