"""Offline submission checks; the session double does not model PostgreSQL locks."""

import json
from contextlib import nullcontext
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList, Null

from knora.adapters.postgres.ingestion_jobs.submission import PostgresPdfSubmissionStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentTable,
    DocumentVersionTable,
    IdempotencyRecordTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.answering.stores import RetrievalConfiguration
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import (
    PdfExtractionSubmissionConfiguration,
    PdfSubmissionConfiguration,
    PreparedPdfSubmission,
    PreparedReprocess,
)
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration, LexicalProfile
from knora.providers.embedding import EmbeddingConfiguration


def _evaluate(expression, row):
    if isinstance(expression, BindParameter):
        return expression.value
    if isinstance(expression, Null):
        return None
    if isinstance(expression, BooleanClauseList):
        assert expression.operator in (operators.and_, operators.or_)
        combine = all if expression.operator is operators.and_ else any
        return combine(_evaluate(clause, row) for clause in expression.clauses)
    if isinstance(expression, BinaryExpression):
        left = _evaluate(expression.left, row)
        right = _evaluate(expression.right, row)
        if expression.operator is operators.in_op:
            return left in right
        if expression.operator is operators.json_getitem_op:
            return left[right] if left is not None else None
        if expression.operator is operators.is_:
            return left is right
        if expression.operator is operators.eq:
            return left == right
        raise AssertionError(f"Unsupported predicate: {expression}")
    return getattr(row, expression.name)


class _Session:
    def __init__(self, rows):
        self.rows = list(rows)

    def get(self, model, identity):
        if model is LexicalHeadTable:
            return next(
                (row for row in self.rows if type(row) is model and row.document_id == identity),
                None,
            )
        return next((row for row in self.rows if type(row) is model and row.id == identity), None)

    def scalar(self, statement):
        description = statement.column_descriptions[0]
        rows = [
            row
            for row in self.rows
            if type(row) is description["entity"]
            and all(_evaluate(clause, row) for clause in statement._where_criteria)
        ]
        if not rows:
            return None
        row = rows[0]
        return (
            row
            if description["expr"] is description["entity"]
            else getattr(row, description["name"])
        )

    def add(self, row):
        self.rows.append(row)

    def delete(self, row):
        self.rows.remove(row)

    def flush(self):
        # Model the existing uniqueness boundary without pretending to model concurrency.
        keys = [
            (row.workspace_id, row.operation, row.content_fingerprint)
            for row in self.rows
            if isinstance(row, IngestionJobTable)
        ]
        assert len(keys) == len(set(keys)), "duplicate persisted job fingerprint"


@pytest.fixture
def scenario():
    now = datetime.now(UTC)
    dense = PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    config = PdfExtractionSubmissionConfiguration(
        parser_configuration_id=dense.parser_configuration_id,
        normalizer_configuration_id=dense.normalizer_configuration_id,
        chunking_configuration=dense.chunking_configuration,
        lexical_profile=LexicalProfile("profile", "word", "1", 1.2, 0.75, 4, "statistics"),
    )
    workspace = WorkspaceTable(id="workspace", revision=3, archived=False)
    document = DocumentTable(
        id="document",
        workspace_id="workspace",
        source_key="source",
        revision=4,
        archived=False,
        current_document_version_id="version",
    )
    source = OriginalSourceObjectTable(
        id="object",
        workspace_id="workspace",
        document_version_id="version",
        object_key="retained-key",
        raw_sha256="a" * 64,
        byte_size=123,
        media_type="application/pdf",
    )
    metadata = ObjectMetadata("workspace", "retained-key", "a" * 64, 123, "application/pdf")
    submission = PreparedPdfSubmission(
        workspace_id="workspace",
        source_key="source",
        source_name="source.pdf",
        source_object=metadata,
        content_fingerprint="original-request-fingerprint",
        idempotency_operation="submit_pdf",
        idempotency_key="request-1",
        idempotency_expires_at=now + timedelta(hours=24),
        configuration=config,
    )
    reprocess = PreparedReprocess(
        workspace_id="workspace",
        document_id="document",
        document_version_id="version",
        source_object=metadata,
        request_fingerprint="original-reprocess-fingerprint",
        idempotency_operation="reprocess_document_version",
        idempotency_key="request-1",
        idempotency_expires_at=now + timedelta(hours=24),
        requested_config_mode="same_as_job",
        resolved_config_mode="same_as_job",
        config_source_job_id="old-job",
        prior_job_id="old-job",
        configuration=config,
        actor_key_id="actor",
    )
    session = _Session(
        [
            workspace,
            document,
            source,
            DocumentVersionTable(id="version", document_id="document", raw_sha256="a" * 64),
        ]
    )
    factory = SimpleNamespace(begin=lambda: nullcontext(session))
    store = PostgresPdfSubmissionStore(factory, lambda session: now)
    return SimpleNamespace(
        store=store,
        session=session,
        workspace=workspace,
        document=document,
        submission=submission,
        reprocess=reprocess,
        dense=dense,
    )


def _commit(scenario, operation, prepared=None):
    if operation == "submit":
        return scenario.store.commit_pdf_submission(prepared or scenario.submission)
    return scenario.store.commit_reprocess(prepared or scenario.reprocess)


@pytest.mark.parametrize("operation", ["submit", "reprocess"])
@pytest.mark.parametrize("prior_status", ["queued", "processing", "succeeded", "failed"])
@pytest.mark.parametrize("changed", ["workspace", "document"])
def test_fresh_lexical_request_after_unarchive_creates_new_snapshot(
    scenario,
    operation,
    prior_status,
    changed,
):
    original = _commit(scenario, operation)
    old_job = scenario.session.get(IngestionJobTable, original.ingestion_job_id)
    old_job.status = prior_status
    getattr(scenario, changed).revision += 2
    prepared = getattr(scenario, "submission" if operation == "submit" else "reprocess")

    result = _commit(scenario, operation, replace(prepared, idempotency_key="request-2"))

    assert result.ingestion_job_id != original.ingestion_job_id
    job = scenario.session.get(IngestionJobTable, result.ingestion_job_id)
    assert job.source_revision == scenario.document.revision
    assert job.workspace_revision == scenario.workspace.revision
    assert job.content_fingerprint != old_job.content_fingerprint
    assert job.embedding_configuration_id is None
    assert job.derivation_kind == "pdf_extraction"
    record = next(
        row
        for row in scenario.session.rows
        if isinstance(row, IdempotencyRecordTable) and row.key == "request-2"
    )
    assert record.request_fingerprint == (
        prepared.content_fingerprint if operation == "submit" else prepared.request_fingerprint
    )
    replay = _commit(scenario, operation)
    assert replay.ingestion_job_id == original.ingestion_job_id
    assert (
        replay.submission_outcome if operation == "submit" else replay.outcome
    ) == "idempotency_replay"


@pytest.mark.parametrize("operation", ["submit", "reprocess"])
def test_matching_lexical_snapshot_reuses_the_existing_job(scenario, operation):
    original = _commit(scenario, operation)
    scenario.session.get(IngestionJobTable, original.ingestion_job_id).status = (
        "succeeded" if operation == "submit" else "processing"
    )
    prepared = getattr(scenario, "submission" if operation == "submit" else "reprocess")

    result = _commit(scenario, operation, replace(prepared, idempotency_key="request-2"))

    assert result.ingestion_job_id == original.ingestion_job_id


def test_reprocess_dense_reuse_requires_the_same_embedding_configuration(scenario):
    first = scenario.store.commit_reprocess(
        replace(scenario.reprocess, configuration=scenario.dense)
    )
    scenario.session.get(IngestionJobTable, first.ingestion_job_id).status = "succeeded"
    different = replace(
        scenario.dense,
        embedding_configuration=replace(
            scenario.dense.embedding_configuration, id="other-embedding"
        ),
    )
    second = scenario.store.commit_reprocess(
        replace(
            scenario.reprocess,
            configuration=different,
            idempotency_key="request-2",
            request_fingerprint="different-deployed-configuration",
        )
    )

    assert second.ingestion_job_id != first.ingestion_job_id
    job = scenario.session.get(IngestionJobTable, second.ingestion_job_id)
    assert job.embedding_configuration_id == "other-embedding"
    assert job.content_fingerprint == "different-deployed-configuration"
    assert job.source_revision is None and job.workspace_revision is None


def test_reprocess_lexical_profile_digest_is_part_of_reuse(scenario):
    first = scenario.store.commit_reprocess(scenario.reprocess)
    scenario.session.get(IngestionJobTable, first.ingestion_job_id).status = "succeeded"
    different = replace(
        scenario.reprocess.configuration,
        lexical_profile=replace(scenario.reprocess.configuration.lexical_profile, avg_len=8),
    )
    second = scenario.store.commit_reprocess(
        replace(
            scenario.reprocess,
            configuration=different,
            idempotency_key="request-2",
            request_fingerprint="different-profile-request",
        )
    )

    assert second.ingestion_job_id != first.ingestion_job_id
    job = scenario.session.get(IngestionJobTable, second.ingestion_job_id)
    assert job.lexical_profile == {
        **asdict(different.lexical_profile),
        "digest": different.lexical_profile.digest(),
    }


@pytest.mark.parametrize("operation", ["submit", "reprocess"])
@pytest.mark.parametrize("changed", ["workspace", "document"])
def test_historical_idempotency_replay_survives_archive(scenario, operation, changed):
    original = _commit(scenario, operation)
    getattr(scenario, changed).archived = True
    getattr(scenario, changed).revision += 1

    result = _commit(scenario, operation)

    assert result.ingestion_job_id == original.ingestion_job_id
    assert (
        result.submission_outcome if operation == "submit" else result.outcome
    ) == "idempotency_replay"


def test_submission_snapshot_follows_the_committed_current_version_revision(scenario):
    scenario.document.current_document_version_id = None

    result = scenario.store.commit_pdf_submission(scenario.submission)

    job = scenario.session.get(IngestionJobTable, result.ingestion_job_id)
    assert scenario.document.revision == job.source_revision == 5
    assert job.workspace_revision == 3


@pytest.mark.parametrize("operation", ["submit", "reprocess"])
def test_dense_persisted_fingerprint_and_revision_contract_is_unchanged(scenario, operation):
    prepared = getattr(scenario, "submission" if operation == "submit" else "reprocess")
    prepared = replace(prepared, configuration=scenario.dense)

    result = _commit(scenario, operation, prepared)

    job = scenario.session.get(IngestionJobTable, result.ingestion_job_id)
    assert job.content_fingerprint == (
        prepared.content_fingerprint if operation == "submit" else prepared.request_fingerprint
    )
    assert job.derivation_kind == "dense"
    assert job.embedding_configuration_id == scenario.dense.embedding_configuration.id
    assert job.source_revision is None and job.workspace_revision is None


@pytest.fixture
def selected_generation(scenario):
    result = scenario.store.commit_pdf_submission(scenario.submission)
    job = scenario.session.get(IngestionJobTable, result.ingestion_job_id)
    job.status = "succeeded"
    config = scenario.submission.configuration
    generation = LexicalGeneration(
        "selected-generation",
        "workspace",
        "document",
        "version",
        "chunk-set",
        config.lexical_profile,
        2,
        (LexicalChunk("chunk", 0, "checksum"),),
    )
    row = LexicalGenerationTable(
        id=generation.generation_id,
        workspace_id="workspace",
        document_id="document",
        document_version_id="version",
        chunk_set_id="chunk-set",
        revision=2,
        source_revision=4,
        workspace_revision=3,
        profile_digest=config.lexical_profile.digest(),
        content_digest=generation.content_digest(),
        expected_count=1,
        manifest=json.loads(json.dumps(asdict(generation))),
        status="active",
    )
    head = LexicalHeadTable(
        document_id="document",
        revision=2,
        desired_generation_id=row.id,
        active_generation_id=row.id,
    )
    chunk_set = ChunkSetTable(
        id="chunk-set",
        document_version_id="version",
        status="completed",
        parser_configuration_id=config.parser_configuration_id,
        normalizer_configuration_id=config.normalizer_configuration_id,
        chunking_configuration_id=config.chunking_configuration.id,
    )
    for item in (row, head, chunk_set):
        scenario.session.add(item)
    scenario.store._retrieval_configuration = RetrievalConfiguration.bm25_diagnostic_v1()
    return SimpleNamespace(row=row, head=head, chunk_set=chunk_set, job=job)


def _current_configuration(scenario):
    return scenario.store._current_configuration_for_document(
        session=scenario.session,
        document=scenario.document,
        document_version_id="version",
    )


def test_bm25_current_configuration_uses_the_selected_generation_profile(
    scenario, selected_generation
):
    configuration = _current_configuration(scenario)

    assert configuration == scenario.submission.configuration
    assert isinstance(configuration, PdfExtractionSubmissionConfiguration)


@pytest.mark.parametrize(
    "change",
    [
        "revoked",
        "document_revision",
        "workspace_revision",
        "workspace",
        "document",
        "version",
        "manifest",
        "digest",
        "head_revision",
        "incomplete_chunks",
        "job_profile",
    ],
)
def test_bm25_current_configuration_rejects_invalid_selected_authority(
    scenario,
    selected_generation,
    change,
):
    selected = selected_generation
    if change == "revoked":
        selected.row.status = "revoked"
    elif change == "document_revision":
        scenario.document.revision += 2
    elif change == "workspace_revision":
        scenario.workspace.revision += 2
    elif change in {"workspace", "document", "version"}:
        setattr(
            selected.row, f"{change}_id" if change != "version" else "document_version_id", "other"
        )
    elif change == "manifest":
        selected.row.manifest = {}
    elif change == "digest":
        selected.row.profile_digest = "wrong-profile-digest"
    elif change == "head_revision":
        selected.head.revision += 1
    elif change == "incomplete_chunks":
        selected.chunk_set.status = "processing"
    else:
        selected.job.lexical_profile = {**selected.job.lexical_profile, "digest": "other"}

    with pytest.raises(KnoraError, match="CONFIGURATION_NOT_AVAILABLE"):
        _current_configuration(scenario)


def test_bm25_current_configuration_does_not_fall_back_to_a_dense_job(scenario):
    dense_job = scenario.store.commit_reprocess(
        replace(scenario.reprocess, configuration=scenario.dense)
    )
    scenario.session.get(IngestionJobTable, dense_job.ingestion_job_id).status = "succeeded"
    scenario.store._retrieval_configuration = RetrievalConfiguration.bm25_diagnostic_v1()

    with pytest.raises(KnoraError, match="CONFIGURATION_NOT_AVAILABLE"):
        _current_configuration(scenario)


def test_default_current_configuration_remains_dense(scenario):
    dense_job = scenario.store.commit_reprocess(
        replace(scenario.reprocess, configuration=scenario.dense)
    )
    scenario.session.get(IngestionJobTable, dense_job.ingestion_job_id).status = "succeeded"

    assert _current_configuration(scenario) == scenario.dense


def test_same_as_job_retains_lexical_profile_after_generation_revocation(
    scenario, selected_generation
):
    selected_generation.row.status = "revoked"
    scenario.document.revision += 2

    configuration = scenario.store._configuration_from_job(
        scenario.session, selected_generation.job
    )

    assert configuration == scenario.submission.configuration


def test_same_as_job_rejects_internal_lexical_index_job(scenario, selected_generation):
    selected_generation.job.derivation_kind = "lexical_index"
    selected_generation.job.lexical_profile = None

    with pytest.raises(KnoraError, match="CONFIGURATION_NOT_AVAILABLE"):
        scenario.store._configuration_from_job(scenario.session, selected_generation.job)


@pytest.mark.parametrize("field", ["k1", "b", "avg_len"])
def test_same_as_job_rejects_overflowing_persisted_profile(scenario, selected_generation, field):
    selected_generation.job.lexical_profile = {
        **selected_generation.job.lexical_profile,
        field: 10**1000,
    }
    with pytest.raises(KnoraError, match="CONFIGURATION_NOT_AVAILABLE"):
        scenario.store._configuration_from_job(scenario.session, selected_generation.job)


def test_bm25_current_uses_desired_rebuild_profile_while_old_generation_is_active(
    scenario, selected_generation
):
    selected = selected_generation
    old = replace(scenario.submission.configuration.lexical_profile, avg_len=9)
    active = LexicalGeneration(
        "old-generation",
        "workspace",
        "document",
        "version",
        "chunk-set",
        old,
        1,
        (LexicalChunk("chunk", 0, "checksum"),),
    )
    scenario.session.add(
        LexicalGenerationTable(
            id=active.generation_id,
            workspace_id="workspace",
            document_id="document",
            document_version_id="version",
            chunk_set_id="chunk-set",
            revision=1,
            source_revision=4,
            workspace_revision=3,
            profile_digest=old.digest(),
            content_digest=active.content_digest(),
            expected_count=1,
            manifest=json.loads(json.dumps(asdict(active))),
            status="active",
        )
    )
    selected.head.active_generation_id = active.generation_id
    selected.row.status = "requested"

    assert _current_configuration(scenario) == scenario.submission.configuration


def test_bm25_current_rejects_missing_desired_without_falling_back_to_active(
    scenario, selected_generation
):
    selected_generation.head.desired_generation_id = "missing"
    with pytest.raises(KnoraError, match="CONFIGURATION_NOT_AVAILABLE"):
        _current_configuration(scenario)
